"""Config loaders (household / tag buckets) and the history.html inject step.

No network, no real data files — everything runs against tmp_path fixtures,
plus a couple of sanity checks against the committed config/ defaults.
"""

import json

import build_timeline_data as btd
import household


# ------------------------------------------------------------------ household loader


def test_load_household_parses_comments_and_blanks(tmp_path):
    p = tmp_path / "household_artists.txt"
    p.write_text("# a comment\n\nCoComelon\n  The Wiggles  \n# another\n")
    got = household._load_household(str(p))
    assert got == frozenset({"CoComelon", "The Wiggles"})


def test_load_household_missing_file_is_empty(tmp_path, capsys):
    got = household._load_household(str(tmp_path / "nope.txt"))
    assert got == frozenset()
    assert "warning" in capsys.readouterr().err


def test_committed_household_config_loads():
    assert "CoComelon" in household.HOUSEHOLD_ARTISTS
    assert household.is_household("Deep White Noise Sleep")
    assert not household.is_household("Jason Isbell")


# ------------------------------------------------------------------ tag-bucket loader


def test_load_tag_buckets_missing_file_is_empty(tmp_path, capsys):
    got = btd._load_tag_buckets(str(tmp_path / "nope.json"))
    assert got == {}
    assert "warning" in capsys.readouterr().err


def test_committed_tag_buckets_load_and_order_preserved():
    assert btd.TAG_BUCKETS["americana"] == "folk/americana"
    # specific-before-generic ordering must survive the JSON round trip:
    keys = list(btd.TAG_BUCKETS)
    assert keys.index("alt-country") < keys.index("country")


# ------------------------------------------------------------------ inject


def _write_template(tmp_path):
    t = tmp_path / "history.html"
    t.write_text(
        '<html><script id="timeline-data" type="application/json">'
        "__TIMELINE_JSON__</script></html>"
    )
    return t


def test_inject_replaces_placeholder(tmp_path):
    t = _write_template(tmp_path)
    d = tmp_path / "timeline.json"
    d.write_text(json.dumps({"years": [2024]}))
    out = tmp_path / "history.local.html"
    btd.inject_timeline(str(t), str(d), str(out))
    html = out.read_text()
    assert "__TIMELINE_JSON__" not in html
    assert '"years":[2024]' in html


def test_inject_escapes_closing_script_tag(tmp_path):
    t = _write_template(tmp_path)
    d = tmp_path / "timeline.json"
    d.write_text(json.dumps({"note": "evil</script><b>"}))
    out = tmp_path / "out.html"
    btd.inject_timeline(str(t), str(d), str(out))
    html = out.read_text()
    assert "evil</script>" not in html
    assert "evil<\\/script>" in html
    # escaped form must still parse back to the original string
    payload = html.split('type="application/json">', 1)[1].split("</script>", 1)[0]
    assert json.loads(payload)["note"] == "evil</script><b>"


def test_inject_rejects_already_injected_file(tmp_path):
    t = tmp_path / "history.html"
    t.write_text("<html>no placeholder here</html>")
    d = tmp_path / "timeline.json"
    d.write_text("{}")
    try:
        btd.inject_timeline(str(t), str(d), str(tmp_path / "out.html"))
    except ValueError as e:
        assert "placeholder" in str(e)
    else:
        raise AssertionError("expected ValueError")
