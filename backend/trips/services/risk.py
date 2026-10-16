LEVELS = ["Low", "Moderate", "High", "Severe", "No Travel"]


def classify(wind_mph, rain_in, snow_in, weight_lb):
    factors = ((wind_band, wind_mph), (rain_band, rain_in), (snow_band, snow_in))
    bands = [band(value) for band, value in factors if value is not None]
    if not bands:
        return None
    worst = max(bands)
    if wind_mph is not None:
        # Load rules from the brief: the heavier the trailer, the less wind it takes.
        if wind_mph >= 45 and weight_lb > 30000:
            worst = 4
        elif wind_mph >= 35 and weight_lb > 40000:
            worst = max(worst, 3)
    return LEVELS[worst]


# The brief lists shared limits twice (0.25 in is both Moderate and High); a reading
# on a limit takes the higher band, as 25 mph already does in the wind row.
def wind_band(mph):
    return sum(mph >= t for t in (25, 35, 45, 55))


def rain_band(inches):
    # No Travel starts strictly above 1.00 in/h for rain and 3.0 in/h for snow,
    # unlike wind, where 55 mph itself already stops the trip.
    if inches > 1.00:
        return 4
    return sum(inches >= t for t in (0.10, 0.25, 0.50))


def snow_band(inches):
    if inches > 3.0:
        return 4
    return sum(inches >= t for t in (0.5, 1.0, 2.0))
