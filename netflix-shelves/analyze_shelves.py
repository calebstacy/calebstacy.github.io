#!/usr/bin/env python3
"""Compile the public Netflix shelf crawl into counted naming evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path

from mine_public import (
    extract_document,
    filtered_text_records,
    page_title,
    structured_data_summary,
)


HERE = Path(__file__).resolve().parent

SURFACE_NAMES = {
    "homepage": "netflix.com signed-out homepage",
    "genre": "netflix.com public genre page",
    "top10": "top10.netflix.com",
    "title": "netflix.com public title page",
}

TITLE_SHELF_LABELS = {
    "Episodes",
    "More Like This",
    "Trailers & More",
    "Trending Now",
    "You Might Also Like",
}

TITLE_UI_HEADINGS = {
    "More Details",
}

TITLE_DETAIL_LABELS = {
    "Audio",
    "Cast",
    "Genres",
    "Subtitles",
    "This movie is ...",
    "This show is ...",
    "Watch offline",
}

TOP10_LIST_H2 = re.compile(
    r"^(?:Global Top 10 |Top 10 Most Popular |Most Popular |"
    r"Explore The Most Watched )(?:Movies|Shows|Non-English Movies|"
    r"Non-English Shows)$"
)
TOP10_OVERVIEW = re.compile(r"^Top 10 .+ overview$")
TOP10_FACET = re.compile(r"^(?:Movies|Shows) \| (?:English|Non-English)$")
TOP10_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2} - \d{1,2}/\d{1,2}/\d{2}$")

WORD_RE = re.compile(
    r"[A-Za-z0-9]+(?:[’'][A-Za-z0-9]+)?\+?(?:-[A-Za-z0-9]+)*"
)
LOWERCASE_TITLE_WORDS = {
    "a", "an", "and", "as", "at", "by", "for", "from", "in", "into",
    "of", "on", "or", "the", "to", "with",
}

UNIT_TERMS = [
    "TV Shows",
    "Documentary Series",
    "TV Comedies",
    "TV Dramas",
    "Movies",
    "Shows",
    "Films",
    "Series",
    "Documentaries",
    "Comedies",
    "Dramas",
    "Thrillers",
    "Mysteries",
    "Mockumentaries",
    "Sitcoms",
    "Cartoons",
    "Flicks",
    "Anime",
    "Comedy",
    "Docs",
    "TV",
]
UNIT_RE = re.compile(
    r"\b(?:" + "|".join(
        re.escape(term) for term in sorted(UNIT_TERMS, key=len, reverse=True)
    ) + r")\b",
    re.IGNORECASE,
)

TOKEN_CLASS_SPECS = [
    (
        "audience",
        "Audience or community",
        re.compile(
            r"(?:\b(?:Kids?|Children|Family|Teens?|Young Adult|"
            r"Older Kids|All Ages|Latino|Women|Black|Beginners)\b|"
            r"\bLGBTQ\+?(?!\w))",
            re.IGNORECASE,
        ),
    ),
    (
        "origin-language",
        "Origin or language",
        re.compile(
            r"\b(?:British|Canadian|Korean|Asian|International|"
            r"Spanish-Language|English|Non-English|K-Dramas?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "tone-mood",
        "Tone or mood",
        re.compile(
            r"\b(?:Witty|Feel-good|Feel-Good|Heartfelt|Scary|Suspenseful|"
            r"Exciting|Gritty|Dark|Emotional|Psychological|Offbeat|"
            r"Irreverent|Goofy|Provocative|Soapy|Escapist|Cringe|Bold|"
            r"Brash|Relentless|Tearjerker|Steamy)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "era",
        "Era",
        re.compile(r"\b(?:Classic|Retro|Vintage|Nostalgic|\d{2}s|\d{4}s)\b", re.I),
    ),
    (
        "franchise-brand",
        "Franchise, institution, or brand",
        re.compile(r"\b(?:Netflix|SNL)\b", re.IGNORECASE),
    ),
    (
        "curation-quality",
        "Curation or quality",
        re.compile(
            r"\b(?:Best|Essential|Critically Acclaimed|Acclaimed|"
            r"Award-Winning|Award-winning|Popular|Favorites|Favorite|"
            r"Familiar|Blockbuster|Hits|Crowd Pleasers|Must-Watch|"
            r"Most Watched)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "temporal-availability",
        "Temporal or availability",
        re.compile(
            r"\b(?:Trending Now|New on Netflix|Your Next Watch|"
            r"Watch in One Weekend|Watch in One Night|30-Minute|90-Minute|"
            r"Under 90 Minutes|Bingeworthy|All Time|Right Now)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "format-unit",
        "Format or content unit",
        UNIT_RE,
    ),
]

ATTRIBUTE_RE = re.compile(
    "|".join(f"(?:{spec.pattern})" for _, _, spec in TOKEN_CLASS_SPECS[:-1]),
    re.IGNORECASE,
)


def load_log(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_items(log: dict) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    seen: set[tuple[str, str, str, str]] = set()

    def add(
        source: dict,
        source_index: int,
        text: str,
        kind: str,
        pointer: str,
    ) -> None:
        text = text.strip()
        key = (text, SURFACE_NAMES[source["source_kind"]], source["source_url"], kind)
        if not text or key in seen:
            return
        seen.add(key)
        items.append(
            {
                "text": text,
                "surface": SURFACE_NAMES[source["source_kind"]],
                "url": source["source_url"],
                "kind": kind,
                "fetched_on": source["fetched_on"],
                "source_pointer": (
                    f"fetch-log.json#/sources/{source_index}/{pointer}"
                ),
            }
        )

    for source_index, source in enumerate(log["sources"]):
        if source["status"] != "public":
            continue
        source_kind = source["source_kind"]
        records = source["text_records"]

        if source_kind == "homepage":
            for record_index, record in enumerate(records):
                if record["tag"] == "h2" and record["text"] == "Trending Now":
                    add(
                        source,
                        source_index,
                        record["text"],
                        "shelf-heading",
                        f"text_records/{record_index}",
                    )

        elif source_kind == "genre":
            genre_name_added = False
            for record_index, record in enumerate(records):
                text = record["text"]
                if record["tag"] == "h1" and not genre_name_added:
                    add(
                        source,
                        source_index,
                        text,
                        "genre-name",
                        f"text_records/{record_index}",
                    )
                    genre_name_added = True
                elif (
                    record["tag"] == "h2"
                    and text not in {
                        "A Plan To Suit Your Needs",
                        "1080p",
                        "4K + HDR",
                    }
                ):
                    add(
                        source,
                        source_index,
                        text,
                        "shelf-heading",
                        f"text_records/{record_index}",
                    )

        elif source_kind == "top10":
            selected_date_added = False
            for record_index, record in enumerate(records):
                tag = record["tag"]
                text = record["text"]
                pointer = f"text_records/{record_index}"
                if tag == "h1":
                    add(source, source_index, text, "list-name", pointer)
                elif tag in {"h2", "span"} and TOP10_LIST_H2.fullmatch(text):
                    add(source, source_index, text, "list-name", pointer)
                elif tag in {"h2", "span"} and TOP10_OVERVIEW.fullmatch(text):
                    add(source, source_index, text, "ui-label", pointer)
                elif tag == "th":
                    add(source, source_index, text, "ui-label", pointer)
                elif tag == "h3" and text in {
                    "Find a Show or Movie",
                    "Understand the Methodology",
                }:
                    add(source, source_index, text, "ui-label", pointer)
                elif tag == "button" and text in {
                    "More Details",
                    "Top 10 Search",
                }:
                    add(source, source_index, text, "ui-label", pointer)
                elif tag == "span" and (
                    text == "Global" or TOP10_FACET.fullmatch(text)
                ):
                    add(
                        source,
                        source_index,
                        text,
                        "list-name" if TOP10_FACET.fullmatch(text) else "ui-label",
                        pointer,
                    )
                elif tag == "span" and text == "All Time":
                    add(source, source_index, text, "ui-label", pointer)
                elif (
                    tag == "span"
                    and TOP10_DATE.fullmatch(text)
                    and not selected_date_added
                ):
                    add(source, source_index, text, "ui-label", pointer)
                    selected_date_added = True
            for aria_index, entry in enumerate(source.get("aria_labels", [])):
                if entry["text"] == "Downloads":
                    add(
                        source,
                        source_index,
                        entry["text"],
                        "ui-label",
                        f"aria_labels/{aria_index}",
                    )

        elif source_kind == "title":
            title_name = next(
                (
                    record["text"]
                    for record in records
                    if record["tag"] == "h1"
                ),
                None,
            )
            for record_index, record in enumerate(records):
                tag = record["tag"]
                text = record["text"]
                pointer = f"text_records/{record_index}"
                if tag == "h2" and text in TITLE_SHELF_LABELS:
                    add(source, source_index, text, "shelf-heading", pointer)
                elif tag == "h2" and text in TITLE_UI_HEADINGS:
                    add(source, source_index, text, "ui-label", pointer)
                elif tag == "h4" and text in TITLE_DETAIL_LABELS:
                    add(source, source_index, text, "ui-label", pointer)
                elif tag == "label" and text == "Select Season":
                    add(source, source_index, text, "ui-label", pointer)
                elif (
                    tag in {"div", "p", "span"}
                    and text != title_name
                    and (
                        re.fullmatch(r"(?:TV-[A-Z0-9]+|G|PG|PG-13|R|NC-17)", text)
                        or re.fullmatch(r"\d+ Seasons?", text)
                    )
                ):
                    add(source, source_index, text, "ui-label", pointer)
            for data_index, data in enumerate(source.get("structured_data", [])):
                rating = data.get("contentRating")
                if rating:
                    add(
                        source,
                        source_index,
                        str(rating),
                        "ui-label",
                        f"structured_data/{data_index}/contentRating",
                    )

    return items


def word_tokens(text: str) -> list[str]:
    return WORD_RE.findall(text)


def is_title_case_name(text: str) -> bool:
    tokens = word_tokens(text)
    if not tokens:
        return False
    for token_index, token in enumerate(tokens):
        for part_index, part in enumerate(token.split("-")):
            cleaned = part.rstrip("'’+")
            if not cleaned or not any(char.isalpha() for char in cleaned):
                continue
            if cleaned.isupper():
                continue
            lowered = cleaned.casefold()
            if (
                (token_index > 0 or part_index > 0)
                and lowered in LOWERCASE_TITLE_WORDS
            ):
                continue
            if not cleaned[0].isupper():
                return False
    return True


def rate(matches: int, denominator: int) -> float:
    return round(100 * matches / denominator, 1) if denominator else 0.0


def make_rule(
    rule_id: str,
    dimension: str,
    assertion: str,
    eligible: list[int],
    matches: list[int],
    items: list[dict[str, object]],
    note: str,
) -> dict[str, object]:
    match_set = set(matches)
    counter = [index for index in eligible if index not in match_set]
    return {
        "id": rule_id,
        "dimension": dimension,
        "assertion": assertion,
        "denominator": len(eligible),
        "match_count": len(matches),
        "match_pct": rate(len(matches), len(eligible)),
        "counter_example_count": len(counter),
        "match_item_indices": matches,
        "counter_example_item_indices": counter,
        "match_examples": [items[index]["text"] for index in matches[:5]],
        "counter_examples": [items[index]["text"] for index in counter[:10]],
        "note": note,
    }


def induce_grammar(items: list[dict[str, object]]) -> dict[str, object]:
    naming_indices = [
        index
        for index, item in enumerate(items)
        if item["kind"] in {"genre-name", "shelf-heading", "list-name"}
    ]
    naming_items = [items[index] for index in naming_indices]

    title_case_matches = [
        index for index in naming_indices if is_title_case_name(items[index]["text"])
    ]

    unit_eligible: list[int] = []
    unit_terminal_matches: list[int] = []
    modifier_unit_eligible: list[int] = []
    modifier_before_matches: list[int] = []
    tv_eligible: list[int] = []
    tv_upper_matches: list[int] = []
    connective_eligible: list[int] = []
    ampersand_matches: list[int] = []
    facet_eligible: list[int] = []
    facet_matches: list[int] = []

    for index in naming_indices:
        text = items[index]["text"]
        unit_matches = list(UNIT_RE.finditer(text))
        if unit_matches:
            unit_eligible.append(index)
            last_unit = unit_matches[-1]
            trailing = text[last_unit.end():].strip(" \t\r\n.!?")
            if not trailing:
                unit_terminal_matches.append(index)
            attribute_matches = list(ATTRIBUTE_RE.finditer(text))
            if attribute_matches:
                modifier_unit_eligible.append(index)
                if all(match.start() < last_unit.start() for match in attribute_matches):
                    modifier_before_matches.append(index)

        tv_forms = list(re.finditer(r"\btv\b", text, flags=re.IGNORECASE))
        if tv_forms:
            tv_eligible.append(index)
            if all(match.group(0) == "TV" for match in tv_forms):
                tv_upper_matches.append(index)

        has_ampersand = "&" in text
        has_and = bool(re.search(r"\band\b", text, flags=re.IGNORECASE))
        if has_ampersand or has_and:
            connective_eligible.append(index)
            if has_ampersand and not has_and:
                ampersand_matches.append(index)

        if "|" in text:
            facet_eligible.append(index)
            if TOP10_FACET.fullmatch(text):
                facet_matches.append(index)

    token_classes = []
    for class_id, name, pattern in TOKEN_CLASS_SPECS:
        class_indices: list[int] = []
        fills: Counter[str] = Counter()
        for index in naming_indices:
            matches = list(pattern.finditer(items[index]["text"]))
            if matches:
                class_indices.append(index)
                fills.update(match.group(0) for match in matches)
        token_classes.append(
            {
                "id": class_id,
                "name": name,
                "occurrence_item_count": len(class_indices),
                "unique_name_count": len(
                    {items[index]["text"] for index in class_indices}
                ),
                "item_indices": class_indices,
                "most_common_fills": [
                    {"text": text, "count": count}
                    for text, count in fills.most_common(12)
                ],
                "note": (
                    "Classes are lexicon matches and may overlap; counts are naming-item "
                    "occurrences, not mutually exclusive classifications."
                ),
            }
        )

    rules = [
        make_rule(
            "title-case-discipline",
            "casing",
            "Genre, shelf, and list names use Title Case, allowing lowercase short connectives.",
            naming_indices,
            title_case_matches,
            items,
            "Every genre-name, shelf-heading, and list-name occurrence is in the denominator.",
        ),
        make_rule(
            "content-unit-terminal",
            "ordering",
            "When a recognized content-unit token appears, it closes the name.",
            unit_eligible,
            unit_terminal_matches,
            items,
            (
                "Counter-examples include Top 10 sentence frames and facet labels, where "
                "a locale, time, or platform clause follows the unit."
            ),
        ),
        make_rule(
            "attribute-before-unit",
            "ordering",
            "Audience, origin, tone, era, brand, curation, and temporal modifiers precede the final content unit.",
            modifier_unit_eligible,
            modifier_before_matches,
            items,
            (
                "Eligible names contain at least one lexicon-matched modifier and one "
                "recognized content unit."
            ),
        ),
        make_rule(
            "tv-uppercase",
            "casing",
            "The initialism TV is always rendered in all caps.",
            tv_eligible,
            tv_upper_matches,
            items,
            "The denominator is every naming item containing TV in any casing.",
        ),
        make_rule(
            "top10-facet-order",
            "ordering",
            "Top 10 selector labels use content unit, a vertical bar, then language: [Movies|Shows] | [English|Non-English].",
            facet_eligible,
            facet_matches,
            items,
            "The denominator is every naming item containing a vertical bar.",
        ),
        make_rule(
            "ampersand-over-and",
            "connective",
            "Names with a coordinating connective use & rather than the word and.",
            connective_eligible,
            ampersand_matches,
            items,
            (
                "A name containing both forms would count as a counter-example; none is "
                "silently removed."
            ),
        ),
    ]

    connective_by_surface: dict[str, dict[str, int]] = {}
    for surface in sorted({item["surface"] for item in naming_items}):
        surface_texts = [
            item["text"] for item in naming_items if item["surface"] == surface
        ]
        connective_by_surface[surface] = {
            "ampersand": sum("&" in text for text in surface_texts),
            "and": sum(
                bool(re.search(r"\band\b", text, re.IGNORECASE))
                for text in surface_texts
            ),
            "both": sum(
                "&" in text
                and bool(re.search(r"\band\b", text, re.IGNORECASE))
                for text in surface_texts
            ),
        }

    occurrence_lengths = [len(word_tokens(item["text"])) for item in naming_items]
    unique_names = sorted({item["text"] for item in naming_items})
    unique_lengths = [len(word_tokens(text)) for text in unique_names]

    def length_block(lengths: list[int]) -> dict[str, object]:
        counts = Counter(lengths)
        return {
            "n": len(lengths),
            "min": min(lengths),
            "median": statistics.median(lengths),
            "mean": round(statistics.mean(lengths), 2),
            "max": max(lengths),
            "exact_word_counts": {
                str(length): counts[length] for length in sorted(counts)
            },
            "bins": {
                "1_word": sum(length == 1 for length in lengths),
                "2_words": sum(length == 2 for length in lengths),
                "3_words": sum(length == 3 for length in lengths),
                "4_words": sum(length == 4 for length in lengths),
                "5_plus_words": sum(length >= 5 for length in lengths),
            },
        }

    return {
        "corpus": {
            "item_occurrences": len(naming_indices),
            "unique_names": len(unique_names),
            "counts_by_kind": dict(
                Counter(items[index]["kind"] for index in naming_indices)
            ),
            "item_indices": naming_indices,
            "note": (
                "Occurrence counts retain the same heading on different public URLs; "
                "duplicate tags on one URL are collapsed."
            ),
        },
        "token_classes": token_classes,
        "rules": rules,
        "casing": {
            "title_case_matches": len(title_case_matches),
            "title_case_counter_examples": len(naming_indices) - len(title_case_matches),
            "tv_occurrence_items": len(tv_eligible),
            "tv_non_uppercase_items": len(tv_eligible) - len(tv_upper_matches),
        },
        "connectives": {
            "ampersand_item_count": sum("&" in item["text"] for item in naming_items),
            "and_item_count": sum(
                bool(re.search(r"\band\b", item["text"], re.IGNORECASE))
                for item in naming_items
            ),
            "by_surface": connective_by_surface,
        },
        "length_distribution": {
            "occurrences": length_block(occurrence_lengths),
            "unique_names": length_block(unique_lengths),
        },
    }


def terminology_counts(items: list[dict[str, object]]) -> dict[str, object]:
    naming_indices = [
        index
        for index, item in enumerate(items)
        if item["kind"] in {"genre-name", "shelf-heading", "list-name"}
    ]
    term_patterns = {
        "TV Shows": re.compile(r"\bTV Shows\b", re.IGNORECASE),
        "Movies": re.compile(r"\bMovies\b", re.IGNORECASE),
        "Series": re.compile(r"\bSeries\b", re.IGNORECASE),
        "Films": re.compile(r"\bFilms\b", re.IGNORECASE),
        "Shows (bare)": re.compile(r"(?<!TV )\bShows\b", re.IGNORECASE),
    }
    terms: dict[str, dict[str, object]] = {}
    surfaces = sorted({items[index]["surface"] for index in naming_indices})
    for term, pattern in term_patterns.items():
        total = 0
        by_surface = {surface: 0 for surface in surfaces}
        item_indices: list[int] = []
        for index in naming_indices:
            occurrences = len(pattern.findall(items[index]["text"]))
            if not occurrences:
                continue
            total += occurrences
            by_surface[items[index]["surface"]] += occurrences
            item_indices.append(index)
        terms[term] = {
            "total_occurrences": total,
            "by_surface": by_surface,
            "item_indices": item_indices,
        }

    movie_show = (
        terms["Movies"]["total_occurrences"]
        + terms["TV Shows"]["total_occurrences"]
        + terms["Shows (bare)"]["total_occurrences"]
    )
    series_film = (
        terms["Series"]["total_occurrences"]
        + terms["Films"]["total_occurrences"]
    )
    return {
        "scope": (
            "Exact whole-term occurrences in genre-name, shelf-heading, and "
            "list-name items; UI labels and title names are excluded."
        ),
        "terms": terms,
        "families": {
            "movie_show": movie_show,
            "series_film": series_film,
            "movie_show_to_series_film_ratio": (
                round(movie_show / series_film, 2) if series_film else None
            ),
        },
        "verdict": (
            f"The public product naming corpus uses the movie/show family "
            f"{movie_show} times (Movies + TV Shows + bare Shows) versus "
            f"{series_film} uses of Series + Films."
        ),
    }


def surface_counts(
    items: list[dict[str, object]],
    indices: list[int],
) -> dict[str, int]:
    counts = Counter(items[index]["surface"] for index in indices)
    return {surface: counts[surface] for surface in sorted(counts)}


def item_pointers(indices: list[int], limit: int = 20) -> list[str]:
    return [f"#/items/{index}" for index in indices[:limit]]


def build_derived_records(
    items: list[dict[str, object]],
    grammar: dict[str, object],
    terminology: dict[str, object],
    run_date: str,
) -> list[dict[str, object]]:
    rules = {rule["id"]: rule for rule in grammar["rules"]}
    terms = terminology["terms"]

    content_indices = sorted(
        {
            index
            for term in ["TV Shows", "Movies", "Shows (bare)", "Series", "Films"]
            for index in terms[term]["item_indices"]
        }
    )
    content_variant_specs = [
        ("TV Shows", "identical"),
        ("Movies", "identical"),
        ("Shows (bare)", "identical"),
        ("Series", "contrast"),
        ("Films", "contrast"),
    ]
    content_variants = []
    for form, relation in content_variant_specs:
        entry = terms[form]
        content_variants.append(
            {
                "form": form,
                "counts_by_surface": {
                    surface: count
                    for surface, count in entry["by_surface"].items()
                    if count
                },
                "total": entry["total_occurrences"],
                "relation_to_canonical": relation,
            }
        )

    title_rule = rules["title-case-discipline"]
    title_counter_indices = title_rule["counter_example_item_indices"]
    title_match_indices = title_rule["match_item_indices"]

    tv_rule = rules["tv-uppercase"]
    connective_rule = rules["ampersand-over-and"]

    return [
        {
            "id": "term.content-unit.movie-show.public-product.v1",
            "version": 1,
            "kind": "extension",
            "status": "proposed",
            "concept": (
                "the content-unit family used in Netflix's public product "
                "taxonomy, shelves, and Top 10 list names"
            ),
            "canonical": "movie / show",
            "register": [
                "netflix.com public genre page",
                "top10.netflix.com",
            ],
            "owner": "product terminology owner",
            "variants": content_variants,
            "assertion": (
                f"Public product names use the movie/show family "
                f"{terminology['families']['movie_show']} times versus "
                f"{terminology['families']['series_film']} uses of the "
                f"series/film family in this crawl; this record proposes "
                f"movie/show as the product-register extension."
            ),
            "evidence": {
                "source_file": "plays/netflix-shelves/shelves.json",
                "count_pointer": "#/terminology",
                "item_pointers": item_pointers(content_indices, 30),
                "confidence": "clean",
                "confidence_note": (
                    "Counts are exact whole-term matches across every naming item "
                    "in the signed-out crawl; repeated headings on different source "
                    "URLs remain separate occurrences."
                ),
            },
            "precedence": {
                "supersedes": None,
                "superseded_by": None,
                "competing_proposal": None,
            },
            "created": run_date,
            "machine_route": (
                "variant-flagging, not yet active: if adopted for this register, "
                "flag Series or Films where a product taxonomy/list content unit is "
                "intended; do not apply to editorial prose."
            ),
            "localization_note": (
                "These are public product taxonomy labels, so locale-specific "
                "translations should preserve the content-type distinction while "
                "allowing the target language's normal number and compounding."
            ),
        },
        {
            "id": "term.naming-case.title-case.public-product.v1",
            "version": 1,
            "kind": "extension",
            "status": "proposed",
            "concept": "casing of public genre, shelf, and list names",
            "canonical": "Title Case",
            "register": [
                "netflix.com signed-out homepage",
                "netflix.com public genre page",
                "top10.netflix.com",
                "netflix.com public title page",
            ],
            "owner": "product content design lead",
            "variants": [
                {
                    "form": "Title Case",
                    "counts_by_surface": surface_counts(items, title_match_indices),
                    "total": title_rule["match_count"],
                    "relation_to_canonical": "identical",
                },
                {
                    "form": "non-Title-Case form",
                    "counts_by_surface": surface_counts(items, title_counter_indices),
                    "total": title_rule["counter_example_count"],
                    "relation_to_canonical": "drift",
                },
            ],
            "assertion": (
                f"{title_rule['match_count']} of {title_rule['denominator']} "
                f"public naming occurrences use Title Case; "
                f"{title_rule['counter_example_count']} counter-examples are retained "
                f"rather than normalized away."
            ),
            "evidence": {
                "source_file": "plays/netflix-shelves/shelves.json",
                "count_pointer": "#/grammar/rules/0",
                "item_pointers": (
                    item_pointers(title_match_indices, 12)
                    + item_pointers(title_counter_indices, 20)
                ),
                "confidence": "clean",
                "confidence_note": (
                    "The denominator is the complete naming corpus; UI labels and "
                    "title names are excluded before casing is tested."
                ),
            },
            "precedence": {
                "supersedes": None,
                "superseded_by": None,
                "competing_proposal": None,
            },
            "created": run_date,
            "machine_route": (
                "casing check, not yet active: if adopted, flag non-Title-Case "
                "genre, shelf, or list names for review rather than auto-fixing "
                "the observed hyphenated counter-examples."
            ),
            "localization_note": (
                "Title Case is English-specific and should not be exported as a "
                "locale-independent capitalization rule."
            ),
        },
        {
            "id": "term.initialism.tv.public-product.v1",
            "version": 1,
            "kind": "extension",
            "status": "proposed",
            "concept": "casing of the TV initialism in public product names",
            "canonical": "TV",
            "register": "netflix.com public genre page",
            "owner": "product terminology owner",
            "variants": [
                {
                    "form": "TV",
                    "counts_by_surface": surface_counts(
                        items, tv_rule["match_item_indices"]
                    ),
                    "total": tv_rule["match_count"],
                    "relation_to_canonical": "identical",
                },
                {
                    "form": "Tv / tv",
                    "counts_by_surface": {},
                    "total": tv_rule["counter_example_count"],
                    "relation_to_canonical": "drift",
                },
            ],
            "assertion": (
                f"All {tv_rule['denominator']} naming items containing the "
                f"initialism render it as TV; no Tv or tv counter-example was "
                f"observed."
            ),
            "evidence": {
                "source_file": "plays/netflix-shelves/shelves.json",
                "count_pointer": "#/grammar/rules/3",
                "item_pointers": item_pointers(tv_rule["match_item_indices"], 30),
                "confidence": "clean",
                "confidence_note": (
                    "The casing check scans every naming item case-insensitively, "
                    "then tests the original matched form."
                ),
            },
            "precedence": {
                "supersedes": None,
                "superseded_by": None,
                "competing_proposal": None,
            },
            "created": run_date,
            "machine_route": (
                "exact-match casing check, not yet active: if adopted, flag Tv or "
                "tv in this public product naming register."
            ),
            "localization_note": (
                "The Latin-script initialism may remain TV in many locales, but a "
                "locale owner should decide whether transliteration or a local term "
                "takes precedence."
            ),
        },
        {
            "id": "term.naming-connective.ampersand.public-product.v1",
            "version": 1,
            "kind": "extension",
            "status": "proposed",
            "concept": "coordinating connective in public genre and shelf names",
            "canonical": "&",
            "register": "netflix.com public genre page",
            "owner": "product content design lead",
            "variants": [
                {
                    "form": "&",
                    "counts_by_surface": surface_counts(
                        items, connective_rule["match_item_indices"]
                    ),
                    "total": connective_rule["match_count"],
                    "relation_to_canonical": "identical",
                },
                {
                    "form": "and",
                    "counts_by_surface": surface_counts(
                        items, connective_rule["counter_example_item_indices"]
                    ),
                    "total": connective_rule["counter_example_count"],
                    "relation_to_canonical": "drift",
                },
            ],
            "assertion": (
                f"Of {connective_rule['denominator']} public naming occurrences "
                f"with a coordinating connective, {connective_rule['match_count']} "
                f"use & and {connective_rule['counter_example_count']} use and."
            ),
            "evidence": {
                "source_file": "plays/netflix-shelves/shelves.json",
                "count_pointer": "#/grammar/rules/5",
                "item_pointers": (
                    item_pointers(connective_rule["match_item_indices"], 20)
                    + item_pointers(
                        connective_rule["counter_example_item_indices"], 20
                    )
                ),
                "confidence": "clean",
                "confidence_note": (
                    "Every name containing either connective is counted; names with "
                    "both would be counter-examples."
                ),
            },
            "precedence": {
                "supersedes": None,
                "superseded_by": None,
                "competing_proposal": None,
            },
            "created": run_date,
            "machine_route": (
                "connective review, not yet active: if adopted, flag and in short "
                "public genre/shelf names while retaining a human exception path."
            ),
            "localization_note": (
                "The preference is English-surface punctuation, not a universal "
                "localization rule; translated conjunctions must follow locale norms."
            ),
        },
    ]


def prune_fetch_log(log: dict) -> dict:
    for source in log["sources"]:
        source["catalog_title_id_count"] = len(source.get("title_ids", []))
        source.pop("title_ids", None)
        source["links"] = []
        source["aria_labels"] = [
            entry
            for entry in source.get("aria_labels", [])
            if source["source_kind"] == "top10" and entry["text"] == "Downloads"
        ]
        source["meta"] = {
            key: value
            for key, value in source.get("meta", {}).items()
            if key in {"description", "og:title", "og:description"}
        }

        kept: list[dict[str, str]] = []
        selected_date_kept = False
        for record in source.get("text_records", []):
            tag = record["tag"]
            text = record["text"]
            kind = source["source_kind"]
            keep = False
            if kind == "homepage":
                keep = tag in {"title", "h1"} or (
                    tag == "h2" and text == "Trending Now"
                )
            elif kind == "genre":
                keep = tag in {"title", "h1", "h2"}
            elif kind == "top10":
                keep = (
                    tag == "h1"
                    or (
                        tag in {"h2", "span"}
                        and (
                            TOP10_LIST_H2.fullmatch(text)
                            or TOP10_OVERVIEW.fullmatch(text)
                        )
                    )
                    or tag == "th"
                    or (
                        tag == "h3"
                        and text in {
                            "Find a Show or Movie",
                            "Understand the Methodology",
                        }
                    )
                    or (
                        tag == "button"
                        and text in {"More Details", "Top 10 Search"}
                    )
                    or (
                        tag == "span"
                        and (
                            text in {"Global", "All Time"}
                            or TOP10_FACET.fullmatch(text)
                        )
                    )
                )
                if tag == "span" and TOP10_DATE.fullmatch(text):
                    keep = not selected_date_kept
                    selected_date_kept = True
            elif kind == "title":
                keep = (
                    tag == "h1"
                    or (tag == "h2" and text in TITLE_SHELF_LABELS | TITLE_UI_HEADINGS)
                    or (tag == "h4" and text in TITLE_DETAIL_LABELS)
                    or (tag == "label" and text == "Select Season")
                )
            if keep:
                kept.append(record)
        source["text_records"] = kept
    log["run"]["sampled_title_source_urls"] = [
        source["source_url"]
        for source in log["sources"]
        if source["source_kind"] == "title"
    ]
    return log


def notes_markdown(payload: dict[str, object]) -> str:
    run = payload["run"]
    grammar = payload["grammar"]
    terminology = payload["terminology"]
    item_counts = Counter(item["kind"] for item in payload["items"])
    rules = {rule["id"]: rule for rule in grammar["rules"]}
    title_rule = rules["title-case-discipline"]
    unit_rule = rules["content-unit-terminal"]
    tv_rule = rules["tv-uppercase"]
    connective_rule = rules["ampersand-over-and"]
    length = grammar["length_distribution"]["occurrences"]
    one_to_three = (
        length["exact_word_counts"].get("1", 0)
        + length["exact_word_counts"].get("2", 0)
        + length["exact_word_counts"].get("3", 0)
    )
    one_to_three_pct = rate(one_to_three, length["n"])
    terms = terminology["terms"]

    return f"""# Netflix public shelf and genre naming

