from concurrent.futures import ThreadPoolExecutor

from django.core.cache import cache

from . import cache_key, ors

LB_PER_METRIC_TON = 2204.62
ROUTE_COUNT = 3
CELL_DEG = 0.02
DUPLICATE_OVERLAP = 0.85
# The public ORS server snaps waypoints only within 350 m, so detour
# via-points are snapped to a road first, with a radius of their own.
SNAP_RADIUS_M = 30000
MIN_DETOUR_DEG = 0.15
DETOUR_SPREAD = 0.08
# A detour much slower than the main route is noise, not an option.
MAX_DETOUR_FACTOR = 1.5


def route_options(origin, destination, weight_lb):
    a = [origin["lon"], origin["lat"]]
    b = [destination["lon"], destination["lat"]]
    with ThreadPoolExecutor(max_workers=4) as pool:
        # ORS native alternatives only work under 100 km, and for the hgv profile
        # only "recommended" and "shortest" run on the fast index ("fastest" takes
        # ~100 s on a long haul and returns the same road), so the extra options
        # come from the shortest route and from detours through snapped via-points.
        main_job = pool.submit(directions, [a, b], weight_lb, "Fastest", "recommended")
        jobs = [pool.submit(directions, [a, b], weight_lb, "Shortest", "shortest")]
        main = main_job.result()
        for via in snap(detour_points(main["coordinates"], a, b)):
            jobs.append(pool.submit(directions, [a, via["location"], b], weight_lb, "Detour", "recommended"))
        candidates = []
        for job in jobs:
            try:
                candidates.append(job.result())
            except ors.ORSError:
                continue
    routes = [main]
    for route in sorted(candidates, key=lambda r: r["duration_seconds"]):
        if route["duration_seconds"] > main["duration_seconds"] * MAX_DETOUR_FACTOR:
            break
        if all(overlap(route, kept) <= DUPLICATE_OVERLAP for kept in routes):
            if route["name"] == "Detour":
                route["name"] = via_label(route, main) or f"Alternative {len(routes)}"
            routes.append(route)
        if len(routes) == ROUTE_COUNT:
            break
    return routes


def via_label(route, main):
    main_roads = {step["road"] for step in main["steps"]}
    new_roads = [step for step in route["steps"] if step["road"] and step["road"] not in main_roads]
    if not new_roads:
        return None
    return "Via " + short_road(max(new_roads, key=lambda step: step["distance_miles"])["road"])


def short_road(name):
    # ORS joins the street name and its refs: "Marvin D Love Freeway, US 67".
    parts = list(dict.fromkeys(part.strip() for part in name.split(",")))
    refs = [part for part in parts if any(ch.isdigit() for ch in part)]
    return min(refs, key=len) if refs else parts[0]


def directions(points, weight_lb, name, preference):
    body = {
        "coordinates": points,
        "preference": preference,
        "units": "mi",
        "options": {
            "vehicle_type": "hgv",
            "profile_params": {"restrictions": {"weight": round(weight_lb / LB_PER_METRIC_TON, 2)}},
        },
    }
    key = cache_key("directions", body)
    route = cache.get(key)
    if route is None:
        data = ors.request("POST", "/v2/directions/driving-hgv/geojson", json=body)
        route = parse_route(data, name)
        cache.set(key, route, 3600)
    return dict(route, name=name)


def parse_route(data, name):
    feature = data["features"][0]
    props = feature["properties"]
    steps = [
        {
            "distance_miles": step["distance"],
            "duration_seconds": step["duration"],
            "from": step["way_points"][0],
            "to": step["way_points"][1],
            "road": step.get("name", "").strip("-"),
        }
        for segment in props["segments"]
        for step in segment["steps"]
    ]
    return {
        "name": name,
        "coordinates": feature["geometry"]["coordinates"],
        "distance_miles": props["summary"]["distance"],
        "duration_seconds": props["summary"]["duration"],
        "steps": steps,
    }


def snap(points):
    if not points:
        return []
    body = {"locations": points, "radius": SNAP_RADIUS_M}
    key = cache_key("snap", body)
    snapped = cache.get(key)
    if snapped is None:
        try:
            data = ors.request("POST", "/v2/snap/driving-hgv", json=body)
        except ors.ORSError:
            return []
        snapped = [loc for loc in data.get("locations", []) if loc]
        cache.set(key, snapped, 3600)
    return snapped


def detour_points(coords, a, b):
    if len(coords) < 2:
        return []
    straight = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
    offset = max(MIN_DETOUR_DEG, DETOUR_SPREAD * straight)
    span = max(1, len(coords) // 12)
    points = []
    for fraction in (1 / 3, 2 / 3):
        i = int(len(coords) * fraction)
        (x1, y1), (x2, y2) = coords[max(0, i - span)], coords[min(len(coords) - 1, i + span)]
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5 or 1
        nx, ny = -dy / length, dx / length
        x, y = coords[i]
        points.append([round(x + nx * offset, 4), round(y + ny * offset, 4)])
        points.append([round(x - nx * offset, 4), round(y - ny * offset, 4)])
    return points


def overlap(route, other):
    cells = grid_cells(route["coordinates"])
    return len(cells & grid_cells(other["coordinates"])) / len(cells)


def grid_cells(coords):
    # Highway geometries have vertices miles apart, so each segment is walked in
    # CELL_DEG steps; otherwise two routes on the same road share almost no cells.
    cells = set()
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        n = int(max(abs(x2 - x1), abs(y2 - y1)) / CELL_DEG) + 1
        for i in range(n):
            t = i / n
            cells.add((round((x1 + (x2 - x1) * t) / CELL_DEG), round((y1 + (y2 - y1) * t) / CELL_DEG)))
    x, y = coords[-1]
    cells.add((round(x / CELL_DEG), round(y / CELL_DEG)))
    return cells
