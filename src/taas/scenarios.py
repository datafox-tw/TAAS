from __future__ import annotations

import math
from typing import Any

from .schemas import ScenarioRequest


FUNDING_PRESETS: dict[str, dict[str, float | str]] = {
    "employer_led": {"label": "企業主導", "city": 0.10, "employers": 0.65, "operator": 0.10, "riders": 0.15},
    "balanced": {"label": "均衡共擔", "city": 0.25, "employers": 0.50, "operator": 0.10, "riders": 0.15},
    "policy_launch": {"label": "政策啟動", "city": 0.40, "employers": 0.35, "operator": 0.10, "riders": 0.15},
}


def _normalize(values: list[float]) -> list[float]:
    total = sum(values)
    if total <= 0:
        return [1 / len(values)] * len(values) if values else []
    return [value / total for value in values]


def _redistribute_shifted(curve: list[float], affected_trips: float) -> tuple[list[float], float]:
    if not curve or affected_trips <= 0:
        return curve[:], 0.0
    weights = _normalize(curve)
    removed = [affected_trips * weight for weight in weights]
    result = [max(0.0, value - removed[index]) for index, value in enumerate(curve)]
    outside = 0.0
    for index, amount in enumerate(removed):
        for offset, share in ((-2, 1 / 3), (0, 1 / 3), (2, 1 / 3)):
            destination = index + offset
            if 0 <= destination < len(result):
                result[destination] += amount * share
            else:
                outside += amount * share
    return [max(0.0, value) for value in result], outside


def _redistribute_flexible(curve: list[float], affected_trips: float) -> list[float]:
    if not curve or affected_trips <= 0:
        return curve[:]
    weights = _normalize(curve)
    removed = [affected_trips * weight for weight in weights]
    result = [max(0.0, value - removed[index]) for index, value in enumerate(curve)]
    # Gentle shoulder-weighted distribution across the full demo window.
    spread_weights = _normalize([1.2 if index in (0, 1, len(curve) - 2, len(curve) - 1) else 0.9 for index in range(len(curve))])
    for index, weight in enumerate(spread_weights):
        result[index] += affected_trips * weight
    return [max(0.0, value) for value in result]


def _apply_shuttle(curve: list[float], removed_vehicle_trips: float, bus_departures: int) -> list[float]:
    if not curve:
        return []
    weights = _normalize(curve)
    result = [max(0.0, value - removed_vehicle_trips * weights[index]) for index, value in enumerate(curve)]
    for index in range(len(result)):
        result[index] += bus_departures / len(result)
    return result


def _policy_metrics(name: str, label: str, curve: list[float], baseline_peak: float, note: str) -> dict[str, Any]:
    peak = max(curve) if curve else 0.0
    reduction = max(0.0, baseline_peak - peak)
    return {
        "id": name,
        "label": label,
        "curve": [round(value, 1) for value in curve],
        "peak_vehicle_passages": round(peak, 1),
        "peak_reduction": round(reduction, 1),
        "peak_reduction_pct": round(100 * reduction / baseline_peak, 1) if baseline_peak else 0.0,
        "window_vehicle_passages": round(sum(curve), 1),
        "note": note,
    }


