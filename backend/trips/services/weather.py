from datetime import timedelta, timezone
from urllib.parse import urlencode

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# "rain" alone misses convective showers, which is where the heavy bursts come from.
HOURLY = ["wind_speed_10m", "rain", "showers", "snowfall", "temperature_2m", "weather_code"]
# Open-Meteo takes more points per call; 100 keeps the URL short and a failed batch small.
BATCH_SIZE = 100


class BadForecast(Exception):
    pass


def window(start, end):
    start = utc(start).replace(minute=0, second=0, microsecond=0)
    end = utc(end)
    if end.minute or end.second or end.microsecond:
        end += timedelta(hours=1)
    return start, end.replace(minute=0, second=0, microsecond=0)


def urls(points, start, end):
    # Open-Meteo's free tier is limited per IP and cloud hosts share theirs, so the
    # browser fetches these with its own quota and posts the answers back.
    return [url(points[i:i + BATCH_SIZE], start, end) for i in range(0, len(points), BATCH_SIZE)]


def url(points, start, end):
    params = {
        "latitude": ",".join(f"{p['lat']:.3f}" for p in points),
        "longitude": ",".join(f"{p['lon']:.3f}" for p in points),
        "hourly": ",".join(HOURLY),
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "temperature_unit": "fahrenheit",
        "timezone": "UTC",
        "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
    }
    return f"{FORECAST_URL}?{urlencode(params, safe=',:')}"


def read(answers, points, start, hours):
    # Each answer is what Open-Meteo sent for one URL: a list, or a lone object for one point.
    items = [item for answer in answers for item in (answer if isinstance(answer, list) else [answer])]
    if len(items) != len(points):
        raise BadForecast(f"Expected forecasts for {len(points)} checkpoints, got {len(items)}.")
    return [parse(item, point, start, hours) for item, point in zip(items, points)]


def parse(item, point, start, hours):
    try:
        hourly = item["hourly"]
        times = hourly["time"]
        wind, rain, showers, snow, temp, code = (hourly[name] for name in HOURLY)
    except (KeyError, TypeError):
        raise BadForecast("A forecast is missing its hourly values.")
    series = (times, wind, rain, showers, snow, temp, code)
    if not all(isinstance(values, list) and len(values) == hours for values in series) or times[0] != start.strftime("%Y-%m-%dT%H:%M"):
        raise BadForecast("A forecast does not cover the trip's time window.")
    if not all(number(value) for values in series[1:] for value in values):
        raise BadForecast("Forecast values must be numbers.")
    return {
        "lat": point["lat"],
        "lon": point["lon"],
        "start": start,
        "wind_mph": wind,
        "rain_in": [liquid(r, s) for r, s in zip(rain, showers)],
        "snow_in": snow,
        "temp_f": temp,
        "weather_code": code,
    }


def number(value):
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


def liquid(rain, showers):
    if rain is None and showers is None:
        return None
    return round((rain or 0.0) + (showers or 0.0), 3)


def utc(when):
    if when.tzinfo is None:
        raise ValueError("expected an aware datetime")
    return when.astimezone(timezone.utc)


def at(forecast, when):
    seconds = (utc(when) - forecast["start"]).total_seconds()
    i = int((seconds + 1800) // 3600)
    i = max(0, min(i, len(forecast["wind_mph"]) - 1))
    return {
        "time": forecast["start"] + timedelta(hours=i),
        "wind_mph": forecast["wind_mph"][i],
        "rain_in": forecast["rain_in"][i],
        "snow_in": forecast["snow_in"][i],
        "temp_f": forecast["temp_f"][i],
        "weather_code": forecast["weather_code"][i],
    }
