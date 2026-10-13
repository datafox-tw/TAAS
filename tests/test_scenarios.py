from pathlib import Path

import pytest
from pydantic import ValidationError

from taas.repository import DashboardRepository
from taas.scenarios import evaluate_scenarios
from taas.schemas import ScenarioRequest


@pytest.fixture(scope="module")
def baseline() -> list[dict]:
    repository = DashboardRepository(Path("data/demo"))
    return repository.traffic_series("all")["series"]


def test_zero_switch_has_no_bus_service(baseline: list[dict]) -> None:
    result = evaluate_scenarios(baseline, ScenarioRequest(switch_rate=0))
    assert result["shuttle"]["riders"] == 0
    assert result["shuttle"]["bus_departures"] == 0
    assert result["shuttle"]["fleet_required"] == 0
    assert result["shuttle"]["daily_cost"] == 0


def test_more_switching_never_reduces_relief(baseline: list[dict]) -> None:
    low = evaluate_scenarios(baseline, ScenarioRequest(switch_rate=0.05))
    high = evaluate_scenarios(baseline, ScenarioRequest(switch_rate=0.20))
    assert high["shuttle"]["riders"] > low["shuttle"]["riders"]
    assert high["shuttle"]["net_vehicle_trips_removed"] > low["shuttle"]["net_vehicle_trips_removed"]


def test_priority_does_not_require_more_vehicles(baseline: list[dict]) -> None:
    result = evaluate_scenarios(baseline, ScenarioRequest(priority_time_saving_pct=0.20))
    assert result["shuttle"]["priority_fleet_required"] <= result["shuttle"]["fleet_required"]


def test_policy_curves_never_go_negative(baseline: list[dict]) -> None:
    result = evaluate_scenarios(
        baseline,
        ScenarioRequest(addressable_commuters=50_000, switch_rate=0.60, staggered_share=0.50, flexible_share=0.50),
    )
    assert all(value >= 0 for policy in result["policies"] for value in policy["curve"])


def test_funding_sums_to_daily_cost(baseline: list[dict]) -> None:
    result = evaluate_scenarios(baseline, ScenarioRequest(funding_preset="balanced"))
    assert abs(sum(result["shuttle"]["funding"].values()) - result["shuttle"]["daily_cost"]) <= 2


def test_source_shares_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        ScenarioRequest(from_car_share=0.5, from_motorcycle_share=0.2, from_transit_share=0.1)