Run date: {run['date']}.

## Method

This is a signed-out, GET-only crawl. It used a normal Chrome browser user agent, no login, no cookie jar, no interaction, one request at a time, and a deterministic 2–4 second delay between actual HTTP requests. Redirects were followed one hop at a time only when the destination remained public; a redirect to login, sign-in, account, or sign-up was logged and stopped before the destination was requested. The hard cap was 390 actual requests. Raw HTML stayed outside the repository; `fetch-log.json` contains request metadata and the extracted text needed to audit `shelves.json`.

The run made {run['fetch_count']} actual GETs for {run['source_url_count']} source URLs. It classified {run['public_source_count']} sources as public, {run['out_of_bounds_count']} as out of bounds, and {run['not_public_count']} as non-contentful or otherwise not public enough for this corpus. The item corpus contains {len(payload['items'])} occurrences: {item_counts['genre-name']} genre names, {item_counts['shelf-heading']} shelf headings, {item_counts['list-name']} list names, and {item_counts['ui-label']} UI labels. The same heading on two different URLs remains two occurrences; duplicate tags on one URL are collapsed.

## What was public, and what was walled

- The signed-out homepage was public and exposed the row heading `Trending Now`.
- All seven tested `top10.netflix.com` routes remained public. They now redirect to public Netflix Tudum Top 10 pages; the redirect chain is preserved in `fetch-log.json`.
- Of {run['genre_probe_count']} genre IDs probed, {run['public_genre_count']} served both a rendered genre H1 and a full signed-out catalog. {run['walled_genre_count']} redirected to `login?nextpage=...`; the crawler did not request the login destination. The remaining {run['not_public_genre_count']} returned no full catalog, no genre display heading, or one HTTP 503.
- All {run['title_sample_count']} sampled public title URLs served title-specific content without authentication. The sample was selected round-robin across successful genre pages, preferring IDs seen on fewer genre pages.

