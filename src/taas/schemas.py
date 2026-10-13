from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


CorridorId = Literal["all", "diting", "minquan", "nanjing", "core"]
FundingPreset = Literal["balanced", "employer_led", "policy_launch"]


class ScenarioRequest(BaseModel):
    corridor: CorridorId = "all"
    addressable_commuters: int = Field(default=5_000, ge=100, le=50_000)
    switch_rate: float = Field(default=0.12, ge=0, le=0.60)
    from_car_share: float = Field(default=0.65, ge=0, le=1)
    from_motorcycle_share: float = Field(default=0.25, ge=0, le=1)
    from_transit_share: float = Field(default=0.10, ge=0, le=1)
    average_car_occupancy: float = Field(default=1.20, ge=1, le=4)
    shuttle_capacity: int = Field(default=43, ge=10, le=60)
    target_load_factor: float = Field(default=0.85, ge=0.40, le=1)
    one_way_minutes: int = Field(default=55, ge=10, le=180)
    turnaround_minutes: int = Field(default=15, ge=0, le=90)
    service_window_minutes: int = Field(default=150, ge=60, le=360)
    priority_time_saving_pct: float = Field(default=0.12, ge=0, le=0.40)
    assumed_daily_cost_per_bus: int = Field(default=12_000, ge=1_000, le=100_000)
    staggered_share: float = Field(default=0.20, ge=0, le=0.80)
    flexible_share: float = Field(default=0.25, ge=0, le=0.80)
    funding_preset: FundingPreset = "balanced"

    @model_validator(mode="after")
    def validate_shares(self) -> "ScenarioRequest":
        source_total = self.from_car_share + self.from_motorcycle_share + self.from_transit_share
        if abs(source_total - 1.0) > 0.001:
            raise ValueError("原運具比例合計必須為 100%")
        if self.staggered_share + self.flexible_share > 1:
            raise ValueError("分批上班與彈性工時參與率合計不可超過 100%")
        return self

