import re
import sqlite3
from collections import Counter
from functools import lru_cache

from pydantic import TypeAdapter

from app.core.database import db_ram_connection
from app.core.schemas.film import FilmInDB, HTMLFilmInDB
from app.utils.sql import combined_search_param, fulltext_search_param, sanitize_fulltext_string
from app.utils.url import normalize_slug

# Max results allowed for a search request
MAX_RESULTS = 101
MAX_FALLBACK_WORDS = 12
MAX_FALLBACK_REMOVALS = 5
MAX_FALLBACK_RESULTS = 10

# Literal queries for each autocomplete scope keep the searched columns whitelisted.
_AUTOCOMPLETE_QUERIES = {
    "name": "SELECT name FROM films WHERE name MATCH ?",
    "manufacturer": "SELECT manufacturer FROM films WHERE manufacturer MATCH ?",
    "search": "SELECT name, manufacturer, distributor FROM films "
    "WHERE films MATCH ('{name manufacturer distributor} : (' || ? || ')')",
}
AUTOCOMPLETE_COLUMNS = tuple(_AUTOCOMPLETE_QUERIES)
# Max suggestions returned by an autocomplete request
MAX_AUTOCOMPLETE_RESULTS = 11
# Minimum length of the word being completed before we start suggesting
MIN_AUTOCOMPLETE_PREFIX = 2
# Match word tokens roughly like the FTS5 unicode61 tokenizer. \w is Unicode-aware in Python 3, so
# this keeps Cyrillic, CJK, accented letters, etc. (a plain [^a-z0-9] split would drop them all).
_AUTOCOMPLETE_WORD_RE = re.compile(r"\w+")
# Generic words that carry little distinguishing value. They are still suggested, but their ranking
# score is multiplied by AUTOCOMPLETE_STOPWORD_PENALTY so they fall below distinctive words (brands,
# model names, ISO speeds...). Tweak this set freely; it is intentionally lowercase (any language).
AUTOCOMPLETE_STOPWORDS = frozenset(
    {
        "and",
        "asa",
        "base",
        "box",
        "camera",
        "code",
        "color",
        "colour",
        "contrast",
        "couleur",
        "definition",
        "din",
        "direct",
        "emulsion",
        "film",
        "films",
        "for",
        "foto",
        "high",
        "improved",
        "iso",
        "lab",
        "line",
        "motion",
        "negative",
        "new",
        "no",
        "photo",
        "photography",
        "picture",
        "positive",
        "print",
        "prints",
        "process",
        "professional",
        "roll",
        "safety",
        "sound",
        "special",
        "speed",
        "super",
        "type",
        "ultra",
        "version",
        "тип",
    }
)
# Multiplier applied to a stopword's score so it ranks low without being removed entirely.
AUTOCOMPLETE_STOPWORD_PENALTY = 0.05

cursor = db_ram_connection.cursor()


def get_film_type(dx_extract: int) -> str | None:
    """Return the film type for the given DX extract code, None if not found."""
    dx_extract = int(dx_extract)
    row = cursor.execute(
        "SELECT label FROM film_types WHERE ? >= dx_min and ? <= dx_max ORDER BY rowid DESC LIMIT 1",
        [dx_extract, dx_extract],
    ).fetchone()
    column_names = [description[0] for description in cursor.description]
    film_type = dict(zip(column_names, row, strict=False)).get("label") if row else None
    return film_type


def get_by_id(rowid: int) -> FilmInDB | None:
    """Return a film in database by its SQLite row ID."""
    query = "SELECT * FROM films WHERE rowid = ?"
    cursor.execute(query, [rowid])
    row = cursor.fetchone()
    if not row:
        return None
    column_names = [description[0] for description in cursor.description]
    film = dict(zip(column_names, row, strict=False))
    return FilmInDB(**film)


