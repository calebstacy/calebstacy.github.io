# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "terminaltexteffects>=0.15",
#   "anthropic>=0.60",
# ]
# ///
"""shelf tool — a terminal onto the Netflix shelf-naming records.

The proper CLI twin of plays/netflix-shelves/ask.html. Same two schemas
(shelves.json, moves.json — the single source of truth), the crawl's own rule
definitions imported straight from analyze_shelves.py, TerminalTextEffects for
the boot ident, and the same Claude agent with the same deterministic tools.

Run:  uv run shelftool.py            (uv resolves the dependencies above)
      uv run shelftool.py --plain    (skip the ident)
Agent: export ANTHROPIC_API_KEY, or `key sk-ant-…` inside the session.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import socket
import sys
import textwrap
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_shelves as A  # the crawl's own token definitions — never re-declared
import derive_corpus as D

# ---------------------------------------------------------------- palette

def _tty() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

def _c(code: str) -> str:
    return code if _tty() else ""

RED = _c("\x1b[38;2;229;9;20m")
AMBER = _c("\x1b[38;2;233;196;106m")
SAGE = _c("\x1b[38;2;157;184;174m")
INK = _c("\x1b[38;2;242;236;224m")
DIM = _c("\x1b[2m")
BOLD = _c("\x1b[1m")
R = _c("\x1b[0m")

BANNER = "█▄ █ █▀▀ ▀█▀ █▀▀ █   █ ▀▄▀\n█ ▀█ ██▄  █  █▀  █▄▄ █ █ █"

def _scale_banner(src: str) -> str:
    """Double the banner in both directions: each half-block cell becomes a 2x2
    block, so the mark reads at marquee size where the terminal has the room."""
    up = {"█": ("██", "██"), "▀": ("██", "  "), "▄": ("  ", "██"), " ": ("  ", "  ")}
    rows: list[str] = []
    for line in src.split("\n"):
        rows.append("".join(up[ch][0] for ch in line).rstrip())
        rows.append("".join(up[ch][1] for ch in line).rstrip())
    return "\n".join(rows)

def _center_block(block: str, cols: int) -> str:
    width = max(len(line) for line in block.split("\n"))
    pad = " " * max(0, (cols - width) // 2)
    return "\n".join(pad + line for line in block.split("\n"))
NAMING_KINDS = {"genre-name", "shelf-heading", "list-name"}
AGENT_MODEL = "claude-opus-5"
SHAPE_LABELS = {
    "TONE": "tone word",
    "GEN": "genre",
    "UNIT": "the noun",
    "AUD": "audience",
    "ORIG": "place",
    "ERA": "era",
    "BRAND": "brand",
    "CUR": "quality cue",
    "TEMP": "time cue",
    "IMP": "opener",
    "&": "an ampersand",
}
READING_LABELS = {
    "title-case-discipline": "keeps Title Case",
    "content-unit-present": "uses a closing noun",
    "content-unit-terminal": "puts the noun last",
    "tv-casing-holds": "keeps TV uppercase",
    "connective-ampersand": "couples the pair with an ampersand",
    "tone-present": "uses a tone word",
    "second-person": "speaks to the viewer",
    "speech-act-question": "opens as a question",
    "speech-act-command": "opens as an invitation",
    "speech-act-plain": "states the category plainly",
    "curatorial-authority": "makes an editorial claim",
    "time-promise": "promises a viewing length",
    "no-unit": "drops the closing noun",
    "wordplay-mechanical-rhyme": "uses a rhyme",
    "wordplay-mechanical-alliteration": "repeats an opening sound",
    "wordplay-semantic-signed": "carries a reviewed double reading",
}
KIND_ALIASES = {
    "genre pages": "kind:genre-name",
    "rows": "kind:shelf-heading",
    "ranked lists": "kind:list-name",
}

# Public-deployment caps, set via environment (0 or unset = off; local runs unchanged).
# On the demo box these arrive through the systemd EnvironmentFile next to the key.
def _env_int(name: str) -> int:
    try:
        return max(0, int(os.environ.get(name, "0")))
    except ValueError:
        return 0

MAX_AGENT_TURNS = _env_int("SHELFELF_MAX_AGENT_TURNS")  # house-key agent turns per session
MAX_ASK_CHARS = _env_int("SHELFELF_MAX_ASK_CHARS")      # longest single ask routed to the agent
MAX_TOKENS = _env_int("SHELFELF_MAX_TOKENS") or 16000   # per-reply output ceiling
MEASURE_HOST = "127.0.0.1"
MEASURE_PORT = 7699
MEASURE_TIMEOUT_SECONDS = 0.25
MEASURE_MAX_RESPONSE_BYTES = 65_536
MEASURE_MIN_WORDS = 50
MEASURE_DIMENSION_COUNT = 12


def reading_label(reading_id: str) -> str:
    if reading_id in READING_LABELS:
        return READING_LABELS[reading_id]
    if reading_id.startswith("audience-who:"):
        return f"names {reading_id.split(':', 1)[1]}"
    if reading_id == "audience-position:leads":
        return "puts the audience first"
    if reading_id == "audience-position:trails_for_phrase":
        return 'places the audience after "for"'
    if reading_id == "audience-position:other":
        return "names the audience elsewhere"
    if reading_id == "audience-position:absent":
        return "leaves the audience unstated"
    if reading_id.startswith("name-length:"):
        value = reading_id.split(":", 1)[1]
        return "uses five or more words" if value == "5plus" else f"uses {value} words"
    raise KeyError(reading_id)


def construction_display(text: str) -> str:
    shape = D.template_shape(text)
    labels = [SHAPE_LABELS[tag] for tag in shape.split() if tag in SHAPE_LABELS]
    return ", then ".join(labels) if labels else "a phrase without a named category"


VISIBLE_TEXT_REPLACEMENTS = [
    (re.compile(r"\bplaybook_report\b", re.IGNORECASE), "that group"),
    (re.compile(r"\blane_report\b", re.IGNORECASE), "that lane"),
    (re.compile(r"\bcheck_name\b", re.IGNORECASE), "that name"),
    (re.compile(r"\bsearch_names\b", re.IGNORECASE), "the shipped names"),
    (re.compile(r"\bself-check\b", re.IGNORECASE), "boot check"),
    (re.compile(r"\btaxonomy\b", re.IGNORECASE), "genre pages"),
    (re.compile(r"\bledger\b", re.IGNORECASE), "notes"),
    (re.compile(r"\bcurated\b", re.IGNORECASE), "selected"),
    (re.compile(r"\bcorpus\b", re.IGNORECASE), "catalog"),
    (re.compile(r"\boccurrences?\b", re.IGNORECASE), "times"),
    (re.compile(r"\bdeterministic\b", re.IGNORECASE), "repeatable"),
    (re.compile(r"\benvironment\b", re.IGNORECASE), "setup"),
    (re.compile(r"\brecorded totals\b", re.IGNORECASE), "counts"),
    (re.compile(r"\bsession budget\b", re.IGNORECASE), "questions left"),
    (re.compile(r"\bagent asks\b", re.IGNORECASE), "questions"),
    (re.compile(r"\bdenominator\b", re.IGNORECASE), "sample size"),
    (re.compile(r"\bsituations\b", re.IGNORECASE), "groups"),
    (re.compile(r"\bsituation\b", re.IGNORECASE), "group"),
    (re.compile(r"\btechniques\b", re.IGNORECASE), "choices"),
    (re.compile(r"\btechnique\b", re.IGNORECASE), "choice"),
    (re.compile(r"\bplaybook\b", re.IGNORECASE), "Content Index"),
    (re.compile(r"\bscorecards\b", re.IGNORECASE), "name checks"),
    (re.compile(r"\bdetectors\b", re.IGNORECASE), "checks"),
    (re.compile(r"\bdetector\b", re.IGNORECASE), "check"),
    (re.compile(r"\bresidual\b", re.IGNORECASE), "unclaimed word"),
    (re.compile(r"\blexicon\b", re.IGNORECASE), "word list"),
    (re.compile(r"\battributive\b", re.IGNORECASE), "modifier"),
    (re.compile(r"\brule ids?\b", re.IGNORECASE), "internal labels"),
    (re.compile(r"\bitem indices\b", re.IGNORECASE), "source pointers"),
    (re.compile(r"\bitem index\b", re.IGNORECASE), "source pointer"),
    (re.compile(r"\bunit-terminal\b", re.IGNORECASE), "noun last"),
    (re.compile(r"\bmoves\.json\b", re.IGNORECASE), "the wordplay notes"),
    (re.compile(r"\bconnective\b", re.IGNORECASE), "pairing word"),
    (re.compile(r"\bregister\b", re.IGNORECASE), "tone"),
    (re.compile(r"\bunit\b", re.IGNORECASE), "noun"),
    (re.compile(r"\bkind\b", re.IGNORECASE), "group"),
]


def clean_visible_text(text: str) -> str:
    cleaned = re.sub(r"\s*—\s*", ", ", text)
    for pattern, replacement in VISIBLE_TEXT_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def measure_answer(text: str) -> dict | None:
    """Ask the warm loopback service without ever holding up an answer."""
    deadline = time.monotonic() + MEASURE_TIMEOUT_SECONDS
    request = (
        json.dumps(
            {"text": text},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as conn:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            conn.settimeout(remaining)
            conn.connect((MEASURE_HOST, MEASURE_PORT))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            conn.settimeout(remaining)
            conn.sendall(request)
            conn.shutdown(socket.SHUT_WR)
            response = bytearray()
            while b"\n" not in response:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                conn.settimeout(remaining)
                chunk = conn.recv(4096)
                if not chunk:
                    break
                response.extend(chunk)
                if len(response) > MEASURE_MAX_RESPONSE_BYTES:
                    return None
        if not response:
            return None
        payload = json.loads(bytes(response).split(b"\n", 1)[0].decode("utf-8"))
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("in_band"), bool)
            or not isinstance(payload.get("misses"), list)
            or not isinstance(payload.get("measured"), list)
            or not isinstance(payload.get("skipped"), list)
        ):
            return None
        return payload
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return None


def measurement_receipt(text: str, measurement: dict | None) -> str | None:
    if measurement is None:
        return None
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text)
    if len(words) < MEASURE_MIN_WORDS:
        return None
    measured = measurement["measured"]
    skipped = measurement["skipped"]
    if len(skipped) > len(measured):
        return None
    if (
        measurement["in_band"]
        and len(measured) == MEASURE_DIMENSION_COUNT
        and not skipped
    ):
        return "re-measured · twelve dimensions in band"
    misses = []
    for miss in measurement["misses"]:
        if not isinstance(miss, dict):
            return None
        name = miss.get("dimension")
        if not isinstance(name, str):
            return None
        misses.append(name.replace("_", " "))
    if misses:
        return "re-measured · out of band on " + ", ".join(misses)
    return None


# ---------------------------------------------------------------- data + engine
# Corpus verdicts are recomputed with analyze_shelves' own primitives and compared
# to the recorded totals at boot — the same self-check the web terminal runs.

class Records:
    def __init__(self) -> None:
        self.shelves = json.loads((HERE / "shelves.json").read_text(encoding="utf-8"))
        self.moves = json.loads((HERE / "moves.json").read_text(encoding="utf-8"))
        self.scorecards = json.loads((HERE / "scorecards.json").read_text(encoding="utf-8"))
        self.playbook = json.loads((HERE / "playbook.json").read_text(encoding="utf-8"))
        self.items = self.shelves["items"]
        self.naming = [dict(i, index=n) for n, i in enumerate(self.items) if i["kind"] in NAMING_KINDS]
        self.occ: dict[str, int] = {}
        for n in self.naming:
            self.occ[n["text"]] = self.occ.get(n["text"], 0) + 1
        self.lanes = {
            "kids": (re.compile(r"\b(?:Kids?|Children|Family|Teens?|Older Kids|All Ages)\b", re.I), "kids & family"),
            "anime": (re.compile(r"\bAnime\b", re.I), "anime"),
            "horror": (re.compile(r"\b(?:Horror|Scary|Screams?|Chilling|Supernatural)\b", re.I), "horror"),
            "kdrama": (re.compile(r"\b(?:Korean|K-Dramas?)\b", re.I), "K-drama"),
        }
        self.playbook_cells = {
            (cell["situation_id"], cell["technique_id"]): cell
            for cell in self.playbook["cells"]
        }

    def rule(self, rid: str) -> dict:
        return next(r for r in self.shelves["grammar"]["rules"] if r["id"] == rid)

    def move(self, mid: str) -> dict:
        return next(m for m in self.moves["moves"] if m["id"] == mid)

    # -- per-name checks, using the crawl's definitions
    @staticmethod
    def unit_terminal(text: str):
        ms = list(A.UNIT_RE.finditer(text))
        if not ms:
            return None
        return not text[ms[-1].end():].strip(" \t\r\n.!?")

    @staticmethod
    def tv_ok(text: str):
        forms = list(re.finditer(r"\btv\b", text, re.I))
        if not forms:
            return None
        return all(m.group(0) == "TV" for m in forms)

    @staticmethod
    def connective_ok(text: str):
        has_amp, has_and = "&" in text, bool(re.search(r"\band\b", text, re.I))
        if not (has_amp or has_and):
            return None
        return has_amp and not has_and

    def self_check(self) -> bool:
        tc = sum(1 for n in self.naming if A.is_title_case_name(n["text"]))
        ut = [self.unit_terminal(n["text"]) for n in self.naming]
        tv = [self.tv_ok(n["text"]) for n in self.naming]
        cn = [self.connective_ok(n["text"]) for n in self.naming]
        def hit(vals):  # (matches, eligible)
            return sum(1 for v in vals if v is True), sum(1 for v in vals if v is not None)
        return (
            (tc, len(self.naming)) == (self.rule("title-case-discipline")["match_count"], self.rule("title-case-discipline")["denominator"])
            and hit(ut) == (self.rule("content-unit-terminal")["match_count"], self.rule("content-unit-terminal")["denominator"])
            and hit(tv) == (self.rule("tv-uppercase")["match_count"], self.rule("tv-uppercase")["denominator"])
            and hit(cn) == (self.rule("ampersand-over-and")["match_count"], self.rule("ampersand-over-and")["denominator"])
        )

    def self_check_derived(self) -> bool:
        recomputed_tone = sum(
            bool(D.tone_words(item["text"]))
            for item in self.naming
        )
        recomputed_families = sum(
            bool(D.genre_families(item["text"]))
            for item in self.naming
        )
        family_labels = sorted(
            {
                family
                for item in self.naming
                for family in D.genre_families(item["text"])
            },
            key=str.casefold,
        )
        expected_situations = {
            "kind:genre-name",
            "kind:shelf-heading",
            "kind:list-name",
            *(f"family:{family}" for family in family_labels),
        }
        recorded_situations = {
            row["id"]
            for row in self.playbook["situations"]
        }
        return (
            self.scorecards["run_date"]
            == self.playbook["run_date"]
            == self.moves["run_date"]
            == self.shelves["run"]["date"]
            and recomputed_tone
            == self.scorecards["totals"]["tone_present_occurrences"]
            and recomputed_families
            == self.scorecards["totals"]["genre_family_tagged_occurrences"]
            and expected_situations == recorded_situations
            and all(
                value["match"]
                for value in self.scorecards["totals"]["reconciliation"].values()
            )
            and all(
                cell["basis"] in {"observed", "structural"}
                and cell["band"] in {"broad", "small-sample", "near-singleton"}
                for cell in self.playbook["cells"]
            )
        )

    @staticmethod
    def title_case_fix(text: str) -> str:
        def fix_token(ti: int, token: str) -> str:
            parts = token.split("-")
            out = []
            for pi, part in enumerate(parts):
                cleaned = part.rstrip("'’+")
                if not cleaned or not any(ch.isalpha() for ch in cleaned):
                    out.append(part)
                elif cleaned.isupper():
                    out.append(part)
                elif (ti > 0 or pi > 0) and cleaned.casefold() in A.LOWERCASE_TITLE_WORDS:
                    out.append(part.lower())
                else:
                    i = next(k for k, ch in enumerate(part) if ch.isalpha())
                    out.append(part[:i] + part[i].upper() + part[i + 1:].lower())
            return "-".join(out)
        ti = -1
        def repl(m):
            nonlocal ti
            ti += 1
            return fix_token(ti, m.group(0))
        return A.WORD_RE.sub(repl, text)

    def apply_fixes(self, text: str) -> str:
        fixed = re.sub(r",\s*\band\b", " &", text, flags=re.I)
        fixed = re.sub(r"\band\b", "&", fixed, flags=re.I)
        fixed = self.title_case_fix(fixed)
        fixed = re.sub(r"\btv\b", "TV", fixed, flags=re.I)
        return re.sub(r"\s{2,}", " ", fixed).strip()

    @staticmethod
    def hyphen_tendency(text: str) -> bool:
        for token in A.WORD_RE.findall(text):
            for part in token.split("-")[1:]:
                cl = part.rstrip("'’+")
                if cl and any(c.isalpha() for c in cl) and not cl.isupper() \
                        and cl.casefold() not in A.LOWERCASE_TITLE_WORDS and cl[0].islower():
                    return True
        return False

    def check_name(self, name: str) -> dict:
        ut = self.unit_terminal(name)
        tv = self.tv_ok(name)
        cn = self.connective_ok(name)
        tc = A.is_title_case_name(name)
        mech_fail = (not tc) or tv is False or cn is False
        fixed = self.apply_fixes(name) if mech_fail else None
        detected = []
        if "?" in name:
            detected.append("question-hook")
        if D.IMPERATIVE_OPEN_RE.match(name):
            detected.append("imperative-open")
        if re.search(r"\b(?:You|Your)\b", name):
            detected.append("direct-address")
        lanes = [label for rx, label in self.lanes.values() if rx.search(name)]
        tone_words = D.tone_words(name)
        families = D.genre_families(name)
        audience = D.audience(name)
        speech = D.speech_act(name)
        rhyme = D.detect_rhyme(name)
        alliteration = D.detect_alliteration(name)
        reading_ids = []
        if tc:
            reading_ids.append("title-case-discipline")
        content = D.content_unit(name)
        if content["present"]:
            reading_ids.append("content-unit-present")
        else:
            reading_ids.append("no-unit")
        if content["position"] == "terminal":
            reading_ids.append("content-unit-terminal")
        if tv is True:
            reading_ids.append("tv-casing-holds")
        if cn is True:
            reading_ids.append("connective-ampersand")
        if tone_words:
            reading_ids.append("tone-present")
        if D.second_person(name):
            reading_ids.append("second-person")
        reading_ids.append(f"speech-act-{speech}")
        reading_ids.extend(
            f"audience-who:{who}"
            for who in audience["who"]
        )
        reading_ids.append(f"audience-position:{audience['position']}")
        if rhyme:
            reading_ids.append("wordplay-mechanical-rhyme")
        if alliteration:
            reading_ids.append("wordplay-mechanical-alliteration")
        if any(
            entry["text"].casefold() == name.casefold()
            for entry in self.moves["reads"]
        ):
            reading_ids.append("wordplay-semantic-signed")
        word_count = len(A.WORD_RE.findall(name))
        reading_ids.append(
            f"name-length:{word_count if word_count < 5 else '5plus'}"
        )
        situated = []
        for family in families:
            for reading_id in reading_ids:
                cell = self.playbook_cells.get((f"family:{family}", reading_id))
                if not cell or cell["basis"] == "structural":
                    continue
                finding = {
                    "technique": reading_label(reading_id),
                    "situation": family,
                    "count": cell["count"],
                    "denominator": cell["denominator"],
                    "band": cell["band"],
                    "examples": cell["examples"],
                }
                if "rate_pct" in cell:
                    finding["rate_pct"] = cell["rate_pct"]
                situated.append(finding)
        return {
            "name": name,
            "ships_today_occurrences": self.occ.get(name, 0),
            "title_case": "holds" if tc else "breaks",
            "tv_casing": "not applicable" if tv is None else ("holds" if tv else "breaks"),
            "unit_terminal": "no unit word — phrase register" if ut is None else ("holds" if ut else "breaks (judgment flag, not auto-fixed)"),
            "connective": "not applicable" if cn is None else ("holds" if cn else "breaks"),
            "mechanical_fix": fixed if fixed and fixed != name else None,
            "hyphen_lowercase_tendency": (not tc) and self.hyphen_tendency(name),
            "moves_detected": detected,
            "lanes": lanes,
            "tone_words": tone_words,
            "genre_families": families,
            "unrecognized_modifiers": D.unrecognized_modifiers(name),
            "audience": audience,
            "speech_act": speech,
            "wordplay_mechanical": {
                "rhyme": rhyme,
                "alliteration": alliteration,
            },
            "construction": construction_display(name),
            "situated": situated,
            "catalog_evidence": {
                "title_case": f"{self.rule('title-case-discipline')['match_count']}/{self.rule('title-case-discipline')['denominator']}",
                "tv": f"{self.rule('tv-uppercase')['match_count']}/{self.rule('tv-uppercase')['denominator']}",
                "unit_terminal": f"{self.rule('content-unit-terminal')['match_count']}/{self.rule('content-unit-terminal')['denominator']}",
                "ampersand_vs_and": f"{self.rule('ampersand-over-and')['match_count']} vs {self.rule('ampersand-over-and')['counter_example_count']}",
            },
        }

    def playbook_report(self, situation: str) -> dict:
        needle = situation.strip().casefold()
        aliases = dict(KIND_ALIASES)
        display_by_id = {
            "kind:genre-name": "genre pages",
            "kind:shelf-heading": "rows",
            "kind:list-name": "ranked lists",
        }
        for entry in self.playbook["situations"]:
            if entry["facet"] == "genre-family":
                aliases[entry["label"].casefold()] = entry["id"]
                display_by_id[entry["id"]] = entry["label"]
        situation_id = aliases.get(needle)
        if situation_id is None:
            suggestions = [
                label
                for label in aliases
                if needle and (needle in label or label in needle)
            ][:5]
            if not suggestions:
                suggestions = difflib.get_close_matches(
                    needle,
                    list(aliases),
                    n=5,
                    cutoff=0.35,
                )
            return {
                "error": f"no match for {situation!r}",
                "suggestions": suggestions,
            }
        entry = next(
            row
            for row in self.playbook["situations"]
            if row["id"] == situation_id
        )
        rows = []
        for cell in self.playbook["cells"]:
            if cell["situation_id"] != situation_id:
                continue
            if cell["basis"] == "structural":
                continue
            row = {
                "technique": reading_label(cell["technique_id"]),
                "count": cell["count"],
                "denominator": cell["denominator"],
                "band": cell["band"],
                "examples": cell["examples"],
            }
            if "rate_pct" in cell:
                row["rate_pct"] = cell["rate_pct"]
            rows.append(row)
        return {
            "situation": display_by_id[situation_id],
            "denominator_occurrences": entry["denominator_occurrences"],
            "denominator_distinct_names": entry["denominator_distinct_names"],
            "rows": rows,
        }

    def lane_report(self, lane: str) -> dict:
        if lane == "top10":
            items = [n for n in self.naming if n["kind"] == "list-name" or "Top 10" in n["text"]]
            label = "Top 10"
        elif lane in self.lanes:
            rx, label = self.lanes[lane]
            items = [n for n in self.naming if rx.search(n["text"])]
        else:
            return {"error": "unknown lane"}
        unique = sorted({n["text"] for n in items})
        occ_tc = sum(1 for n in items if A.is_title_case_name(n["text"]))
        ut = [self.unit_terminal(n["text"]) for n in items]
        out = {
            "lane": label,
            "occurrences": len(items),
            "distinct_names": len(unique),
            "title_case": f"{occ_tc}/{len(items)}",
            "unit_terminal": f"{sum(1 for v in ut if v is True)}/{sum(1 for v in ut if v is not None)}",
            "all_names": unique,
        }
        if lane == "kids":
            out["audience_leads"] = [t for t in unique if A.WORD_RE.findall(t) and self.lanes["kids"][0].search(A.WORD_RE.findall(t)[0])]
            out["audience_trails_in_for_phrase"] = [t for t in unique if re.search(r"\bfor\b", t, re.I)]
        if lane == "anime":
            out["bare_anime_as_unit"] = [t for t in unique if (m := list(A.UNIT_RE.finditer(t))) and not t[m[-1].end():].strip(" .!?") and m[-1].group(0).lower() == "anime"]
        if lane == "kdrama":
            out["fused_brand_unit"] = [t for t in unique if re.search(r"\bK-Dramas?\b", t)]
            out["spelled_origin"] = [t for t in unique if re.search(r"\bKorean\b", t, re.I)]
        if lane == "top10":
            facet = self.rule("top10-facet-order")
            out["selector_facet_pattern"] = f"[Movies|Shows] | [English|Non-English], {facet['match_count']} of {facet['denominator']}"
        return out

    def search_names(self, query: str) -> dict:
        needle = query.lower()
        hits: dict[str, dict] = {}
        for n in self.naming:
            if needle and needle in n["text"].lower():
                h = hits.setdefault(n["text"], {"name": n["text"], "occurrences": 0, "kinds": set()})
                h["occurrences"] += 1
                h["kinds"].add(n["kind"])
        out = [{**h, "kinds": sorted(h["kinds"])} for h in hits.values()]
        return {"query": query, "distinct_matches": len(out), "matches": out[:40], "truncated": len(out) > 40}

# ---------------------------------------------------------------- boot

def boot(rec: Records, plain: bool, key_present: bool) -> None:
    ident = _tty() and not plain
    cols = shutil.get_terminal_size((100, 24)).columns
    mark = _center_block(_scale_banner(BANNER) if cols >= 64 else BANNER, cols)
    card_plain = _center_block("S H E L F   T O O L", cols)
    if ident:
        try:
            from terminaltexteffects.effects import Beams, Decrypt
            from terminaltexteffects.utils.graphics import Color

            def play(effect, seconds: float) -> None:
                """Play an effect in exactly `seconds`, on our clock alone. The
                library's own fps cap sleeps ~100ms per print (a 12-second boot);
                uncapped it fast-forwards. So: uncap, materialize the frames —
                generation is cheap CPU — then print an evenly spaced subset, last
                frame guaranteed, at a fixed cadence. Same sweep, honest duration."""
                try:
                    effect.terminal_config.frame_rate = 0
                except Exception:
                    pass
                frames = list(effect)
                if not frames:
                    return
                step = 0.028
                budget = max(2, int(seconds / step))
                if len(frames) > budget:
                    picks = sorted({round(i * (len(frames) - 1) / (budget - 1)) for i in range(budget)})
                else:
                    picks = list(range(len(frames)))
                with effect.terminal_output() as term:
                    for i in picks:
                        term.print(frames[i])
                        time.sleep(step)

            print()  # a beat of air above the mark — it owns the room, not the corner
            eff = Beams(mark)
            eff.effect_config.beam_gradient_stops = (Color("ffd9d0"), Color("ff4d3f"), Color("e50914"))
            eff.effect_config.final_gradient_stops = (Color("e50914"),)
            eff.effect_config.final_gradient_frames = 2
            play(eff, 2.2)
            sub = Decrypt(_center_block("SHELF TOOL", cols))
            sub.effect_config.ciphertext_colors = (Color("4a6b5e"), Color("6e8d80"), Color("9db8ae"))
            sub.effect_config.final_gradient_stops = (Color("f2ece0"),)
            play(sub, 1.0)
        except Exception:
            print(f"\n{RED}{mark}{R}\n{BOLD}{INK}{card_plain}{R}")
    else:
        print(f"\n{RED}{mark}{R}\n{BOLD}{INK}{card_plain}{R}")
    tagline = "a shelf-naming instrument · signed-out public crawl, 26 jul 2026 · not affiliated with netflix"
    for line in textwrap.wrap(tagline, max(24, cols - 1)):
        print(f"{SAGE}{line}{R}")
    ok = rec.self_check()
    derived_ok = rec.self_check_derived()
    facts = [
        f"the catalog · {len(rec.naming):,} names pulled straight off Netflix's own shelves, four records built on them",
        f"the rhetoric · {len(rec.moves['moves'])} moves spotted in how they're named, {len(rec.moves['reads'])} wordplay reads on top",
        "recounted the whole catalog on boot; it matches what's on record" if ok
        else "recounted the whole catalog on boot and got different numbers this time; treat what follows as unverified",
        "double-checked the mood-word and genre counts myself against the shelf names. they match" if derived_ok
        else "the mood-word and genre counts don't add up right now. treat the newer answers as unverified",
        "agent · a key's here, connecting now" if key_present
        else "agent · no key yet. the computed commands work fine without one; bring your own with key sk-ant-… or export ANTHROPIC_API_KEY",
        "type help for commands",
    ]
    wrap_w = max(20, cols - 3)
    for i, fact in enumerate(facts):
        tone = SAGE if i >= len(facts) - 2 else INK
        lines = textwrap.wrap(fact, wrap_w) or [fact]
        print(f"{AMBER}{BOLD}{len(facts) - i:02d}{R} {tone}{lines[0]}{R}")
        for cont in lines[1:]:
            print(f"   {tone}{cont}{R}")
        if ident:
            time.sleep(0.11)

# ---------------------------------------------------------------- deterministic replies

def say(text: str = "", tone: str = "") -> None:
    print(f"{tone}{text}{R}" if tone else text)

def reply_check(rec: Records, name: str) -> None:
    v = rec.check_name(name)
    if v["ships_today_occurrences"]:
        n = v["ships_today_occurrences"]
        say(f"that exact name ships today: {n} time{'s' if n != 1 else ''} in the catalog", INK)
    ev = v["catalog_evidence"]
    unit_state = v["unit_terminal"]
    if unit_state.startswith("no unit word"):
        unit_state = "no closing word, reads like a phrase"
    rows = [
        ("Title Case", v["title_case"], ev["title_case"]),
        ("TV stays uppercase", v["tv_casing"], ev["tv"]),
        ("Noun closes the name", unit_state, ev["unit_terminal"]),
        ("Pairing word", v["connective"], "& over and, " + ev["ampersand_vs_and"]),
    ]
    for label, state, cite in rows:
        col = AMBER if "breaks" in state else INK
        say(f"  {label:<22} {col}{state:<38}{R} {DIM}catalog: {cite}{R}")
    say(f"  {'Construction':<22} {v['construction']}", INK)
    if v["tone_words"]:
        say(f"  {'Tone word':<22} {', '.join(v['tone_words'])}", INK)
    if v["genre_families"]:
        say(f"  {'Genre':<22} {', '.join(v['genre_families'])}", INK)
    if v["unrecognized_modifiers"]:
        say(
            f"  {'No shipped example':<22} "
            + ", ".join(v["unrecognized_modifiers"]),
            AMBER,
        )
    if v["audience"]["who"]:
        position = {
            "leads": "first",
            "trails_for_phrase": 'after "for"',
            "other": "elsewhere",
        }[v["audience"]["position"]]
        say(
            f"  {'Audience':<22} {', '.join(v['audience']['who'])}, {position}",
            INK,
        )
    if v["speech_act"] != "plain":
        act = "question" if v["speech_act"] == "question" else "invitation"
        say(f"  {'Opening':<22} {act}", INK)
    if v["wordplay_mechanical"]["rhyme"]:
        pairs = ", ".join(
            f"{left}/{right}"
            for left, right in v["wordplay_mechanical"]["rhyme"]
        )
        say(f"  {'Rhyme':<22} {pairs}", INK)
    if v["wordplay_mechanical"]["alliteration"]:
        pairs = ", ".join(
            f"{left}/{right}"
            for left, right in v["wordplay_mechanical"]["alliteration"]
        )
        say(f"  {'Opening sound':<22} {pairs}", INK)
    if v["mechanical_fix"]:
        say(f"I'd write it: {BOLD}{v['mechanical_fix']}{R}; the casing and pairing fixes are mechanical", INK)
    if v["hyphen_lowercase_tendency"]:
        say("wrinkle: lowercase after a hyphen is a recorded tendency (16 shipped names keep it); the record follows the majority for now", SAGE)
    for mid in v["moves_detected"]:
        m = rec.move(mid)
        tax = ", never in the genre list" if not m["by_kind"].get("genre-name") else ""
        say(f"that's the {m['name'].lower()} move: ships {m['occurrence_count']}x{tax}", SAGE)
    if v["lanes"]:
        say(f"lane: {', '.join(v['lanes'])}. try: lane {v['lanes'][0].split(' ')[0].lower()}", SAGE)
    for finding in v["situated"][:2]:
        family = finding["situation"].lower()
        if finding["band"] == "near-singleton":
            examples = ", ".join(f"“{text}”" for text in finding["examples"])
            detail = (
                f"{examples}; one data point, not a pattern"
                if examples
                else "no example here; this is too small to call a pattern"
            )
            say(f"  {family}: {finding['technique']}. {detail}", SAGE)
        elif finding["band"] == "small-sample":
            say(
                f"  {family}: {finding['count']} of {finding['denominator']} "
                f"{finding['technique']}; a small set where one more name could shift it",
                SAGE,
            )
        else:
            say(
                f"  {family}: {finding['count']} of {finding['denominator']} "
                f"{finding['technique']}",
                SAGE,
            )

LANE_LABEL_KEYS = {
    "audience_leads": "opens with the audience",
    "audience_trails_in_for_phrase": 'the audience trails in, after "for"',
    "bare_anime_as_unit": '"anime" standing alone at the end',
    "fused_brand_unit": "K-Dramas, fused into one word",
    "spelled_origin": '"Korean" spelled out instead',
}

def reply_lane(rec: Records, arg: str) -> None:
    key = arg.strip().lower().replace("-", "").replace(" ", "")
    key = {"kidsfamily": "kids", "family": "kids", "kdramas": "kdrama", "korean": "kdrama"}.get(key, key)
    r = rec.lane_report(key)
    if "error" in r:
        say("unknown lane. try: lane kids · lane anime · lane horror · lane k-drama · lane top10", SAGE)
        return
    say(f"{BOLD}{r['lane']}{R}: {r['occurrences']} names shipped here, {r['distinct_names']} of them distinct · Title Case {r['title_case']} · ends clean {r['unit_terminal']}", INK)
    for k in ("audience_leads", "audience_trails_in_for_phrase", "bare_anime_as_unit", "fused_brand_unit", "spelled_origin"):
        if r.get(k):
            say(f"  {LANE_LABEL_KEYS[k]}: " + ", ".join(f"“{t}”" for t in r[k][:6]), SAGE)
    if r.get("selector_facet_pattern"):
        say(f"  the toggle: {r['selector_facet_pattern']}", SAGE)
    say("  names: " + ", ".join(f"“{t}”" for t in r["all_names"][:10]) + (" …" if len(r["all_names"]) > 10 else ""), DIM)


REPORT_PRIORITY = [
    "uses a tone word",
    "opens as a question",
    "opens as an invitation",
    "speaks to the viewer",
    "drops the closing noun",
    "uses a rhyme",
    "repeats an opening sound",
    "carries a reviewed double reading",
    "puts the audience first",
    "leaves the audience unstated",
]


def reply_family(rec: Records, arg: str) -> None:
    report = rec.playbook_report(arg)
    if "error" in report:
        suggestions = report["suggestions"]
        tail = " try: " + " · ".join(suggestions) if suggestions else ""
        say(f"I couldn't match that name.{tail}", SAGE)
        return
    sample_size = report["denominator_occurrences"]
    if sample_size >= 20:
        sample_line = f"a broad set of {sample_size} shipped names"
    elif sample_size >= 5:
        sample_line = f"a small set of {sample_size} shipped names"
    else:
        sample_line = (
            f"only {sample_size} shipped name{'s' if sample_size != 1 else ''}; "
            "one data point, not a pattern"
        )
    say(f"{BOLD}{report['situation']}{R}: {sample_line}", INK)
    rows_by_label = {
        row["technique"]: row
        for row in report["rows"]
    }
    selected = [
        rows_by_label[label]
        for label in REPORT_PRIORITY
        if label in rows_by_label
        and (
            rows_by_label[label]["count"] > 0
            or label in {"opens as a question", "opens as an invitation"}
        )
    ][:2]
    if not selected:
        selected = [
            row
            for row in report["rows"]
            if row["count"] > 0
        ][:2]
    for row in selected:
        if row["band"] == "near-singleton":
            examples = ", ".join(f"“{text}”" for text in row["examples"])
            evidence = examples or "no example"
            say(f"  {row['technique']}: {evidence}; one data point, not a pattern", SAGE)
        elif row["band"] == "small-sample":
            say(
                f"  {row['count']} of {row['denominator']} {row['technique']}; "
                "small enough that one more name could shift it",
                SAGE,
            )
        else:
            rate = row["rate_pct"]
            if rate == 0:
                line = f"no name {row['technique']}"
            elif rate == 100:
                line = f"every name {row['technique']}"
            else:
                line = f"in about {rate:g}% of them, the name {row['technique']}"
            say(f"  {line}", SAGE)


def reply_moves(rec: Records) -> None:
    qh, da, nu = rec.move("question-hook"), rec.move("direct-address"), rec.move("no-unit")
    say("the style-guide shape of the tone rule is an adjective: don't be too playful unless the situation asks for it. nobody can lint an adjective. measured, the same rule has numbers:", INK)
    say(f"  question hooks   {qh['occurrence_count']:>4}x — all on rows, zero in the genre list, zero in Top 10", INK)
    say(f"  second person    {da['occurrence_count']:>4}x — all on rows", INK)
    say(f"  unit-less names  {nu['share_of_kind_pct']['shelf-heading']}% of rows · {nu['share_of_kind_pct']['genre-name']}% of the genre list · 0% of Top 10", INK)
    say("playfulness lives on the rows, about a third of the time; never in the genre list, never in ranked lists", INK)
    for read in rec.moves["reads"][:6]:
        say(f"  “{read['text']}” {AMBER}{read['read']}{R} {DIM}{read['basis']}{R}")
    say(f"wordplay is read, never detected · {len(rec.moves['reads'])} readings on record", DIM)

HELP = f"""  {AMBER}check <draft name>{R}                  hold a draft up to what's shipped; casing and pairing fixes come free
  {AMBER}lane kids|anime|horror|k-drama|top10{R}  what ships in that lane, counted live
  {AMBER}family <name>{R}                       how a genre (horror, anime, comedy...) tends to be named
  {AMBER}moves{R}                               the catalog's rhetoric, measured
  {AMBER}key sk-ant-…{R}                        connect the agent for this session (or export ANTHROPIC_API_KEY)
  {AMBER}clear{R} · {AMBER}exit{R}                        housekeeping
