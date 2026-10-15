import requests
from django.conf import settings

BASE_URL = "https://api.openrouteservice.org"


class ORSError(Exception):
    pass


class PlaceNotFound(ORSError):
    pass


def request(method, path, **kwargs):
    if not settings.ORS_API_KEY:
        raise ORSError("ORS_API_KEY is not configured")
    headers = {"Authorization": settings.ORS_API_KEY}
    try:
        response = requests.request(method, BASE_URL + path, headers=headers, timeout=20, **kwargs)
    except requests.RequestException as exc:
        raise ORSError(f"OpenRouteService is unreachable: {exc}") from exc
    if response.status_code >= 400:
        raise ORSError(f"OpenRouteService error {response.status_code}: {error_message(response)}")
    try:
        return response.json()
    except ValueError as exc:
        raise ORSError("OpenRouteService returned an unexpected response") from exc


def error_message(response):
    try:
        body = response.json()
    except ValueError:
        return response.text[:200]
    if isinstance(body.get("error"), dict):
        return body["error"].get("message", str(body["error"]))
    # The geocoder is Pelias and uses its own error envelope.
    errors = body.get("geocoding", {}).get("errors")
    if errors:
        return errors[0]
    return response.text[:200]
