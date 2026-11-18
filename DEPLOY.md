# Lab 06 — PaaS deployment

This runbook uses the Lab 05 API and UI images on four Render image-backed web
services: API and UI in staging and production. Neon provides one PostgreSQL project
per environment; Upstash provides one Redis database per environment. The UI image
reads its API URL at container startup, so both environments can use one digest.

## Account resources to provision

Repository changes prepare the application and workflows. Live endpoints, Neon and
Upstash databases, Render deploy hooks, GitHub Environment protection, and operational
measurements must come from the owner's accounts; they are not committed here.

Create two Neon projects (wishlist-staging and wishlist-prod), two Upstash Redis
databases, and four Render web services configured to deploy existing public GHCR
images. Disable Render auto-deploys so only the workflow selects image versions.

| Service | Image repository | Environment |
| --- | --- | --- |
| wishlist-api-staging | ghcr.io/sarccasm/wishlist-api | staging |
| wishlist-ui-staging | ghcr.io/sarccasm/wishlist-ui | staging |
| wishlist-api-prod | ghcr.io/sarccasm/wishlist-api | production |
| wishlist-ui-prod | ghcr.io/sarccasm/wishlist-ui | production |

The Render service's configured image repository must match the deploy-hook imgURL
registry and image name. The hook changes only the API tag or UI digest.

## Render environment variables

Set these separately in each Render service's Environment page. Use environment-specific
values; do not put credentials in GitHub workflow files.

### API

| Variable | Value |
| --- | --- |
| ENVIRONMENT | staging or production |
| DATABASE_URL | Neon pooled connection URL with TLS (sslmode=require) |
| REDIS_URL | Upstash URL beginning rediss:// |
| SECRET_KEY | Separate random key per environment |
| ALGORITHM | HS256 |
| ALLOWED_ORIGINS | Exact UI origin for this environment |
| WEB_CONCURRENCY | 1 |
| DB_POOL_SIZE | 2 |
| DB_MAX_OVERFLOW | 0 |

Render supplies PORT. The API listens on 0.0.0.0:$PORT. Keep the application on
Neon's pooled endpoint; the separate migration URL uses Neon's direct endpoint.

### UI

| Variable | Value |
| --- | --- |
| VITE_API_BASE | Full API origin for this environment, e.g. https://wishlist-api-staging.onrender.com |

Nginx renders the SPA config at startup. Deep links such as /wishlists/1 use the
index.html fallback and do not return 404.

## GitHub Environments and secrets

In wishlist-api, open Settings → Environments and create staging and production.
Add these environment secrets separately to both:

- MIGRATION_DATABASE_URL: direct Neon connection URL for that environment, with
  sslmode=require. It is used only by the migration job.
- API_DEPLOY_HOOK: that environment's API Render deploy hook.
- UI_DEPLOY_HOOK: that environment's UI Render deploy hook.

Add these environment variables to both:

- API_BASE_URL: public API origin for smoke checks.
- UI_BASE_URL: public UI origin for smoke checks.

For production, configure Required reviewers with another teammate and enable Prevent
self-review. Set the production environment variable PRODUCTION_APPROVAL_READY=true only
after those protection rules are saved. Until then the production job is skipped, so a
staging success cannot deploy to an unprotected production environment. Workflow YAML
cannot configure the reviewer or Prevent self-review setting.
Application credentials stay in Render; migration URLs and deploy hooks are GitHub
environment secrets. Never print or commit these values.

## Delivery pipeline

1. A successful API CI run on main triggers the deploy workflow. The workflow uses the
   API image tagged with that commit's short SHA and snapshots the currently published
   UI main image as an immutable digest.
2. The staging job runs Alembic from that API image against the staging direct database
   URL. If migration fails, no Render deploy hook runs.
3. It deploys the API tag and UI digest, waits up to ten minutes for cold starts, then
   checks API /health, API /wishlists, UI /, and UI /wishlists/1.
4. Only after staging succeeds does the production job request the configured reviewer.
   After approval it migrates production and deploys the same API tag and UI digest.
5. The manual Roll back production images workflow accepts a previously deployed API
   SHA tag and UI tag or digest. It does not run migrations; rollback leaves the schema
   unchanged.

Render deploy hooks start a deployment but do not wait for health. The workflow polls
the public endpoints afterward. On the free Render plan a service may sleep, so the
poll allows up to ten minutes for its first request.

The accepted tradeoff is that migrations run in GitHub Actions before Render deploys
the service, because Render free-tier pre-deploy commands are unavailable. A platform
failure after migration can leave the schema ahead of the currently running app. Keep
schema changes backward-compatible using expand/contract.

## Migrations