anything else goes to the agent once a key is connected"""

# ---------------------------------------------------------------- agent

def build_system(rec: Records) -> str:
    records = [{"id": r["id"], "kind": r["kind"], "status": r["status"], "assertion": r["assertion"]} for r in rec.shelves["derived_records"]]
    rules = [{"id": r["id"], "assertion": r["assertion"], "matches": f"{r['match_count']}/{r['denominator']}"} for r in rec.shelves["grammar"]["rules"]]
    moves = [{"id": m["id"], "name": m["name"], "occurrences": m["occurrence_count"], "by_kind": m["by_kind"]} for m in rec.moves["moves"]]
    reads = [{"name": r["text"], "read": r["read"], "basis": r["basis"]} for r in rec.moves["reads"]]
    family_count = len({
        family
        for row in rec.scorecards["rows"]
        for family in row["genre_families"]
    })
    return "\n".join([
        "You are shelf tool, the naming desk agent from Caleb Stacy's portfolio, running as a real CLI: a content-design partner for thinking through Netflix shelf, row, and genre names. You are Claude, under the user's own API key. You are not affiliated with Netflix.",
        "",
        "Your ground truth is a signed-out public crawl of Netflix's own surfaces from " + rec.shelves["run"]["date"] + f": {len(rec.naming)} naming occurrences, four derived records, six measured grammar rules, and a rhetoric layer of detected moves and wordplay readings. All of it is below or reachable through your tools. Nothing else about Netflix's naming may be asserted as fact.",
        "",
        "DERIVED RECORDS (status proposed; derived from public behavior; not Netflix policy):",
        json.dumps(records),
        "GRAMMAR RULES (occurrence counts from the crawl):",
        json.dumps(rules),
        "MOVES (rhetoric, deterministically detected; by_kind keys: shelf-heading, genre-name, list-name):",
        json.dumps(moves),
        "WORDPLAY READINGS (authored judgments with stated basis; counted as readings, not detections):",
        json.dumps(reads),
        "CONTENT INDEX HEADLINES:",
        f"The shipped names resolve into {family_count} genre families. Those families come from the names themselves. Twenty-three mood words are earlier seeds marked as such; newer entries must be found in shipped names. An unfamiliar modifier may have no precedent, and that gap must be said plainly.",
        "SAMPLE-SIZE LANGUAGE:",
        "20 or more is broad: state the rate in prose, with at most one exact number. 5 to 19 is a small set: say one more name could shift it. 1 to 4 is one data point, not a pattern: name the examples and never give a percentage. A zero-sized row is never shown.",
        "",
        "Instructions:",
        "1. Descriptive, never prescriptive. The records describe what the public catalog already does; whether any of it is ruled on inside Netflix cannot be read from out here. Never claim Netflix policy, internal knowledge, or the absence of internal documentation.",
        "2. Every count, verdict, or example you state must come from this prompt or from a tool result in this conversation. If neither can answer, say so plainly. Never invent names, numbers, or catalog contents.",
        "3. When the user proposes, revises, or asks about a specific draft name, call check_name on it before giving a verdict. For lane or audience strategy, call lane_report. For a named genre or one of the three naming surfaces, call playbook_report. To test whether a word or construction ships anywhere, call search_names. When someone asks how playful, bold, or far a group can stretch, call playbook_report for the relevant surface, then call check_name on the strongest actual example it returns before answering. Do not restate a tool result verbatim; interpret it. Even in your visible reasoning, never name these tools out loud. Think 'check that name' or 'look at that lane,' in plain words.",
        "4. Any name you author, whether a suggestion, rewrite, or invented example, must go through check_name before the user sees it and arrive with its verdict attached. Never show an unchecked name of your own. If you offer five options, check all five. If one breaks a record, say so beside it.",
        "5. Frame open questions as experiments: a record is a gate today and an A/B hypothesis the day someone wants to move it. Where the catalog ships two shapes for one job, both arms already exist.",
        "6. Subtitle and caption language is out of scope: licensed translators' creative work, a different discipline. Decline briefly if asked.",
        "7. You are writing into a terminal. Plain text only: no markdown, no headers, no bullet symbols, no emoji. Sentence case. Keep replies to a few short sentences unless the user asks for depth. No marketing register. Write it the way you'd say it across a desk: commas, periods, and the occasional semicolon carry a sentence. Never use an em dash.",
        "8. You are a design buddy at the naming desk, not the tool's documentation. Say what a viewer would actually see, in ordinary words: 'names here end on the noun, Horror Anime, Sci-Fi Anime', never 'anime is the terminal content unit'. Internal vocabulary stays internal. Never say unit, connective, register, corpus, occurrence, detector, taxonomy, rule id, item index, kind, situation, technique, playbook, scorecards, denominator, residual, lexicon, attributive, self-check, ledger, curated, deterministic, environment, recorded totals, or moves.json to the user. Translate all of it into plain talk about names. Numbers earn their place: fold them into prose, round when exactness decides nothing ('almost every name', 'two out of three'), and cite at most one or two exact counts per reply, the ones that settle something. Fractions like 411/467 never appear in conversation.",
        "9. When asked to brainstorm or generate names, lead with the names themselves, a handful, each on its own line, then one plain sentence on each about how it sits with what ships. Chat first, evidence second. An introduction is one warm sentence and an invitation, never an inventory of the data.",
        f"10. If asked what you are: shelf tool, a demo agent from Caleb Stacy's portfolio, model {AGENT_MODEL}, grounded in that public crawl, with real tools doing the counting, never a guess.",
        "11. Ground every judgment in the construction, not counts alone. Say which word does which job, where it sits, and how that position changes the reading. A noun at the end makes a category; without that noun, the name tips into mood. An ampersand couples a pair in a way 'and' does not. Counts are evidence; construction is explanation; every verdict needs both. Use plain craft words: noun, modifier, opener, coupling, beat, rhyme. Never expose the records' internal field names.",
    ])

AGENT_TOOLS = [
    {
        "name": "check_name",
        "description": "Run a draft shelf, row, or genre name against the four derived records and the move detectors. Call this whenever the user proposes, revises, or asks about a specific draft name.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "The draft name exactly as the user wrote it"}}, "required": ["name"], "additionalProperties": False},
    },
    {
        "name": "lane_report",
        "description": "Compute live statistics for one lane of the catalog: counts, rule conformance, every observed name, and the lane's own constructions. Call this when the user asks about a genre, audience, or lane strategy.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {"lane": {"type": "string", "enum": ["kids", "anime", "horror", "kdrama", "top10"]}}, "required": ["lane"], "additionalProperties": False},
    },
    {
        "name": "playbook_report",
        "description": "Look up how naming choices behave inside one group: genre pages, rows, ranked lists, or a genre family such as comedy, horror, or anime. Call this for a group-specific question, and after a name check finds a genre family.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "situation": {
                    "type": "string",
                    "description": "A group name, case-insensitive: genre pages, rows, ranked lists, or a genre family.",
                }
            },
            "required": ["situation"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_names",
        "description": "Case-insensitive substring search over the distinct public names in the catalog. Call this to check whether a word, unit, or construction actually ships before making a claim about it.",
        "strict": True,
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False},
    },
]

# Display-only phrasing for the live turn stream — never the names the API itself
# uses (those stay exactly as declared in AGENT_TOOLS above).
TOOL_VERBS = {
    "check_name": ("checking that name", "checked that name"),
    "lane_report": ("counting that lane", "counted that lane"),
    "playbook_report": ("reading that group", "read that group"),
    "search_names": ("searching the catalog", "searched the catalog"),
}

class Status:
    """The live activity line: a pulsing glyph, a verb for what is actually
    happening right now, the elapsed wall-clock, and the tool count so far.
    Every number is real — the clock is a clock, the verbs come from stream
    events, and the line erases itself the moment the answer starts. Whole
    lines of content print above it; nothing ever interleaves mid-line."""

    FRAMES = "✻✳✶✳"

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.text: str | None = None
        self.started = time.monotonic()
        self.tools = 0
        self.live = False
        self.frame = 0
        self.thread: threading.Thread | None = None

    def _render(self) -> str:
        elapsed = time.monotonic() - self.started
        glyph = self.FRAMES[self.frame % len(self.FRAMES)]
        tools = f" · {self.tools} tool call{'s' if self.tools != 1 else ''}" if self.tools else ""
        return f"{SAGE}{glyph} {self.text}… ({elapsed:.0f}s{tools}){R}"

    def _draw_locked(self) -> None:
        sys.stdout.write("\r\x1b[2K" + self._render())
        sys.stdout.flush()

    def _tick(self) -> None:
        while self.live:
            with self.lock:
                if self.live and self.text:
                    self.frame += 1
                    self._draw_locked()
            time.sleep(0.12)

    def start(self, text: str) -> None:
        with self.lock:
            self.text = text
            if self.live:
                self._draw_locked()
                return
            self.live = True
        self.thread = threading.Thread(target=self._tick, daemon=True)
        self.thread.start()

    def verb(self, text: str) -> None:
        with self.lock:
            self.text = text
            if self.live:
                self._draw_locked()

    def line(self, content: str) -> None:
        """Print one whole line above the status line."""
        with self.lock:
            sys.stdout.write("\r\x1b[2K" + content + "\n")
            if self.live and self.text:
                self._draw_locked()
            sys.stdout.flush()

    def stop(self) -> None:
        thread = None
        with self.lock:
            if self.live:
                self.live = False
                thread = self.thread
            sys.stdout.write("\r\x1b[2K")
            sys.stdout.flush()
        if thread:
            thread.join(timeout=0.5)


class Agent:
    def __init__(self, rec: Records, api_key: str, house: bool = False):
        import anthropic
        self.anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.client.models.retrieve(AGENT_MODEL)  # verifies the key, zero token spend
        self.rec = rec
        self.house = house  # True when running on the deployment's own key — caps apply
        self.system = build_system(rec)
        self.messages: list[dict] = []

    def run_tool(self, name: str, tool_input: dict) -> dict:
        if name == "check_name":
            return self.rec.check_name(str(tool_input.get("name", "")))
        if name == "lane_report":
            return self.rec.lane_report(str(tool_input.get("lane", "")))
        if name == "playbook_report":
            return self.rec.playbook_report(str(tool_input.get("situation", "")))
        if name == "search_names":
            return self.rec.search_names(str(tool_input.get("query", "")))
        return {"error": f"unknown tool {name}"}

    def turn(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        cols = shutil.get_terminal_size((100, 24)).columns
        status = Status()
        status.start("reaching the model")
        think_ms = 0.0
        out_tokens = 0
        think_buf = ""
        line_open = False  # True while an answer line is mid-stream and unterminated
        final_answer = ""

        def emit(content: str) -> None:
            """Print one whole line. If the answer has a line mid-stream, close it
            first — nothing may ever erase or splice into streamed answer text."""
            nonlocal line_open
            if line_open:
                sys.stdout.write("\n")
                line_open = False
            status.line(content)

        def flush_thinking(force: bool = False) -> None:
            """Emit finished sentences of the summarized reasoning as whole dim
            indented lines — the work sits one gutter in from the answer."""
            nonlocal think_buf
            while True:
                cut = -1
                for mark in ("\n", ". "):
                    idx = think_buf.find(mark)
                    if idx != -1:
                        cut = idx + len(mark)
                        break
                if cut == -1:
                    break
                chunk, think_buf = think_buf[:cut].strip(), think_buf[cut:]
                for wline in textwrap.wrap(clean_visible_text(chunk), max(24, cols - 4)):
                    emit(f"  {DIM}{SAGE}{wline}{R}")
            if force and think_buf.strip():
                for wline in textwrap.wrap(
                    clean_visible_text(think_buf.strip()),
                    max(24, cols - 4),
                ):
                    emit(f"  {DIM}{SAGE}{wline}{R}")
                think_buf = ""

        try:
            for _hop in range(8):
                think_start = None
                answering = False
                hop_answer: list[str] = []
                status.start("reaching the model")
                with self.client.beta.messages.stream(
                    model=AGENT_MODEL,
                    max_tokens=MAX_TOKENS,
                    thinking={"type": "adaptive", "display": "summarized"},
                    output_config={"effort": "medium"},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                    system=[{"type": "text", "text": self.system, "cache_control": {"type": "ephemeral"}}],
                    tools=AGENT_TOOLS,
                    messages=self.messages,
                ) as stream:
                    for event in stream:
                        if event.type == "content_block_start":
                            b = event.content_block
                            if b.type == "thinking":
                                if think_start is None:
                                    think_start = time.monotonic()
                                status.verb("thinking")
                            elif b.type == "tool_use":
                                if think_start is not None:
                                    think_ms += (time.monotonic() - think_start) * 1000; think_start = None
                                flush_thinking(force=True)
                                status.tools += 1
                                verb, _done = TOOL_VERBS.get(b.name, (b.name, b.name))
                                status.verb(verb)
                                emit(f"  {AMBER}→ {verb}{R}")
                            elif b.type == "text":
                                if think_start is not None:
                                    think_ms += (time.monotonic() - think_start) * 1000; think_start = None
                                flush_thinking(force=True)
                                if not answering:
                                    answering = True
                                    status.stop()
                                    sys.stdout.write(f"\n{INK}")  # one line of air: the ledger above, the answer below
                        elif event.type == "content_block_delta":
                            d = event.delta
                            if d.type == "thinking_delta" and d.thinking:
                                think_buf += d.thinking
                                flush_thinking()
                            elif d.type == "text_delta" and d.text and answering:
                                visible_delta = clean_visible_text(d.text)
                                hop_answer.append(visible_delta)
                                sys.stdout.write(visible_delta)
                                line_open = not visible_delta.endswith("\n")
                                sys.stdout.flush()
                    resp = stream.get_final_message()
                if think_start is not None:
                    think_ms += (time.monotonic() - think_start) * 1000
                usage_out = getattr(getattr(resp, "usage", None), "output_tokens", None)
                if usage_out:
                    out_tokens += usage_out
                if answering:
                    sys.stdout.write(R)
                    if line_open:
                        sys.stdout.write("\n")
                        line_open = False
                    sys.stdout.flush()
                if resp.stop_reason == "refusal":
                    status.stop()
                    cat = getattr(resp.stop_details, "category", None) if resp.stop_details else None
                    say(f"that one got declined{f' (category: {cat})' if cat else ''}; try rephrasing it", AMBER)
                    self.messages.pop()
                    return
                self.messages.append({"role": "assistant", "content": resp.content})
                tool_uses = [b for b in resp.content if b.type == "tool_use"]
                if resp.stop_reason == "tool_use" and tool_uses:
                    results = []
                    for tu in tool_uses:
                        out = self.run_tool(tu.name, tu.input)
                        _verb, done = TOOL_VERBS.get(tu.name, (tu.name, tu.name))
                        emit(f"  {SAGE}✓ {done}{R}")
                        results.append({"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(out)})
                    self.messages.append({"role": "user", "content": results})
                    continue
                if resp.stop_reason == "pause_turn":
                    continue
                final_answer = "".join(hop_answer)
                if resp.stop_reason == "max_tokens":
                    say("(that answer ran out of room and got cut short)", DIM)
                break
            status.stop()
            if line_open:
                sys.stdout.write("\n")
                line_open = False
            measurement_line = measurement_receipt(
                final_answer,
                measure_answer(final_answer),
            )
            parts = []
            if think_ms > 0:
                parts.append(f"thought for {think_ms / 1000:.1f}s")
            if status.tools:
                parts.append(f"{status.tools} tool call" + ("" if status.tools == 1 else "s"))
            if parts:
                say("closed · " + " · ".join(parts), DIM)
            if measurement_line:
                say(measurement_line, DIM)
            print()  # air before the next prompt — each exchange is its own block
        except self.anthropic.AuthenticationError:
            say("key rejected (401) — reconnect with: key sk-ant-…", AMBER)
            self.messages.pop()
            raise
        except self.anthropic.RateLimitError:
            say("rate limited by the API — wait a moment and try again", AMBER)
            self.messages.pop()
        except self.anthropic.APIConnectionError:
            say("could not reach api.anthropic.com — check the connection", AMBER)
            self.messages.pop()
        finally:
            status.stop()

# ---------------------------------------------------------------- repl

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    os.system("")  # enable ANSI on classic Windows consoles
    ap = argparse.ArgumentParser(description="shelf tool — the Netflix shelf-naming records as a CLI")
    ap.add_argument("--plain", action="store_true", help="skip the boot ident")
    args = ap.parse_args()

    rec = Records()
    agent: Agent | None = None
    agent_turns = 0
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    boot(rec, plain=args.plain, key_present=bool(env_key))
    if env_key:
        try:
            agent = Agent(rec, env_key, house=True)
            say(f"agent connected · {AGENT_MODEL} · verified against api.anthropic.com", INK)
            if MAX_AGENT_TURNS:
                say(f"{MAX_AGENT_TURNS} questions on the house this session; the commands keep going either way", DIM)
        except Exception as e:
            say(f"could not connect the agent: {e}", AMBER)

    while True:
        try:
            raw = input(f"{AMBER}> {R}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not raw:
            continue
        low = raw.lower()
        if low in ("exit", "quit"):
            return
        if low == "help":
            print(HELP)
            continue
        if low == "clear":
            os.system("cls" if os.name == "nt" else "clear")
            continue
        if low == "moves":
            reply_moves(rec)
            continue
        if low.startswith("family"):
            reply_family(rec, raw[6:] or "?")
            continue
        if low.startswith("lane"):
            reply_lane(rec, raw[4:] or "?")
            continue
        if low.startswith("check "):
            reply_check(rec, raw[6:].strip().strip('"“”'))
            continue
        if low.startswith("key"):
            arg = raw[3:].strip()
            if not arg:
                say("agent connected" if agent else "no key connected · key sk-ant-… or export ANTHROPIC_API_KEY", SAGE)
            elif arg == "clear":
                agent = None
                say("key forgotten for this session — commands still answer", INK)
            elif not arg.startswith("sk-"):
                say("that doesn't look like an Anthropic API key (they start with sk-)", AMBER)
            else:
                try:
                    agent = Agent(rec, arg)
                    say(f"agent connected · {AGENT_MODEL} · key verified, held in memory for this session only", INK)
                except Exception as e:
                    say(f"key rejected or connection failed: {e}", AMBER)
            continue
        if agent:
            if agent.house and MAX_ASK_CHARS and len(raw) > MAX_ASK_CHARS:
                say(f"that ask is over this terminal's {MAX_ASK_CHARS}-character limit — trim it down", AMBER)
                continue
            if agent.house and MAX_AGENT_TURNS and agent_turns >= MAX_AGENT_TURNS:
                say("the questions on the house are spent for this session; check, lane, and moves still answer, or connect your own key: key sk-ant-…", AMBER)
                continue
            try:
                agent.turn(raw)
                agent_turns += 1
            except Exception:
                agent = None
        else:
            say(f'that isn\'t a command, and no agent is connected. try: check "{raw[:40]}" — or connect a key (help lists everything)', SAGE)

if __name__ == "__main__":
    main()
