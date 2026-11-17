# Lab 05: Containers

This stack uses the sibling `wishlist-api` and `wishlist-ui` repositories. Clone them next to each other:

```bash
git clone https://github.com/sarccasm/wishlist-api.git
git clone https://github.com/sarccasm/wishlist-ui.git
cd wishlist-api
cp .env.example .env
```

Edit `.env` and set non-empty values for `DB_PASSWORD` and `SECRET_KEY`. Keep `.env` local; it is ignored by Git and Docker.

Start the full stack from the `wishlist-api` directory:

```bash
docker compose up --build -d
docker compose ps
```

Open the UI at http://localhost:8080 and the API docs at http://localhost:8000/docs. Stop the services with `docker compose down`. PostgreSQL data remains in the named `postgres_data` volume. To delete that data too, run `docker compose down -v`.

## What runs

| Service | Image / build | Host port | Health check |
| --- | --- | ---: | --- |
| `postgres` | `postgres:16-alpine` | internal only | `pg_isready` |
| `redis` | `redis:7-alpine` | internal only | `redis-cli ping` |
| `api` | local multi-stage build | 8000 | `GET /health` |
| `ui` | local Node build, nginx runtime | 8080 | HTTP request to nginx |

Compose waits for PostgreSQL and Redis to become healthy before starting the API, then waits for the API before starting the UI. Only the UI and API ports are published to the host.

## Why the UI API address is a build argument

The UI is compiled by Vite into static JavaScript. Vite replaces `VITE_API_BASE` while building the bundle, so setting it as a container runtime environment variable would be too late. The Compose file passes it as a Docker build argument. The default is `http://localhost:8000` because requests come from the user's browser; the Compose-only hostname `api` would not resolve on the host browser.

## Secrets

Compose requires `DB_PASSWORD` and `SECRET_KEY` to be set in the local `.env` file and has no password fallback. They are passed to the running API and database containers as environment variables; they are not Docker build arguments. The Docker ignore file excludes local `.env` files from the build context.

## Diagnostics and persistence evidence

Useful commands:

```bash
docker compose config
docker compose ps
docker compose logs --tail=100 api postgres redis ui
docker compose exec api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"
docker compose down
docker compose up -d
```

To show that the database volume survives a restart, create a wishlist through the UI/API, run `docker compose down` and `docker compose up -d`, then confirm the same record is still present. `docker compose down -v` removes the volume and its data.

## Image size measurements

Record the sizes from the same Docker installation after building both stages. Do not compare the builder stage to a compressed registry download:

```bash
docker build --target builder -t wishlist-api:build .
docker build -t wishlist-api:local .
docker build --target build -t wishlist-ui:build ../wishlist-ui
docker build -t wishlist-ui:local ../wishlist-ui
docker image ls --format 'table {{.Repository}}:{{.Tag}}\t{{.Size}}' | grep -E 'wishlist-(api|ui)'
```

| Image | Size |
| --- | --- |
| API builder stage (`wishlist-api:build`) | Measure locally |
| API final stage (`wishlist-api:local`) | Measure locally |
| UI build stage (`wishlist-ui:build`) | Measure locally |
| UI final stage (`wishlist-ui:local`) | Measure locally |

Largest layer notes: add the layer inspection result after running `docker history wishlist-api:local` and `docker history wishlist-ui:local`.

## GHCR releases

Each repository's workflow runs its existing CI checks before building the container. Pull requests build but do not publish. A push to `main` publishes `main` and a short `sha-<commit>` tag; a `v*` Git tag publishes semantic version tags.

After the first successful publish, set each GitHub Container Registry package visibility to **Public** in the package settings so unauthenticated pulls work. Example release commands:

```bash
git tag v1.0.0
git push origin v1.0.0
docker pull ghcr.io/sarccasm/wishlist-api:1.0.0
docker pull ghcr.io/sarccasm/wishlist-ui:1.0.0
```

The API and UI packages are separate because each has its own source repository and image workflow.
