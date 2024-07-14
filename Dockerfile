FROM python:3.11-slim-bookworm AS base

# You can periodically change this variable to enable rebuild, eg. for regular security updates
ARG CACHEBUST=0

# Prepare environment

RUN apt-get update -y \
  && apt-get upgrade -y \
  && apt-get install -yq pkg-config \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* \
  && mkdir -p /usr/src/app/logs

FROM base AS buildstage

# Dependencies needed for build only
RUN apt-get update -y \
  && apt-get install -yq build-essential python3-dev git \
  && pip3 install --no-cache-dir --upgrade pip \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY ./requirements.txt /usr/src/app/requirements.txt
RUN pip3 install --no-cache-dir -r /usr/src/app/requirements.txt

FROM buildstage AS installstage

WORKDIR /usr/src

# Install dependencies
COPY ./requirements-install.txt /usr/src/app/requirements-install.txt
RUN pip3 install --no-cache-dir -r /usr/src/app/requirements-install.txt
COPY app /usr/src/app

# Create the SQLite database from the Film CSV database
ARG FILM_DATABASE_REPO="https://github.com/Merinorus/Open-source-film-database"
RUN git clone $FILM_DATABASE_REPO Open-source-film-database
RUN python -m app.install

FROM buildstage AS buildstage-dev

# Install additional dependencies for development & testing
COPY ./requirements-dev.txt /usr/src/app/requirements-dev.txt
RUN pip3 install --no-cache-dir -r /usr/src/app/requirements-dev.txt


FROM base AS local-image

# Convenient packages to help debugging
RUN apt-get update -y \
  && apt-get install -yq iputils-ping vim \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Copy dependencies to dev image
COPY --from=buildstage-dev /usr/local/lib /usr/local/lib
COPY --from=buildstage-dev /usr/local/bin /usr/local/bin
COPY --from=installstage /usr/src/app/data/film_database.db /usr/src/app/data/film_database.db

# Copy all the source code (including tests)

COPY . /usr/src

# Launch the application
ENTRYPOINT ["python", "-m", "app"]

FROM base AS runtime-image

# Copy dependencies to runtime image
COPY --from=buildstage /usr/local/lib /usr/local/lib
COPY --from=buildstage /usr/local/bin /usr/local/bin
COPY --from=installstage /usr/src/data/film_database.db /usr/src/data/film_database.db

# Expose API port 3500

# Copy app files
COPY app /usr/src/app
COPY templates /usr/src/templates
RUN useradd -u 9999 app
RUN chown -R app:app /usr/src/app
USER app

WORKDIR /usr/src

EXPOSE 3500

# Launch the application
ENTRYPOINT []
CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "3500"]

# Regular health check
HEALTHCHECK --interval=10s --timeout=3s --retries=3 --start-period=10s CMD python -m app.healthcheck
