from datetime import timedelta

import pytest
from django.utils import timezone

from trips import serializers, views
from trips.services import ors, planning, weather

URL = "/api/trips/plan/"
PLACES = {
    "Dallas": {"label": "Dallas, TX, USA", "lat": 32.78, "lon": -96.8},
    "Chicago": {"label": "Chicago, IL, USA", "lat": 41.88, "lon": -87.63},
}


def geocode(text):
    try:
        return PLACES[text]
    except KeyError:
        raise ors.PlaceNotFound(f"Could not find a place called {text!r}")


@pytest.fixture
def planned(monkeypatch):
    monkeypatch.setattr(serializers, "geocode", geocode)
    calls = []

    def plan(**trip):
        calls.append(trip)
        return {"recommended": "Fastest", "routes": []}

    monkeypatch.setattr(views.planning, "plan", plan)
    return calls


def at(delta):
    return timezone.now() + delta


def soon():
    return at(timedelta(hours=2))


def body(**changes):
    trip = {"origin": "Dallas", "destination": "Chicago", "departure": soon().isoformat(), "weight_lb": 35000}
    trip.update(changes)
    return trip


def post(client, trip):
    return client.post(URL, trip, content_type="application/json")


def test_plan_passes_the_resolved_trip_to_the_planner(client, planned):
    when = soon()
    response = post(client, body(departure=when.isoformat(), interval=25))

    assert response.status_code == 200
    assert response.json() == {"recommended": "Fastest", "routes": []}
    assert planned == [
        {
            "origin": PLACES["Dallas"],
            "destination": PLACES["Chicago"],
            "departure": when,
            "weight_lb": 35000,
            "interval": 25,
        }
    ]


def test_interval_may_be_left_out_or_null(client, planned):
    assert post(client, body()).status_code == 200
    assert post(client, body(interval=None)).status_code == 200
    assert "interval" not in planned[0]
    assert planned[1]["interval"] is None


def test_missing_fields_are_reported_one_by_one(client, planned):
    response = post(client, {})

    assert response.status_code == 400
    assert set(response.json()) == {"origin", "destination", "departure", "weight_lb"}
    assert planned == []


@pytest.mark.parametrize("weight", [0, -5, "heavy", 350.5])
def test_weight_must_be_a_positive_whole_number(client, planned, weight):
    response = post(client, body(weight_lb=weight))

    assert response.status_code == 400
    assert list(response.json()) == ["weight_lb"]


def test_interval_must_be_one_of_the_sampling_steps(client, planned):
    response = post(client, body(interval=30))

    assert response.status_code == 400
    assert list(response.json()) == ["interval"]


@pytest.mark.parametrize("delta, message", [(timedelta(hours=-2), "past"), (timedelta(days=7, minutes=1), "7 days")])
def test_departure_must_fall_inside_the_forecast_window(client, planned, delta, message):
    response = post(client, body(departure=at(delta).isoformat()))

    assert response.status_code == 400
    assert message in response.json()["departure"][0]


def test_departure_earlier_in_the_current_hour_is_accepted(client, planned):
    hour = timezone.now().replace(minute=0, second=0, microsecond=0)

    assert post(client, body(departure=hour.isoformat())).status_code == 200


def test_departure_without_a_timezone_is_read_as_utc(client, planned):
    when = soon().replace(microsecond=0)
    post(client, body(departure=when.strftime("%Y-%m-%dT%H:%M:%S")))

    assert planned[0]["departure"] == when


def test_unknown_place_is_reported_on_its_field(client, planned):
    response = post(client, body(destination="Nowhere"))

    assert response.status_code == 400
    assert response.json() == {"destination": ["Could not find a place called 'Nowhere'"]}


def test_same_origin_and_destination_is_rejected(client, planned, monkeypatch):
    def plan(**trip):
        raise planning.SamePlace("Origin and destination are the same place.")

    monkeypatch.setattr(views.planning, "plan", plan)
    response = post(client, body())

    assert response.status_code == 400
    assert response.json() == {"destination": ["Origin and destination are the same place."]}


