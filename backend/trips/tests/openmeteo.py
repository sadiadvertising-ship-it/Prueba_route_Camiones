from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

CALM = {"wind_speed_10m": 5.0, "rain": 0.0, "showers": 0.0, "snowfall": 0.0, "temperature_2m": 60.0, "weather_code": 1}
NO_DATA = dict.fromkeys(CALM)


def answers(trip, reading=lambda route, point, hour: {}):
    # What Open-Meteo sends back for each of the trip's URLs; reading(route, point, hour)
    # overrides the calm defaults for one checkpoint at one hour of the window.
    points = iter([(route, point) for route in trip["routes"] for point in route["checkpoints"]])
    out = []
    for url in trip["forecast_urls"]:
        query = {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}
        start = datetime.fromisoformat(query["start_hour"]).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(query["end_hour"]).replace(tzinfo=timezone.utc)
        hours = (end - start) // timedelta(hours=1) + 1
        items = []
        for _ in query["latitude"].split(","):
            route, point = next(points)
            rows = [dict(CALM, **reading(route, point, hour)) for hour in range(hours)]
            hourly = {name: [row[name] for row in rows] for name in CALM}
            hourly["time"] = [(start + timedelta(hours=hour)).strftime("%Y-%m-%dT%H:%M") for hour in range(hours)]
            items.append({"latitude": point["lat"], "longitude": point["lon"], "hourly": hourly})
        out.append(items)
    return out