def get_by_url(url: str) -> FilmInDB | None:
    """Return a film by its URL name."""
    if len(url) > 255 or not re.fullmatch(r"[a-z0-9_-]+", url):
        # Silently refuse unsafe URLs (404 error). All films in DB have a valid url safe name.
        result = None
    else:
        cursor = db_ram_connection.cursor()
        db_query = "SELECT * FROM films WHERE url_name = ?"
        cursor.execute(db_query, [normalize_slug(url)])
        row = cursor.fetchone()
        column_names = [description[0] for description in cursor.description]
        result = HTMLFilmInDB(**dict(zip(column_names, row, strict=False))) if row else None
    return result


def suggest_for_missing_url(url: str) -> list[FilmInDB]:
    """Try the slug, then up to five shorter prefixes, with bounded search work."""
    if len(url) > 255 or not re.fullmatch(r"[a-z0-9_-]+", url):
        return []
    words = list(dict.fromkeys(re.findall(r"[a-z0-9]+", url)))
    if len(words) > MAX_FALLBACK_WORDS:
        return []
    # Keep numeric endings: they may be ISO speeds rather than duplicate suffixes.
    for _ in range(MAX_FALLBACK_REMOVALS + 1):
        if not any(len(word) >= 3 and word not in AUTOCOMPLETE_STOPWORDS for word in words):
            break
        results = search(q=" ".join(words), limit=MAX_FALLBACK_RESULTS)
        if results:
            return results
        words.pop()
    return []


def get_random(limit: int = 1) -> list[FilmInDB]:
    """Return a list of random films from the database.

    Args:
        limit (int, optional): Number of random films to return. Defaults to 1.

    Returns:
        list[FilmInDB]: The randomly selected films.
    """
    cursor = db_ram_connection.cursor()
    cursor.execute("SELECT * FROM films ORDER BY RANDOM() LIMIT ?", [limit])
    rows = cursor.fetchall()
    column_names = [description[0] for description in cursor.description]
    films = [dict(zip(column_names, row, strict=False)) for row in rows]
    ta = TypeAdapter(list[HTMLFilmInDB])
    return ta.validate_python(films)


def autocomplete(column: str, text: str, limit: int = MAX_AUTOCOMPLETE_RESULTS) -> list[str]:
    """Suggest completions within one column or across name, manufacturer and distributor.

    Completion is context-aware: every already-typed word must appear in the same film row, so a
    word is only suggested if a real film actually combines it with the previous words (eg. "kodak
    ekt" -> "ektachrome", but "fujifilm ekt" -> nothing, since no such film exists). Suggestions are
    ranked by how many matching films contain them (contextual frequency), most frequent first.

    The minimum prefix length only applies to the very first word (no context yet). As soon as at
    least one complete word precedes it, suggestions are returned regardless of the last word length,
    including the "next word" case where the input ends with a space (eg. "kodak " -> "gold",
    "portra"..., or "kodak p" -> "portra", "professional"...). Words already typed are never
    re-suggested.

    Args:
        column (str): An AUTOCOMPLETE_COLUMNS entry; 'search' combines the three identity columns.
        text (str): The partial search input. Only its last word is completed.
        limit (int, optional): Max number of suggestions. Defaults to MAX_AUTOCOMPLETE_RESULTS.

    Raises:
        ValueError: If ``column`` is not an allowed autocomplete column.

    Returns:
        list[str]: The suggested completed words, ranked by contextual frequency.
    """
    if column not in AUTOCOMPLETE_COLUMNS:
        raise ValueError(f"Unsupported autocomplete column: {column!r}")

    # Cache on the sanitized text so casing/whitespace variants collapse onto a single entry. The
    # trailing space (which distinguishes the "next word" case) is preserved by the sanitizer. The
    # in-RAM DB is read-only after startup, so cached results can never go stale.
    return list(_autocomplete_cached(column, sanitize_fulltext_string(text), limit))


