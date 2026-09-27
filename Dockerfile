FROM python:3.13-slim-trixie AS runtimebase

ENV PATH="/opt/venv/bin:$PATH"

# You can periodically change this variable to enable rebuild, eg. for regular security updates
ARG CACHEBUST=0

# Prepare environment

RUN apt-get update -y \
  && apt-get upgrade -y \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p /usr/src/app/logs

FROM python:3.13-trixie AS buildbase

# Prepare environment

RUN apt-get update -y \
  && apt-get install --no-install-recommends -yq pkg-config \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

FROM buildbase AS buildstage

COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /usr/src

# Install dependencies
COPY pyproject.toml uv.lock /usr/src/

# You can periodically change this variable to enable rebuild, eg. for regular security updates
ARG CACHEBUST=0
RUN uv sync --locked --no-dev --no-cache

FROM buildstage AS installstage

WORKDIR /usr/src

# Install dependencies
RUN uv sync --locked --no-dev --group install --no-cache
COPY app /usr/src/app

# Create the SQLite database from the Film CSV database
ARG FILM_DATABASE_REPO="https://github.com/Merinorus/Open-source-film-database"
ARG FILM_DATABASE_BRANCH="main"
RUN git clone -b $FILM_DATABASE_BRANCH $FILM_DATABASE_REPO Open-source-film-database
RUN python -m app.install

FROM buildstage AS buildstage-dev

# Install additional dependencies for development & testing
RUN uv sync --locked --no-cache


FROM runtimebase AS local-image

# Convenient packages to help debugging
RUN apt-get update -y \
  && apt-get install --no-install-recommends -yq iputils-ping vim \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Copy dependencies to dev image
COPY --from=buildstage-dev /opt/venv /opt/venv
COPY --from=installstage /usr/src/data/film_database.db /usr/src/data/film_database.db

# Copy all the source code (including tests)

COPY . /usr/src

# Launch the application
WORKDIR /usr/src
ENTRYPOINT ["python", "-m", "app.run"]

FROM runtimebase AS runtime-image

# Copy dependencies to runtime image
COPY --from=buildstage /opt/venv /opt/venv
COPY --from=installstage /usr/src/data/film_database.db /usr/src/data/film_database.db

# Expose API port 3500

# Copy app files
COPY . /usr/src
RUN useradd -u 9999 app
RUN chown -R app:app /usr/src
USER app

WORKDIR /usr/src

EXPOSE 3500

# Launch the application
ENTRYPOINT []
CMD ["python", "-m", "app.run"]

# Regular health check
HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=10s CMD python -m app.healthcheck
