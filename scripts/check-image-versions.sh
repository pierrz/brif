#!/usr/bin/env bash
#
# Checks that a built image holds the versions the repository locks, since the images are only
# built by CI. For the backend image (setup/app/Dockerfile) and the celery one (setup/celery/Dockerfile).
#
#   bash scripts/check-image-versions.sh IMAGE      e.g. bash scripts/check-image-versions.sh brif_api_img
#
# Inside the image, with its own python:
# 1. fastapi, pydantic, celery and starlette_core are imported and their versions printed;
# 2. every package that the Dockerfiles install (uv export --no-dev of app/uv.lock) and every
#    '==' pin of app/pyproject.toml must be installed, once, at exactly that version (starlette-core:
#    at the locked commit). Packages of the base image that are not in the lock are not looked at.
# The first mismatch list ends the script with exit code 1.
#
# Needs docker and uv on the PATH (CI: astral-sh/setup-uv, same version as the Dockerfiles).

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: bash scripts/check-image-versions.sh IMAGE" >&2
    exit 2
fi
image=$1

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

for tool in docker uv; do
    command -v "$tool" >/dev/null || {
        echo "$tool is required." >&2
        exit 1
    }
done

# what must be in the image: the lock as the Dockerfiles install it, then the pins of pyproject.toml
expected=$(
    uv export --project "$repo_root/app" --frozen --no-dev --no-hashes --no-emit-project \
        --no-header --no-annotate
    sed -n '/^dependencies = \[/,/^\]/p' "$repo_root/app/pyproject.toml" | grep -oE '"[A-Za-z0-9_.-]+==[^"]+"' | tr -d '"'
)

# run in the image (python 3.8, pip's vendored 'packaging' evaluates the markers of the export)
check='
import importlib.metadata as metadata
import json
import re
import sys

from pip._vendor.packaging.requirements import Requirement


def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()


installed = {}
for dist in metadata.distributions():
    installed.setdefault(norm(dist.metadata["Name"]), []).append(dist)

problems = []
checked = 0
for line in sys.stdin.read().splitlines():
    if not line.strip():
        continue
    req = Requirement(line)
    if req.marker is not None and not req.marker.evaluate():
        continue
    dists = installed.get(norm(req.name), [])
    if len(dists) != 1:
        problems.append(f"{req.name}: {len(dists)} installations found, expected 1")
        continue
    checked += 1
    if req.url:
        direct_url = json.loads(dists[0].read_text("direct_url.json") or "{}")
        found, wanted = direct_url.get("vcs_info", {}).get("commit_id"), req.url.rsplit("@", 1)[1]
    else:
        found, wanted = dists[0].version, next(iter(req.specifier)).version
    if found != wanted:
        problems.append(f"{req.name}: installed {found}, locked {wanted}")

if problems:
    print("\n".join(problems), file=sys.stderr)
    sys.exit(1)

import celery
import fastapi
import pydantic
import starlette_core

starlette_core_version = installed["starlette-core"][0].version
print(
    f"imports ok: fastapi {fastapi.__version__}, pydantic {pydantic.VERSION}, "
    f"celery {celery.__version__}, {starlette_core.__name__} {starlette_core_version}"
)
print(f"{checked} requirements (the lock and the pins of pyproject.toml) hold at exactly the locked version")
'

printf '%s\n' "$expected" | docker run --rm --interactive --workdir / --entrypoint python "$image" -c "$check"
