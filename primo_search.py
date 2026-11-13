"""Mock Primo search for the SJSU Library Kingbot prototype.

The interface calls search_primo(). That function currently uses
search_primo_mock(). When the library is ready, implement
search_primo_live() and switch the one-line return inside search_primo().

Do not hardcode an API key. Read it later from the PRIMO_API_KEY
environment variable or from Streamlit secrets at ["primo"]["api_key"].
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


# Visible OneSearch names are not the same as Primo API scope codes.
# Leave the identifiers blank until Jessie or the SJSU Library team
# confirms the values from Alma / Primo configuration.
SCOPE_IDENTIFIERS = {
    "Everything": "",
    "SJSU Collections / Everything": "",
    "Expanded Search": "",
}

# Public OneSearch view id from the library's current Kingbot prompt.
# Confirm this before any live call.
PRIMO_VID = "01CALS_SJO:01CALS_SJO"

# Regional Ex Libris host. Confirm the region before go-live.
PRIMO_API_HOST = "https://api-na.hosted.exlibrisgroup.com"
PRIMO_SEARCH_PATH = "/primo/v1/search"

# Facet values vary by tenant. Confirm before they are sent to Primo.
RESOURCE_TYPE_FACETS = {
    "books": "facet_rtype,exact,books",
    "articles": "facet_rtype,exact,articles",
    "dissertations": "facet_rtype,exact,dissertations",
    "general": None,
}

LOCAL_SEARCH = {
    "scope": "Everything",
    "scope_label": "SJSU Collections / Everything",
    "search_source": "SJSU Library collection",
    "pc_availability": False,
}

EXPANDED_SEARCH = {
    "scope": "Expanded Search",
    "scope_label": "Expanded Search",
    "search_source": "Expanded Search",
    "pc_availability": True,
}

RECORD_TYPE = {
    "books": "book",
    "articles": "article",
    "dissertations": "dissertation",
    "general": None,
}

TYPE_LABELS = {
    "books": "books",
    "articles": "articles",
    "dissertations": "dissertations",
    "general": "library materials",
    "book": "Book",
    "article": "Article",
    "dissertation": "Dissertation",
}

SJSU_AVAILABLE = "Available through SJSU Library"
EXPANDED_AVAILABLE = (
    "Not held by SJSU; may be requestable through CSU+ or interlibrary loan"
)
REQUEST_NOTE = (
    "Request information: this item is not held by SJSU. It may be "
    "requestable through CSU+ or interlibrary loan, and it is not "
    "immediately available."
)
BOOK_REVIEW_NOTICE = (
    "I found a related article/book review, but I did not find the "
    "requested book record in the SJSU collection."
)
DISSERTATION_NOTICE = (
    "I could not confirm this dissertation in the current SJSU search "
    "results. You may also want to check SJSU ScholarWorks, ProQuest "
    "Dissertations & Theses, or ask a librarian for help."
)
DISSERTATION_LINKS = (
    "[SJSU ScholarWorks](https://scholarworks.sjsu.edu/) · "
    "[Ask a librarian](https://library.sjsu.edu/ask-librarian)"
)

STOPWORDS = {
    "a", "an", "about", "and", "are", "article", "articles", "ask",
    "book", "books", "called", "can", "copy", "dissertation",
    "dissertations", "do", "does", "ebook", "ebooks", "find", "for",
    "from", "get", "have", "help", "how", "i", "in", "is", "it",
    "journal", "journals", "library", "look", "looking", "me",
    "monograph", "monographs", "my", "need", "of", "on", "or", "our",
    "peer", "please", "reviewed", "scholarly", "search", "show",
    "sjsu", "some", "the", "thesis", "theses", "this", "that",
    "title", "titled", "to", "want", "we", "with", "you", "your",
}

DATA_PATH = Path(__file__).with_name("mock_primo_data.json")


@lru_cache(maxsize=1)
def load_records() -> list[dict]:
    """Load the demonstration catalog once per process."""
    with DATA_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload["records"]


def normalize(text: str) -> str:
    """Lowercase text and treat punctuation as spaces."""
    text = (text or "").lower()
    text = text.replace("feng shui", "fengshui").replace("feng-shui", "fengshui")
    text = text.replace("a.i.", "artificial intelligence")
    text = text.replace("video-game", "video game").replace("videogame", "video game")
    text = re.sub(r"\bai\b", "artificial intelligence", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text: str) -> list[str]:
    tokens = []
    for token in normalize(text).split():
        if token in STOPWORDS or len(token) < 3:
            continue
        tokens.append(token)
    return tokens


def _words(text: str) -> list[str]:
    return normalize(text).split()


def token_in_text(token: str, words: list[str]) -> bool:
    stem = token.rstrip("s")
    for word in words:
        if word == token or word.rstrip("s") == stem:
            return True
    return False


def topical_score(query: str, record: dict) -> float:
    tokens = tokenize(query)
    if not tokens:
        return 0.0
    haystack = " ".join(
        [
            record.get("title", ""),
            record.get("author", ""),
            record.get("description", ""),
            record.get("related_title", ""),
            " ".join(record.get("keywords", [])),
        ]
    )
    words = _words(haystack)
    hits = sum(1 for token in tokens if token_in_text(token, words))
    return hits / len(tokens)


def title_similarity(query_title: str, record_title: str) -> float:
    """Score how closely a question names a specific catalog title."""
    query_norm = normalize(query_title)
    title_norm = normalize(record_title)
    if not query_norm or not title_norm:
        return 0.0
    if query_norm == title_norm:
        return 1.0
    if len(query_norm) >= 20 and (
        title_norm.startswith(query_norm) or query_norm.startswith(title_norm)
    ):
        return 0.94
    query_tokens = set(query_norm.split())
    title_tokens = set(title_norm.split())
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens & title_tokens) / len(query_tokens)
    # A review title contains the book title, but it is not that book.
    if query_norm in title_norm and overlap >= 0.8 and not title_norm.startswith("review"):
        return 0.9
    return overlap * 0.5


def is_book_review(record: dict) -> bool:
    return record.get("genre") == "book_review" or bool(record.get("misclassified"))


def _search_mode(scope: str, pc_availability: bool) -> str:
    """Map the prototype parameters onto local or expanded demonstration data.

    pc_availability=True is the expanded search in this prototype, because
    that is the behavior requested for the demo. Confirm with the library
    before go-live: in some Primo tenants this flag means "physically
    available items only," which is a different search.
    """
    scope_key = (scope or "").strip().lower()
    if pc_availability or scope_key in {"expanded", "expanded search"}:
        return "expanded"
    return "local"


def search_primo_mock(
    query: str,
    scope: str = "Everything",
    pc_availability: bool = False,
    resource_type: str = "books",
) -> list[dict]:
    """Return demonstration records for one catalog search.

    Replace this function later with search_primo_live(). Keep the
    parameter names stable: query, scope, pc_availability, resource_type.
    """
    resource_type = resource_type if resource_type in RECORD_TYPE else "general"
    origin = _search_mode(scope, pc_availability)
    scope_name = "sjsu" if origin == "local" else "expanded"
    wanted = RECORD_TYPE[resource_type]
    matched: list[dict] = []

    for record in load_records():
        if scope_name not in record.get("scopes", []):
            continue
        # Keep a misclassified book review in the raw response so the
        # validation layer can reject it and explain the mismatch.
        if wanted and record.get("resource_type") != wanted and not record.get("misclassified"):
            continue
        score = topical_score(query, record)
        similarity = title_similarity(query, record.get("title", ""))
        if max(score, similarity) < 0.66 and similarity < 0.88:
            continue
        item = dict(record)
        item["score"] = round(max(score, similarity), 3)
        item["title_similarity"] = round(similarity, 3)
        item["result_origin"] = origin
        item["scope"] = scope
        item["pc_availability"] = pc_availability
        item["requested_resource_type"] = resource_type
        matched.append(item)

    matched.sort(
        key=lambda item: (
            item.get("title_similarity", 0),
            item.get("is_sjsu_owned", False),
            item.get("score", 0),
        ),
        reverse=True,
    )
    return matched


def search_primo_live(
    query: str,
    scope: str,
    pc_availability: bool,
    resource_type: str,
) -> list[dict]:
    """Future Primo Search API call. This prototype never sends it.

    When the library is ready:
    1. Read the key from the environment variable PRIMO_API_KEY, or pass
       in the value from st.secrets["primo"]["api_key"]. Never print it.
    2. Fill SCOPE_IDENTIFIERS with the exact Primo scope codes. Do not
       send the visible OneSearch label as the scope parameter.
    3. Remove the NotImplementedError below and map the JSON response
       into the same record fields the mock records use.

    Expected request shape, with the key supplied at runtime:

        GET {PRIMO_API_HOST}{PRIMO_SEARCH_PATH}
        Header: Authorization: apikey <PRIMO_API_KEY>
        Params:
            vid = PRIMO_VID
            tab = the confirmed tab code
            scope = SCOPE_IDENTIFIERS[scope]
            q = any,contains,<query>
            qInclude = RESOURCE_TYPE_FACETS[resource_type]  (omit for general)
            pcAvailability = true or false
            lang = en
            limit = 10
            offset = 0
    """
    del query, scope, pc_availability, resource_type
    raise NotImplementedError(
        "Live Primo search is not connected. search_primo() still calls "
        "search_primo_mock()."
    )


def search_primo(
    query: str,
    scope: str = "Everything",
    pc_availability: bool = False,
    resource_type: str = "books",
) -> list[dict]:
    """Single search entry point used by the interface.

    LIVE INTEGRATION POINT: return search_primo_live(...) here after the
    live function is implemented and the scope identifiers are confirmed.
    """
    return search_primo_mock(
        query,
        scope=scope,
        pc_availability=pc_availability,
        resource_type=resource_type,
    )


def _extract_title(query: str) -> str | None:
    text = re.sub(r"\s+", " ", query.strip())
    patterns = [
        r"(?i)\b(?:titled|called)\s+[\"“']?(?P<title>.+?)[\"”']?\s*$",
        r"(?i)^(?:do you have|do we have|does the library have|have you got)\s+(?P<title>.+?)\s*$",
        r"[\"“](?P<title>.+?)[\"”]",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        title = match.group("title").strip(" ?.")
        title = re.sub(
            r"(?i)^(a copy of|the book|the article|the dissertation|the thesis|book|article|dissertation|thesis)\s+",
            "",
            title,
        ).strip()
        if not title or re.fullmatch(
            r"(?i)(this|that|it|the book|this book|that book|a book)",
            title,
        ):
            return None
        return title
    return None


def _resource_types(query: str) -> list[str]:
    patterns = [
        ("dissertations", r"\b(dissertations?|theses|thesis)\b"),
        ("articles", r"\b(articles?|scholarly|journals?|peer[- ]reviewed)\b"),
        ("books", r"\b(books?|ebooks?|monographs?)\b"),
    ]
    found = []
    for name, pattern in patterns:
        match = re.search(pattern, query, flags=re.IGNORECASE)
        if match:
            found.append((match.start(), name))
    found.sort()
    return [name for _, name in found]


def parse_question(query: str) -> dict:
    """Decide the resource type and whether this is a known-item question."""
    types = _resource_types(query)
    title = _extract_title(query)
    known_item = bool(title) or bool(
        re.search(
            r"(?i)\b(do you have|do we have|does the library have|this book|this article|this dissertation)\b",
            query,
        )
    )
    # "Find books about ..." is a topic search even though it names a type.
    if re.search(r"(?i)\babout\b", query) and not re.search(r"(?i)\b(titled|called)\b", query):
        if not re.search(r"(?i)\b(do you have|do we have|does the library have)\b", query):
            known_item = False
            title = None

    resource_type = types[0] if types else "general"
    type_note = ""
    if len(types) > 1:
        type_note = (
            f"I search one material type at a time, so I treated this as a "
            f"search for {TYPE_LABELS[resource_type]}."
        )

    search_text = title if known_item and title else query
    return {
        "question": query.strip(),
        "resource_type": resource_type,
        "resource_label": TYPE_LABELS[resource_type],
        "known_item": known_item,
        "extracted_title": title,
        "search_text": search_text,
        "type_note": type_note,
        "demonstration_data": True,
    }


def availability_label(record: dict) -> str:
    if record.get("is_sjsu_owned"):
        status = record.get("availability")
        if status in {"available", "online"}:
            return SJSU_AVAILABLE
        if status == "checked_out":
            return "Checked out at SJSU Library and not currently available"
        return "Held by SJSU Library; availability could not be confirmed"
    return EXPANDED_AVAILABLE


def _decorate(record: dict) -> dict:
    item = dict(record)
    item["availability_label"] = availability_label(item)
    item["request_note"] = (
        REQUEST_NOTE if item.get("requestable") and not item.get("is_sjsu_owned") else ""
    )
    item["display_type"] = TYPE_LABELS.get(item.get("resource_type"), "Resource")
    return item


def _review_mentions(record: dict, title: str | None, query: str) -> bool:
    if not is_book_review(record):
        return False
    related = normalize(record.get("related_title", ""))
    review_title = normalize(record.get("title", ""))
    for candidate in (title, query):
        normalized = normalize(candidate or "")
        if not normalized:
            continue
        if normalized in related or related in normalized or normalized in review_title:
            return True
        if topical_score(candidate or "", record) >= 0.66:
            return True
    return record.get("score", 0) >= 0.66


def validate_results(raw: list[dict], parsed: dict, expanded: bool = False) -> dict:
    """Filter resource type, drop book reviews, and prefer exact titles.

    The first search also keeps SJSU-owned records only. Expanded search
    keeps the non-local demonstration records.
    """
    resource_type = parsed["resource_type"]
    wanted = RECORD_TYPE[resource_type]
    known_item = parsed["known_item"]
    title = parsed.get("extracted_title")
    review_found = any(
        _review_mentions(record, title, parsed["search_text"]) for record in raw
    )

    candidates = []
    for record in raw:
        if is_book_review(record):
            continue
        if wanted and record.get("resource_type") != wanted:
            continue
        if not expanded and not record.get("is_sjsu_owned"):
            continue
        if expanded and record.get("is_sjsu_owned"):
            continue
        item = _decorate(record)
        if known_item and title:
            item["title_similarity"] = round(
                title_similarity(title, item.get("title", "")),
                3,
            )
            if item["title_similarity"] < 0.88:
                continue
        candidates.append(item)

    if resource_type == "general" and candidates:
        groups: dict[str, list[dict]] = {}
        for item in candidates:
            groups.setdefault(item["resource_type"], []).append(item)
        if known_item:
            best_type = max(
                groups,
                key=lambda name: max(record["title_similarity"] for record in groups[name]),
            )
        else:
            best_type = max(
                groups,
                key=lambda name: max(record["score"] for record in groups[name]),
            )
        candidates = groups[best_type]

    candidates.sort(
        key=lambda item: (
            item.get("title_similarity", 0),
            item.get("is_sjsu_owned", False),
            item.get("score", 0),
        ),
        reverse=True,
    )
    if known_item and any(item.get("title_similarity", 0) >= 0.94 for item in candidates):
        candidates = [item for item in candidates if item.get("title_similarity", 0) >= 0.94]

    results = candidates[:5]
    # Offer expanded search after every completed catalog search, including
    # when the SJSU collection already has useful copies. A known-item
    # question with no title has not been searched, so it stays hidden.
    show_expand = not expanded
    if known_item and not title:
        show_expand = False

    notice = ""
    followup = ""
    if known_item and not title:
        notice = "Please share the title, and I can check whether the SJSU Library has it."
    elif resource_type == "dissertations" and not results and not expanded:
        notice = DISSERTATION_NOTICE
        followup = DISSERTATION_LINKS
    elif review_found and resource_type in {"books", "general"} and not results and not expanded:
        notice = BOOK_REVIEW_NOTICE
    elif not results and not expanded:
        notice = "I did not find a matching record in the SJSU Library collection."
    elif not results and expanded:
        notice = (
            "I did not find a matching record in the expanded demonstration "
            "collection. You can ask a librarian for help."
        )
        followup = "[Ask a librarian](https://library.sjsu.edu/ask-librarian)"

    return {
        "results": results,
        "notice": notice,
        "followup": followup,
        "show_expand": show_expand,
        "review_found": review_found,
    }


def _topic_phrase(parsed: dict) -> str:
    if parsed["known_item"] and parsed.get("extracted_title"):
        return parsed["extracted_title"]
    text = parsed["question"]
    text = re.sub(r"(?i)^(please\s+)?(find|search for|show me|look for|get)\s+", "", text)
    text = re.sub(
        r"(?i)^(some\s+)?(scholarly\s+)?(books?|articles?|dissertations?|theses|thesis)\s+(about|on|for)\s+",
        "",
        text,
    )
    return text.strip(" .?")


def _lead(parsed: dict, validation: dict) -> str:
    pieces = []
    if parsed.get("type_note"):
        pieces.append(parsed["type_note"])
    if validation["notice"] in {DISSERTATION_NOTICE, BOOK_REVIEW_NOTICE}:
        pieces.append(validation["notice"])
        return " ".join(pieces)
    if parsed["known_item"] and not parsed.get("extracted_title"):
        pieces.append(validation["notice"])
        return " ".join(pieces)
    if parsed["known_item"] and validation["results"]:
        pieces.append("Yes. This title is in the SJSU Library collection.")
        return " ".join(pieces)
    topic = _topic_phrase(parsed)
    material = parsed["resource_label"]
    if validation["results"]:
        if parsed["known_item"]:
            pieces.append("Yes. This title is in the SJSU Library collection.")
        else:
            pieces.append(
                f"I checked the SJSU Library collection for {material} about {topic}."
            )
    else:
        pieces.append(validation["notice"] or "I did not find a matching record in the SJSU Library collection.")
    return " ".join(pieces)


def _debug_block(parsed: dict, scope: dict, results: list[dict], origin: str) -> dict:
    identifier = SCOPE_IDENTIFIERS.get(scope["scope_label"]) or SCOPE_IDENTIFIERS.get(scope["scope"])
    return {
        "resource_type": parsed["resource_type"],
        "scope_label": scope["scope_label"],
        "pc_availability": scope["pc_availability"],
        "result_count": len(results),
        "origin": origin,
        "api_scope_identifier": identifier or "(not configured)",
        "demonstration_data": True,
    }


def build_local_search(query: str) -> dict:
    """Run the SJSU collection search once and validate the records."""
    parsed = parse_question(query)
    if parsed["known_item"] and not parsed.get("extracted_title"):
        validation = {
            "results": [],
            "notice": "Please share the title, and I can check whether the SJSU Library has it.",
            "followup": "",
            "show_expand": False,
            "review_found": False,
        }
    else:
        raw = search_primo(
            parsed["search_text"],
            scope=LOCAL_SEARCH["scope"],
            pc_availability=LOCAL_SEARCH["pc_availability"],
            resource_type=parsed["resource_type"],
        )
        validation = validate_results(raw, parsed, expanded=False)

    return {
        "parsed": parsed,
        "question": parsed["question"],
        "resource_type": parsed["resource_type"],
        "known_item": parsed["known_item"],
        "lead": _lead(parsed, validation),
        "notice": "" if validation["notice"] and validation["notice"] in _lead(parsed, validation) else validation["notice"],
        "followup": validation["followup"],
        "results": validation["results"],
        "show_expand": validation["show_expand"],
        "search_source": LOCAL_SEARCH["search_source"],
        "scope_label": LOCAL_SEARCH["scope_label"],
        "pc_availability": LOCAL_SEARCH["pc_availability"],
        "origin": "local",
        "debug": _debug_block(parsed, LOCAL_SEARCH, validation["results"], "local"),
    }


def build_expanded_search(parsed: dict) -> dict:
    """Run the expanded search only after the patron asks for it."""
    raw = search_primo(
        parsed["search_text"],
        scope=EXPANDED_SEARCH["scope"],
        pc_availability=EXPANDED_SEARCH["pc_availability"],
        resource_type=parsed["resource_type"],
    )
    validation = validate_results(raw, parsed, expanded=True)
    return {
        "heading": "Expanded Search results",
        "explanation": (
            "These materials may not be immediately available through SJSU. "
            "They may be requestable through CSU+ or interlibrary loan."
        ),
        "notice": validation["notice"],
        "followup": validation["followup"],
        "results": validation["results"],
        "search_source": EXPANDED_SEARCH["search_source"],
        "scope_label": EXPANDED_SEARCH["scope_label"],
        "pc_availability": EXPANDED_SEARCH["pc_availability"],
        "origin": "expanded",
        "debug": _debug_block(parsed, EXPANDED_SEARCH, validation["results"], "expanded"),
    }


def run_demo_checks() -> None:
    """Check the seven prototype questions plus the book-review case."""
    books = build_local_search("Find books about Chicano comics.")
    assert books["resource_type"] == "books", books["resource_type"]
    assert len(books["results"]) >= 2
    assert all(item["resource_type"] == "book" and item["is_sjsu_owned"] for item in books["results"])
    assert books["show_expand"] is True
    assert all(item["availability_label"] == SJSU_AVAILABLE for item in books["results"])

    games = build_local_search("Find books about video-game history.")
    assert games["resource_type"] == "books"
    assert len(games["results"]) >= 2
    assert games["show_expand"] is True
    assert all("video" in item["title"].lower() or "console" in item["title"].lower() for item in games["results"])

    dissertation = build_local_search(
        "Find the dissertation titled Influences on Career Decisions of "
        "International Students Attending Community Colleges in the United States."
    )
    assert dissertation["resource_type"] == "dissertations"
    assert dissertation["known_item"] is True
    assert dissertation["results"] == []
    assert DISSERTATION_NOTICE in dissertation["lead"]
    assert dissertation["show_expand"] is True
    dissertation_expanded = build_expanded_search(dissertation["parsed"])
    assert len(dissertation_expanded["results"]) == 1
    assert dissertation_expanded["results"][0]["is_sjsu_owned"] is False
    assert dissertation_expanded["results"][0]["availability_label"] == EXPANDED_AVAILABLE

    fengshui = build_local_search(
        "Do you have The Culture of Fengshui in Korea: An Exploration of East Asian Geomancy?"
    )
    assert fengshui["known_item"] is True
    assert len(fengshui["results"]) == 1
    assert fengshui["results"][0]["is_sjsu_owned"] is True
    assert "fengshui" in fengshui["results"][0]["title"].lower()
    assert fengshui["show_expand"] is True
    assert fengshui["results"][0]["availability_label"] == SJSU_AVAILABLE

    short_title = build_local_search("Do you have The Culture of Fengshui in Korea?")
    assert len(short_title["results"]) == 1
    assert short_title["show_expand"] is True

    articles = build_local_search("Find scholarly articles about artificial intelligence.")
    assert articles["resource_type"] == "articles"
    assert articles["results"]
    assert all(item["resource_type"] == "article" and item["genre"] != "book_review" for item in articles["results"])
    assert articles["show_expand"] is True
    assert "review of artificial intelligence" not in " ".join(item["title"].lower() for item in articles["results"])

    missing = build_local_search(
        "Do you have Borderlands Ink: A History of Chicano Comics in California?"
    )
    assert missing["results"] == []
    assert missing["show_expand"] is True
    missing_expanded = build_expanded_search(missing["parsed"])
    assert len(missing_expanded["results"]) == 1
    assert missing_expanded["results"][0]["is_sjsu_owned"] is False
    assert missing_expanded["results"][0]["availability_label"] == EXPANDED_AVAILABLE
    assert "Available through SJSU" not in missing_expanded["results"][0]["availability_label"]

    empty = build_local_search("Find books about lunar librarianship.")
    assert empty["resource_type"] == "books"
    assert empty["results"] == []
    assert empty["show_expand"] is True
    empty_expanded = build_expanded_search(empty["parsed"])
    assert empty_expanded["results"] == []

    review = build_local_search("Do you have Artificial Intelligence: A Guide for Thinking Humans?")
    assert review["results"] == []
    assert BOOK_REVIEW_NOTICE in review["lead"]
    assert review["show_expand"] is True
    review_expanded = build_expanded_search(review["parsed"])
    assert len(review_expanded["results"]) == 1
    assert review_expanded["results"][0]["resource_type"] == "book"
    assert review_expanded["results"][0]["genre"] != "book_review"

    mixed = build_local_search("Find books and articles about artificial intelligence.")
    assert mixed["resource_type"] == "books"
    assert all(item["resource_type"] == "book" for item in mixed["results"])
    assert mixed["show_expand"] is True

    untitled = build_local_search("Do you have this book?")
    assert untitled["results"] == []
    assert untitled["show_expand"] is False

    try:
        search_primo_live("test", "Everything", False, "books")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("search_primo_live should not run in this prototype")

    assert SCOPE_IDENTIFIERS["Expanded Search"] == ""
    assert all(not item.get("api_key") for item in load_records())
    print("All demonstration searches passed.")


if __name__ == "__main__":
    run_demo_checks()
