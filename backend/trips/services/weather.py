from datetime import timedelta, timezone

import requests
from django.core.cache import cache

from . import cache_key

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# "rain" alone misses convective showers, which is where the heavy bursts come from.
HOURLY = ["wind_speed_10m", "rain", "showers", "snowfall", "temperature_2m", "weather_code"]
# Open-Meteo takes more points per call; 100 keeps the URL short and a failed batch small.
BATCH_SIZE = 100


class WeatherError(Exception):
    pass


def hourly_forecast(points, start, end):
    start = utc(start).replace(minute=0, second=0, microsecond=0)
    end = utc(end)
    if end.minute or end.second or end.microsecond:
        end += timedelta(hours=1)
    end = end.replace(minute=0, second=0, microsecond=0)
    forecasts = []
    for i in range(0, len(points), BATCH_SIZE):
        forecasts += fetch(points[i:i + BATCH_SIZE], start, end)
    return forecasts


def fetch(points, start, end):
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
    key = cache_key("weather", params)
    forecasts = cache.get(key)
    if forecasts is None:
        data = request(params)
        items = data if isinstance(data, list) else [data]
        forecasts = [parse(item, point, start) for item, point in zip(items, points)]
        cache.set(key, forecasts, 600)
    return forecasts


def request(params):
    try:
        response = requests.get(FORECAST_URL, params=params, timeout=20)
    except requests.RequestException as exc:
        raise WeatherError("Open-Meteo did not answer. Try again in a minute.") from exc
    if response.status_code >= 400:
        try:
            body = response.json()
        except ValueError:
            body = None
        reason = body.get("reason") if isinstance(body, dict) else None
        raise WeatherError(f"Open-Meteo error {response.status_code}: {reason or response.text[:200]}")
    try:
        return response.json()
    except ValueError as exc:
        raise WeatherError("Open-Meteo returned an unexpected response") from exc


def parse(item, point, start):
    hourly = item["hourly"]
    return {
        "lat": point["lat"],
        "lon": point["lon"],
        "start": start,
        "wind_mph": hourly["wind_speed_10m"],
        "rain_in": [liquid(rain, showers) for rain, showers in zip(hourly["rain"], hourly["showers"])],
        "snow_in": hourly["snowfall"],
        "temp_f": hourly["temperature_2m"],
        "weather_code": hourly["weather_code"],
    }


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
