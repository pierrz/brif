FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8

ENV PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100

RUN pip install uv==0.13.5

WORKDIR /opt/app

# install npm dependencies
RUN apt update \
    && apt install -y npm \
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
