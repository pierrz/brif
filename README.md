# brif

A boilerplate tool based on Docker, designed to streamline the development and deployment of IIIF compliant platforms.

Embedded with `FastAPI, Celery + Rabbit-MQ + Flower, Postgres + PGAdmin, Cantaloupe, Bulma`
and provided with an example configuration for `Nginx`.

**NB:** _This tool is not actively maintained annd you might encounter some issues during the `docker compose build` phase. 
Overall, it's mostly a matter of dependencies to update and some `Dockerfiles` to refine._

### IIIF features:
- Cantaloupe image server <=> Image API 2.1
- FastAPI implementation <=> Presentation API 2.1
- Automated manifest creation from CSV files
- IIIF manifests creation based on [Prezi](https://github.com/iiif-prezi/iiif-prezi)
- [Tify viewer](https://github.com/tify-iiif-viewer/tify) directly embedded with each manifest

<br>

---

### Table of Contents
- [Creative material](#creative-material)
- [Installation](#installation)
    - [Backend](#backend)
    - [Cantaloupe](#cantaloupe)
    - [Frontend](#frontend)
    - [Data](#data)
- [Test](#test)
- [Run](#run)
- [Manual](#manual)
  - [Notes](#notes)
  - [Data and images sample](#data-and-images-sample)
  - [Docs & Monitoring](#docs--monitoring)
  - [Dashboard UI](#dashboard-ui)
- [Development](#development)

<br>

---


### Creative material
The tiny dataset and 6 related images used in the demo are released as copyright-free materials, and come from the Finnish National Gallery [Open Data platform](https://www.kansallisgalleria.fi/en/api-sovelluskehittajille).

<br>

### Installation
#### Backend
You should use the `main` branch, other branches being used for development purpose.

Fetch all the Git LFS resources: `git lfs install && git lfs fetch --all && git lfs pull`

If you want to use Nginx, you can just create a symbolic link
from `setup/all_containers.conf` to the Nginx websites directories in `/etc/nginx/sites-*` in your machine, and tweak the the provided example configuration with the correct Docker containers IPs
and relevant references to your certificates.
From the repository root, use this command to retrieve these IPs:
```
docker compose ps -q | xargs docker inspect -f '{{.Name}} - {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
```


Same goes with [servers.json](setup/pgadmin/servers.json.example) if you use the `pgadmin` container.

Then you're left with creating the `.env` environment file.

*NB: For all these required files, you'll find `xxxxxx.example` sample files ready to adapt.*

<br>

#### Cantaloupe
Mount your images as volumes in the `cantaloupe` service and set `FilesystemSource.BasicLookupStrategy.path_prefix` in [cantaloupe.properties](setup/cantaloupe/cantaloupe.properties.example) accordingly to get things going.
From there, you can easily set your logs, enable/disable different API version number (i.e. from to 3) as it follows the very [official documentation](https://cantaloupe-project.github.io/).

<br>

#### Frontend
You can add your own [head_meta.html](app/templates/html/head_meta.html.example), or discard it from `base.html` while implementing up the `{title}` tag again.

<!-- There is a template to use along your chosen analytics provider. 
In our case it is [head_meta.html](app/templates/html/head_meta.html.example) -->

<br>

#### Data
You just need to copy your datasets in `data/input`, and the dashboard should automatically pick them up. 

Or change accordingly in docker's [x-brif-common](docker-compose.brif.yml) 

Each directory can contain multiple datasets, and they will be treated separately. Each directory can have only 1 specific mapping.

Each directory can contain one [mapping.json](app/src/mappings/default_mapping_csv.json) file to implement a specific mapping for the data pipeline. If not present, a default mapping will be applied.

<br>

### Test
To check your installation, run the following command.
```
docker-compose docker-compose.yml api_test up
```

**NB:** You will need to import the provided data and image samples for all the tests to pass. 
See in [Section](#data-and-images-sample) for further details.

### Run
Only the main containers
```
docker-compose up
```

\+ monitoring containers
```
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up
```

\+ with Brif app (including test container)
```
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up
```

<br>

Docker is great but sometimes tricky ... when changes are made, don't forget to:
- Use the `--build` flag.
- Cleanse the database properly by using the `prune` and `rm` tools to purge volumes and containers.

<br>

### Manual

##### Notes

This tool is not meant to search within the collection, only to transform the raw data into valid IIIF manifests.

To browse further the collection you will probably need to import the transformed data into a search engine such as Elasticsearch or Solr.

Each transformed dataset comes with a new `collection` dataset which gathers all the transformed IIIF manifests URLs, thus making it easy to import the related data within your system.

<br>

##### Data and images sample
To make it easier to test this tool in action, we included both data and image samples.

You should import them in the locations you for chose these elements, 
which can be set up via the paramenters `DATA_DIR` and `CONTENT_DIR` in the `.env` file.

Find the files in the `setup` directory:
- `setup/app/input_sample/test_dataset/test_records.csv`
- `setup/cantaloupe/test_images.zip`


##### Docs & Monitoring
You can find the Swagger UI for the whole tool at the `/docs` url. Some endpoints are voluntarily not presented there, look for `include_in_schema=False` for the exclusions if necessary.

The tool comes with optional monitoring services (Flower and PGAdmin) to monitor further your Postgres database and the tasks going through the pipeline.

<br>

##### Dashboard UI

At startup, a dashboard is directly accessible at the url `/dashboard`
- The dashboards is a basic UI to manage your datasets and check the transformed collections. 
- It shows some stats, along with sample links.

The workflow is relatively simple:
- The whole dataset is itemised.
- A dedicated IIIF Image API is spinned up based on the provided images.
- Each new item/record is transformed into a IIIF manifest.
- A new collection dataset is created which gathers all the IIIF manifests urls.

Once processed, all manifests can be accessed with their base URI followed by `/manifest.json` to access the data or either `/view` for the Tify viewer.

<br>

### Development
If you want to make some changes in this repo while following the same environment tooling.
```
poetry config virtualenvs.in-project true
poetry install && poetry shell
pre-commit install
```
