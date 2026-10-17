import json

import pytest
import responses

from trips.services import ors
from trips.services.routing import detour_points, overlap, parse_route, route_options

DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/driving-hgv/geojson"
SNAP_URL = "https://api.openrouteservice.org/v2/snap/driving-hgv"
ORIGIN = {"lat": 30.0, "lon": -100.0}
DESTINATION = {"lat": 30.0, "lon": -99.0}
A, B = [-100.0, 30.0], [-99.0, 30.0]
# Via-points for the straight west-east fixture route: 1/3 and 2/3 of the way, 0.15 deg to each side.
NORTH_1, SOUTH_1, NORTH_2, SOUTH_2 = [-99.7, 30.15], [-99.7, 29.85], [-99.3, 30.15], [-99.3, 29.85]


def line(lat, miles=100.0, seconds=7200.0, n=11, road="I 10"):
    coords = [[-100.0 + i / (n - 1), lat] for i in range(n)]
    summary = {"distance": miles, "duration": seconds}
    steps = [{"distance": miles, "duration": seconds, "way_points": [0, n - 1], "name": road}]
    return {
        "features": [
            {
                "geometry": {"coordinates": coords},
                "properties": {"summary": summary, "segments": [{"steps": steps}]},
            }
        ]
    }


def body_has(**fields):
    def matcher(request):
        body = json.loads(request.body)
        missing = {k: v for k, v in fields.items() if body.get(k) != v}
        return not missing, f"body lacks {missing}"

    return matcher


def snapped(*locations):
    return {"locations": [{"location": p, "name": "", "snapped_distance": 10.0} if p else None for p in locations]}


def add_ends(*locations):
    # The trip's ends are snapped onto a road before any route is asked for.
    responses.post(SNAP_URL, json=snapped(*(locations or (A, B))), match=[body_has(locations=[A, B])])


def add_detour_snap(*locations):
    responses.post(SNAP_URL, json=snapped(*locations), match=[body_has(locations=[NORTH_1, SOUTH_1, NORTH_2, SOUTH_2])])


def add_main(response):
    responses.post(DIRECTIONS_URL, json=response, match=[body_has(preference="recommended", coordinates=[A, B])])


def add_shortest(response):
    responses.post(DIRECTIONS_URL, json=response, match=[body_has(preference="shortest")])


def add_detour(via, response, status=200):
    responses.post(DIRECTIONS_URL, json=response, status=status, match=[body_has(coordinates=[A, via, B])])


def bodies():
    return [json.loads(c.request.body) for c in responses.calls if c.request.url == DIRECTIONS_URL]


@responses.activate
def test_options_are_the_fastest_distinct_routes():
    add_ends()
    add_main(line(30.0))
    add_shortest(line(30.5, miles=90.0, seconds=9000.0, road="US 380"))
    add_detour_snap(NORTH_1, None, NORTH_2, SOUTH_2)
    add_detour(NORTH_1, line(31.0, seconds=8000.0, road="US 83"))
    add_detour(NORTH_2, line(30.0, seconds=7300.0))
    add_detour(SOUTH_2, line(30.0, seconds=7400.0))

    routes = route_options(ORIGIN, DESTINATION, 35000)

    assert [r["name"] for r in routes] == ["Fastest", "Via US 83", "Shortest"]
    assert routes[0]["distance_miles"] == 100.0
    assert routes[0]["steps"] == [{"distance_miles": 100.0, "duration_seconds": 7200.0, "from": 0, "to": 10, "road": "I 10"}]
    assert len(responses.calls) == 7


@responses.activate
def test_detour_without_a_road_of_its_own_gets_a_numbered_label():
    add_ends()
    add_main(line(30.0))
    add_shortest(line(30.0))
    add_detour_snap(NORTH_1, NORTH_2, SOUTH_2)
    add_detour(NORTH_1, line(31.0, seconds=8000.0, road="Marvin D Love Freeway, US 67"))
    add_detour(NORTH_2, line(31.5, seconds=8500.0, road="-"))
    add_detour(SOUTH_2, line(32.0, seconds=9000.0, road="FM 12"))

    routes = route_options(ORIGIN, DESTINATION, 35000)

    assert [r["name"] for r in routes] == ["Fastest", "Via US 67", "Alternative 2"]


@responses.activate
def test_slow_and_duplicate_candidates_leave_fewer_options():
    add_ends()
    add_main(line(30.0))
    add_shortest(line(30.5, seconds=20000.0))
    add_detour_snap(NORTH_1, SOUTH_1)
    add_detour(NORTH_1, line(30.0, seconds=7300.0))
    add_detour(SOUTH_1, line(30.0, seconds=7400.0))

    routes = route_options(ORIGIN, DESTINATION, 35000)

    assert [r["name"] for r in routes] == ["Fastest"]


@responses.activate
def test_failed_detour_is_skipped():
    add_ends()
    add_main(line(30.0))
    add_shortest(line(30.5, seconds=9000.0))
    add_detour_snap(NORTH_1, NORTH_2)
    add_detour(NORTH_1, {"error": {"code": 2010, "message": "Point not found"}}, status=404)
    add_detour(NORTH_2, line(31.5, seconds=8500.0, road="US 90"))

    routes = route_options(ORIGIN, DESTINATION, 35000)

    assert [r["name"] for r in routes] == ["Fastest", "Via US 90", "Shortest"]


