from datetime import timedelta
from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_MI = 3958.8
# A regular checkpoint within a mile of the destination would sit on top of it.
MERGE_MI = 1.0


def spacing(distance_miles):
    # The brief samples every 10, 25 or 50 miles; the step grows with the trip so a
    # cross-country haul does not turn into hundreds of forecast points per route.
    if distance_miles <= 200:
        return 10
    if distance_miles <= 600:
        return 25
    return 50


def along(route, interval, departure):
    coords = route["coordinates"]
    miles, seconds = progress(route)
    marks = [0.0]
    while marks[-1] + interval < miles[-1] - MERGE_MI:
        marks.append(marks[-1] + interval)
    marks.append(miles[-1])
    points = []
    j = 0
    for mile in marks:
        while miles[j + 1] < mile:
            j += 1
        t = (mile - miles[j]) / (miles[j + 1] - miles[j])
        (lon1, lat1), (lon2, lat2) = coords[j], coords[j + 1]
        points.append(
            {
                "mile": round(mile, 1),
                "lat": round(lat1 + (lat2 - lat1) * t, 5),
                "lon": round(lon1 + (lon2 - lon1) * t, 5),
                "eta": departure + timedelta(seconds=round(seconds[j] + (seconds[j + 1] - seconds[j]) * t)),
            }
        )
    return points


def progress(route):
    # ORS reports distance and time per step, so the mile count and the clock follow
    # its road data; the geometry only places a checkpoint between two vertices.
    coords = route["coordinates"]
    miles = [0.0] * len(coords)
    seconds = [0.0] * len(coords)
    mile = secs = 0.0
    for step in route["steps"]:
        vertices = coords[step["from"]:step["to"] + 1]
        legs = [haversine(p, q) for p, q in zip(vertices, vertices[1:])]
        length = sum(legs)
        for k, leg in enumerate(legs, start=step["from"] + 1):
            mile += step["distance_miles"] * leg / length
            secs += step["duration_seconds"] * leg / length
            miles[k], seconds[k] = mile, secs
    return miles, seconds


def haversine(p, q):
    lon1, lat1, lon2, lat2 = map(radians, (*p, *q))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_MI * asin(sqrt(a))
