FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100

RUN pip install poetry

WORKDIR /opt/app

# install npm dependencies
RUN apt update \
    && apt install -y npm \
    && cd /tmp \
    && npm install tify bulma @creativebulma/bulma-tooltip

# Copy only requirements to cache them in docker layer
COPY ./app/pyproject.toml ./app/poetry.lock* ./

# Project initialization:
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-dev

# Creating folders and files for the project:
COPY ./app ./

# Copy vue, tify and bulma
RUN cd /tmp/node_modules \
    && cp bulma/css/bulma.min.css /opt/app/static/css \
    && cp -r tify/dist /opt/app/static/tify \
    && cp \@creativebulma/bulma-tooltip/dist/bulma-tooltip.min.css /opt/app/static/css
