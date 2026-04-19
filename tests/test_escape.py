"""XSS-prevention tests for _escape_report()."""
from __future__ import annotations

from vibecheck.api.profile import _escape_report


def test_escape_simple_script_tag() -> None:
    out = _escape_report({"headline": "<script>alert(1)</script>"})
    assert out["headline"] == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_escape_nested_list() -> None:
    out = _escape_report({"top_interests": ["<img src=x onerror=alert(1)>", "ok"]})
    assert "&lt;img" in out["top_interests"][0]
    assert out["top_interests"][1] == "ok"


def test_escape_nested_dict() -> None:
    out = _escape_report({
        "avatar": {"emoji": "<b>✨</b>", "mood": "chill"},
        "personality_traits": [{"name": "<x>", "evidence": "<y>", "strength": 3}],
    })
    assert out["avatar"]["emoji"] == "&lt;b&gt;✨&lt;/b&gt;"
    assert out["avatar"]["mood"] == "chill"
    assert out["personality_traits"][0]["name"] == "&lt;x&gt;"
    assert out["personality_traits"][0]["strength"] == 3  # non-str untouched


def test_escape_preserves_non_string_types() -> None:
    out = _escape_report({"vibe_score": 85, "flag": True, "missing": None})
    assert out == {"vibe_score": 85, "flag": True, "missing": None}


def test_escape_ampersand() -> None:
    out = _escape_report({"summary": "Tom & Jerry <script>"})
    assert out["summary"] == "Tom &amp; Jerry &lt;script&gt;"
