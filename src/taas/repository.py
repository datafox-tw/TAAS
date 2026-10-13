from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb


CORRIDORS: dict[str, dict[str, Any]] = {
    "all": {"label": "內科觀測範圍", "keywords": []},
    "diting": {"label": "堤頂大道", "keywords": ["堤頂"]},
    "minquan": {"label": "民權走廊", "keywords": ["民權"]},
    "nanjing": {"label": "南京走廊", "keywords": ["南京"]},
    "core": {"label": "園區核心", "keywords": ["瑞光", "港墘", "舊宗", "內湖"]},
}


class DataContractError(RuntimeError):
    """Raised when a checked-in demo file does not satisfy its contract."""


class DashboardRepository:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir.resolve()
        self.station_path = self.data_dir / "neihu_vd_stations.csv"
        self.observation_path = self.data_dir / "neihu_vd_2026-10-06_0700-0930.csv.gz"
        self.origin_path = self.data_dir / "metro_od_to_neihu_weekday_am_202608_origin_summary.csv"
        self._assert_files()
        self._load()

    def _assert_files(self) -> None:
        missing = [str(path) for path in (self.station_path, self.observation_path, self.origin_path) if not path.is_file()]
        if missing:
            raise DataContractError(f"缺少 demo 資料：{', '.join(missing)}")

    def _load(self) -> None:
        connection = duckdb.connect(":memory:")
        try:
            connection.execute(
                "CREATE TABLE stations AS SELECT * FROM read_csv_auto(?, header=true)",
                [str(self.station_path)],
            )
            connection.execute(
                "CREATE TABLE observations AS SELECT * FROM read_csv_auto(?, header=true)",
                [str(self.observation_path)],
            )
            connection.execute(
                "CREATE TABLE origins AS SELECT * FROM read_csv_auto(?, header=true)",
                [str(self.origin_path)],
            )

            station_rows = connection.execute(
                """
                SELECT vd_id, road_name, CAST(lon AS DOUBLE), CAST(lat AS DOUBLE),
                       road_id, CAST(road_class AS INTEGER), link_ids
                FROM stations ORDER BY vd_id
                """
            ).fetchall()
            self.stations = [
                {
                    "vd_id": row[0],
                    "road_name": row[1],
                    "lon": row[2],
                    "lat": row[3],
                    "road_id": row[4],
                    "road_class": row[5],
                    "link_ids": row[6],
                }
                for row in station_rows
            ]
            self.station_by_id = {row["vd_id"]: row for row in self.stations}

            observation_rows = connection.execute(
                """
                SELECT CAST(observed_at AS VARCHAR), vd_id, road_name,
                       CAST(lon AS DOUBLE), CAST(lat AS DOUBLE), CAST(status AS INTEGER),
                       CAST(volume_total AS DOUBLE), CAST(speed_weighted_kph AS DOUBLE),
                       CAST(occupancy_mean_pct AS DOUBLE)
                FROM observations
                ORDER BY observed_at, vd_id
                """
            ).fetchall()
            self.observations = [
                {
                    "observed_at": row[0],
                    "vd_id": row[1],
                    "road_name": row[2],
                    "lon": row[3],
                    "lat": row[4],
                    "status": row[5],
                    "volume_total": row[6] or 0.0,
                    "speed_weighted_kph": row[7],
                    "occupancy_mean_pct": row[8],
                }
                for row in observation_rows
            ]

            origin_rows = connection.execute(
                """
                SELECT origin_station, destination_station,
                       CAST(riders_month_total AS BIGINT),
                       CAST(workday_count AS INTEGER),
                       CAST(average_per_workday AS DOUBLE)
                FROM origins
                """
            ).fetchall()
        finally:
            connection.close()

        self._observations_by_time: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self.observations:
            self._observations_by_time[row["observed_at"]].append(row)
        self.times = sorted(self._observations_by_time)

        origin_totals: dict[str, dict[str, Any]] = {}
        for origin, destination, monthly, workdays, average in origin_rows:
            item = origin_totals.setdefault(
                origin,
                {"origin_station": origin, "monthly_total": 0, "average_per_workday": 0.0, "destinations": {}},
            )
            item["monthly_total"] += int(monthly)
            item["average_per_workday"] += float(average)
            item["destinations"][destination] = round(float(average), 1)
            item["workday_count"] = int(workdays)
        self.origins = sorted(origin_totals.values(), key=lambda row: row["average_per_workday"], reverse=True)

        self._station_ids = {
            corridor_id: {
                station["vd_id"]
                for station in self.stations
                if not definition["keywords"]
                or any(keyword in station["road_name"] for keyword in definition["keywords"])
            }
            for corridor_id, definition in CORRIDORS.items()
        }
        self._validate_contract()

    def _validate_contract(self) -> None:
        unique_keys = {(row["observed_at"], row["vd_id"]) for row in self.observations}
        if len(self.stations) != 56:
            raise DataContractError(f"預期 56 個 VD，實際 {len(self.stations)}")
        if len(self.times) != 150:
            raise DataContractError(f"預期 150 個分鐘，實際 {len(self.times)}")
        if len(self.observations) != 8_400 or len(unique_keys) != 8_400:
            raise DataContractError("VD demo 必須包含 8,400 個唯一的 minute × VD 觀測")
        if not self.times[0].startswith("2026-10-06 07:00") or not self.times[-1].startswith("2026-10-06 09:29"):
            raise DataContractError(f"非預期時間範圍：{self.times[0]} — {self.times[-1]}")

    def _validate_corridor(self, corridor: str) -> set[str]:
        try:
            return self._station_ids[corridor]
        except KeyError as exc:
            raise ValueError(f"未知走廊：{corridor}") from exc

    def metadata(self) -> dict[str, Any]:
        return {
            "dataset": {
                "label": "TDX 臺北市 VD 歷史資料",
                "demo_date": "2026-10-06",
                "window": "07:00–09:30",
                "timezone": "Asia/Taipei",
                "station_count": len(self.stations),
                "minute_count": len(self.times),
                "observation_count": len(self.observations),
                "value_type": "observed",
            },
            "times": self.times,
            "corridors": [
                {
                    "id": corridor_id,
                    "label": definition["label"],
                    "station_count": len(self._station_ids[corridor_id]),
                }
                for corridor_id, definition in CORRIDORS.items()
            ],
            "lineage": [
                {"label": "VD 流量／速度", "type": "observed", "source": "TDX", "date": "2026-10-06"},
                {"label": "15 分鐘聚合", "type": "derived", "source": "TAAS aggregation v0.1", "date": "2026-10-13"},
                {"label": "政策與成本", "type": "assumed", "source": "使用者輸入／情境模型", "date": "demo input"},
            ],
        }

    def snapshot(self, observed_at: str, corridor: str) -> dict[str, Any]:
        station_ids = self._validate_corridor(corridor)
        if observed_at not in self._observations_by_time:
            raise ValueError(f"未知時間：{observed_at}")
        rows = [row for row in self._observations_by_time[observed_at] if row["vd_id"] in station_ids]
        valid_speeds = [row for row in rows if row["speed_weighted_kph"] is not None]
        volume_total = sum(row["volume_total"] for row in rows)
        speed_denominator = sum(row["volume_total"] for row in valid_speeds)
        weighted_speed = (
            sum(row["speed_weighted_kph"] * row["volume_total"] for row in valid_speeds) / speed_denominator
            if speed_denominator
            else None
        )
        expected = len(station_ids)
        return {
            "observed_at": observed_at,
            "corridor": corridor,
            "corridor_label": CORRIDORS[corridor]["label"],
            "summary": {
                "volume_total": round(volume_total),
                "speed_weighted_kph": round(weighted_speed, 1) if weighted_speed is not None else None,
                "normal_stations": sum(1 for row in rows if row["status"] == 0),
                "station_count": len(rows),
                "completeness_pct": round(100 * len(rows) / expected, 1) if expected else 0,
            },
            "stations": rows,
            "value_type": "observed",
        }

    def traffic_series(self, corridor: str) -> dict[str, Any]:
        station_ids = self._validate_corridor(corridor)
        buckets: dict[datetime, dict[str, Any]] = {}
        for row in self.observations:
            if row["vd_id"] not in station_ids:
                continue
            observed_at = row["observed_at"].replace(" ", "T")
            # DuckDB formats whole-hour UTC offsets as +08; Python 3.10 expects +08:00.
            if len(observed_at) >= 3 and observed_at[-3] in ("+", "-") and observed_at[-2:].isdigit():
                observed_at = f"{observed_at}:00"
            dt = datetime.fromisoformat(observed_at)
            bucket = dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)
            item = buckets.setdefault(
                bucket,
                {"volume": 0.0, "speed_numerator": 0.0, "speed_denominator": 0.0, "rows": 0, "abnormal": 0},
            )
            volume = row["volume_total"]
            item["volume"] += volume
            item["rows"] += 1
            item["abnormal"] += int(row["status"] != 0)
            if row["speed_weighted_kph"] is not None and volume > 0:
                item["speed_numerator"] += row["speed_weighted_kph"] * volume
                item["speed_denominator"] += volume

        expected_rows = len(station_ids) * 15
        series = []
        for bucket, item in sorted(buckets.items()):
            speed = item["speed_numerator"] / item["speed_denominator"] if item["speed_denominator"] else None
            series.append(
                {
                    "bucket_at": bucket.isoformat(),
                    "label": bucket.strftime("%H:%M"),
                    "volume_total": round(item["volume"], 1),
                    "speed_weighted_kph": round(speed, 1) if speed is not None and math.isfinite(speed) else None,
                    "completeness_pct": round(100 * item["rows"] / expected_rows, 1) if expected_rows else 0,
                    "abnormal_observations": item["abnormal"],
                }
            )
        return {
            "corridor": corridor,
            "corridor_label": CORRIDORS[corridor]["label"],
            "station_count": len(station_ids),
            "series": series,
            "value_type": "derived",
            "warning": "多個 VD 加總為偵測器車流通過量，並非不重複車輛數。",
        }

    def demand_origins(self, limit: int = 12) -> dict[str, Any]:
        safe_limit = max(1, min(limit, 50))
        return {
            "destinations": ["西湖", "港墘"],
            "period": "2026-08 工作日 07–09 時",
            "origins": self.origins[:safe_limit],
            "value_type": "derived",
            "warning": "僅代表捷運 OD，不能視為全體內科員工居住地。",
        }

