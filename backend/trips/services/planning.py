from datetime import timedelta

from . import checkpoints, ranking, risk, weather
from .routing import route_options

# The heatmap slider covers 48 h from departure, so one forecast request serves
# both the slider and the ETAs of a trip shorter than that.
FORECAST_HOURS = 48


class SamePlace(Exception):
    pass


def plan(origin, destination, departure, weight_lb, interval=None):
    routes = route_options(origin, destination, weight_lb)
    if not routes[0]["distance_miles"]:
        # ORS snaps both places to one road point, so there is no road to sample.
        raise SamePlace("Origin and destination are the same place.")
    # One interval for the whole trip, sized by the main route, so the routes are sampled alike.
    interval = interval or checkpoints.spacing(routes[0]["distance_miles"])
    for route in routes:
        route["checkpoints"] = checkpoints.along(route, interval, departure)
    points = [point for route in routes for point in route["checkpoints"]]
    arrival = max(route["checkpoints"][-1]["eta"] for route in routes)
    end = max(arrival, departure + timedelta(hours=FORECAST_HOURS))
    for point, forecast in zip(points, weather.hourly_forecast(points, departure, end)):
        hour = weather.at(forecast, point["eta"])
        point["weather"] = hour
        point["level"] = risk.classify(hour["wind_mph"], hour["rain_in"], hour["snow_in"], weight_lb)
    ranked = ranking.rank(routes)
    for route in ranked:
        # The client draws the geometry and the checkpoints; the steps only served the sampling.
        del route["steps"]
    return {
        "origin": origin,
        "destination": destination,
        "departure": departure,
        "weight_lb": weight_lb,
        "interval_miles": interval,
        "recommended": next((route["name"] for route in ranked if route["recommended"]), None),
        "routes": ranked,
    }
