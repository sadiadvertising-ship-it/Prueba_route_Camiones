from datetime import datetime, timedelta, timezone

import pytest
import requests
import responses

from trips.services.weather import WeatherError, at, hourly_forecast

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
START = datetime(2026, 10, 15, 21, 0, tzinfo=timezone.utc)
END = START + timedelta(hours=48)
DALLAS = {"lat": 32.7362, "lon": -96.7844}
CHICAGO = {"lat": 41.879, "lon": -87.6606}


def location(hours=49, wind=5.0, rain=0.0, showers=0.0, snow=0.0):
    times = [(START + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    return {
        "latitude": 32.75,
        "longitude": -96.75,
        "hourly": {
            "time": times,
            "wind_speed_10m": [wind] * hours,
            "rain": [rain] * hours,
            "showers": [showers] * hours,
            "snowfall": [snow] * hours,
            "temperature_2m": [70.0] * hours,
            "weather_code": [0] * hours,
        },
    }


@responses.activate
def test_request_uses_us_units_and_whole_hours():
    responses.get(FORECAST_URL, json=[location(), location()])

    forecasts = hourly_forecast([DALLAS, CHICAGO], START + timedelta(minutes=45), END)

    params = responses.calls[0].request.params
    assert params["latitude"] == "32.736,41.879"
    assert params["longitude"] == "-96.784,-87.661"
    assert params["hourly"] == "wind_speed_10m,rain,showers,snowfall,temperature_2m,weather_code"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert params["temperature_unit"] == "fahrenheit"
    assert params["timezone"] == "UTC"
    assert params["start_hour"] == "2026-10-15T21:00"
    assert params["end_hour"] == "2026-10-17T21:00"
    assert forecasts[0]["start"] == START


@responses.activate
def test_window_end_is_rounded_up_to_the_next_hour():
    responses.get(FORECAST_URL, json=location())

    hourly_forecast([DALLAS], START, START + timedelta(hours=1, minutes=30))

    assert responses.calls[0].request.params["end_hour"] == "2026-10-15T23:00"


@responses.activate
def test_times_are_normalized_to_utc_and_must_carry_a_zone():
    responses.get(FORECAST_URL, json=location())
    central = timezone(timedelta(hours=-5))

    forecast = hourly_forecast([DALLAS], START.astimezone(central), END.astimezone(central))[0]

    assert responses.calls[0].request.params["start_hour"] == "2026-10-15T21:00"
    assert forecast["start"] == START
    assert forecast["start"].utcoffset() == timedelta(0)
    with pytest.raises(ValueError):
        hourly_forecast([DALLAS], START.replace(tzinfo=None), END)
    with pytest.raises(ValueError):
        at(forecast, START.replace(tzinfo=None))


@responses.activate
def test_forecasts_line_up_with_the_points_asked_for():
    responses.get(FORECAST_URL, json=[location(wind=5.0), location(wind=30.0)])

    forecasts = hourly_forecast([DALLAS, CHICAGO], START, END)

    assert [(f["lat"], f["lon"]) for f in forecasts] == [(32.7362, -96.7844), (41.879, -87.6606)]
    assert forecasts[1]["wind_mph"][0] == 30.0
    assert len(forecasts[0]["wind_mph"]) == 49


@responses.activate
def test_single_location_comes_back_as_a_list_of_one():
    responses.get(FORECAST_URL, json=location())

    forecasts = hourly_forecast([DALLAS], START, END)

    assert len(forecasts) == 1
    assert forecasts[0]["lat"] == DALLAS["lat"]


@responses.activate
def test_rain_includes_showers_and_keeps_missing_values():
    data = location(rain=0.1, showers=0.25)
    data["hourly"]["rain"][1] = None
    data["hourly"]["showers"][1] = None
    data["hourly"]["showers"][2] = None
    data["hourly"]["rain"][4] = None
    data["hourly"]["wind_speed_10m"][3] = None
    responses.get(FORECAST_URL, json=data)

    forecast = hourly_forecast([DALLAS], START, END)[0]

    assert forecast["rain_in"][0] == 0.35
    assert forecast["rain_in"][1] is None
    assert forecast["rain_in"][2] == 0.1
    assert forecast["rain_in"][4] == 0.25
    assert forecast["wind_mph"][3] is None


@responses.activate
def test_at_picks_the_nearest_hour_and_stays_inside_the_window():
    data = location()
    data["hourly"]["wind_speed_10m"] = list(range(49))
    data["hourly"]["rain"] = [i / 100 for i in range(49)]
    data["hourly"]["snowfall"] = [i / 1000 for i in range(49)]
    data["hourly"]["temperature_2m"] = [50 + i for i in range(49)]
    data["hourly"]["weather_code"] = list(range(49))
    responses.get(FORECAST_URL, json=data)
    forecast = hourly_forecast([DALLAS], START, END)[0]

    assert at(forecast, START + timedelta(hours=2, minutes=40)) == {
        "time": START + timedelta(hours=3),
        "wind_mph": 3,
        "rain_in": 0.03,
        "snow_in": 0.003,
        "temp_f": 53,
        "weather_code": 3,
    }
    assert at(forecast, START + timedelta(hours=2, minutes=20))["wind_mph"] == 2
    assert at(forecast, START + timedelta(hours=1, minutes=30))["wind_mph"] == 2
    assert at(forecast, START + timedelta(hours=2, minutes=30))["wind_mph"] == 3
    assert at(forecast, START - timedelta(hours=5))["wind_mph"] == 0
    assert at(forecast, START + timedelta(days=9))["wind_mph"] == 48


@responses.activate
def test_points_are_fetched_in_batches_of_a_hundred():
    responses.get(FORECAST_URL, json=[location()] * 100)
    responses.get(FORECAST_URL, json=[location()] * 50)
    points = [{"lat": 30 + i * 0.01, "lon": -100.0} for i in range(150)]

    forecasts = hourly_forecast(points, START, END)

    assert len(forecasts) == 150
    assert len(responses.calls) == 2
    assert responses.calls[0].request.params["latitude"].count(",") == 99
    assert responses.calls[1].request.params["latitude"].count(",") == 49
    assert forecasts[149]["lat"] == pytest.approx(31.49)


@responses.activate
def test_forecast_is_cached_per_points_and_window():
    responses.get(FORECAST_URL, json=location())

    first = hourly_forecast([DALLAS], START, END)
    again = hourly_forecast([DALLAS], START + timedelta(minutes=5), END)
    assert again == first
    assert len(responses.calls) == 1

    hourly_forecast([CHICAGO], START, END)
    assert len(responses.calls) == 2
    hourly_forecast([DALLAS], START, END + timedelta(hours=1))
    assert len(responses.calls) == 3


@responses.activate
def test_api_reason_is_reported():
    responses.get(FORECAST_URL, json={"error": True, "reason": "Invalid value: latitude"}, status=400)

    with pytest.raises(WeatherError, match="400: Invalid value: latitude"):
        hourly_forecast([DALLAS], START, END)


@responses.activate
def test_plain_text_error_body_is_reported():
    responses.get(FORECAST_URL, body="Bad Gateway", status=502)

    with pytest.raises(WeatherError, match="502: Bad Gateway"):
        hourly_forecast([DALLAS], START, END)


@responses.activate
def test_non_json_success_body_becomes_weather_error():
    responses.get(FORECAST_URL, body="<html>maintenance</html>")

    with pytest.raises(WeatherError, match="unexpected response"):
        hourly_forecast([DALLAS], START, END)


@responses.activate
def test_network_failure_becomes_weather_error():
    responses.get(FORECAST_URL, body=requests.ConnectTimeout("timed out"))

    with pytest.raises(WeatherError, match="did not answer") as failure:
        hourly_forecast([DALLAS], START, END)
    assert "timed out" not in str(failure.value)
