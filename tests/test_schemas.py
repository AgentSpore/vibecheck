"""Validator tests: RU-only headline/summary + mode/field contract."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from vibecheck.schemas.profile import AvatarSpec, VibeReport


def _avatar() -> AvatarSpec:
    return AvatarSpec(
        gender="neutral", mood="chill", vibe_color="#fbbf24",
        accessories=["glasses"], emoji="✨",
    )


def _report(headline: str, summary: str) -> VibeReport:
    return VibeReport(
        headline=headline, top_interests=["код", "музыка"],
        personality_traits=[], red_flags=[], green_flags=[],
        vibe_score=70, summary=summary, avatar=_avatar(),
    )


def test_headline_latin_only_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        _report(
            headline="This is a completely English headline with many words here",
            summary="Тут по-русски, всё ок, нормальный саммари получился",
        )
    assert "русском" in str(exc_info.value) or "RUSSIAN" in str(exc_info.value).upper()


def test_summary_latin_only_rejected() -> None:
    with pytest.raises(ValidationError):
        _report(
            headline="Спокойный разработчик с хорошим вайбом",
            summary="All english and nothing else to see here folks really",
        )


def test_russian_headline_accepted() -> None:
    r = _report(
        headline="Разработчик с хорошим вайбом и юмором",
        summary="Активный, любопытный, пишет код и читает книги на досуге",
    )
    assert r.vibe_score == 70


def test_mixed_but_mostly_russian_ok() -> None:
    # Russian with technical English terms should pass (cyr*2 >= lat).
    r = _report(
        headline="Backend-разработчик, пишет на Python и увлекается ML",
        summary="Активный разработчик, делится опытом, пишет понятный код и документацию",
    )
    assert "Backend" in r.headline


def test_short_latin_string_ok() -> None:
    # <= 3 latin chars allowed (AI/ML abbreviations).
    r = _report(
        headline="Разработчик AI-систем и любитель котиков из Санкт-Петербурга",
        summary="Строит нейросети, делится знаниями, любит походы и хорошую музыку",
    )
    assert r.avatar.emoji == "✨"
