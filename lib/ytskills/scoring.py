"""Demand and opportunity on a 0-5 scale, shared by every score that ranks by them.

The idea score (youtube-strategy score_idea.py) and the niche score (youtube-demand niches.py) both
weigh measured demand against measured competition. They read the same tiers from here, so a niche
and the ideas inside it are ranked by one rule, and changing a tier changes both.

  volume tier    Google web monthly searches: 0 -> 0, 1-99 -> 1, 100-999 -> 2, 1k-9.9k -> 3,
                 10k-99.9k -> 4, >=100k -> 5
  interest tier  Google Trends YouTube index 0-100: index / 20, halves rounded up (10 -> 1, 50 -> 3,
                 90 -> 5); Python's round() sends halves to even, which made 50 a 2 and 70 a 4
  demand         the larger of the two tiers present, because web volume undercounts YouTube-native
                 searches (mixes, edits, music) and the index alone has no absolute size
  opportunity    5 * (1 - yt_competition); without it 5 * (1 - kd_web / 100), a web proxy

Each function returns the value and its basis, so an output can say what was measured.
"""

from __future__ import annotations

import math

# The measured part of the idea score. The niche score keeps the same ratio between the two, so a
# niche is ranked the way its ideas will be.
DEMAND_WEIGHT = 0.25
OPPORTUNITY_WEIGHT = 0.20

VOLUME_TIERS = ((100_000, 5), (10_000, 4), (1_000, 3), (100, 2), (1, 1))


def volume_tier(volume: float) -> int:
    for floor, tier in VOLUME_TIERS:
        if volume >= floor:
            return tier
    return 0


def interest_tier(index: float) -> int:
    return min(5, math.floor(index / 20 + 0.5))


def demand(volume: float | None, yt_interest: float | None) -> tuple[float, str] | None:
    """The demand tier and what it came from, or None when neither number was measured."""
    tiers: list[tuple[int, str]] = []
    if volume is not None:
        tiers.append((volume_tier(volume), "volume"))
    if yt_interest is not None:
        tiers.append((interest_tier(yt_interest), "yt_interest"))
    if not tiers:
        return None
    value, basis = max(tiers, key=lambda t: t[0])
    return float(value), basis


def opportunity(yt_competition: float | None, kd_web: float | None) -> tuple[float, str] | None:
    """5 * (1 - competition) and its basis, or None when neither competition number was measured."""
    if yt_competition is not None:
        return 5 * (1 - yt_competition), "yt_competition"
    if kd_web is not None:
        return 5 * (1 - kd_web / 100), "kd_web (web proxy)"
    return None


def measured_score(demand_tier: float, opportunity_value: float) -> float:
    """0-100 from demand and opportunity alone, in the idea score's ratio between them."""
    total = DEMAND_WEIGHT + OPPORTUNITY_WEIGHT
    return 20 * (DEMAND_WEIGHT * demand_tier + OPPORTUNITY_WEIGHT * opportunity_value) / total
