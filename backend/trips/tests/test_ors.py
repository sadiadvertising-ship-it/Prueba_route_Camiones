import pytest
import requests
import responses

from trips.services import ors

URL = "https://api.openrouteservice.org/geocode/search"


@responses.activate
def test_network_failure_becomes_ors_error():
    responses.get(URL, body=requests.ConnectTimeout("timed out"))

    with pytest.raises(ors.ORSError, match="unreachable"):
        ors.request("GET", "/geocode/search")


@responses.activate
def test_plain_text_error_body_is_reported():
    responses.get(URL, body="Bad Gateway", status=502)

    with pytest.raises(ors.ORSError, match="502: Bad Gateway"):
        ors.request("GET", "/geocode/search")


@responses.activate
def test_pelias_error_message_is_reported():
    responses.get(URL, json={"geocoding": {"errors": ["invalid param 'text': text length, must be >0"]}}, status=400)

    with pytest.raises(ors.ORSError, match="text length"):
        ors.request("GET", "/geocode/search")


@responses.activate
def test_non_json_success_body_becomes_ors_error():
    responses.get(URL, body="<html>maintenance</html>")

    with pytest.raises(ors.ORSError, match="unexpected response"):
        ors.request("GET", "/geocode/search")


@responses.activate
def test_missing_key_fails_before_any_call(settings):
    settings.ORS_API_KEY = ""

    with pytest.raises(ors.ORSError, match="not configured"):
        ors.request("GET", "/geocode/search")
    assert len(responses.calls) == 0
