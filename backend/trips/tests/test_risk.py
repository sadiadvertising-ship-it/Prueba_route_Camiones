import pytest

from trips.services.risk import classify


def level(wind=0.0, rain=0.0, snow=0.0, weight=20000):
    return classify(wind, rain, snow, weight)


@pytest.mark.parametrize(
    "wind, expected",
    [
        (0, "Low"),
        (24.9, "Low"),
        (25, "Moderate"),
        (34.9, "Moderate"),
        (35, "High"),
        (44.9, "High"),
        (45, "Severe"),
        (54.9, "Severe"),
        (55, "No Travel"),
        (80, "No Travel"),
    ],
)
def test_wind_bands(wind, expected):
    assert level(wind=wind) == expected


@pytest.mark.parametrize(
    "rain, expected",
    [
        (0.09, "Low"),
        (0.10, "Moderate"),
        (0.24, "Moderate"),
        (0.25, "High"),
        (0.49, "High"),
        (0.50, "Severe"),
        (1.00, "Severe"),
        (1.01, "No Travel"),
    ],
)
def test_rain_bands(rain, expected):
    assert level(rain=rain) == expected


@pytest.mark.parametrize(
    "snow, expected",
    [
        (0.4, "Low"),
        (0.5, "Moderate"),
        (0.9, "Moderate"),
        (1.0, "High"),
        (1.9, "High"),
        (2.0, "Severe"),
        (3.0, "Severe"),
        (3.1, "No Travel"),
    ],
)
def test_snow_bands(snow, expected):
    assert level(snow=snow) == expected


def test_worst_factor_wins():
    assert level(wind=30, rain=0.6, snow=0.2) == "Severe"
    assert level(wind=50, rain=0.05) == "Severe"
    assert level(wind=10, snow=3.5) == "No Travel"


@pytest.mark.parametrize(
    "wind, weight, expected",
    [
        (55, 1000, "No Travel"),
        (45, 30000, "Severe"),
        (45, 30001, "No Travel"),
        (54.9, 35000, "No Travel"),
        (35, 40000, "High"),
        (35, 40001, "Severe"),
        (44.9, 45000, "Severe"),
        (34.9, 45000, "Moderate"),
        (50, 45000, "No Travel"),
    ],
)
def test_load_rules(wind, weight, expected):
    assert level(wind=wind, weight=weight) == expected


def test_load_rule_never_lowers_a_worse_level():
    assert level(wind=40, rain=1.5, weight=45000) == "No Travel"
    assert level(wind=36, snow=2.5, weight=45000) == "Severe"


def test_missing_factors_are_skipped_and_all_missing_is_unknown():
    assert classify(None, 0.3, None, 45000) == "High"
    assert classify(None, 0.0, 0.0, 45000) == "Low"
    assert classify(None, None, None, 45000) is None
