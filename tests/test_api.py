from pathlib import Path

import pytest

from taas.main import demand_origins, health, meta, scenarios_evaluate, traffic_series, traffic_snapshot
from taas.repository import DashboardRepository
from taas.schemas import ScenarioRequest


@pytest.fixture(scope="module")
def repository() -> DashboardRepository:
    return DashboardRepository(Path("data/demo"))


def test_api_contracts(repository: DashboardRepository) -> None:
    health_payload = health(repository)
    assert health_payload["status"] == "ok"

    meta_payload = meta(repository)
    assert len(meta_payload["times"]) == 150

    snapshot = traffic_snapshot(at=None, corridor="all", repo=repository)
    assert len(snapshot["stations"]) == 56

    series = traffic_series(corridor="all", repo=repository)
    assert len(series["series"]) == 10

    origins = demand_origins(limit=8, repo=repository)
    assert len(origins["origins"]) == 8

    scenario = scenarios_evaluate(ScenarioRequest(), repository)
    assert len(scenario["policies"]) == 6
    assert scenario["value_type"] == "assumed"


def test_repository_rejects_bad_corridor(repository: DashboardRepository) -> None:
    with pytest.raises(ValueError):
        repository.traffic_series("unknown")
