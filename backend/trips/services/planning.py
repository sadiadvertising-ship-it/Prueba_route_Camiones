from datetime import datetime, timedelta

from django.core import signing

from . import checkpoints, ranking, risk, weather
from .routing import route_options

# The heatmap slider covers 48 h from departure, so one forecast request serves
# both the slider and the ETAs of a trip shorter than that.
FORECAST_HOURS = 48
SALT = "trips.plan"
# A forecast is fetched for the moment of planning; an hour later the trip is planned again.
TICKET_AGE = 3600


class SamePlace(Exception):
    pass


class Expired(Exception):
    pass


def level(hour, weight_lb):
    return risk.classify(hour["wind_mph"], hour["rain_in"], hour["snow_in"], weight_lb)


def prepare(origin, destination, departure, weight_lb, interval=None):
    routes = route_options(origin, destination, weight_lb)
    if not routes[0]["distance_miles"]:
        # ORS snaps both places to one road point, so there is no road to sample.
        raise SamePlace("Origin and destination are the same place.")
    # One interval for the whole trip, sized by the main route, so the routes are sampled alike.
    interval = interval or checkpoints.spacing(routes[0]["distance_miles"])
    for i, route in enumerate(routes):
        route["id"] = i
        route["checkpoints"] = checkpoints.along(route, interval, departure)
        # The client draws the geometry and the checkpoints; the steps only served the sampling.
        del route["steps"]
    points = [point for route in routes for point in route["checkpoints"]]
    arrival = max(route["checkpoints"][-1]["eta"] for route in routes)
    start, end = weather.window(departure, max(arrival, departure + timedelta(hours=FORECAST_HOURS)))
    summary = {
        "weight_lb": weight_lb,
        "start": start.isoformat(),
        "hours": (end - start) // timedelta(hours=1) + 1,
        "routes": [
            {
                "id": route["id"],
                "name": route["name"],
                "distance_miles": route["distance_miles"],
                "duration_seconds": route["duration_seconds"],
                "checkpoints": [dict(point, eta=point["eta"].isoformat()) for point in route["checkpoints"]],
            }
            for route in routes
        ],
    }
    return {
        "origin": origin,
        "destination": destination,
        "departure": departure,
        "weight_lb": weight_lb,
        "interval_miles": interval,
        "hours": [start + timedelta(hours=i) for i in range(FORECAST_HOURS + 1)],
        "routes": routes,
        "forecast_urls": weather.urls(points, start, end),
        # The browser hands this back with the forecasts; the signature keeps the checkpoints
        # the server sampled from being swapped, and the server keeps nothing in between.
        "ticket": signing.dumps(summary, salt=SALT, compress=True),
    }


def assess(ticket, forecasts):
    try:
        trip = signing.loads(ticket, salt=SALT, max_age=TICKET_AGE)
    except signing.BadSignature:
        raise Expired("This plan has expired. Plan the trip again.")
    start = datetime.fromisoformat(trip["start"])
    hours = [start + timedelta(hours=i) for i in range(FORECAST_HOURS + 1)]
    routes = trip["routes"]
    points = [point for route in routes for point in route["checkpoints"]]
    weight_lb = trip["weight_lb"]
    for point, forecast in zip(points, weather.read(forecasts, points, start, trip["hours"])):
        point["eta"] = datetime.fromisoformat(point["eta"])
        point["weather"] = weather.at(forecast, point["eta"])
        point["level"] = level(point["weather"], weight_lb)
        # The heatmap slider shows the whole corridor at one moment, under the same load rules.
        point["hourly"] = [level(weather.at(forecast, when), weight_lb) for when in hours]
    ranked = ranking.rank(routes)
    return {
        "recommended": next((route["name"] for route in ranked if route["recommended"]), None),
        "routes": ranked,
    }
