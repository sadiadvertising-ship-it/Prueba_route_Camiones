from datetime import timedelta

from . import checkpoints, ranking, risk, weather
from .routing import route_options

# The heatmap slider covers 48 h from departure, so one forecast request serves
# both the slider and the ETAs of a trip shorter than that.
FORECAST_HOURS = 48


class SamePlace(Exception):
    pass


def level(hour, weight_lb):
    return risk.classify(hour["wind_mph"], hour["rain_in"], hour["snow_in"], weight_lb)


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
    forecasts = weather.hourly_forecast(points, departure, end)
    hours = [forecasts[0]["start"] + timedelta(hours=i) for i in range(FORECAST_HOURS + 1)]
    for point, forecast in zip(points, forecasts):
        point["weather"] = weather.at(forecast, point["eta"])
        point["level"] = level(point["weather"], weight_lb)
        # The heatmap slider shows the whole corridor at one moment, under the same load rules.
        point["hourly"] = [level(weather.at(forecast, when), weight_lb) for when in hours]
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
        "hours": hours,
        "recommended": next((route["name"] for route in ranked if route["recommended"]), None),
        "routes": ranked,
    }