That split matters: “Netflix genre code” is not one uniformly public surface. In this run, {run['public_genre_count']} of {run['genre_probe_count']} probed IDs were genuinely public and full, while {run['walled_genre_count']} were explicitly account-walled.

## Grammar

The naming grammar covers genre names, shelf headings, and Top 10 list names; UI labels and actual title names are excluded.

- **Case:** {title_rule['match_count']} of {title_rule['denominator']} naming occurrences ({title_rule['match_pct']}%) use Title Case. The {title_rule['counter_example_count']} retained counter-examples are concentrated in hyphenated forms such as `Feel-good Movies`, `Award-winning Documentaries`, and `Latino Stand-up Comedy`.
- **Unit position:** among {unit_rule['denominator']} names containing a recognized content-unit token, {unit_rule['match_count']} ({unit_rule['match_pct']}%) end on that unit. The {unit_rule['counter_example_count']} counter-examples are not random drift: Top 10 uses longer sentence frames (`Top 10 Movies on Netflix Right Now`) and selector facets put language after the unit (`Movies | English`).
- **Initialism:** all {tv_rule['denominator']} naming items containing `TV` render it in all caps; zero `Tv` or `tv` forms were observed.
- **Connective:** {connective_rule['match_count']} of {connective_rule['denominator']} names with a coordinating connective use `&`; {connective_rule['counter_example_count']} use `and`.
- **Length:** the occurrence corpus has a median of {length['median']} words and a mean of {length['mean']}. {one_to_three} of {length['n']} names ({one_to_three_pct}%) are one to three words.

