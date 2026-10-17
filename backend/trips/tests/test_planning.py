from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core import signing

from trips.services import planning, weather
from trips.tests.openmeteo import answers

DEPARTURE = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
ORIGIN = {"label": "Origin", "lat": 30.0, "lon": -100.0}
DESTINATION = {"label": "Destination", "lat": 30.0, "lon": -99.0}
# 46 mph on the fast route is Severe for a light load and No Travel above 30,000 lb,
# so the same forecast serves the ranking test and the load test. It calms down after
# a day, which the hourly series must show while the ETAs, all within hours, do not.
WIND = {"Fast": 46.0, "Slow": 10.0}
CALM_AFTER = 24


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


def stormy(route, point, hour):
    return {"wind_speed_10m": WIND[route["name"]] if hour < CALM_AFTER else 10.0}


def prepare(weight_lb=20000, departure=DEPARTURE, **options):
    return planning.prepare(ORIGIN, DESTINATION, departure, weight_lb, **options)


def plan(**options):
    trip = prepare(**options)
    return trip, planning.assess(trip["ticket"], answers(trip, stormy))


def window(trip):
    (only,) = trip["forecast_urls"]
    query = {key: values[0] for key, values in parse_qs(urlsplit(only).query).items()}
    return query["start_hour"], query["end_hour"], len(query["latitude"].split(","))


def test_every_checkpoint_of_every_route_goes_into_one_two_day_forecast_request(routes):
    trip = prepare()

    assert trip["interval_miles"] == 10
    assert [(r["id"], r["name"]) for r in trip["routes"]] == [(0, "Fast"), (1, "Slow")]
    assert [len(r["checkpoints"]) for r in trip["routes"]] == [11, 13]
    assert window(trip) == ("2026-10-20T12:00", "2026-10-22T12:00", 24)
    assert (trip["hours"][0], trip["hours"][-1]) == (DEPARTURE, DEPARTURE + timedelta(hours=48))
    assert all("steps" not in r and "coordinates" in r for r in trip["routes"])


def test_the_window_stretches_to_the_arrival_of_a_longer_trip(routes):
    routes[1]["duration_seconds"] = 60 * 3600.0
    routes[1]["steps"][0]["duration_seconds"] = 60 * 3600.0

    trip = prepare()

    assert window(trip)[1] == "2026-10-23T00:00"
    assert len(trip["hours"]) == 49


def test_the_hours_start_at_the_departure_hour_not_at_the_departure_minute(routes):
    trip, result = plan(departure=DEPARTURE + timedelta(minutes=30))

    assert trip["hours"][0] == DEPARTURE
    assert window(trip)[:2] == ("2026-10-20T12:00", "2026-10-22T13:00")
    _, fast = result["routes"]
    assert fast["checkpoints"][0]["hourly"] == ["Severe"] * 24 + ["Low"] * 25


def test_checkpoints_carry_weather_and_level_and_the_safer_route_wins(routes):
    _, result = plan()

    slow, fast = result["routes"]
    assert (slow["name"], slow["id"], fast["name"], fast["id"]) == ("Slow", 1, "Fast", 0)
    assert result["recommended"] == "Slow"
    assert slow["recommended"] is True and fast["recommended"] is False
    assert fast["miles"]["Severe"] == 100.0
    assert {p["level"] for p in fast["checkpoints"]} == {"Severe"}
    assert {p["level"] for p in slow["checkpoints"]} == {"Low"}
    first = slow["checkpoints"][0]
    assert first["weather"]["wind_mph"] == 10.0
    assert first["weather"]["time"] == DEPARTURE
    assert slow["checkpoints"][-1]["eta"] == DEPARTURE + timedelta(seconds=9000)


def test_every_checkpoint_carries_the_risk_of_each_hour_of_the_window(routes):
    _, result = plan()

    slow, fast = result["routes"]
    for cp in fast["checkpoints"]:
        assert cp["hourly"] == ["Severe"] * 24 + ["Low"] * 25
    assert {tuple(cp["hourly"]) for cp in slow["checkpoints"]} == {tuple(["Low"] * 49)}


def test_the_load_signed_into_the_ticket_is_applied_to_every_checkpoint(routes):
    _, result = plan(weight_lb=35000)

    fast = result["routes"][1]
    assert fast["no_travel"] is True
    assert {p["level"] for p in fast["checkpoints"]} == {"No Travel"}
    assert result["recommended"] == "Slow"


def test_places_that_snap_to_one_road_point_are_rejected(routes):
    for found in routes:
        found["distance_miles"] = 0.0

    with pytest.raises(planning.SamePlace):
        prepare()


def test_explicit_interval_is_used_for_every_route(routes):
    trip = prepare(interval=25)

    assert trip["interval_miles"] == 25
    miles = {r["name"]: [p["mile"] for p in r["checkpoints"]] for r in trip["routes"]}
    assert miles["Fast"] == [0, 25, 50, 75, 100]
    assert miles["Slow"] == [0, 25, 50, 75, 100, 120]


def test_a_forged_ticket_is_refused(routes):
    trip = prepare()
    forged = signing.dumps({"weight_lb": 1, "start": DEPARTURE.isoformat(), "hours": 49, "routes": []}, salt="someone else")

    with pytest.raises(planning.Expired):
        planning.assess(forged, answers(trip, stormy))


def test_a_ticket_older_than_an_hour_is_refused(routes, monkeypatch):
    trip = prepare()
    later = signing.time.time() + planning.TICKET_AGE + 1
    monkeypatch.setattr(signing, "time", SimpleNamespace(time=lambda: later))

    with pytest.raises(planning.Expired):
        planning.assess(trip["ticket"], answers(trip, stormy))


def test_forecasts_that_do_not_match_the_checkpoints_are_refused(routes):
    trip = prepare()
    (items,) = answers(trip, stormy)

    with pytest.raises(weather.BadForecast):
        planning.assess(trip["ticket"], [items[:-1]])
