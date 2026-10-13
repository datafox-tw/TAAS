from pathlib import Path

import pytest

from taas.repository import DashboardRepository


@pytest.fixture(scope="module")
def repository() -> DashboardRepository:
    return DashboardRepository(Path("data/demo"))


def test_demo_data_contract(repository: DashboardRepository) -> None:
    assert len(repository.stations) == 56
    assert len(repository.times) == 150
    assert len(repository.observations) == 8_400
    assert repository.times[0].startswith("2026-10-06")
    assert repository.times[-1].startswith("2026-10-06")


def test_fifteen_minute_aggregation(repository: DashboardRepository) -> None:
    result = repository.traffic_series("all")
    assert result["station_count"] == 56
    assert len(result["series"]) == 10
    assert all(row["volume_total"] >= 0 for row in result["series"])
    assert all(row["completeness_pct"] == 100 for row in result["series"])


def test_snapshot_is_complete(repository: DashboardRepository) -> None:
    result = repository.snapshot(repository.times[60], "all")
    assert result["summary"]["station_count"] == 56
    assert result["summary"]["completeness_pct"] == 100
    assert len(result["stations"]) == 56


def test_corridor_filter(repository: DashboardRepository) -> None:
    all_result = repository.traffic_series("all")
    diting = repository.traffic_series("diting")
    assert 0 < diting["station_count"] < all_result["station_count"]
    assert sum(row["volume_total"] for row in diting["series"]) < sum(
        row["volume_total"] for row in all_result["series"]
    )
