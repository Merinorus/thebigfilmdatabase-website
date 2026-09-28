# The Big Film Database

This repository contains the source code of this website: [thebigfilmdatabase.merinorus.com/](https://thebigfilmdatabase.merinorus.com/)

This is a modified version of [The Big Film Database](http://industrieplus.alwaysdata.net/dxdatabase/), which is still available (as of June, 2025).

You can find the original author website's source code with its database and his explanations on [GitHub](https://github.com/dxdatabase/Open-source-film-database).


## Install and run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then sync the project.
Python 3.13 or newer is required; uv can download a compatible version if needed.

```sh
uv sync
```

Create the SQLite database from the film CSV (only needed initially or to refresh it):

```sh
git clone https://github.com/Merinorus/Open-source-film-database Open-source-film-database
uv run --group install python -m app.install
```

Start the server:

```sh
uv run python -m app
```

Or with automatic reload:

```sh
uv run uvicorn app.app:app --reload --port 3500
```

Browse the full catalogue at `/search`. Search results and the catalogue use numbered
pages (`/search?page=2`), with 100 films per page by default. Pagination links preserve
the search filters and the optional `limit` parameter. Pages beyond the last result
return HTTP 404. Film detail URLs are unchanged.

The API supports the same pagination: `/api/search?q=kodak&page=2&limit=50`.
Its JSON response keeps `status` and the `data` array, and adds `page`, `limit`,
`total` (all matching films), and `pages`. Without filters, it lists the whole
catalogue. The default page is 1 and the default limit is 100 (maximum 101).
An empty search result returns `data: []`, `total: 0`, and `pages: 1` on page 1;
pages beyond the last result return HTTP 404, and invalid page/limit values
return HTTP 422. These parameters and response fields are documented in `/docs`.

Run the development checks:

```sh
uv run pre-commit run --all-files
```

Dependencies are declared in `pyproject.toml` and locked in `uv.lock`. Commit both
when changing dependencies with `uv add`. The default `dev` group contains
pre-commit; the optional `install` group contains NumPy and pandas for importing
the CSV. Production uses `uv sync --locked --no-dev`.

### Build with Docker
```sh
docker build -t thebigfilmdatabase . && docker run --rm -p "3500:3500" --name thebigfilmdatabase thebigfilmdatabase
```
