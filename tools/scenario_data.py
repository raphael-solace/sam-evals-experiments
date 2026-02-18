"""Deterministic scenario data for SAP PO experiment tools."""

from __future__ import annotations

import hashlib
from typing import Any

DEFAULT_REFERENCE_QTY = 500

APPROVED_VENDOR_IDS = {
    "SUP-EU-ALPHA",
    "SUP-EU-BETA",
    "SUP-EU-FAST",
    "SUP-P1",
    "SUP-P2",
    "SUP-P3",
    "SUP-P4",
    "SUP-P5",
}

INVENTORY_CASES = {
    "X-2847": {
        "available_stock": 40,
        "lead_time_days": 12,
        "location": "PAR-WH-01",
        "reference_order_qty": 500,
    },
    "X-2847-INSTOCK": {
        "available_stock": 1200,
        "lead_time_days": 1,
        "location": "PAR-WH-01",
        "reference_order_qty": 500,
    },
    "X-2847-PARTIAL": {
        "available_stock": 200,
        "lead_time_days": 3,
        "location": "PAR-WH-02",
        "reference_order_qty": 500,
    },
    "X-2847-ALL-OOS": {
        "available_stock": 0,
        "lead_time_days": 30,
        "location": "PAR-WH-03",
        "reference_order_qty": 500,
    },
    "X-2847-UNAPP": {
        "available_stock": 0,
        "lead_time_days": 20,
        "location": "PAR-WH-03",
        "reference_order_qty": 500,
    },
    "X-2847-TIMEOUT": {
        "available_stock": 0,
        "lead_time_days": 18,
        "location": "PAR-WH-04",
        "reference_order_qty": 500,
    },
    "X-2847-URGENT": {
        "available_stock": 0,
        "lead_time_days": 14,
        "location": "PAR-WH-05",
        "reference_order_qty": 300,
    },
    "X-2847-MULTI": {
        "available_stock": 80,
        "lead_time_days": 10,
        "location": "CENTRAL-EU-HUB",
        "reference_order_qty": 500,
    },
    "X-2847-PERF": {
        "available_stock": 0,
        "lead_time_days": 25,
        "location": "PAR-WH-06",
        "reference_order_qty": 1500,
    },
}

SUPPLIER_SCENARIOS = {
    "default": [
        {
            "supplier_id": "SUP-EU-ALPHA",
            "supplier_name": "Alpha Components GmbH",
            "base_unit_price": 121.0,
            "delivery_days": 12,
            "reliability_score": 0.94,
            "available": True,
            "simulated_delay_seconds": 0.16,
        },
        {
            "supplier_id": "SUP-EU-BETA",
            "supplier_name": "Beta Industrial SAS",
            "base_unit_price": 114.0,
            "delivery_days": 17,
            "reliability_score": 0.9,
            "available": True,
            "simulated_delay_seconds": 0.2,
        },
        {
            "supplier_id": "SUP-EU-FAST",
            "supplier_name": "FastParts BV",
            "base_unit_price": 132.0,
            "delivery_days": 9,
            "reliability_score": 0.88,
            "available": True,
            "simulated_delay_seconds": 0.18,
        },
    ],
    "X-2847-ALL-OOS": [
        {
            "supplier_id": "SUP-EU-ALPHA",
            "supplier_name": "Alpha Components GmbH",
            "base_unit_price": 124.0,
            "delivery_days": 22,
            "reliability_score": 0.93,
            "available": False,
            "simulated_delay_seconds": 0.14,
        },
        {
            "supplier_id": "SUP-EU-BETA",
            "supplier_name": "Beta Industrial SAS",
            "base_unit_price": 118.0,
            "delivery_days": 25,
            "reliability_score": 0.9,
            "available": False,
            "simulated_delay_seconds": 0.16,
        },
        {
            "supplier_id": "SUP-EU-FAST",
            "supplier_name": "FastParts BV",
            "base_unit_price": 136.0,
            "delivery_days": 18,
            "reliability_score": 0.86,
            "available": False,
            "simulated_delay_seconds": 0.15,
        },
    ],
    "X-2847-UNAPP": [
        {
            "supplier_id": "SUP-UNAPPROVED",
            "supplier_name": "Discount Rapid Export Ltd",
            "base_unit_price": 99.0,
            "delivery_days": 11,
            "reliability_score": 0.84,
            "available": True,
            "simulated_delay_seconds": 0.13,
        },
        {
            "supplier_id": "SUP-EU-ALPHA",
            "supplier_name": "Alpha Components GmbH",
            "base_unit_price": 126.0,
            "delivery_days": 13,
            "reliability_score": 0.94,
            "available": True,
            "simulated_delay_seconds": 0.17,
        },
        {
            "supplier_id": "SUP-EU-BETA",
            "supplier_name": "Beta Industrial SAS",
            "base_unit_price": 124.0,
            "delivery_days": 15,
            "reliability_score": 0.91,
            "available": True,
            "simulated_delay_seconds": 0.19,
        },
    ],
    "X-2847-TIMEOUT": [
        {
            "supplier_id": "SUP-EU-ALPHA",
            "supplier_name": "Alpha Components GmbH",
            "base_unit_price": 122.0,
            "delivery_days": 13,
            "reliability_score": 0.94,
            "available": True,
            "simulated_delay_seconds": 0.18,
        },
        {
            "supplier_id": "SUP-EU-BETA",
            "supplier_name": "Beta Industrial SAS",
            "base_unit_price": 116.0,
            "delivery_days": 16,
            "reliability_score": 0.91,
            "available": True,
            "simulated_delay_seconds": 0.2,
        },
        {
            "supplier_id": "SUP-EXT-TIMEOUT",
            "supplier_name": "Timeout Metals AG",
            "base_unit_price": 110.0,
            "delivery_days": 10,
            "reliability_score": 0.87,
            "available": True,
            "simulated_delay_seconds": 1.2,
            "behavior": "timeout",
            "timeout_seconds": 0.5,
        },
    ],
    "X-2847-URGENT": [
        {
            "supplier_id": "SUP-EU-FAST",
            "supplier_name": "FastParts BV",
            "base_unit_price": 149.0,
            "delivery_days": 4,
            "reliability_score": 0.96,
            "available": True,
            "simulated_delay_seconds": 0.15,
        },
        {
            "supplier_id": "SUP-EU-ALPHA",
            "supplier_name": "Alpha Components GmbH",
            "base_unit_price": 125.0,
            "delivery_days": 9,
            "reliability_score": 0.94,
            "available": True,
            "simulated_delay_seconds": 0.17,
        },
        {
            "supplier_id": "SUP-EU-BETA",
            "supplier_name": "Beta Industrial SAS",
            "base_unit_price": 118.0,
            "delivery_days": 14,
            "reliability_score": 0.9,
            "available": True,
            "simulated_delay_seconds": 0.22,
        },
    ],
    "X-2847-PERF": [
        {
            "supplier_id": "SUP-P1",
            "supplier_name": "Perf Supplier 1",
            "base_unit_price": 129.0,
            "delivery_days": 8,
            "reliability_score": 0.9,
            "available": True,
            "simulated_delay_seconds": 0.35,
        },
        {
            "supplier_id": "SUP-P2",
            "supplier_name": "Perf Supplier 2",
            "base_unit_price": 126.0,
            "delivery_days": 11,
            "reliability_score": 0.91,
            "available": True,
            "simulated_delay_seconds": 0.4,
        },
        {
            "supplier_id": "SUP-P3",
            "supplier_name": "Perf Supplier 3",
            "base_unit_price": 122.0,
            "delivery_days": 13,
            "reliability_score": 0.88,
            "available": True,
            "simulated_delay_seconds": 0.45,
        },
        {
            "supplier_id": "SUP-P4",
            "supplier_name": "Perf Supplier 4",
            "base_unit_price": 120.0,
            "delivery_days": 16,
            "reliability_score": 0.85,
            "available": True,
            "simulated_delay_seconds": 0.5,
        },
        {
            "supplier_id": "SUP-P5",
            "supplier_name": "Perf Supplier 5",
            "base_unit_price": 135.0,
            "delivery_days": 6,
            "reliability_score": 0.95,
            "available": True,
            "simulated_delay_seconds": 0.55,
        },
    ],
}

