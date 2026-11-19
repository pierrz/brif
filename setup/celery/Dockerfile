# same base as setup/app/Dockerfile (Python 3.14 on Debian 13, pinned by digest)
FROM python:3.14-slim@sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100

RUN pip install uv==0.13.5

# Copy only requirements to cache them in docker layer
WORKDIR /opt/celery_app/
COPY ./app/pyproject.toml ./app/uv.lock /

# Project initialization: the packages of uv.lock without the dev tools, into the interpreter of the image
# (uv finds the project in the parent directory /, as Poetry did)
RUN uv export --frozen --no-dev --no-hashes --no-emit-project --output-file /tmp/uv-requirements.txt \
  && uv pip install --system --no-cache --requirement /tmp/uv-requirements.txt \
  && rm /tmp/uv-requirements.txt

COPY ./app .

ENV PYTHONPATH=/opt/celery_app

CMD ["celery", "--app=worker.celery", "worker", "--loglevel=info", "--logfile=logs/celery.log"]