The original first migration was empty. It now creates the four tables and their
indexes; the second migration changes users.full_name to nullable. API startup no
longer creates tables. CI runs alembic upgrade head on a fresh PostgreSQL service and
prints the table list.

New environments are migrated by the deploy workflow using the exact API image tag.

For an existing Lab 05 local database, make a backup first. Compare its tables, indexes,
and nullability with the final migrated schema. The Lab 05 application created tables
from current SQLAlchemy models, including nullable full_name. If schema matches, mark
the existing database at head without recreating tables or changing rows:

```bash
python -m alembic stamp head
python -m alembic current
```

If it differs, preserve the backup and apply only the missing schema changes before
stamping. Do not run the initial migration over existing tables.

## Connection budget

The API uses one Uvicorn worker, pool size 2, max overflow 0, and one Render instance per
environment. Maximum application connections are:

```text
1 worker × 2 pooled connections × 1 instance = 2 connections per environment
```

On 2026-11-18, both Neon projects (`wishlist-staging` and `wishlist-production`) were
shown on the Free plan. Running `SHOW max_connections;` in each project's default
`production` branch returned `901`. The staging compute is configured from 0.25 to 2
CU. Compared with PostgreSQL's reported server cap, the API's maximum of 2 connections
is 2/901 (about 0.22%) per environment. Migration uses one separate NullPool connection
while it runs, so plan for 3/901 (about 0.33%) during a release. Recalculate if worker,
pool, or instance counts change.

`SHOW max_connections` is the server-side PostgreSQL setting; it is not a separate
PgBouncer client-connection quota. The application uses Neon’s pooled endpoint, while
migrations use the direct endpoint, so the values above describe the app's configured
pool budget compared with the server-reported cap.

## Operational checks and evidence

### Redis unavailable on staging

Temporarily replace REDIS_URL in the staging Render service with a deliberately invalid
password. Verify /health stays HTTP 200 and marks Redis degraded, /wishlists still reads
from PostgreSQL, and the Render service stays healthy. Restore the real Upstash URL and
confirm Redis becomes healthy. Capture the response and service history; do not paste
the real URL into the report.

### Backup and restore

Record Neon's PostgreSQL server major version and use a matching or newer postgres
client image. Keep both connection strings in local shell environment variables:

```bash
export PROD_DATABASE_URL='(Neon production URL)'
export RESTORE_DATABASE_URL='(empty Neon branch direct URL or local restore database URL)'
time docker run --rm -e PROD_DATABASE_URL -v "$PWD:/backup" postgres:16-alpine \
  sh -ec 'pg_dump "$PROD_DATABASE_URL" --format=custom --file=/backup/wishlist.dump'
time docker run --rm -e RESTORE_DATABASE_URL -v "$PWD:/backup" postgres:16-alpine \
  sh -ec 'pg_restore --no-owner --dbname="$RESTORE_DATABASE_URL" /backup/wishlist.dump'
```

Replace 16 if Neon reports another major version. Run on production and the restored
database, then record counts and latest timestamps:

```sql
SELECT 'users' AS table_name, count(*) AS rows, max(created_at) AS newest FROM users
UNION ALL
SELECT 'wishlists', count(*), max(created_at) FROM wishlists
UNION ALL
SELECT 'wish_items', count(*), max(created_at) FROM wish_items
UNION ALL
SELECT 'wish_item_statuses', count(*), max(created_at) FROM wish_item_statuses;
```

Add the actual staging/prod URLs, Neon connection limits, restore duration, row counts,
and screenshots of the staging approval and production rollback after resources are
provisioned. These values cannot be inferred from public repositories.

## Observed staging evidence — 2026-11-18

- Deployment workflow run [#3](https://github.com/sarccasm/wishlist-api/actions/runs/44338789227) completed successfully at commit `ca099c855a6be25fa921fb2d73db9ffd8b783898`. The image resolution and staging migration/deployment jobs passed; the production job was skipped because `PRODUCTION_APPROVAL_READY` is not enabled.
- Direct staging check: `GET https://wishlist-api-staging.onrender.com/health` returned HTTP 200 with `{"status":"healthy","redis":"healthy"}` at 2026-11-18T15:49:15Z.
- The staging UI home route loaded and displayed the WishList application. The workflow's smoke check also passed the API `/wishlists` route, UI `/`, and UI history route `/wishlists/1`.
- The bare API root `/` is not an application route and returns `{"detail":"Not Found"}`; use `/health`, `/docs`, or documented API endpoints for checks.

The Redis-outage test, production backup/restore comparison, actual Neon connection limit, and production approval/deploy/rollback evidence are still pending. Do not enter estimated values as observed results. Record the commands, timings, counts, and Neon plan limit after those checks are performed.
