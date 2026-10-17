from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from trips.services.weather import BadForecast, at, read, urls, window

START = datetime(2026, 10, 15, 21, 0, tzinfo=timezone.utc)
END = START + timedelta(hours=48)
DALLAS = {"lat": 32.7362, "lon": -96.7844}
CHICAGO = {"lat": 41.879, "lon": -87.6606}


def query(url):
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


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


def test_urls_ask_for_us_units_and_whole_hours():
    start, end = window(START + timedelta(minutes=45), END)
    (only,) = urls([DALLAS, CHICAGO], start, end)

    params = query(only)
    assert only.startswith("https://api.open-meteo.com/v1/forecast?")
    assert params["latitude"] == "32.736,41.879"
    assert params["longitude"] == "-96.784,-87.661"
    assert params["hourly"] == "wind_speed_10m,rain,showers,snowfall,temperature_2m,weather_code"
    assert params["wind_speed_unit"] == "mph"
    assert params["precipitation_unit"] == "inch"
    assert params["temperature_unit"] == "fahrenheit"
    assert params["timezone"] == "UTC"
    assert params["start_hour"] == "2026-10-15T21:00"
    assert params["end_hour"] == "2026-10-17T21:00"


def test_window_end_is_rounded_up_to_the_next_hour():
    assert window(START, START + timedelta(hours=1, minutes=30)) == (START, START + timedelta(hours=2))
    assert window(START, START + timedelta(hours=2)) == (START, START + timedelta(hours=2))


def test_times_are_normalized_to_utc_and_must_carry_a_zone():
    central = timezone(timedelta(hours=-5))

    start, end = window(START.astimezone(central), END.astimezone(central))

    assert (start, end) == (START, END)
    assert start.utcoffset() == timedelta(0)
    with pytest.raises(ValueError):
        window(START.replace(tzinfo=None), END)
    forecast = read([location()], [DALLAS], START, 49)[0]
    with pytest.raises(ValueError):
        at(forecast, START.replace(tzinfo=None))


def test_points_go_out_in_batches_of_a_hundred():
    points = [{"lat": 30 + i * 0.01, "lon": -100.0} for i in range(150)]

    first, second = urls(points, START, END)

    assert query(first)["latitude"].count(",") == 99
    assert query(second)["latitude"].count(",") == 49
    assert query(second)["latitude"].startswith("31.000,")


def test_answers_line_up_with_the_points_asked_for():
    forecasts = read([[location(wind=5.0), location(wind=30.0)]], [DALLAS, CHICAGO], START, 49)

    assert [(f["lat"], f["lon"]) for f in forecasts] == [(32.7362, -96.7844), (41.879, -87.6606)]
    assert forecasts[1]["wind_mph"][0] == 30.0
    assert forecasts[0]["start"] == START
    assert len(forecasts[0]["wind_mph"]) == 49


def test_answers_to_several_urls_are_joined_in_order_and_a_lone_point_comes_as_one_object():
    points = [{"lat": 30 + i * 0.01, "lon": -100.0} for i in range(101)]

    forecasts = read([[location()] * 100, location(wind=9.0)], points, START, 49)

    assert len(forecasts) == 101
    assert forecasts[100]["lat"] == pytest.approx(31.0)
    assert forecasts[100]["wind_mph"][0] == 9.0


def test_rain_includes_showers_and_keeps_missing_values():
    data = location(rain=0.1, showers=0.25)
    data["hourly"]["rain"][1] = None
    data["hourly"]["showers"][1] = None
    data["hourly"]["showers"][2] = None
    data["hourly"]["rain"][4] = None
    data["hourly"]["wind_speed_10m"][3] = None

    forecast = read([data], [DALLAS], START, 49)[0]

    assert forecast["rain_in"][0] == 0.35
    assert forecast["rain_in"][1] is None
    assert forecast["rain_in"][2] == 0.1
    assert forecast["rain_in"][4] == 0.25
    assert forecast["wind_mph"][3] is None


def test_at_picks_the_nearest_hour_and_stays_inside_the_window():
    data = location()
    data["hourly"]["wind_speed_10m"] = list(range(49))
    data["hourly"]["rain"] = [i / 100 for i in range(49)]
    data["hourly"]["snowfall"] = [i / 1000 for i in range(49)]
    data["hourly"]["temperature_2m"] = [50 + i for i in range(49)]
    data["hourly"]["weather_code"] = list(range(49))
    forecast = read([data], [DALLAS], START, 49)[0]

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


def short(answer):
    answer["hourly"]["rain"].pop()


def late(answer):
    answer["hourly"]["time"][0] = "2026-10-15T22:00"


def bare(answer):
    del answer["hourly"]


def text(answer):
    answer["hourly"]["wind_speed_10m"][5] = "40"


def flag(answer):
    answer["hourly"]["snowfall"][5] = True


@pytest.mark.parametrize(
    "spoil, message",
    [
        (bare, "missing its hourly values"),
        (short, "does not cover the trip's time window"),
        (late, "does not cover the trip's time window"),
        (text, "must be numbers"),
        (flag, "must be numbers"),
    ],
)
def test_answers_that_do_not_fit_the_request_are_refused(spoil, message):
    answer = location()
    spoil(answer)

    with pytest.raises(BadForecast, match=message):
        read([answer], [DALLAS], START, 49)


def test_a_missing_answer_is_refused():
    with pytest.raises(BadForecast, match="Expected forecasts for 2 checkpoints, got 1"):
        read([location()], [DALLAS, CHICAGO], START, 49)
