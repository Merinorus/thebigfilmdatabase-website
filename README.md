# The Big Film Database

## Install and run locally

In a python virtual environment, install the required packages:

```sh
pip install -r requirements-install.txt

```

Then, update the local database from the Film CSV file:

```sh
python -m app.install
```

Lastly, start the server, either:

```sh
python -m app
```

Or with uvicorn (ASGI web server):

```sh
uvicorn app.app:app --reload --port 3500
```

### Build with Docker
```sh
docker build -t thebigfilmdatabase . && docker run --rm -p "3500:3500" --name thebigfilmdatabase thebigfilmdatabase
```
