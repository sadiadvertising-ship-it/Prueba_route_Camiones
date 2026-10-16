from datetime import datetime, timedelta, timezone

import pytest

from trips.services import planning

DEPARTURE = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
ORIGIN = {"label": "Origin", "lat": 30.0, "lon": -100.0}
DESTINATION = {"label": "Destination", "lat": 30.0, "lon": -99.0}
# 46 mph on the fast route is Severe for a light load and No Travel above 30,000 lb,
# so the same forecast serves the ranking test and the load test.
WIND = {30.0: 46.0, 31.0: 10.0}


def route(name, lat, miles=100.0, seconds=7200.0):
    lons = [-100.0 + i / 10 for i in range(11)]
    last = len(lons) - 1
    return {
        "name": name,
        "coordinates": [[lon, lat] for lon in lons],
        "distance_miles": miles,
        "duration_seconds": seconds,
        "steps": [
            {"distance_miles": miles, "duration_seconds": seconds, "from": 0, "to": last},
            {"distance_miles": 0.0, "duration_seconds": 0.0, "from": last, "to": last},
        ],
    }


@pytest.fixture
def routes(monkeypatch):
    found = [route("Fast", 30.0), route("Slow", 31.0, miles=120.0, seconds=9000.0)]
    monkeypatch.setattr(planning, "route_options", lambda origin, destination, weight_lb: found)
    return found


@pytest.fixture
def forecast_calls(monkeypatch):
    calls = []

    def hourly_forecast(points, start, end):
        calls.append((points, start, end))
        hours = int((end - start).total_seconds() // 3600) + 1
        return [
            {
                "lat": p["lat"],
                "lon": p["lon"],
                "start": start,
                "wind_mph": [WIND[p["lat"]]] * hours,
                "rain_in": [0.0] * hours,
                "snow_in": [0.0] * hours,
                "temp_f": [60.0] * hours,
                "weather_code": [1] * hours,
            }
            for p in points
        ]

    monkeypatch.setattr(planning.weather, "hourly_forecast", hourly_forecast)
    return calls


def test_weather_is_fetched_once_for_every_checkpoint_over_two_days(routes, forecast_calls):
    trip = planning.plan(ORIGIN, DESTINATION, DEPARTURE, 20000)

    assert trip["interval_miles"] == 10
    assert [len(r["checkpoints"]) for r in trip["routes"]] == [13, 11]
    assert len(forecast_calls) == 1
    points, start, end = forecast_calls[0]
    assert len(points) == 24
    assert (start, end) == (DEPARTURE, DEPARTURE + timedelta(hours=48))


def test_forecast_window_stretches_to_the_arrival_of_a_longer_trip(routes, forecast_calls):
    routes[1]["duration_seconds"] = 60 * 3600.0
    routes[1]["steps"][0]["duration_seconds"] = 60 * 3600.0

    planning.plan(ORIGIN, DESTINATION, DEPARTURE, 20000)

    assert forecast_calls[0][2] == DEPARTURE + timedelta(hours=60)


def test_checkpoints_carry_weather_and_level_and_the_safer_route_wins(routes, forecast_calls):
    trip = planning.plan(ORIGIN, DESTINATION, DEPARTURE, 20000)

    slow, fast = trip["routes"]
    assert (slow["name"], fast["name"]) == ("Slow", "Fast")
    assert trip["recommended"] == "Slow"
    assert slow["recommended"] is True and fast["recommended"] is False
    assert fast["miles"]["Severe"] == 100.0
    assert {p["level"] for p in fast["checkpoints"]} == {"Severe"}
    assert {p["level"] for p in slow["checkpoints"]} == {"Low"}
    first = slow["checkpoints"][0]
    assert first["weather"]["wind_mph"] == 10.0
    assert first["weather"]["time"] == DEPARTURE
    assert slow["checkpoints"][-1]["eta"] == DEPARTURE + timedelta(seconds=9000)
    assert "steps" not in slow and "coordinates" in slow


def test_the_load_is_applied_to_every_checkpoint(routes, forecast_calls):
    trip = planning.plan(ORIGIN, DESTINATION, DEPARTURE, 35000)

    fast = trip["routes"][1]
    assert fast["no_travel"] is True
    assert {p["level"] for p in fast["checkpoints"]} == {"No Travel"}
    assert trip["recommended"] == "Slow"


def test_places_that_snap_to_one_road_point_are_rejected_before_any_forecast(routes, forecast_calls):
    routes[0]["distance_miles"] = 0.0

    with pytest.raises(planning.SamePlace):
        planning.plan(ORIGIN, DESTINATION, DEPARTURE, 20000)
    assert forecast_calls == []


def test_explicit_interval_is_used_for_every_route(routes, forecast_calls):
    trip = planning.plan(ORIGIN, DESTINATION, DEPARTURE, 20000, interval=25)

    assert trip["interval_miles"] == 25
    miles = {r["name"]: [p["mile"] for p in r["checkpoints"]] for r in trip["routes"]}
    assert miles["Fast"] == [0, 25, 50, 75, 100]
    assert miles["Slow"] == [0, 25, 50, 75, 100, 120]
