from django.core.cache import cache

from . import cache_key, ors

# Counties and states are left out: "Boise, ID" otherwise comes back as Boise County,
# a point in the mountains an hour from town.
LAYERS = "address,venue,street,neighbourhood,borough,locality,localadmin,postalcode"


def geocode(text):
    text = " ".join(text.split())
    if not text:
        raise ors.PlaceNotFound("Enter a place name")
    key = cache_key("geocode", text.lower())
    place = cache.get(key)
    if place is None:
        place = search(text)
        cache.set(key, place, 24 * 3600)
    return place


def search(text):
    data = ors.request("GET", "/geocode/search", params={"text": text, "size": 1, "layers": LAYERS})
    features = data.get("features") or []
    if not features:
        raise ors.PlaceNotFound(f"Could not find a place called {text!r}")
    lon, lat = features[0]["geometry"]["coordinates"]
    label = features[0]["properties"].get("label", text)
    return {"label": label, "lat": lat, "lon": lon}
