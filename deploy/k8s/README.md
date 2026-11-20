# brif on Kubernetes: an example

A small, generic set of manifests to run brif's own pieces on any Kubernetes cluster: the API, the Celery worker, PostgreSQL,
RabbitMQ and Cantaloupe. Plain YAML with a `kustomization.yaml`: no Helm, no operator, nothing to install first.

It is an example to start from, not a product. One replica of everything, no high availability, no backups, no autoscaling.
Read [What is not here](#what-is-not-here) and [Status](#status) before you rely on it.

## What is here

| File | What it holds |
|---|---|
| `kustomization.yaml` | what `kubectl apply -k` applies, the namespace, and a commented block to pin images by digest |
| `namespace.yaml` | the namespace `brif` |
| `configmap.yaml` | the settings that are not secret (`brif-config`): database name, public domain, where Cantaloupe is, data directory |
| `secret.yaml.example` | the shape of the Secret `brif-secret`, placeholders only (you copy it, see [Apply](#apply)) |
| `data.yaml` | the claim `brif-data`: the data directory of the API and the worker |
| `postgres.yaml` | PostgreSQL 17 (StatefulSet, Service `db`), and the init script that creates the application role and database |
| `rabbitmq.yaml` | RabbitMQ 4 with the management plugin (StatefulSet, Service `rabbitmq`) |
| `cantaloupe.yaml` | Cantaloupe (Deployment, Service `cantaloupe`), its properties as a ConfigMap, the claims for the images and the cache |
| `backend.yaml` | the API: `uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers` (Deployment, Service `backend`) |
| `celery.yaml` | the worker: `celery --app=worker.celery worker --loglevel=info` (the same image as the API) |
| `optional/flower.yaml` | **optional**: Flower, to watch the worker |
| `optional/ingress.yaml` | **optional, an example**: a plain Ingress with `example.org` host names |

## What is not here

- **A search engine.** brif does not use one: it turns your datasets into IIIF manifests and serves them. Searching a collection
  is left to another tool, see the main README.
- **Anything specific to a cluster:** no ingress controller or route, no certificate issuer, no DNS, no VPN. `optional/ingress.yaml`
  is a plain `networking.k8s.io/v1` Ingress to adapt.
- **Backups, monitoring, NetworkPolicies, autoscaling, high availability.** Your data is in four volumes (see
  [Data and images](#data-and-images)) and you decide how to copy them off the cluster.
- **docker compose.** The compose files of the repository are for local use. This folder does not use them.

## Apply

You need a cluster with a default StorageClass (the claims do not name one) and `kubectl`.

1. In `configmap.yaml`, set `BASE_URL` and `APP_SUBDOMAIN` to your domain. They end up in the URLs written into the IIIF manifests
   (`https://<APP_SUBDOMAIN>.<BASE_URL>` and `https://cantaloupe.<BASE_URL>`), so set them **before** you generate manifests.
2. Create the namespace, then the Secret:

   ```
   kubectl apply -f deploy/k8s/namespace.yaml
   cp deploy/k8s/secret.yaml.example deploy/k8s/secret.yaml
   # edit deploy/k8s/secret.yaml: replace every CHANGE_ME (the file is git-ignored)
   kubectl apply -f deploy/k8s/secret.yaml
   ```

   The Secret is applied by itself, and is not in `kustomization.yaml`, so that `kubectl kustomize` never prints a real value and
   the folder renders without it. The RabbitMQ password appears twice in it (`RABBITMQ_DEFAULT_PASS` and inside
   `CELERY_BROKER_URL`): the two must match.
3. Apply everything else:

   ```
   kubectl apply -k deploy/k8s
   kubectl -n brif get pods --watch
   ```

   The first start takes a minute or two: PostgreSQL runs its init script once, the API and the worker wait for the database
   and for RabbitMQ (init containers), then start.

To look at what would be applied, without a cluster: `kubectl kustomize deploy/k8s`.

To remove it: `kubectl delete -k deploy/k8s` deletes the namespace `brif` and **everything in it**, the volumes (your data) and
the Secret included. To keep the data, delete only the Deployments and StatefulSets instead.

### Check that it runs

```
kubectl -n brif port-forward svc/backend 8000:8000
```

Then open `http://localhost:8000/docs` (the API) and `http://localhost:8000/demo` (the dashboard, empty until you add a dataset).
The worker logs `celery@... ready.` once it is connected: `kubectl -n brif logs deploy/celery`.

## Data and images

Two volumes hold what you bring. Both start empty.

**`brif-data`**, mounted at `/opt/data` in the API and the worker (`DATA_DIR`):

```
/opt/data/input/<dataset directory>/<dataset>.csv     your datasets, and an optional mapping.json
/opt/data/output/<dataset directory>/...              written by the pipeline: the split records and the IIIF manifests
```

**`cantaloupe-images`**, mounted at `/mnt/directories` in Cantaloupe: the images, in one directory per dataset directory, named
as in `brif-data`: `/mnt/directories/<dataset directory>/<image>`. brif asks Cantaloupe for `<dataset directory>%2F<image>`.

The repository has a tiny sample (see "Data and images sample" in the main README). To copy it in, from the root of the repository:

```
BACKEND=$(kubectl -n brif get pod -l app.kubernetes.io/name=backend -o jsonpath='{.items[0].metadata.name}')
kubectl -n brif cp setup/app/input_sample/test_dataset "$BACKEND":/opt/data/input/test_dataset

unzip setup/cantaloupe/test_images.zip -d sample-images
CANTALOUPE=$(kubectl -n brif get pod -l app.kubernetes.io/name=cantaloupe -o jsonpath='{.items[0].metadata.name}')
kubectl -n brif cp sample-images/test_dataset "$CANTALOUPE":/mnt/directories/test_dataset
```

`kubectl cp` needs `tar` in the container (both images are Debian based and have it). For a real collection, fill the claim in whatever way suits you
(a one-off pod that mounts it, `rsync`, a restore), or point Cantaloupe at another source (S3, HTTP, ...): the sections of
`setup/cantaloupe/cantaloupe.properties.example` that the ConfigMap leaves out show how.

Keep the originals of your datasets elsewhere: `output/` can be generated again from `input/`, but `input/` lives only here.

The four volumes: `brif-data`, `cantaloupe-images`, `cantaloupe-cache` (a cache: it can be deleted), and the two created by the
StatefulSets, `data-postgres-0` (the database) and `data-rabbitmq-0` (the queue). `brif-data` and the database are what you back up.
A logical dump of the database, for instance: `kubectl -n brif exec postgres-0 -- pg_dump -U postgres brif > brif.sql`.

## How the pieces talk to each other

```
browser or IIIF viewer           (through your own Ingress)
   |
   |--> backend ---------> db <--------+
   |       |                           |
   |       +--> rabbitmq ---> celery --+--> cantaloupe
   |                                           ^
   +-------------------------------------------+
```

| From | To | What for | Set by |
|---|---|---|---|
| backend | `db:5432` | the dashboard table and the dataset status | `DB_NAME`, `DB_USER`, `DB_PASSWORD`; the host name `db` is fixed in `app/src/db/database.py`, so the Service must keep its name |
| backend, celery | `rabbitmq:5672` | send the tasks (backend), receive them (celery); results come back the same way | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` |
| celery | `db:5432` | read and write the dataset status | as backend |
| celery, backend | `cantaloupe:8182` | check every image through the IIIF Image API while the manifests are built | `API_IMAGE_BACKEND` |
| backend, celery | `brif-data` | read `input/`, write `output/`, serve the manifests | `DATA_DIR` |
| cantaloupe | `cantaloupe-images` | read the images | `FilesystemSource.BasicLookupStrategy.path_prefix` in the properties |
| a browser or a IIIF viewer | backend, cantaloupe | read the manifests and the images, from outside | your Ingress, `BASE_URL`, `APP_SUBDOMAIN` |

Only the Services inside the namespace are reachable by name (`db`, `rabbitmq`, `cantaloupe`, `backend`). Nothing is exposed
outside the cluster by this folder.

Because `brif-data` is a ReadWriteOnce claim shared by the API and the worker, `celery.yaml` asks to be scheduled on the node of the
API (`podAffinity`); on a single-node cluster that changes nothing. With a ReadWriteMany class, change the claim and delete that block.

## Pin the images by digest

The manifests name the images by tag, which is readable but not immutable: a tag can be moved. A real deployment pins
`tag@digest`, so that every pod runs exactly the build you looked at.

- `ghcr.io/pierrz/brif-backend` and `ghcr.io/pierrz/brif-cantaloupe` are built by the CI of this repository on every push to `main`.
  Their tags are the full commit SHA (a `latest` tag exists and follows `main`: do not use it). The manifests name one commit;
  take a newer one when you update, and rebuild your own images if you change the code (`setup/app/Dockerfile`,
  `setup/cantaloupe/Dockerfile`).
- `postgres`, `rabbitmq`, `busybox` (the wait init containers) and `mher/flower` come from Docker Hub with a version tag.

Read the digest of a tag, for any of them:

```
docker buildx imagetools inspect ghcr.io/pierrz/brif-backend:020da48013e9c61676b9b3911d4d0c8285d9de27   # the "Digest:" line
crane digest postgres:17.12-bookworm                                                                     # if you have crane
kubectl -n brif get pods -o jsonpath='{range .items[*]}{.status.containerStatuses[*].imageID}{"\n"}{end}'  # what runs now
```

For the two brif images the job summary of the CI run on `main` also prints `ghcr.io/pierrz/<image>@sha256:...`.

Then either write `image: name:tag@sha256:...` in the manifests, or leave them and uncomment the `images:` block of
`kustomization.yaml`: kustomize renders `name:tag@sha256:...` (check with `kubectl kustomize deploy/k8s | grep image:`). Keep the
tag next to the digest: Kubernetes pulls by digest, and the tag tells a reader which version it is.

## Changing the configuration

- `configmap.yaml` (`brif-config`) is read when a pod starts: after a change, `kubectl -n brif rollout restart deploy/backend deploy/celery`.
- The Cantaloupe properties are mounted as a single file (`subPath`), which Kubernetes does not update in a running pod:
  `kubectl -n brif rollout restart deploy/cantaloupe` after a change.
- The PostgreSQL init script and the RabbitMQ user and password are used **once**, on an empty volume. Changing them later does
  not change an existing database or broker.
- Changing a major version of PostgreSQL or RabbitMQ needs a procedure of its own (dump and restore, feature flags): changing the
  tag is not enough.

## Security notes

- **The API has no login.** Among others, `/delete_dataset/...` and `/process_dataset/...` act on a plain GET. Do not expose
  the API host to the Internet as it is: put an authentication in front of it (at your Ingress controller), or keep it on a private
  network, and publish only the manifests and Cantaloupe if you need public IIIF. Flower has no login either.
- Passwords and keys are in a Secret that you create. A Secret is not encrypted by Kubernetes unless you enable encryption at
  rest, and anyone who can read Secrets in the namespace can read these.
- Each container gets only the keys of the Secret that it needs: the API and the worker receive the application database password
  and the broker URL (which holds the RabbitMQ password), not the PostgreSQL superuser password.
- The pods use the runtime default seccomp profile, forbid privilege escalation where the images allow it, and do not mount a
  service account token. The brif images run as root, as built; no NetworkPolicy is included, so any pod of the cluster can reach
  the Services. Add policies if your network plugin enforces them.

## Status

Written from the repository's own `docker-compose.yml` and Dockerfiles, and checked by the `k8s-example` job of the CI
(`.github/workflows/ci.yml`): `kubectl kustomize deploy/k8s` must render, every container must have resource requests and limits,
nothing may refer to a particular cluster, and the references between the objects (Services, ConfigMaps, Secret keys, claims) must
resolve (`scripts/check_k8s_example.py`). The CI does **not** apply the manifests to a cluster.

Specifically:

- The init script of PostgreSQL was run against a throwaway PostgreSQL 16 server; the images, the probes and the rest were not run.
- brif's own tests (`bash scripts/test.sh`) use RabbitMQ 3.8 as their broker; this example uses RabbitMQ 4.4.
- Flower is optional and was not run against RabbitMQ 4.

If you find that something does not work on your cluster, an issue or a pull request is welcome.
