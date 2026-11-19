# Python 3.14 on Debian 13 (python:3.14-slim, 3.14.10 when it was pinned, 2026-11-19), pinned by digest of the
# multi-platform index: read it again with 'docker buildx imagetools inspect python:3.14-slim' to move it.
# The former base, tiangolo/uvicorn-gunicorn-fastapi, has no tag after python3.11 (checked 2026-11-19).
# uvicorn comes from app/uv.lock; gunicorn is not installed: the cluster and docker-compose start uvicorn.
FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100

RUN pip install uv==0.13.5

WORKDIR /opt/app

# install npm dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends npm \
    && rm -rf /var/lib/apt/lists/* \
    && cd /tmp \
    && npm install tify@0.31.0 bulma@1.0.2 @creativebulma/bulma-tooltip@1.2.0

# Copy only requirements to cache them in docker layer
COPY ./app/pyproject.toml ./app/uv.lock ./

# Project initialization: the packages of uv.lock without the dev tools, into the interpreter of the image
RUN uv export --frozen --no-dev --no-hashes --no-emit-project --output-file /tmp/uv-requirements.txt \
    && uv pip install --system --no-cache --requirement /tmp/uv-requirements.txt \
    && rm /tmp/uv-requirements.txt

# Creating folders and files for the project:
COPY ./app ./

# Copy vue, tify and bulma
RUN cd /tmp/node_modules \
    && cp bulma/css/bulma.min.css /opt/app/static/css \
    && cp -r tify/dist /opt/app/static/tify \
    && cp \@creativebulma/bulma-tooltip/dist/bulma-tooltip.min.css /opt/app/static/css

# What the cluster runs (it passes its own command): the API, behind the proxy that sets X-Forwarded-Proto
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
