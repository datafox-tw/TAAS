from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo


KEYWORDS = ("內湖", "瑞光", "堤頂", "民權", "成美", "南京東", "舊宗", "港墘")
DESTINATIONS = {"西湖", "港墘"}
MORNING_HOURS = {"07", "08", "09"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@contextmanager
def deterministic_gzip_text(path: Path):
    with path.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                yield text


def build_vd(static_path: Path, history_path: Path, out_dir: Path, date: str) -> dict:
    static = json.loads(static_path.read_text(encoding="utf-8"))
    stations = {
        item["VDID"]: item
        for item in static["VDs"]
        if any(keyword in (item.get("RoadName") or "") for keyword in KEYWORDS)
    }

    station_path = out_dir / "neihu_vd_stations.csv"
    station_fields = [
        "vd_id", "road_name", "lon", "lat", "road_id", "road_class",
        "vd_type", "location_type", "detection_type", "link_ids",
    ]
    with station_path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=station_fields, lineterminator="\n")
        writer.writeheader()
        for vd_id, item in sorted(stations.items()):
            writer.writerow(
                {
                    "vd_id": vd_id,
                    "road_name": item.get("RoadName"),
                    "lon": item.get("PositionLon"),
                    "lat": item.get("PositionLat"),
                    "road_id": item.get("RoadID"),
                    "road_class": item.get("RoadClass"),
                    "vd_type": item.get("VDType"),
                    "location_type": item.get("LocationType"),
                    "detection_type": item.get("DetectionType"),
                    "link_ids": "|".join(str(link.get("LinkID")) for link in item.get("DetectionLinks", [])),
                }
            )

    observation_path = out_dir / f"neihu_vd_{date}_0700-0930.csv.gz"
    observation_fields = [
        "observed_at", "vd_id", "road_name", "lon", "lat", "status",
        "volume_total", "speed_weighted_kph", "occupancy_mean_pct", "link_count", "lane_count",
    ]
    observation_count = 0
    seen_stations: set[str] = set()
    seen_times: set[str] = set()
    with gzip.open(history_path, "rt", encoding="utf-8-sig") as source, deterministic_gzip_text(observation_path) as target:
        writer = csv.DictWriter(target, fieldnames=observation_fields, lineterminator="\n")
        writer.writeheader()
        for line in source:
            row = json.loads(line)
            vd_id = row.get("VDID")
            if vd_id not in stations:
                continue
            local_dt = datetime.fromisoformat(row["DataCollectTime"]).astimezone(ZoneInfo("Asia/Taipei"))
            if local_dt.date().isoformat() != date or not (time(7, 0) <= local_dt.time() < time(9, 30)):
                continue

            total_volume = 0
            speed_numerator = 0.0
            speed_denominator = 0
            occupancies: list[float] = []
            lane_count = 0
            for link in row.get("LinkFlows", []):
                for lane in link.get("Lanes", []):
                    lane_count += 1
                    occupancy = lane.get("Occupancy")
                    if isinstance(occupancy, (int, float)) and occupancy >= 0:
                        occupancies.append(float(occupancy))
                    for vehicle in lane.get("Vehicles", []):
                        volume = vehicle.get("Volume")
                        speed = vehicle.get("Speed")
                        if isinstance(volume, (int, float)) and volume >= 0:
                            total_volume += volume
                            if volume > 0 and isinstance(speed, (int, float)) and speed >= 0:
                                speed_numerator += volume * speed
                                speed_denominator += volume

            item = stations[vd_id]
            writer.writerow(
                {
                    "observed_at": local_dt.isoformat(),
                    "vd_id": vd_id,
                    "road_name": item.get("RoadName"),
                    "lon": item.get("PositionLon"),
                    "lat": item.get("PositionLat"),
                    "status": row.get("Status"),
                    "volume_total": total_volume,
                    "speed_weighted_kph": round(speed_numerator / speed_denominator, 3) if speed_denominator else "",
                    "occupancy_mean_pct": round(sum(occupancies) / len(occupancies), 3) if occupancies else "",
                    "link_count": len(row.get("LinkFlows", [])),
                    "lane_count": lane_count,
                }
            )
            observation_count += 1
            seen_stations.add(vd_id)
            seen_times.add(local_dt.isoformat())

    expected = len(stations) * 150
    if len(stations) != 56 or observation_count != expected or len(seen_stations) != len(stations) or len(seen_times) != 150:
        raise RuntimeError(
            f"VD contract failed: stations={len(stations)}, rows={observation_count}, times={len(seen_times)}"
        )
    return {
        "station_file": station_path.name,
        "station_count": len(stations),
        "observation_file": observation_path.name,
        "observation_count": observation_count,
        "minute_count": len(seen_times),
    }