@lru_cache(maxsize=2048)
def _autocomplete_cached(column: str, sanitized: str, limit: int) -> tuple[str, ...]:
    """Cached core of :func:`autocomplete`. Operates on already-sanitized text, returns a tuple.

    A tuple is returned (and copied to a list by the caller) so the shared cached object can never be
    mutated by a caller.
    """
    if not sanitized:
        return ()
    # A trailing space means the last word is finished: every token is context and we suggest the
    # next word (empty prefix). Otherwise the last token is the prefix being typed.
    tokens = sanitized.split()
    if column == "search":
        # Match the combined search's literal word handling, without exposing FTS operators.
        tokens = re.findall(r"[^\W_]+", sanitized, flags=re.UNICODE)
    if not tokens:
        return ()
    if sanitized.endswith(" "):
        context_words, prefix = tokens, ""
    else:
        *context_words, prefix = tokens

    # The minimum length gate only guards the first word; with context, any prefix (even empty) goes.
    if not context_words and len(prefix) < MIN_AUTOCOMPLETE_PREFIX:
        return ()

    # Already-typed words must match exactly; only the last word (if any) is a prefix query.
    match_param = " ".join([*context_words, prefix + "*"] if prefix else context_words)
    if column == "search":
        match_param = " AND ".join(f'"{word}"' for word in [*context_words, *([prefix] if prefix else [])])
        if prefix:
            match_param += "*"

    cursor = db_ram_connection.cursor()
    try:
        cursor.execute(_AUTOCOMPLETE_QUERIES[column], [match_param])
        rows = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"SQL Error detected in autocomplete: query will silently fail and return no result. Error detail:\n{e}")
        return ()

    # Count, per matching film, the distinct words that complete the prefix, skipping already-typed
    # words (an empty prefix matches every word, so the skip is what surfaces genuinely new words).
    typed_words = set(context_words)
    counts: Counter[str] = Counter()
    for row in rows:
        # A word repeated across columns still counts only once for this film.
        completing_words = {
            word
            for value in row
            if value
            for word in _AUTOCOMPLETE_WORD_RE.findall(value.lower())
            if word.startswith(prefix) and word not in typed_words
        }
        counts.update(completing_words)

    # Rank by contextual frequency, but demote generic stopwords so distinctive words surface first.
    def _score(item: tuple[str, int]) -> float:
        word, count = item
        return count * (AUTOCOMPLETE_STOPWORD_PENALTY if word in AUTOCOMPLETE_STOPWORDS else 1.0)

    ranked = sorted(counts.items(), key=_score, reverse=True)
    return tuple(word for word, _ in ranked[:limit])


def search(
    dx_extract: str = None,
    dx_full: str = None,
    name: str = None,
    manufacturer: str = None,
    limit: int = MAX_RESULTS,
    *,
    q: str | None = None,
) -> list[FilmInDB]:
    """Return the first page of matching films for API clients."""
    films, _ = search_page(dx_extract, dx_full, name, manufacturer, limit, q=q)
    return films


