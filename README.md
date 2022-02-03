# papel
<br>

A boilerplate tool based on Docker, designed to streamline the development and deployment of APIs and data pipelines.

Embedded with:
- FastAPI
- Celery + Rabbit-MQ + Flower
- Postgres + PGAdmin

<br>

#### Reference
This repository follows on the very complete [tiangolo/full-stack-fastapi-postgresql](https://github.com/tiangolo/full-stack-fastapi-postgresql) project, created by the maintainer of [FastAPI](https://github.com/tiangolo/fastapi).

Here, we have removed some backend (`Traeffik`) and frontend (authentication, UI with `vue.js`) elements, as we try to design a minimal and adaptive architecture. The goal being to simplify the implementation of data pipelines within existing systems.

<br>

#### Installation
You should use the `main` branch, other branches being used for development purpose.

You might have to tweak the `volumes` of the `papel_nginx` service to import your own certificate provider directory.
Same goes for the `api_test / api_prod` where you might use the shared `commons` to mount your data within `volumes`.

You have create the required `nginx` configuration files:
- `certificate.json`
- `app_docker.conf`
- `monitor_docker.conf`

Same goes with `servers.json` if you use the `pgadmin` container.

Then you're left with creating the `.env` environment file.

*NB: For all these required files, you'll find `xxxxxx.example` sample files ready to adapt.*

<br>

#### Run
Only the core containers
```
docker-compose -f docker-compose.core.yml up
```

\+ monitoring containers
```
docker-compose -f docker-compose.core.yml -f docker-compose.monitoring.yml up
```

\+ dummy app (including test container)
```
docker-compose -f docker-compose.core.yml -f docker-compose.monitoring.yml -f docker-compose.app.yml up
```
<br>

Docker is great but sometimes tricky ... when changes are made, don't forget to:
- Use the `--build` flag.
- Cleanse the database properly by using the `prune` and `rm` tools to purge volumes and containers.

<br>


#### Development
If you want to make some changes in this repo while following the same environment tooling.
```
poetry config virtualenvs.in-project true
poetry install && poetry shell
pre-commit install
```
