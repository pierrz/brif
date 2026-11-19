#!/usr/bin/env bash
#
# Runs the test suite exactly like CI does (job 'test' of .github/workflows/ci.yml).
#
#   bash scripts/test.sh [pytest arguments]      e.g. bash scripts/test.sh -k dashboard
#
# 1. Builds a Python 3.8 environment (the version of the Docker images) with uv, in ./.venv:
#    'uv sync --locked --no-dev' installs app/uv.lock without the dev tools, the very package set
#    of the Docker images (they install 'uv export --no-dev' of the same lock). --locked stops
#    with an error when uv.lock is not in step with app/pyproject.toml.
# 2. Needs a Postgres. If none answers on $PGHOSTADDR:$PGPORT and docker is available, a throwaway
#    postgres:14.2 container (the version of setup/postgres) is started and removed at the end.
#    It listens on the loopback only and trusts its clients, like the service container of CI.
#    Cantaloupe and Celery are test doubles, RabbitMQ is optional (see below).
# 3. Runs pytest from app/.
#
# Settings, all optional (the defaults are those of the CI service containers):
#   PGHOSTADDR, PGPORT                Postgres address (127.0.0.1, 5432)
#   DB_NAME, DB_USER, DB_PASSWORD     Postgres database, role and password (brif, brif, none)
#   BRIF_TEST_AMQP_URL                a RabbitMQ to also run test_celery_broker.py against,
#                                     e.g. amqp://guest:guest@127.0.0.1:5672// (skipped when unset)
#   BRIF_TEST_VENV                    where to put the environment (<repo>/.venv)

set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
venv=${BRIF_TEST_VENV:-$repo_root/.venv}

export PGHOSTADDR=${PGHOSTADDR:-127.0.0.1}
export PGPORT=${PGPORT:-5432}
export DB_NAME=${DB_NAME:-brif}
export DB_USER=${DB_USER:-brif}
export DB_PASSWORD=${DB_PASSWORD-}

command -v uv >/dev/null || {
    echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
}

# ---------------------------------------------------------------- 1. environment

if [ ! -x "$venv/bin/python" ]; then
    uv venv --python 3.8 "$venv"
fi
if ! "$venv/bin/python" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 8))'; then
    echo "$venv is not a Python 3.8 environment: remove it, or point BRIF_TEST_VENV elsewhere." >&2
    exit 1
fi

# uv sync is exact: whatever is not in the lock is removed from the environment
UV_PROJECT_ENVIRONMENT=$venv uv sync --project "$repo_root/app" --python 3.8 --locked --no-dev

# ---------------------------------------------------------------- 2. Postgres

db_answers() {
    (exec 3<>"/dev/tcp/$PGHOSTADDR/$PGPORT") 2>/dev/null
}

if ! db_answers; then
    if ! command -v docker >/dev/null; then
        echo "No Postgres answers on $PGHOSTADDR:$PGPORT and docker is not available to start one." >&2
        echo "Start a Postgres 14 with the database '$DB_NAME' owned by the role '$DB_USER', or set PGHOSTADDR and PGPORT." >&2
        exit 1
    fi
    case $PGHOSTADDR in
        127.* | ::1) ;;
        *)
            echo "Not starting a Postgres that trusts its clients on $PGHOSTADDR: use 127.0.0.1 or start your own." >&2
            exit 1
            ;;
    esac
    container=brif-test-db-$$
    trap 'docker rm --force "$container" >/dev/null 2>&1 || true' EXIT
    echo "Starting a throwaway Postgres ($container) on $PGHOSTADDR:$PGPORT ..."
    docker run --detach --rm --name "$container" \
        --publish "$PGHOSTADDR:$PGPORT:5432" \
        --env POSTGRES_USER="$DB_USER" --env POSTGRES_DB="$DB_NAME" --env POSTGRES_HOST_AUTH_METHOD=trust \
        postgres:14.2 >/dev/null
    for _ in $(seq 1 60); do
        docker exec "$container" pg_isready --quiet --host 127.0.0.1 --username "$DB_USER" --dbname "$DB_NAME" && break
        sleep 1
    done
    db_answers || {
        echo "The Postgres container did not come up." >&2
        exit 1
    }
fi

# ---------------------------------------------------------------- 3. tests

cd "$repo_root/app"
"$venv/bin/python" -m pytest -ra "$@"