The productive default is short and compositional: an optional audience/origin/tone/era/curation modifier precedes a content-unit head (`British TV Dramas`, `Gritty Movies`, `Classic Comedy Films`). Top 10 is a distinct subgrammar: list selectors are exactly `[Movies|Shows] | [English|Non-English]` in {rules['top10-facet-order']['match_count']} of {rules['top10-facet-order']['denominator']} occurrences, while page titles expand into a sentence-like availability frame.

## Product content-unit terminology

Across naming items, exact whole-term counts are:

- `Movies`: {terms['Movies']['total_occurrences']}
- `TV Shows`: {terms['TV Shows']['total_occurrences']}
- bare `Shows`: {terms['Shows (bare)']['total_occurrences']}
- `Series`: {terms['Series']['total_occurrences']}
- `Films`: {terms['Films']['total_occurrences']}

That is {terminology['families']['movie_show']} uses of the movie/show family against {terminology['families']['series_film']} uses of series/film, a {terminology['families']['movie_show_to_series_film_ratio']}:1 ratio. The product-side verdict is therefore clear: public product taxonomy and list naming align with **movie/show**, not Tudum editorial’s series/film pairing. `Series` and `Films` are real minority forms inside the genre system, not zero-count straw men.

## Three strongest observations

1. **Publicness is a content distinction.** The broad/top-level and selected SEO genres expose full signed-out catalogs, while {run['walled_genre_count']} probed IDs redirect directly to login. A genre-code list cannot be treated as a public corpus without testing every URL.
2. **The product resolves the existing content-unit fork toward movie/show.** The observed ratio is {terminology['families']['movie_show']} to {terminology['families']['series_film']}; Top 10 reinforces it with bare `Shows`, while the public genre surface supplies all observed `Series` and `Films` minority uses.
3. **The grammar is compact but not mechanically uniform.** Title Case ({title_rule['match_count']}/{title_rule['denominator']}), terminal content units ({unit_rule['match_count']}/{unit_rule['denominator']}), and `TV` casing ({tv_rule['match_count']}/{tv_rule['denominator']}) are strong rules; the recorded counter-examples reveal named subgrammars rather than being discarded as noise.

