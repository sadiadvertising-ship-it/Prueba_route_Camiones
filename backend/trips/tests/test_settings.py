import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import settings as config


@pytest.fixture
def reload(monkeypatch):
    # The developer's own .env must not leak into what the settings see here.
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)

    def go(**env):
        for key in ("DJANGO_DEBUG", "DJANGO_SECRET_KEY", "RENDER_EXTERNAL_HOSTNAME"):
            monkeypatch.delenv(key, raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        return importlib.reload(config)

    yield go
    monkeypatch.undo()
    importlib.reload(config)


def test_render_hostname_is_allowed_without_extra_setup(reload):
    assert "api.onrender.com" in reload(RENDER_EXTERNAL_HOSTNAME="api.onrender.com").ALLOWED_HOSTS
    assert "api.onrender.com" not in reload().ALLOWED_HOSTS


def test_production_refuses_the_development_secret(reload):
    with pytest.raises(ImproperlyConfigured):
        reload(DJANGO_DEBUG="0")

    assert reload(DJANGO_DEBUG="0", DJANGO_SECRET_KEY="long-random-string").DEBUG is False
