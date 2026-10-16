from math import inf

from .risk import LEVELS

NO_DATA = "No data"


def rank(routes):
    # The brief ranks by Severe miles, High miles, average risk and time, and says
    # nothing about No Travel; but a route with a reading that stops the truck cannot
    # be the recommendation while another one is drivable, so those sort last, and
    # when every route is flagged nothing is recommended.
    ranked = sorted((dict(route, **summarize(route)) for route in routes), key=order)
    for i, route in enumerate(ranked):
        route["recommended"] = i == 0 and not route["no_travel"]
    return ranked


def order(route):
    miles = route["miles"]
    average = route["average_risk"]
    return (
        route["no_travel"],
        miles["Severe"],
        miles["High"],
        # A route whose forecast came back empty cannot claim a low average.
        inf if average is None else average,
        route["duration_seconds"],
    )


def summarize(route):
    points = route["checkpoints"]
    miles = dict.fromkeys(LEVELS + [NO_DATA], 0.0)
    # A checkpoint's reading stands for the road up to the next checkpoint, so the
    # destination adds no miles: the truck stops there.
    for point, following in zip(points, points[1:]):
        miles[point["level"] or NO_DATA] += following["mile"] - point["mile"]
    # Checkpoints without weather data stay out of the average, but their miles are
    # still shown so the per-level miles add up to the trip.
    scores = [LEVELS.index(point["level"]) for point in points if point["level"] is not None]
    return {
        "miles": {level: round(value, 1) for level, value in miles.items()},
        "average_risk": round(sum(scores) / len(scores), 2) if scores else None,
        "no_travel": any(point["level"] == "No Travel" for point in points),
    }
