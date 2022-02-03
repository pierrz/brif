# brif
<br>

A boilerplate tool based on Docker, designed to streamline the development and deployment of IIIF compliant platforms.

Embedded with:
- FastAPI
- Celery + Rabbit-MQ + Flower
- Postgres + PGAdmin
- Nginx

IIIF features:
- Cantaloupe image server <=> Image API 2.1
- FastAPI implementation <=> Presentation API 2.1
- Automated manifest creation from CSV files
- IIIF manifests creation based on [Prezi](https://github.com/iiif-prezi/iiif-prezi)
- [Tify viewer](https://github.com/tify-iiif-viewer/tify)

<br>

### Reference
This repository is based on the [Papel](https://github.com/pierrz/papel) template repository designed to quickly deploy API based pipelines. 
<br>

### Installation
#### Backend
You should use the `main` branch, other branches being used for development purpose.

Fetch all the Git LFS resources: `git lfs fetch --all && git lfs pull`

You might have to tweak the `volumes` of the `brif_nginx` service to import your own certificate provider directory.

You have to create the required `nginx` configuration files:
- `certificate.json`
- `app_docker.conf`
- `monitor_docker.conf`

Same goes with `servers.json` if you use the `pgadmin` container.

Then you're left with creating the `.env` environment file.

*NB: For all these required files, you'll find `xxxxxx.example` sample files ready to adapt.*

<br>

#### Cantaloupe
Mount your images as volumes in the `cantaloupe` service and set `FilesystemSource.BasicLookupStrategy.path_prefix` in `cantaloupe.properties` accordingly to get things going.
You will also have to implement this location in `./setup/cantaloupe/Dockerfile`.
From there, you can easily set your logs, enable/disable different API version number (i.e. from to 3) as it follows the very [official documentation](https://cantaloupe-project.github.io/).


#### Frontend
You can add your own `head_meta.html`, or discard it from `base.html` while implementing up the `{title}` tag again.


#### Data
You just need to copy your datasets in `data/input`, and the dashboard should automatically pick them up.

Each directory can contain multiple datasets, and they will be treated separately.

Each directory can contain one `mapping.json` file to implement a specific mapping for the data pipeline. If not present, a default mapping will be applied.


#### Run
Only the core containers
```
docker-compose docker-compose.yml up
```

\+ monitoring containers
```
docker-compose -f docker-compose.core.yml -f docker-compose.monitoring.yml up
```

\+ with Brif app (including test container)
```
docker-compose -f docker-compose.core.yml -f docker-compose.monitoring.yml -f docker-compose.brif.yml up
```

\+ only live containers (tagged with 'prod_live' profile)
```
docker-compose -f docker-compose.core.yml -f docker-compose.monitoring.yml -f docker-compose.brif.yml --profile live_prod up
```
<br>

Docker is great but sometimes tricky ... when changes are made, don't forget to:
- Use the `--build` flag.
- Cleanse the database properly by using the `prune` and `rm` tools to purge volumes and containers.

<br>

#### Results
Once processed, all manifests can be accessed with their based URI followed by `/manifest.json` to access the data or either `/view` for the Tify viewer.
Each processed dataset also gets a collection manifest gathering all its manifests URIs.

<br>

#### Development
If you want to make some changes in this repo while following the same environment tooling.
```
poetry config virtualenvs.in-project true
poetry install && poetry shell
pre-commit install
```


## DRAFT

locally: data/input folder
local param / volumes
data workflow explanations
