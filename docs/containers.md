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

Compose requires `DB_PASSWORD` and `SECRET_KEY` to be set in the local `.env` file and has no password fallback. They are passed to the running API and database containers as environment variables; they are not Docker build arguments. The Docker ignore files exclude local `.env` files from both build contexts. The signing algorithm is set to `HS256` in the environment example.

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

The API workflow's Compose smoke check registers a user, creates a wishlist through the API, stops and restarts the stack without removing the volume, and confirms the wishlist is still returned. The check also requests the UI at `/` and `/wishlists` to confirm the nginx history fallback. The [successful run #28](https://github.com/sarccasm/wishlist-api/actions/runs/44070664186) includes this evidence and an image-measurement artifact.

To repeat the persistence check manually, create a wishlist through the UI/API, run `docker compose down` and `docker compose up -d`, then confirm the same record is still present. `docker compose down -v` removes the volume and its data.

## Troubleshooting checklist

Use this order when a service is running but another service cannot reach it:

1. `docker compose ps` — check whether the service is running or healthy.
2. `docker compose config` — inspect the final port mappings and interpolated settings.
3. `docker compose logs --tail=100 <service>` — read the failing service's startup or connection error.
4. Check the address from the caller's point of view: containers use Compose service names such as `postgres` and `api`; a browser uses published host addresses such as `localhost`.

| Injected fault | Expected clue | Where to find it |
| --- | --- | --- |
| Set API `DB_HOST=127.0.0.1` in Compose | API tries to connect to itself and fails before startup; the database is healthy | `docker compose logs api`; Compose API environment in `docker compose config` |
| Change the published UI port from `8080` to `8081` | UI is healthy, but opening `localhost:8080` fails | `docker compose ps` shows the host-to-container port; `docker compose config` shows the mapping |
| Set `VITE_API_BASE=http://api:8000` | UI loads, but browser requests fail because the host browser cannot resolve the Compose-only service name | Browser developer console and the `VITE_API_BASE` build argument in `docker compose config` |

The first CI smoke run exposed two real API configuration errors. The API health request returned HTTP 500; `docker compose logs api` showed Redis rejecting the obsolete `ssl_cert_reqs` option for a `redis://` URL, so that option was removed. After the API became healthy, login returned HTTP 500 because `ALGORITHM` was unset; Compose and `.env.example` now set it to `HS256`. Both fixes are included in the later successful run linked above.

For the separate team fault-injection exercise, record the fault that a teammate actually injects, the command used to identify it, and the relevant output or screenshot here. Do not report a hypothetical fault as an observed result.

## Image size measurements

These sizes were measured with `docker image inspect` on the Ubuntu 24.04 GitHub runner in [CI run #28](https://github.com/sarccasm/wishlist-api/actions/runs/44070664186). MiB values are bytes divided by 1,048,576; local sizes can vary with platform and base-image updates. The run's `lab05-container-evidence` artifact includes raw byte counts and `docker history` output.

| Image | Size |
| --- | ---: |
| API builder stage (`wishlist-api:builder`) | 210.9 MiB |
| API final stage (`wishlist-api:local`) | 194.2 MiB |
| UI build stage (`wishlist-ui:build`) | 310.6 MiB |
| UI final stage (`wishlist-ui:local`) | 46.1 MiB |

The largest non-base API final layer is the installed Python dependencies at 78.5 MB; the Debian base contributes layers of 78.9 MB and 42.4 MB. The UI build stage keeps Node and `node_modules` while building; the final UI image drops those and contains only nginx plus about 160 KB of `dist/`.

## GHCR releases

Each repository's workflow runs its existing CI checks before building the container. Pull requests build but do not publish. A push to `main` publishes `main` and a short `sha-<commit>` tag; a `v*` Git tag publishes semantic version tags.

After the first successful publish, set each GitHub Container Registry package visibility to **Public** in the package settings so unauthenticated pulls work. To publish matching `1.0.0` tags from both repositories:

```bash
git tag v1.0.0 && git push origin v1.0.0
git -C ../wishlist-ui tag v1.0.0 && git -C ../wishlist-ui push origin v1.0.0
docker pull ghcr.io/sarccasm/wishlist-api:1.0.0
docker pull ghcr.io/sarccasm/wishlist-ui:1.0.0
```

The API and UI packages are separate because each has its own source repository and image workflow.
