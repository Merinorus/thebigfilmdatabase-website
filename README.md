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