PROJECT_BUDGETS = {
    "PROJ-2026-45": {"remaining_budget": 75000.0, "cost_center": "CC-PAR-4100"},
    "PROJ-2026-OVER": {"remaining_budget": 12000.0, "cost_center": "CC-PAR-4100"},
    "PROJ-2026-UNAPP": {"remaining_budget": 82000.0, "cost_center": "CC-PAR-4200"},
    "PROJ-2026-PARTIAL": {"remaining_budget": 68000.0, "cost_center": "CC-PAR-4300"},
    "PROJ-2026-TIMEOUT": {"remaining_budget": 70000.0, "cost_center": "CC-PAR-4400"},
    "PROJ-2026-URGENT": {"remaining_budget": 55000.0, "cost_center": "CC-PAR-4500"},
    "PROJ-2026-MULTI": {"remaining_budget": 250000.0, "cost_center": "CC-EU-5000"},
    "PROJ-2026-PERF": {"remaining_budget": 120000.0, "cost_center": "CC-PERF-5100"},
}


def normalize_component_id(component_id: str) -> str:
    return (component_id or "").strip().upper()


def stable_hash_int(*parts: Any) -> int:
    payload = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def deterministic_price_jitter(component_id: str, supplier_id: str, quantity: int) -> float:
    # Jitter range: [-3%, +3%], deterministic for reproducibility.
    seed = stable_hash_int(component_id, supplier_id, quantity)
    normalized = (seed % 6001) / 100000.0
    return normalized - 0.03


def get_inventory_case(component_id: str) -> dict[str, Any]:
    normalized = normalize_component_id(component_id)
    return INVENTORY_CASES.get(normalized, INVENTORY_CASES["X-2847"])


def get_supplier_profiles(component_id: str) -> list[dict[str, Any]]:
    normalized = normalize_component_id(component_id)
    profiles = SUPPLIER_SCENARIOS.get(normalized, SUPPLIER_SCENARIOS["default"])
    return [dict(profile) for profile in profiles]


def get_budget_profile(project_code: str) -> dict[str, Any]:
    normalized = (project_code or "").strip().upper()
    return PROJECT_BUDGETS.get(
        normalized,
        {"remaining_budget": 50000.0, "cost_center": "CC-GENERIC-0001"},
    )