def search_page(
    dx_extract: str = None,
    dx_full: str = None,
    name: str = None,
    manufacturer: str = None,
    limit: int = MAX_RESULTS,
    *,
    q: str | None = None,
    page: int = 1,
) -> tuple[list[FilmInDB], int]:
    """Return a page and the total count, including an unfiltered alphabetical catalogue.

    Legacy name/DX ranking is applied to all matches before slicing. Other searches
    are ranked and paginated in SQLite, so the former result cap cannot hide films.
    """
    if page < 1 or not 1 <= limit <= MAX_RESULTS:
        raise ValueError("Invalid page or page size")
    offset = (page - 1) * limit
    cursor = db_ram_connection.cursor()
    db_query = "SELECT * FROM films WHERE 1=1"
    params = []
    guessed_dx_extract = None
    match_terms = combined_search_param(q) if q is not None else None
    if q is not None and match_terms is None:
        return [], 0
    if match_terms:
        db_query += " AND films MATCH ?"
        params.append(f"{{name manufacturer distributor og_film_or_information}} : ({match_terms})")

    if dx_extract:
        dx_extract = dx_extract.zfill(4)
        db_query += " AND dx_extract = ?"
        params.append(dx_extract)
    if dx_full:
        # Remove the 1st digit as it the same sort of film
        # Remove also the 6th digit as it only means the number of half frame. Sort later
        # Sort the results after DB query
        dx_full = dx_full.zfill(6)
        # Keep the part "OR dx_full = ?" because some films still have mismatching dx_part and dx_full numbers.
        db_query += " AND (dx_extract = ? AND dx_full LIKE ? OR dx_full = ?)"
        guessed_dx_extract = dx_extract or dx_full[1:5]
        dx_full_cropped = dx_full[1:5]
        params.extend([guessed_dx_extract, f"_{dx_full_cropped}_", dx_full])

    if name:
        db_query += " AND name MATCH ?"
        params.append(fulltext_search_param(name))
    if manufacturer:
        db_query += " AND manufacturer MATCH ?"
        params.append(fulltext_search_param(manufacturer))
    try:
        count = cursor.execute(db_query.replace("SELECT *", "SELECT COUNT(*)", 1), params).fetchone()[0]
    except sqlite3.OperationalError:
        return [], 0
    if offset >= count:
        return [], count

    order_by_params = []
    if match_terms:
        # Rank all candidates before LIMIT: name-only matches, identity-column matches,
        # then matches requiring notes. Column weights follow the FTS table schema.
        order_by_params.extend(
            [
                "CASE WHEN rowid IN (SELECT rowid FROM films WHERE name MATCH ?) THEN 0 "
                "WHEN rowid IN (SELECT rowid FROM films WHERE films MATCH ?) THEN 1 ELSE 2 END",
                # Weights in FTS column order: name=10, notes=1, manufacturer=5, distributor=3; others=0.
                "bm25(films, 0, 0, 10, 1, 5, 0, 0, 0, 0, 3, 0, 0, 0)",
            ]
        )
        params.extend([match_terms, f"{{name manufacturer distributor}} : ({match_terms})"])
    elif dx_extract or dx_full:
        order_by_params.append("case when dx_full is null then 1 else 0 end, dx_full, dx_extract")
    if manufacturer and not match_terms:
        order_by_params.append("manufacturer")
    order_by_params.append("name, rowid")
    db_query += " ORDER BY " + ", ".join(order_by_params)
    rank_in_python = (name and not any([dx_extract, dx_full, manufacturer, q])) or (dx_full and not match_terms)
    if not rank_in_python:
        db_query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    try:
        cursor.execute(db_query, params)
        rows = cursor.fetchall()
        column_names = [description[0] for description in cursor.description]
        films = [dict(zip(column_names, row, strict=False)) for row in rows]
    except sqlite3.OperationalError as e:
        print(f"SQL Error detected: query will silently fail and return no result. Error detail:\n{e}")
        return [], 0

    ta = TypeAdapter(list[HTMLFilmInDB])
    models = ta.validate_python(films)

    # Intelligent sort by name if only this has been provided
    if name and not any([dx_extract, dx_full, manufacturer, q]):
        # contains the exact provided name, ignoring the special characters
        models.sort(key=lambda x: sanitize_fulltext_string(name) in sanitize_fulltext_string(x.name), reverse=True)
        # starts with the provided name, ignoring the special characters
        models.sort(
            key=lambda x: sanitize_fulltext_string(x.name).startswith(sanitize_fulltext_string(name)),
            reverse=True,
        )
        # contains the exact provided name
        models.sort(key=lambda x: name.lower() in str(x.name).lower(), reverse=True)
        # starts with the exact provided name
        models.sort(key=lambda x: str(x.name).startswith(name), reverse=True)
        # is exactly the provided name
        models.sort(key=lambda x: str(x.name).lower() == name.lower(), reverse=True)

    # If a DX full number is provided and matches several films (eg: 012514 -> 012514, 012513, 912513)
    if dx_full and not match_terms:
        # is the provided DX Full number, except the last digit (number of full-frame exposures)
        models.sort(key=lambda x: (x.dx_full or "").startswith(dx_full[:-1]), reverse=True)
        # is exactly the provided DX Full number
        models.sort(key=lambda x: x.dx_full == dx_full, reverse=True)

    return (models[offset : offset + limit] if rank_in_python else models), count
