FROM python:3.8

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100

RUN pip install poetry

# Copy only requirements to cache them in docker layer
WORKDIR /opt/celery_app/
COPY ./app/pyproject.toml ./app/poetry.lock* /

# Project initialization:
RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi --no-dev

COPY ./app .

ENV PYTHONPATH=/opt/celery_app

CMD celery --app=worker.celery worker --loglevel=info --logfile=logs/celery.log
