import pytest
import responses

from trips.services import ors
from trips.services.geocoding import geocode

SEARCH_URL = "https://api.openrouteservice.org/geocode/search"


def result(lon, lat, label):
    return {"features": [{"geometry": {"coordinates": [lon, lat]}, "properties": {"label": label}}]}


@responses.activate
def test_geocode_returns_first_match():
    responses.get(SEARCH_URL, json=result(-96.8, 32.78, "Dallas, TX, USA"))

    place = geocode("  dallas   tx ")

    assert place == {"label": "Dallas, TX, USA", "lat": 32.78, "lon": -96.8}
    assert responses.calls[0].request.params["text"] == "dallas tx"
    assert responses.calls[0].request.headers["Authorization"] == "test-key"


@responses.activate
def test_geocode_is_cached_per_place():
    responses.get(SEARCH_URL, json=result(-87.63, 41.88, "Chicago, IL, USA"))
    responses.get(SEARCH_URL, json=result(-96.8, 32.78, "Dallas, TX, USA"))

    assert geocode("Chicago")["label"] == "Chicago, IL, USA"
    assert geocode("chicago")["label"] == "Chicago, IL, USA"
    assert geocode("Dallas")["label"] == "Dallas, TX, USA"
    assert len(responses.calls) == 2


@responses.activate
def test_geocode_raises_when_nothing_matches():
    responses.get(SEARCH_URL, json={"features": []})

    with pytest.raises(ors.PlaceNotFound):
        geocode("nowhere at all")


@responses.activate
def test_blank_text_is_rejected_without_a_call():
    with pytest.raises(ors.PlaceNotFound):
        geocode("   ")
    assert len(responses.calls) == 0


@responses.activate
def test_geocode_reports_upstream_errors():
    responses.get(SEARCH_URL, json={"error": {"message": "Daily quota reached"}}, status=403)

    with pytest.raises(ors.ORSError, match="403: Daily quota reached"):
        geocode("Denver")
