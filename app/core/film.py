import sqlite3

from pydantic import TypeAdapter

from app.core.database import db_ram_connection
from app.core.schemas.film import FilmInDB, HTMLFilmInDB
from app.utils.sql import sanitize_fulltext_string
from app.utils.url import url_safe_str

# Max results allowed for a search request
MAX_RESULTS = 101

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


def get_by_id(rowid: int) -> FilmInDB:
    """Return a film in database by its SQLite row ID."""
    query = "SELECT * FROM films WHERE rowid = ?"
    cursor.execute(query, [rowid])
    row = cursor.fetchone()
    column_names = [description[0] for description in cursor.description]
    film = dict(zip(column_names, row, strict=False))
    return FilmInDB(**film)


def get_by_url(url: str) -> FilmInDB | None:
    """Return a film by its URL name."""
    if url != url_safe_str(url):
        # Silently refuse unsafe URLs (404 error). All films in DB have a valid url safe name.
        result = None
    else:
        cursor = db_ram_connection.cursor()
        db_query = "SELECT * FROM films WHERE url_name = ?"
        cursor.execute(db_query, [url])
        row = cursor.fetchone()
        column_names = [description[0] for description in cursor.description]
        result = HTMLFilmInDB(**dict(zip(column_names, row, strict=False))) if row else None
    return result


def search(
    dx_extract: str = None, dx_full: str = None, name: str = None, manufacturer: str = None, limit: int = MAX_RESULTS
) -> list[FilmInDB]:
    """Return the list of films in database, given the search criterias. At least one must be given.

    Args:
        dx_extract (str, optional): DX code extract (4 digits, with leading zeros). Defaults to None.
        dx_full (str, optional): DX full code (6 digits, with leading zeros). Defaults to None.
        name (str, optional): Film name. Defaults to None.
        manufacturer (str, optional): Film manufacturer. Defaults to None.

    Raises:
        ValueError: If no search parameter is given

    Returns:
        list[FilmInDB]: The found films in database
    """
    db_query = "SELECT * FROM films WHERE 1=1"
    params = []
    guessed_dx_extract = None

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
        params.append(f'"{sanitize_fulltext_string(name)}*"')
    if manufacturer:
        db_query += " AND manufacturer MATCH ?"
        params.append(f'"{sanitize_fulltext_string(manufacturer)}*"')
    if params:
        order_by_params = []
        if dx_extract or dx_full:
            order_by_params.append("case when dx_full is null then 1 else 0 end, dx_full, dx_extract")
        if manufacturer:
            order_by_params.append("manufacturer")
        order_by_params.append("name, rowid")
        db_query += " ORDER BY " + ", ".join(order_by_params) + " LIMIT ?"
        # Do not crop results too much earlier, otherwise the sort would return unrelevant results
        query_limit = min(10 * limit, MAX_RESULTS)
        params.append(query_limit)
        try:
            cursor.execute(db_query, params)
            rows = cursor.fetchall()

            # Convert rows to dictionary
            column_names = [description[0] for description in cursor.description]
            films = [dict(zip(column_names, row, strict=False)) for row in rows]
        except sqlite3.OperationalError as e:
            print(f"SQL Error detected: query will silently fail and return no result. Error detail:\n{e}")
            films = []

    else:
        raise ValueError("No search parameters provided.")

    ta = TypeAdapter(list[HTMLFilmInDB])
    models = ta.validate_python(films)

    # Intelligent sort by name if only this has been provided
    if name and not any([dx_extract, dx_full, manufacturer]):
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
    if dx_full:
        # is the provided DX Full number, except the last digit (number of full-frame exposures)
        models.sort(key=lambda x: x.dx_full.startswith(dx_full[:-1]), reverse=True)
        # is exactly the provided DX Full number
        models.sort(key=lambda x: x.dx_full == dx_full, reverse=True)

    # Limit returned results
    return models[:limit]
