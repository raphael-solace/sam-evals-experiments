"""Mock SAP purchase-order tools for multi-agent evaluation."""

from __future__ import annotations

import asyncio
import datetime as dt
import time
from typing import Any, Dict, List, Optional

from google.adk.tools import ToolContext

from .scenario_data import (
    APPROVED_VENDOR_IDS,
    DEFAULT_REFERENCE_QTY,
    deterministic_price_jitter,
    get_budget_profile,
    get_inventory_case,
    get_supplier_profiles,
    normalize_component_id,
    stable_hash_int,
)


def _now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _estimate_delivery_date(days: int) -> str:
    date_val = dt.date.today() + dt.timedelta(days=max(days, 1))
    return date_val.isoformat()


async def check_inventory_sap(
    component_id: str,
    facility_code: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Check inventory in a mocked SAP ERP source.

    Args:
        component_id: Material/component identifier.
        facility_code: Facility/plant code.

    Returns:
        Inventory status payload for downstream sourcing decisions.
    """
    _ = tool_context, tool_config
    normalized_component = normalize_component_id(component_id)
    case = get_inventory_case(normalized_component)

    reference_qty = int(case.get("reference_order_qty", DEFAULT_REFERENCE_QTY))
    available_stock = int(case.get("available_stock", 0))
    shortage_qty = max(reference_qty - available_stock, 0)

    return {
        "component_id": normalized_component,
        "facility_code": (facility_code or "").strip().upper(),
        "available_stock": available_stock,
        "lead_time_days": int(case.get("lead_time_days", 7)),
        "location": case.get("location", "UNKNOWN"),
        "reference_order_quantity": reference_qty,
        "requires_external_sourcing": shortage_qty > 0,
        "shortage_quantity": shortage_qty,
        "checked_at": _now_iso(),
        "error": None,
    }


async def _simulate_single_supplier_query(
    component_id: str,
    quantity: int,
    max_delivery_days: int,
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    delay_seconds = float(profile.get("simulated_delay_seconds", 0.2))
    behavior = profile.get("behavior")
    await asyncio.sleep(delay_seconds)

    if behavior == "timeout":
        await asyncio.sleep(2.0)

    available = bool(profile.get("available", True))
    supplier_id = str(profile.get("supplier_id", "UNKNOWN"))

    if not available:
        return {
            "supplier_id": supplier_id,
            "supplier_name": profile.get("supplier_name", supplier_id),
            "available": False,
            "out_of_stock": True,
            "unit_price": None,
            "total_price": None,
            "delivery_days": int(profile.get("delivery_days", 999)),
            "within_deadline": False,
            "reliability_score": float(profile.get("reliability_score", 0.0)),
            "approved_vendor": supplier_id in APPROVED_VENDOR_IDS,
        }

    base_unit_price = float(profile.get("base_unit_price", 100.0))
    jitter = deterministic_price_jitter(component_id, supplier_id, quantity)
    unit_price = round(base_unit_price * (1.0 + jitter), 2)
    total_price = round(unit_price * quantity, 2)
    delivery_days = int(profile.get("delivery_days", 14))

    return {
        "supplier_id": supplier_id,
        "supplier_name": profile.get("supplier_name", supplier_id),
        "available": True,
        "out_of_stock": False,
        "unit_price": unit_price,
        "total_price": total_price,
        "delivery_days": delivery_days,
        "within_deadline": delivery_days <= max_delivery_days,
        "reliability_score": float(profile.get("reliability_score", 0.0)),
        "approved_vendor": supplier_id in APPROVED_VENDOR_IDS,
    }


def _select_recommended_supplier(
    quotes: List[Dict[str, Any]], max_delivery_days: int
) -> Optional[str]:
    candidates = [q for q in quotes if q.get("available")]
    if not candidates:
        return None

    min_price = min(float(q["total_price"]) for q in candidates)
    max_price = max(float(q["total_price"]) for q in candidates)
    min_delivery = min(int(q["delivery_days"]) for q in candidates)
    max_delivery = max(int(q["delivery_days"]) for q in candidates)

    def normalize(value: float, low: float, high: float) -> float:
        if high <= low:
            return 0.0
        return (value - low) / (high - low)

    urgent = max_delivery_days <= 7
    weight_price = 0.35 if urgent else 0.55
    weight_delivery = 0.5 if urgent else 0.25
    weight_reliability = 0.15 if urgent else 0.2

    scored: List[tuple[float, Dict[str, Any]]] = []
    for quote in candidates:
        price_component = normalize(
            float(quote["total_price"]), float(min_price), float(max_price)
        )
        delivery_component = normalize(
            float(quote["delivery_days"]), float(min_delivery), float(max_delivery)
        )
        reliability_component = 1.0 - float(quote.get("reliability_score", 0.0))

        score = (
            (weight_price * price_component)
            + (weight_delivery * delivery_component)
            + (weight_reliability * reliability_component)
        )
        scored.append((score, quote))

    scored.sort(key=lambda item: item[0])
    return scored[0][1]["supplier_id"]


async def query_supplier_apis(
    component_id: str,
    quantity: int,
    max_delivery_days: int,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Query mocked supplier APIs in parallel and recommend a supplier.

    Args:
        component_id: Material/component identifier.
        quantity: Requested quantity.
        max_delivery_days: Deadline requirement in days.

    Returns:
        Quotes list, timeout list, and recommendation metadata.
    """
    _ = tool_context, tool_config
    normalized_component = normalize_component_id(component_id)
    profiles = get_supplier_profiles(normalized_component)

    started = time.perf_counter()
    timeouts: List[str] = []
    quotes: List[Dict[str, Any]] = []

    tasks = []
    timeout_limits = []
    for profile in profiles:
        timeout_limit = float(profile.get("timeout_seconds", 0.8))
        timeout_limits.append(timeout_limit)
        tasks.append(
            asyncio.wait_for(
                _simulate_single_supplier_query(
                    normalized_component,
                    int(quantity),
                    int(max_delivery_days),
                    profile,
                ),
                timeout=timeout_limit,
            )
        )

    task_results = await asyncio.gather(*tasks, return_exceptions=True)

    for profile, result in zip(profiles, task_results):
        supplier_id = profile.get("supplier_id", "UNKNOWN")
        if isinstance(result, asyncio.TimeoutError):
            timeouts.append(str(supplier_id))
            continue
        if isinstance(result, Exception):
            continue
        quotes.append(result)

    parallel_elapsed_ms = int((time.perf_counter() - started) * 1000)

    sequential_estimate_seconds = 0.0
    for profile, timeout_limit in zip(profiles, timeout_limits):
        delay = float(profile.get("simulated_delay_seconds", 0.2))
        if profile.get("behavior") == "timeout":
            sequential_estimate_seconds += timeout_limit
        else:
            sequential_estimate_seconds += delay

    recommended_supplier_id = _select_recommended_supplier(quotes, int(max_delivery_days))

    return {
        "component_id": normalized_component,
        "quantity": int(quantity),
        "max_delivery_days": int(max_delivery_days),
        "quotes": quotes,
        "timeouts": timeouts,
        "parallel_elapsed_ms": parallel_elapsed_ms,
        "sequential_estimate_ms": int(sequential_estimate_seconds * 1000),
        "recommended_supplier_id": recommended_supplier_id,
        "error": None,
    }


async def validate_compliance_rules(
    supplier_id: str,
    total_cost: float,
    project_code: str,
    budget: float,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Validate procurement compliance rules.

    Args:
        supplier_id: Selected supplier identifier.
        total_cost: Expected total cost.
        project_code: Project code.
        budget: Budget threshold supplied to compliance check.

    Returns:
        Compliance decision with explicit violations.
    """
    _ = tool_context, tool_config
    normalized_supplier = (supplier_id or "").strip().upper()
    normalized_project = (project_code or "").strip().upper()
    total = float(total_cost)
    budget_value = float(budget)

    violations: List[str] = []
    approval_required = False

    if normalized_supplier not in APPROVED_VENDOR_IDS:
        violations.append("Supplier is not in approved vendor list.")

    if total > budget_value:
        violations.append("Total cost exceeds provided budget limit.")
        approval_required = True

    if total >= (budget_value * 0.8):
        approval_required = True

    if normalized_project.startswith("PROJ-2026-GOV"):
        approval_required = True

    approved = len(violations) == 0

    return {
        "supplier_id": normalized_supplier,
        "project_code": normalized_project,
        "approved": approved,
        "violations": violations,
        "approval_required": approval_required,
        "error": None,
    }


async def check_budget_availability(
    project_code: str,
    amount: float,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Check project budget availability.

    Args:
        project_code: Project code.
        amount: Required budget amount.

    Returns:
        Availability result with remaining budget and cost center.
    """
    _ = tool_context, tool_config
    normalized_project = (project_code or "").strip().upper()
    amount_value = float(amount)
    budget_profile = get_budget_profile(normalized_project)

    remaining = float(budget_profile["remaining_budget"])
    available = amount_value <= remaining

    return {
        "project_code": normalized_project,
        "available": available,
        "remaining_budget": remaining,
        "cost_center": budget_profile["cost_center"],
        "error": None,
    }


async def create_purchase_order(
    supplier_id: str,
    component_id: str,
    quantity: int,
    price: float,
    project_code: str,
    tool_context: Optional[ToolContext] = None,
    tool_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a mocked purchase order.

    Args:
        supplier_id: Supplier identifier.
        component_id: Component identifier.
        quantity: Ordered quantity.
        price: Unit price.
        project_code: Project code.

    Returns:
        Generated PO metadata.
    """
    _ = tool_context, tool_config
    normalized_supplier = (supplier_id or "").strip().upper()
    normalized_component = normalize_component_id(component_id)
    normalized_project = (project_code or "").strip().upper()

    lead_days = 7
    if normalized_supplier == "SUP-EU-FAST":
        lead_days = 4
    elif normalized_supplier in {"SUP-EU-BETA", "SUP-P4"}:
        lead_days = 15
    elif normalized_supplier == "INTERNAL_TRANSFER":
        lead_days = 2

    hash_token = stable_hash_int(
        normalized_supplier,
        normalized_component,
        int(quantity),
        round(float(price), 2),
        normalized_project,
    )
    po_number = f"PO-{hash_token % 100000000:08d}"

    status = "created"
    if normalized_supplier == "INTERNAL_TRANSFER":
        status = "internal_transfer_created"
    elif normalized_supplier == "SUP-UNAPPROVED":
        status = "pending_manual_approval"

    return {
        "po_number": po_number,
        "status": status,
        "estimated_delivery": _estimate_delivery_date(lead_days),
        "supplier_id": normalized_supplier,
        "component_id": normalized_component,
        "quantity": int(quantity),
        "unit_price": round(float(price), 2),
        "total_cost": round(float(price) * int(quantity), 2),
        "project_code": normalized_project,
        "created_at": _now_iso(),
        "error": None,
    }