def build_metro(od_path: Path, calendar_path: Path, out_dir: Path, month: str) -> dict:
    workdays: set[str] = set()
    with calendar_path.open("r", encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            if row["是否放假"] == "0":
                date = row["西元日期"]
                workdays.add(f"{date[:4]}-{date[4:6]}-{date[6:]}")

    compact_month = month.replace("-", "")
    detail_path = out_dir / f"metro_od_to_neihu_weekday_am_{compact_month}.csv.gz"
    summary_path = out_dir / f"metro_od_to_neihu_weekday_am_{compact_month}_origin_summary.csv"
    summary: dict[tuple[str, str], int] = defaultdict(int)
    row_count = 0
    month_workdays: set[str] = set()
    with od_path.open("r", encoding="utf-8-sig", newline="") as source, deterministic_gzip_text(detail_path) as target:
        reader = csv.DictReader(source)
        if reader.fieldnames is None:
            raise RuntimeError("Metro OD has no header")
        writer = csv.DictWriter(target, fieldnames=reader.fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in reader:
            if not row["日期"].startswith(month) or row["日期"] not in workdays:
                continue
            if row["時段"] not in MORNING_HOURS or row["出站"] not in DESTINATIONS:
                continue
            writer.writerow(row)
            summary[(row["進站"], row["出站"])] += int(row["人次"])
            month_workdays.add(row["日期"])
            row_count += 1

    day_count = len(month_workdays)
    fields = ["origin_station", "destination_station", "riders_month_total", "workday_count", "average_per_workday"]
    with summary_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for (origin, destination), riders in sorted(summary.items(), key=lambda item: (-item[1], item[0])):
            writer.writerow(
                {
                    "origin_station": origin,
                    "destination_station": destination,
                    "riders_month_total": riders,
                    "workday_count": day_count,
                    "average_per_workday": round(riders / day_count, 3),
                }
            )
    if row_count == 0 or day_count == 0:
        raise RuntimeError("Metro contract failed: no rows or workdays")
    return {
        "detail_file": detail_path.name,
        "detail_rows": row_count,
        "summary_file": summary_path.name,
        "origin_destination_pairs": len(summary),
        "workday_count": day_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deterministic, commit-friendly TAAS demo data")
    parser.add_argument("--static", type=Path, default=Path("data/raw/tdx/taipei_vd_static_2026-10-13T02-33-29-08-00.json"))
    parser.add_argument("--history", type=Path, default=Path("data/raw/tdx/history/taipei_vd_live_2026-10-06.jsonl.gz"))
    parser.add_argument("--date", default="2026-10-06")
    parser.add_argument("--metro-od", type=Path, default=Path("data/raw/metro/trtc_od_202608.csv"))
    parser.add_argument("--calendar", type=Path, default=Path("data/raw/calendar/taiwan_work_calendar_2026.csv"))
    parser.add_argument("--month", default="2026-08")
    parser.add_argument("--out-dir", type=Path, default=Path("data/demo"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for path in (args.static, args.history, args.metro_od, args.calendar):
        if not path.is_file():
            raise FileNotFoundError(path)

    vd = build_vd(args.static, args.history, args.out_dir, args.date)
    metro = build_metro(args.metro_od, args.calendar, args.out_dir, args.month)
    sources = {
        str(path): {"sha256": sha256(path), "bytes": path.stat().st_size}
        for path in (args.static, args.history, args.metro_od, args.calendar)
    }
    manifest = {
        "schema_version": 1,
        "timezone": "Asia/Taipei",
        "vd": vd,
        "metro": metro,
        "sources": sources,
        "notes": [
            "Generated files are deterministic; gzip mtime is fixed to zero.",
            "Observed, derived and assumed values must remain separately labelled in the UI.",
        ],
    }
    (args.out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
