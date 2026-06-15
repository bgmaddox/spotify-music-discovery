"""Regression: `_artist_names` must tolerate str-or-dict artist entries.

A dump can store artists as {name: ...} dicts or as plain strings; an earlier version
assumed dicts and crashed taste_snapshot on the string shape. This pins both shapes.
"""

import mcp_server


def test_artist_names_handles_dict_entries():
    track = {"artists": [{"name": "Jason Isbell"}, {"name": "Amanda Shires"}]}
    assert mcp_server._artist_names(track) == "Jason Isbell, Amanda Shires"


def test_artist_names_handles_string_entries():
    track = {"artists": ["Jason Isbell", "Amanda Shires"]}
    assert mcp_server._artist_names(track) == "Jason Isbell, Amanda Shires"


def test_artist_names_mixed_and_blanks():
    track = {"artists": ["Plain Name", {"name": "Dict Name"}, {"nope": 1}, ""]}
    assert mcp_server._artist_names(track) == "Plain Name, Dict Name"


def test_artist_names_empty():
    assert mcp_server._artist_names({}) == ""
