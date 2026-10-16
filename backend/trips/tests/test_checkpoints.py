from datetime import datetime, timedelta, timezone

import pytest

from trips.services.checkpoints import along, haversine, spacing

DEPARTURE = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)


def route(miles=100.0, seconds=7200.0, steps=None, lons=None):
    lons = lons or [-100.0 + i / 10 for i in range(11)]
    last = len(lons) - 1
    # ORS closes every segment with a zero-length "arrive" step.
    steps = (steps or [(miles, seconds, 0, last)]) + [(0.0, 0.0, last, last)]
    return {
        "coordinates": [[lon, 30.0] for lon in lons],
        "distance_miles": miles,
        "duration_seconds": seconds,
        "steps": [{"distance_miles": d, "duration_seconds": s, "from": a, "to": b} for d, s, a, b in steps],
    }


def hours(h):
    return DEPARTURE + timedelta(hours=h)


def test_markers_every_interval_end_at_the_destination():
    points = along(route(), 25, DEPARTURE)

    assert [p["mile"] for p in points] == [0, 25, 50, 75, 100]
    assert [p["lon"] for p in points] == [-100.0, -99.75, -99.5, -99.25, -99.0]
    assert [p["eta"] for p in points] == [hours(0), hours(0.5), hours(1), hours(1.5), hours(2)]


def test_destination_is_added_after_the_last_full_interval():
    points = along(route(miles=108.0, seconds=7776.0), 25, DEPARTURE)

    assert [p["mile"] for p in points] == [0, 25, 50, 75, 100, 108]
    assert points[4]["lon"] == -99.07407
    assert points[4]["eta"] == hours(2)
    assert points[5]["lon"] == -99.0
    assert points[5]["eta"] == DEPARTURE + timedelta(seconds=7776)


def test_marker_within_a_mile_of_the_destination_is_merged_into_it():
    assert [p["mile"] for p in along(route(miles=100.5), 50, DEPARTURE)] == [0, 50, 100.5]
    assert [p["mile"] for p in along(route(miles=100.0), 50, DEPARTURE)] == [0, 50, 100]
    assert [p["mile"] for p in along(route(miles=101.5), 50, DEPARTURE)] == [0, 50, 100, 101.5]


def test_eta_follows_the_speed_of_each_step():
    # 20 slow miles through town in an hour, then 80 highway miles in the next.
    points = along(route(steps=[(20.0, 3600.0, 0, 2), (80.0, 3600.0, 2, 10)]), 10, DEPARTURE)

    assert [p["lon"] for p in points[:3]] == [-100.0, -99.9, -99.8]
    assert points[1]["eta"] == hours(0.5)
    assert points[2]["eta"] == hours(1)
    assert points[6]["mile"] == 60
    assert points[6]["lon"] == -99.4
    assert points[6]["eta"] == hours(1.5)
    assert points[-1]["eta"] == hours(2)


def test_detour_arrives_at_its_via_point_halfway():
    steps = [(50.0, 3600.0, 0, 5), (0.0, 0.0, 5, 5), (50.0, 3600.0, 5, 10)]
    points = along(route(steps=steps), 25, DEPARTURE)

    assert [p["mile"] for p in points] == [0, 25, 50, 75, 100]
    assert [p["lon"] for p in points] == [-100.0, -99.75, -99.5, -99.25, -99.0]
    assert [p["eta"] for p in points] == [hours(0), hours(0.5), hours(1), hours(1.5), hours(2)]


def test_markers_are_placed_by_distance_not_by_vertex_count():
    points = along(route(lons=[-100.0, -99.9, -99.5, -99.0]), 25, DEPARTURE)

    assert [p["lon"] for p in points] == [-100.0, -99.75, -99.5, -99.25, -99.0]
    assert [p["eta"] for p in points] == [hours(0), hours(0.5), hours(1), hours(1.5), hours(2)]


def test_short_trip_keeps_origin_and_destination():
    points = along(route(miles=0.5, seconds=60.0, lons=[-100.0, -99.99]), 10, DEPARTURE)

    assert [(p["mile"], p["lon"]) for p in points] == [(0, -100.0), (0.5, -99.99)]
    assert points[1]["eta"] == DEPARTURE + timedelta(minutes=1)


def test_spacing_grows_with_the_trip():
    assert [spacing(d) for d in (30, 200, 201, 600, 601, 1500)] == [10, 10, 25, 25, 50, 50]


def test_haversine_dallas_to_chicago():
    assert haversine([-96.797, 32.7767], [-87.6298, 41.8781]) == pytest.approx(803, abs=3)
