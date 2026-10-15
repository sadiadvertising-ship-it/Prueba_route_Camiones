import hashlib
import json


def cache_key(prefix, value):
    digest = hashlib.sha1(json.dumps(value, sort_keys=True).encode()).hexdigest()
    return f"{prefix}:{digest}"
