import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def fresh_ors(settings):
    settings.ORS_API_KEY = "test-key"
    cache.clear()
