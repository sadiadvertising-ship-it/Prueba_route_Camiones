from trips.services.ranking import rank, summarize


def route(name, levels, interval=25, duration=3600.0, last=None):
    marks = [i * interval for i in range(len(levels))]
    if last is not None:
        marks[-1] = last
    return {
        "name": name,
        "duration_seconds": duration,
        "checkpoints": [{"mile": mile, "level": level} for mile, level in zip(marks, levels)],
    }


def names(routes):
    return [r["name"] for r in routes]


def test_miles_per_level_follow_the_checkpoint_spacing():
    summary = summarize(route("A", ["Low", "Moderate", "High", "Severe", "Low", "Severe"], last=108))

    assert summary["miles"] == {
        "Low": 33.0,
        "Moderate": 25.0,
        "High": 25.0,
        "Severe": 25.0,
        "No Travel": 0.0,
        "No data": 0.0,
    }
    assert summary["average_risk"] == 1.5
    assert summary["no_travel"] is False


def test_fewest_severe_miles_beats_a_faster_route_with_a_better_average():
    fast = route("Fast", ["Severe", "Low", "Low", "Low"], duration=3000.0)
    slow = route("Slow", ["High", "High", "High", "Low"], duration=4000.0)

    assert names(rank([fast, slow])) == ["Slow", "Fast"]


def test_high_miles_break_a_severe_tie_before_the_average():
    a = route("A", ["Severe", "High", "High", "Low", "Low"], duration=3000.0)
    b = route("B", ["Severe", "High", "Moderate", "Moderate", "Moderate"], duration=4000.0)

    assert names(rank([a, b])) == ["B", "A"]


def test_average_risk_breaks_a_high_tie():
    a = route("A", ["High", "Moderate", "Moderate", "Moderate"], duration=3000.0)
    b = route("B", ["High", "Low", "Low", "Low"], duration=4000.0)

    assert names(rank([a, b])) == ["B", "A"]


def test_faster_route_wins_when_risk_is_equal():
    slow = route("Slow", ["Low", "Moderate", "Low"], duration=4000.0)
    fast = route("Fast", ["Moderate", "Low", "Low"], duration=3000.0)

    ranked = rank([slow, fast])

    assert names(ranked) == ["Fast", "Slow"]
    assert [r["recommended"] for r in ranked] == [True, False]


def test_float_noise_in_the_miles_does_not_decide_a_tie():
    fast = route("Fast", ["Moderate"] * 4 + ["Low", "Severe", "Low"], interval=10, duration=3000.0, last=60.1)
    slow = route("Slow", ["Moderate"] * 5 + ["Low", "Severe", "Low"], interval=10, duration=4000.0, last=70.1)

    ranked = rank([slow, fast])

    assert [r["miles"]["Severe"] for r in ranked] == [10.1, 10.1]
    assert names(ranked) == ["Fast", "Slow"]


def test_no_travel_route_sorts_last_even_with_fewer_severe_miles():
    stormy = route("Stormy", ["Low", "No Travel", "Low", "Low"], duration=3000.0)
    severe = route("Severe", ["Severe", "Severe", "Severe", "Low"], duration=4000.0)

    ranked = rank([stormy, severe])

    assert names(ranked) == ["Severe", "Stormy"]
    assert [r["recommended"] for r in ranked] == [True, False]
    assert ranked[1]["no_travel"] is True


def test_no_travel_at_the_destination_still_flags_the_route():
    summary = summarize(route("A", ["Low", "Low", "No Travel"]))

    assert summary["no_travel"] is True
    assert summary["miles"]["No Travel"] == 0.0
    assert summary["average_risk"] == 1.33


def test_nothing_is_recommended_when_every_route_has_no_travel():
    a = route("A", ["No Travel", "Severe", "Low"], duration=3000.0)
    b = route("B", ["No Travel", "Low", "Low"], duration=4000.0)

    ranked = rank([a, b])

    assert names(ranked) == ["B", "A"]
    assert [r["recommended"] for r in ranked] == [False, False]


def test_missing_data_stays_out_of_the_average_but_keeps_its_miles():
    summary = summarize(route("A", ["Low", None, "High", "Low"]))

    assert summary["miles"]["No data"] == 25.0
    assert summary["miles"]["Low"] == 25.0
    assert summary["miles"]["High"] == 25.0
    assert summary["average_risk"] == 0.67


def test_route_without_any_forecast_ranks_after_a_known_one():
    unknown = route("Unknown", [None, None, None], duration=3000.0)
    known = route("Known", ["Moderate", "Moderate", "Moderate"], duration=4000.0)

    ranked = rank([unknown, known])

    assert names(ranked) == ["Known", "Unknown"]
    assert ranked[1]["average_risk"] is None


def test_input_order_is_kept_on_a_full_tie():
    main = route("Main", ["Low", "Low"])
    other = route("Alternative", ["Low", "Low"])

    assert names(rank([main, other])) == ["Main", "Alternative"]