One title-page UI oddity is worth preserving without turning it into a naming rule: all {run['title_sample_count']} sampled pages—including movies—rendered the metadata label `This show is ...`.
"""


def write_outputs(log: dict, output: Path, notes: Path) -> dict[str, object]:
    items = extract_items(log)
    grammar = induce_grammar(items)
    terminology = terminology_counts(items)
    status_counts = Counter(source["status"] for source in log["sources"])
    genre_sources = [
        source for source in log["sources"] if source["source_kind"] == "genre"
    ]
    run = {
        "date": log["run"]["date"],
        "fetch_count": log["run"]["fetch_count"],
        "source_url_count": log["run"]["source_url_count"],
        "public_source_count": status_counts["public"],
        "out_of_bounds_count": status_counts["out_of_bounds"],
        "not_public_count": status_counts["not_public"],
        "error_count": status_counts["error"],
        "genre_probe_count": len(genre_sources),
        "public_genre_count": sum(
            source["status"] == "public" for source in genre_sources
        ),
        "walled_genre_count": sum(
            source["status"] == "out_of_bounds" for source in genre_sources
        ),
        "not_public_genre_count": sum(
            source["status"] == "not_public" for source in genre_sources
        ),
        "title_sample_count": sum(
            source["source_kind"] == "title" for source in log["sources"]
        ),
        "method": log["run"]["method"],
    }
    payload = {
        "run": run,
        "items": items,
        "grammar": grammar,
        "terminology": terminology,
        "derived_records": build_derived_records(
            items, grammar, terminology, run["date"]
        ),
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    notes.write_text(notes_markdown(payload), encoding="utf-8")
    return payload


def inspect_items(log: dict) -> None:
    items = extract_items(log)
    print("ITEM COUNTS", dict(Counter(item["kind"] for item in items)))
    print("SURFACE COUNTS", dict(Counter(item["surface"] for item in items)))
    print("UNIQUE TEXT", len({item["text"] for item in items}), "TOTAL", len(items))
    for kind in ["genre-name", "shelf-heading", "list-name", "ui-label"]:
        print(f"\n{kind.upper()}")
        counts = Counter(
            item["text"] for item in items if item["kind"] == kind
        )
        for text, count in counts.most_common():
            print(f"{count:4d}  {text}")


def reextract_from_raw(
    log: dict,
    raw_dir: Path,
    output: Path,
    source_kind: str | None,
) -> None:
    updated = 0
    for source in log["sources"]:
        if source_kind and source["source_kind"] != source_kind:
            continue
        digest = hashlib.sha256(source["source_url"].encode("utf-8")).hexdigest()[:20]
        html_path = raw_dir / f"{digest}.html"
        if not html_path.exists():
            continue
        extracted = extract_document(html_path.read_text(encoding="utf-8"))
        source["page_title"] = page_title(extracted)
        source["text_records"] = filtered_text_records(
            source["source_kind"], extracted
        )
        source["aria_labels"] = extracted["aria_labels"]
        source["meta"] = extracted["meta"]
        source["structured_data"] = structured_data_summary(extracted)
        source["title_ids"] = extracted["title_ids"]
        relevant_links = []
        if source["source_kind"] in {"homepage", "top10"}:
            for link in extracted["links"]:
                if (
                    link["text"]
                    and len(link["text"]) <= 120
                    and not re.search(r"/title/\d+", link["href"])
                ):
                    relevant_links.append(link)
        source["links"] = relevant_links
        updated += 1
    output.write_text(
        json.dumps(log, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"re-extracted {updated} cached public responses into {output}")


def inspect(log: dict, only: str, limit: int | None) -> None:
    sources = log["sources"]
    print("STATUS BY SOURCE KIND")
    for kind in ["homepage", "top10", "genre", "title"]:
        rows = [row for row in sources if row["source_kind"] == kind]
        print(kind, dict(Counter(row["status"] for row in rows)))
        print(" reasons", dict(Counter(row["reason"] for row in rows)))

    if only == "summary":
        return
    if only == "out-of-bounds":
        for row in sources:
            if row["status"] == "out_of_bounds":
                print(
                    row["source_url"],
                    "->",
                    row["final_url"],
                    "::",
                    row["reason"],
                )
        return
    if only == "top10-headings":
        for row in sources:
            if row["source_kind"] != "top10" or row["status"] != "public":
                continue
            values = [
                f'{record["tag"]}: {record["text"]}'
                for record in row["text_records"]
                if record["tag"] in {"h1", "h2", "h3", "th", "label", "option"}
            ]
            print(row["source_url"])
            print("\n".join(f"  {value}" for value in values))
        return
    if only == "title-tags":
        tag_pattern = re.compile(
            r"^(?:TV-[A-Z0-9]+|R|PG-13|PG|G|NC-17|\d+ Seasons?|\d{4}|"
            r"HD|4K|Ultra HD)$"
        )
        for row in sources:
            if row["source_kind"] != "title" or row["status"] != "public":
                continue
            values = [
                record["text"]
                for record in row["text_records"]
                if tag_pattern.fullmatch(record["text"])
            ]
            structured = row.get("structured_data", [])
            print(row["source_url"], "::", values, "::", structured)
        return
    if only == "items":
        inspect_items(log)
        return
    if only == "grammar":
        items = extract_items(log)
        grammar = induce_grammar(items)
        terminology = terminology_counts(items)
        print("CORPUS", grammar["corpus"])
        print("RULES")
        for rule in grammar["rules"]:
            print(
                rule["id"],
                f'{rule["match_count"]}/{rule["denominator"]}',
                "counter",
                rule["counter_example_count"],
                "examples",
                rule["counter_examples"],
            )
        print("TOKEN CLASSES")
        for token_class in grammar["token_classes"]:
            print(
                token_class["id"],
                token_class["occurrence_item_count"],
                token_class["most_common_fills"],
            )
        print("LENGTH", grammar["length_distribution"])
        print("TERMINOLOGY", json.dumps(terminology, ensure_ascii=False, indent=2))
        return

    kinds = ["homepage", "top10", "title"] if only == "all" else [only]
    for kind in kinds:
        if kind == "genre":
            continue
        print(f"\nPUBLIC {kind.upper()} TEXT")
        shown = 0
        for row in sources:
            if row["source_kind"] != kind or row["status"] != "public":
                continue
            if limit is not None and shown >= limit:
                break
            records = [
                f'{record["tag"]}: {record["text"]}'
                for record in row["text_records"]
            ]
            print(row["source_url"])
            print("\n".join(f"  {record}" for record in records))
            aria = [entry["text"] for entry in row.get("aria_labels", [])]
            if aria:
                print("  ARIA:", " | ".join(dict.fromkeys(aria)))
            links = [
                f'{entry["text"]} => {entry["href"]}'
                for entry in row.get("links", [])
            ]
            if links:
                print("  LINKS:", " | ".join(dict.fromkeys(links)))
            shown += 1

    if only in {"all", "genre"}:
        print("\nPUBLIC GENRE H1/H2")
        shown = 0
        for row in sources:
            if row["source_kind"] != "genre" or row["status"] != "public":
                continue
            if limit is not None and shown >= limit:
                break
            headings = [
                record["text"]
                for record in row["text_records"]
                if record["tag"] in {"h1", "h2"}
            ]
            print(row["source_url"], " :: ", " || ".join(headings))
            shown += 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=HERE / "fetch-log.json")
    parser.add_argument("--output", type=Path, default=HERE / "shelves.json")
    parser.add_argument("--notes", type=Path, default=HERE / "notes.md")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--prune-log", action="store_true")
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument(
        "--only",
        choices=[
            "all", "summary", "homepage", "top10", "genre", "title",
            "out-of-bounds", "top10-headings", "title-tags",
            "items", "grammar",
        ],
        default="summary",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--reextract-raw", type=Path)
    parser.add_argument(
        "--reextract-kind",
        choices=["homepage", "top10", "genre", "title"],
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log = load_log(args.input)
    if args.reextract_raw:
        reextract_from_raw(
            log,
            args.reextract_raw,
            args.input,
            args.reextract_kind,
        )
    if args.prune_log:
        log = prune_fetch_log(log)
        args.input.write_text(
            json.dumps(log, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"pruned extracted fetch log at {args.input}")
    if args.write:
        payload = write_outputs(log, args.output, args.notes)
        print(
            "wrote",
            args.output,
            args.notes,
            "items",
            len(payload["items"]),
            "records",
            [record["id"] for record in payload["derived_records"]],
        )
    if args.inspect:
        inspect(log, args.only, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