@responses.activate
def test_snap_failure_only_drops_the_detours():
    add_main(line(30.0))
    add_shortest(line(30.5, seconds=9000.0))
    responses.post(SNAP_URL, body="Service Unavailable", status=503)

    routes = route_options(ORIGIN, DESTINATION, 35000)

    assert [r["name"] for r in routes] == ["Fastest", "Shortest"]
    assert len(responses.calls) == 4


@responses.activate
def test_main_route_error_is_raised():
    responses.post(DIRECTIONS_URL, json={"error": {"code": 2010, "message": "Could not find routable point"}}, status=404, match=[body_has(preference="recommended")])
    add_shortest(line(30.5))

    with pytest.raises(ors.ORSError, match="Could not find routable point"):
        route_options(ORIGIN, DESTINATION, 35000)


@responses.activate
def test_requests_carry_truck_weight_miles_and_lon_lat_order():
    add_ends()
    add_main(line(30.0))
    add_shortest(line(30.5, seconds=9000.0))
    add_detour_snap(NORTH_1)
    add_detour(NORTH_1, line(31.0, seconds=8000.0))

    route_options(ORIGIN, DESTINATION, 35000)

    main = next(b for b in bodies() if b["preference"] == "recommended")
    assert main["coordinates"] == [[-100.0, 30.0], [-99.0, 30.0]]
    assert main["units"] == "mi"
    assert main["options"]["vehicle_type"] == "hgv"
    assert main["options"]["profile_params"]["restrictions"]["weight"] == pytest.approx(15.88, abs=0.01)
    assert "avoid_features" not in main["options"]
    snaps = [json.loads(c.request.body) for c in responses.calls if c.request.url == SNAP_URL]
    assert snaps == [{"locations": [A, B], "radius": 30000}, {"locations": [NORTH_1, SOUTH_1, NORTH_2, SOUTH_2], "radius": 30000}]


@responses.activate
def test_results_are_cached_per_trip_and_weight():
    add_ends()
    add_main(line(30.0))
    add_shortest(line(30.5, seconds=9000.0))
    add_detour_snap(NORTH_1)
    add_detour(NORTH_1, line(31.0, seconds=8000.0))

    route_options(ORIGIN, DESTINATION, 35000)
    route_options(ORIGIN, DESTINATION, 35000)
    assert len(responses.calls) == 5

    route_options(ORIGIN, DESTINATION, 80000)
    assert len(responses.calls) == 8
    weights = {b["options"]["profile_params"]["restrictions"]["weight"] for b in bodies()}
    assert weights == {15.88, 36.29}


@responses.activate
def test_both_ends_are_moved_onto_a_truck_road_before_routing():
    near_a, near_b = [-100.01, 30.01], [-98.99, 29.99]
    add_ends(near_a, near_b)
    responses.post(DIRECTIONS_URL, json=line(30.0), match=[body_has(preference="recommended", coordinates=[near_a, near_b])])
    add_shortest(line(30.0))

    routes = route_options(ORIGIN, DESTINATION, 35000)

    assert [r["name"] for r in routes] == ["Fastest"]


@responses.activate
def test_an_end_with_no_road_nearby_is_routed_as_given():
    near_b = [-98.99, 29.99]
    add_ends(None, near_b)
    responses.post(DIRECTIONS_URL, json=line(30.0), match=[body_has(preference="recommended", coordinates=[A, near_b])])
    add_shortest(line(30.0))

    routes = route_options(ORIGIN, DESTINATION, 35000)

    assert [r["name"] for r in routes] == ["Fastest"]


def test_detour_points_sit_beside_the_route():
    coords = line(30.0)["features"][0]["geometry"]["coordinates"]

    assert detour_points(coords, A, B) == [NORTH_1, SOUTH_1, NORTH_2, SOUTH_2]
    assert detour_points(coords[:1], A, B) == []


def test_detour_offset_grows_with_the_trip():
    coords = line(30.0)["features"][0]["geometry"]["coordinates"]

    points = detour_points(coords, [-100.0, 30.0], [-90.0, 30.0])

    assert points[0] == [-99.7, 30.8]
    assert points[1] == [-99.7, 29.2]


def test_overlap_ignores_vertex_density_and_sees_real_differences():
    dense = parse_route(line(30.0, n=11), "a")
    sparse = parse_route(line(30.0, n=3), "b")
    other = parse_route(line(30.5), "c")
    forked = parse_route(line(30.0), "d")
    forked["coordinates"] = dense["coordinates"][:8] + [[lon, 30.1] for lon, _ in dense["coordinates"][8:]]

    assert overlap(dense, sparse) == 1.0
    assert overlap(sparse, dense) == 1.0
    assert overlap(dense, other) == 0.0
    assert 0.6 < overlap(forked, dense) < 0.8


def test_parse_route_keeps_steps_from_every_segment():
    data = line(30.0)
    data["features"][0]["properties"]["segments"] = [
        {"steps": [{"distance": 40.0, "duration": 3000.0, "way_points": [0, 5], "name": "I 10"}]},
        {"steps": [{"distance": 60.0, "duration": 4200.0, "way_points": [5, 10], "name": "-"}]},
    ]

    route = parse_route(data, "Detour")

    assert route["name"] == "Detour"
    assert [(s["from"], s["to"], s["road"]) for s in route["steps"]] == [(0, 5, "I 10"), (5, 10, "")]
    assert len(route["coordinates"]) == 11
    assert route["coordinates"][0] == [-100.0, 30.0]
