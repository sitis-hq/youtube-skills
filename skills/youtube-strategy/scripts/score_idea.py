#!/usr/bin/env python3
"""The idea score of youtube-strategy: 0-100, written to the `idea` record's `score` field.

Five dimensions on a 0-5 scale. Two are computed from the idea's `seed` record, three are judged by
the agent against the anchored rubric in references/ideation.md:

  demand       computed: max(volume tier, interest tier), from lib/ytskills/scoring.py
  opportunity  computed: 5 * (1 - yt_competition); without it 5 * (1 - kd_web / 100), marked as a
               web proxy (lib/ytskills/scoring.py, shared with youtube-demand niches.py).
  fit          judged: how squarely the idea sits in a content pillar and the channel's identity.
  packaging    judged: whether hook, title-with-keyword and thumbnail concept are each clear in a line.
  feasibility  judged: whether the channel can make it at its cadence and resources.

  score = 20 * (0.25 demand + 0.20 opportunity + 0.25 fit + 0.15 packaging + 0.15 feasibility)

fit = 0 or feasibility = 0 vetoes the idea: score 0, whatever the demand. A computed dimension can be
given by hand (--demand / --opportunity) when the seed has no data; the output's `basis` says which
dimensions were judged rather than measured, so a reader can tell a measured 70 from a guessed one.

Single idea: flags. Several: --file ideas.json, a list of objects with the same names (and an
optional "title"; seed fields may sit under "seed", as read from the record). Prints JSON sorted by
score; a refusal exits 2. Standard library only: Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "lib"))

from ytskills import scoring  # noqa: E402
from ytskills.scoring import volume_tier  # noqa: E402,F401  (kept importable here: tests and readers use it)

WEIGHTS = {"demand": scoring.DEMAND_WEIGHT, "opportunity": scoring.OPPORTUNITY_WEIGHT, "fit": 0.25, "packaging": 0.15, "feasibility": 0.15}
JUDGED = ("fit", "packaging", "feasibility")


class Refusal(Exception):
    pass


def _num(name: str, v: Any, lo: float, hi: float) -> float | None:
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise Refusal(f"{name} must be a number, got {v!r}") from None
    if not lo <= x <= hi:
        raise Refusal(f"{name} must be within {lo:g}..{hi:g}, got {x:g}")
    return x


def score_one(idea: dict[str, Any]) -> dict[str, Any]:
    seed = {**(idea.get("seed") or {}), **{k: v for k, v in idea.items() if k != "seed"}}
    basis: dict[str, str] = {}
    dims: dict[str, float] = {}

    demand = _num("demand", seed.get("demand"), 0, 5)
    volume = _num("volume", seed.get("volume"), 0, float("inf"))
    interest = _num("yt_interest", seed.get("yt_interest"), 0, 100)
    if demand is not None:
        dims["demand"], basis["demand"] = demand, "judged"
    elif volume is not None or interest is not None:
        dims["demand"], basis["demand"] = scoring.demand(volume, interest)[0], "seed"
    else:
        raise Refusal("demand: the seed has neither volume nor yt_interest; measure it (youtube-demand) "
                      "or give --demand 0-5 by the rubric")

    opportunity = _num("opportunity", seed.get("opportunity"), 0, 5)
    comp = _num("yt_competition", seed.get("yt_competition"), 0, 1)
    kd = _num("kd_web", seed.get("kd_web"), 0, 100)
    if opportunity is not None:
        dims["opportunity"], basis["opportunity"] = opportunity, "judged"
    elif comp is not None or kd is not None:
        value, measured = scoring.opportunity(comp, kd)
        dims["opportunity"], basis["opportunity"] = value, f"seed:{measured}"
    else:
        raise Refusal("opportunity: the seed has neither yt_competition nor kd_web; give --opportunity 0-5")

    for name in JUDGED:
        v = _num(name, seed.get(name), 0, 5)
        if v is None:
            raise Refusal(f"{name} is required: judge it 0-5 by the rubric in references/ideation.md")
        dims[name], basis[name] = v, "judged"

    vetoed = dims["fit"] == 0 or dims["feasibility"] == 0
    value = 0.0 if vetoed else 20 * sum(WEIGHTS[k] * dims[k] for k in WEIGHTS)
    out = {"score": round(value, 1), "components": {k: round(v, 2) for k, v in dims.items()}, "basis": basis}
    if vetoed:
        out["vetoed"] = "fit" if dims["fit"] == 0 else "feasibility"
    if idea.get("title"):
        out = {"title": idea["title"], **out}
    return out


def run(argv: list[str] | None = None) -> dict[str, Any]:
    p = argparse.ArgumentParser(description="Score a video idea 0-100 (youtube-strategy idea score).")
    p.add_argument("--file", help="JSON list of ideas (or one object) with the fields below")
    p.add_argument("--title", help="the idea's working title, echoed back")
    p.add_argument("--volume", help="seed volume: Google web monthly searches")
    p.add_argument("--yt-interest", dest="yt_interest", help="seed yt_interest, 0-100")
    p.add_argument("--yt-competition", dest="yt_competition", help="seed yt_competition, 0..1")
    p.add_argument("--kd-web", dest="kd_web", help="seed kd_web, 0-100 (used only without yt_competition)")
    p.add_argument("--demand", help="judged demand 0-5, only when the seed has no data")
    p.add_argument("--opportunity", help="judged opportunity 0-5, only when the seed has no data")
    for name in JUDGED:
        p.add_argument(f"--{name}", help=f"judged {name} 0-5 (rubric in references/ideation.md)")
    a = p.parse_args(argv)
    if a.file:
        try:
            data = json.loads(Path(a.file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            raise Refusal(f"cannot read --file: {e}") from None
        ideas = data if isinstance(data, list) else [data]
        if not all(isinstance(i, dict) for i in ideas):
            raise Refusal("--file must hold an object or a list of objects")
    else:
        ideas = [{k: v for k, v in vars(a).items() if k != "file" and v is not None}]
    scored = []
    for n, idea in enumerate(ideas):
        try:
            scored.append(score_one(idea))
        except Refusal as e:
            raise Refusal(f"idea {idea.get('title') or n + 1}: {e}") from None
    scored.sort(key=lambda s: -s["score"])
    return {"ok": True, "ideas": scored, "scale": "0-100, youtube-strategy idea score"}


def main(argv: list[str] | None = None) -> int:
    try:
        out = run(argv)
    except Refusal as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