@pytest.mark.parametrize(
    "error",
    [ors.ORSError("OpenRouteService error 503: busy"), weather.WeatherError("Open-Meteo is unreachable")],
)
def test_upstream_failures_come_back_as_a_bad_gateway(client, planned, monkeypatch, error):
    def plan(**trip):
        raise error

    monkeypatch.setattr(views.planning, "plan", plan)
    response = post(client, body())

    assert response.status_code == 502
    assert response.json() == {"detail": str(error)}


def test_geocoder_outage_is_a_bad_gateway_too(client, planned, monkeypatch):
    def geocode(text):
        raise ors.ORSError("OpenRouteService error 403: Daily quota reached")

    monkeypatch.setattr(serializers, "geocode", geocode)
    response = post(client, body())

    assert response.status_code == 502
    assert "quota" in response.json()["detail"]


def test_the_whole_plan_renders_as_json(client, monkeypatch):
    monkeypatch.setattr(serializers, "geocode", geocode)
    route = {
        "name": "Fastest",
        "coordinates": [[-96.8, 32.78], [-96.6, 32.78], [-96.4, 32.78]],
        "distance_miles": 20.0,
        "duration_seconds": 1200.0,
        "steps": [
            {"distance_miles": 20.0, "duration_seconds": 1200.0, "from": 0, "to": 2},
            {"distance_miles": 0.0, "duration_seconds": 0.0, "from": 2, "to": 2},
        ],
    }
    monkeypatch.setattr(planning, "route_options", lambda origin, destination, weight_lb: [route])

    def hourly_forecast(points, start, end):
        hours = int((end - start).total_seconds() // 3600) + 1

        # The middle checkpoint has no forecast at all; the others sit at 40 mph, High on
        # the table, which the 45,000 lb load lifts to Severe.
        def reading(p, value):
            return [None if p["mile"] == 10 else value] * hours

        return [
            {
                "lat": p["lat"],
                "lon": p["lon"],
                "start": start,
                "wind_mph": reading(p, 40.0),
                "rain_in": reading(p, 0.0),
                "snow_in": reading(p, 0.0),
                "temp_f": reading(p, 61.2),
                "weather_code": reading(p, 1),
            }
            for p in points
        ]

    monkeypatch.setattr(planning.weather, "hourly_forecast", hourly_forecast)
    when = soon().replace(minute=0, second=0, microsecond=0)
    response = post(client, body(departure=when.isoformat(), weight_lb=45000))

    assert response.status_code == 200
    trip = response.json()
    assert trip["departure"] == when.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert trip["hours"][0] == trip["departure"] and len(trip["hours"]) == 49
    assert (trip["origin"], trip["destination"], trip["weight_lb"], trip["interval_miles"]) == (PLACES["Dallas"], PLACES["Chicago"], 45000, 10)
    assert trip["recommended"] == "Fastest"
    (fastest,) = trip["routes"]
    assert "steps" not in fastest
    assert fastest["miles"] == {"Low": 0.0, "Moderate": 0.0, "High": 0.0, "Severe": 10.0, "No Travel": 0.0, "No data": 10.0}
    assert [cp["level"] for cp in fastest["checkpoints"]] == ["Severe", None, "Severe"]
    assert fastest["checkpoints"][1]["weather"] == {
        "time": trip["hours"][0],
        "wind_mph": None,
        "rain_in": None,
        "snow_in": None,
        "temp_f": None,
        "weather_code": None,
    }
    assert fastest["checkpoints"][1]["hourly"] == [None] * 49
    assert fastest["checkpoints"][2]["eta"] == (when + timedelta(seconds=1200)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert fastest["checkpoints"][2]["hourly"][:2] == ["Severe", "Severe"]


def test_only_post_is_allowed(client):
    assert client.get(URL).status_code == 405


def test_departure_exactly_a_week_ahead_is_still_accepted(client, planned):
    response = post(client, body(departure=at(timedelta(days=7, seconds=-5)).isoformat()))

    assert response.status_code == 200