def evaluate_scenarios(baseline_series: list[dict[str, Any]], request: ScenarioRequest) -> dict[str, Any]:
    labels = [row["label"] for row in baseline_series]
    baseline = [float(row["volume_total"]) for row in baseline_series]
    baseline_peak = max(baseline) if baseline else 0.0

    riders = round(request.addressable_commuters * request.switch_rate)
    cars_removed = riders * request.from_car_share / request.average_car_occupancy
    motorcycles_removed = riders * request.from_motorcycle_share
    road_vehicle_trips_removed = cars_removed + motorcycles_removed
    usable_seats = request.shuttle_capacity * request.target_load_factor
    bus_departures = math.ceil(riders / usable_seats) if riders > 0 else 0

    base_cycle = 2 * request.one_way_minutes + request.turnaround_minutes
    priority_one_way = request.one_way_minutes * (1 - request.priority_time_saving_pct)
    priority_cycle = 2 * priority_one_way + request.turnaround_minutes
    fleet_required = math.ceil(bus_departures * base_cycle / request.service_window_minutes) if bus_departures else 0
    priority_fleet_required = math.ceil(bus_departures * priority_cycle / request.service_window_minutes) if bus_departures else 0

    vehicle_trip_factor = request.from_car_share / request.average_car_occupancy + request.from_motorcycle_share
    staggered_affected = request.addressable_commuters * request.staggered_share * vehicle_trip_factor
    flexible_affected = request.addressable_commuters * request.flexible_share * vehicle_trip_factor

    staggered_curve, shifted_outside = _redistribute_shifted(baseline, staggered_affected)
    flexible_curve = _redistribute_flexible(baseline, flexible_affected)
    shuttle_curve = _apply_shuttle(baseline, road_vehicle_trips_removed, bus_departures)
    priority_curve = shuttle_curve[:]
    combined_curve, combined_shifted_outside = _redistribute_shifted(baseline, staggered_affected)
    combined_curve = _redistribute_flexible(combined_curve, flexible_affected)
    combined_curve = _apply_shuttle(combined_curve, road_vehicle_trips_removed, bus_departures)

    policies = [
        _policy_metrics("baseline", "現況基準", baseline, baseline_peak, "TDX 代表日的選定 VD 15 分鐘加總。"),
        _policy_metrics("staggered", "分批上班", staggered_curve, baseline_peak, "固定 cohort 前後錯開 30 分鐘；總旅次不預設消失。"),
        _policy_metrics("flexible", "彈性工時", flexible_curve, baseline_peak, "參與者到班時間分散於 07:00–09:30；不等同遠距工作。"),
        _policy_metrics("shuttle", "公私協力接駁", shuttle_curve, baseline_peak, "扣除轉搭者原汽機車並加入接駁班次。"),
        _policy_metrics("shuttle_priority", "接駁＋優先通行", priority_curve, baseline_peak, "道路曲線同接駁方案；優先通行只影響行程時間與車隊周轉。"),
        _policy_metrics("combined", "組合方案", combined_curve, baseline_peak, "分批、彈性與接駁依序套用，不直接相加百分比。"),
    ]

    preset = FUNDING_PRESETS[request.funding_preset]
    daily_cost = fleet_required * request.assumed_daily_cost_per_bus
    priority_daily_cost = priority_fleet_required * request.assumed_daily_cost_per_bus
    funding = {
        key: round(daily_cost * float(preset[key]))
        for key in ("city", "employers", "operator", "riders")
    }

    sensitivity = []
    for step in range(0, 31, 3):
        rate = step / 100
        step_riders = request.addressable_commuters * rate
        removed = step_riders * vehicle_trip_factor
        departures = math.ceil(step_riders / usable_seats) if step_riders else 0
        sensitivity.append(
            {
                "switch_rate": rate,
                "riders": round(step_riders),
                "net_vehicle_trips_removed": round(max(0.0, removed - departures), 1),
                "bus_departures": departures,
            }
        )

    marginal_rate = 0.05
    marginal_riders = request.addressable_commuters * marginal_rate
    marginal_departures = math.ceil(marginal_riders / usable_seats) if marginal_riders else 0
    marginal_removed = marginal_riders * vehicle_trip_factor - marginal_departures
    best_policy = max(policies[1:], key=lambda policy: policy["peak_reduction_pct"])

    return {
        "labels": labels,
        "policies": policies,
        "shuttle": {
            "riders": riders,
            "cars_removed": round(cars_removed, 1),
            "motorcycles_removed": round(motorcycles_removed, 1),
            "bus_departures": bus_departures,
            "net_vehicle_trips_removed": round(max(0.0, road_vehicle_trips_removed - bus_departures), 1),
            "fleet_required": fleet_required,
            "priority_fleet_required": priority_fleet_required,
            "one_way_minutes": request.one_way_minutes,
            "priority_one_way_minutes": round(priority_one_way, 1),
            "daily_cost": daily_cost,
            "priority_daily_cost": priority_daily_cost,
            "cost_per_rider": round(daily_cost / riders, 1) if riders else None,
            "funding_preset": {"id": request.funding_preset, "label": preset["label"]},
            "funding": funding,
        },
        "schedule": {
            "staggered_vehicle_trips_affected": round(staggered_affected, 1),
            "staggered_shifted_outside_window": round(shifted_outside, 1),
            "flexible_vehicle_trips_affected": round(flexible_affected, 1),
            "combined_shifted_outside_window": round(combined_shifted_outside, 1),
        },
        "sensitivity": sensitivity,
        "decision": {
            "headline": f"每多說服 5 個百分點，約可再減少 {max(0, round(marginal_removed)):,} 個晨峰汽機車旅次。",
            "best_peak_policy": best_policy["label"],
            "best_peak_reduction_pct": best_policy["peak_reduction_pct"],
        },
        "assumptions": request.model_dump(),
        "value_type": "assumed",
        "warnings": [
            "VD 加總是偵測器通過量，情境減量是假設每個受影響旅次通過一個入口偵測器的投影。",
            "成本使用可調的每日每車假設，正式決策前需以業者報價替換。",
            "優先通行未計算其他道路使用者的延誤；此處只呈現接駁周轉可能改善。",
        ],
    }

