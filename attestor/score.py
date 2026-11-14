"""Deterministic TAG engagement scoring and per-day caps."""

from dataclasses import dataclass
from typing import Iterable, List, Tuple

WEIGHTS = {"view": 1, "like": 50, "reply": 100, "retweet": 200, "quote": 300}
CAPS = {"original": 5, "quote": 10, "reply": 15}
TOKEN_REPLY_MULTIPLIER_BPS = 15000


@dataclass(frozen=True)
class Tag:
    kind: str
    views: int = 0
    likes: int = 0
    replies: int = 0
    retweets: int = 0
    quotes: int = 0
    reply_to_token: bool = False


def score_tag(tag: Tag) -> int:
    """Score one accepted tag using the PRD's fixed weights."""
    if tag.kind not in ("original", "quote", "reply"):
        raise ValueError("kind must be original, quote, or reply")
    if tag.reply_to_token and tag.kind not in ("quote", "reply"):
        raise ValueError("only quotes and replies can target the token account")
    counts = (tag.views, tag.likes, tag.replies, tag.retweets, tag.quotes)
    if any(type(value) is not int or value < 0 for value in counts):
        raise ValueError("engagement counts must be non-negative integers")
    points = (tag.views * WEIGHTS["view"] + tag.likes * WEIGHTS["like"] +
              tag.replies * WEIGHTS["reply"] + tag.retweets * WEIGHTS["retweet"] +
              tag.quotes * WEIGHTS["quote"])
    if tag.kind == "original":
        points *= 25
    if tag.reply_to_token:
        points = points * TOKEN_REPLY_MULTIPLIER_BPS // 10000
    return points


def score_day(tags: Iterable[Tag]) -> Tuple[List[int], int]:
    """Return per-input scores after ordered caps and their total.

    Input order is the deterministic order supplied by the attestor. Items
    past their type cap remain present with score zero.
    """
    counts = {key: 0 for key in CAPS}
    scored = []
    for tag in tags:
        cap_key = tag.kind
        if cap_key in CAPS:
            if counts[cap_key] >= CAPS[cap_key]:
                scored.append(0)
                continue
            counts[cap_key] += 1
        value = score_tag(tag)
        scored.append(value)
    return scored, sum(scored)
