#!/usr/bin/env python3
"""
Checks of the Kubernetes example in deploy/k8s (the 'k8s-example' job of the CI, or by hand):

    kubectl kustomize deploy/k8s > rendered.yaml
    python3 scripts/check_k8s_example.py rendered.yaml deploy/k8s

The manifests are never applied by the CI, so this is what catches a typo before a reader does. It checks that
  - every container and init container of a Deployment or StatefulSet has CPU and memory requests and limits,
  - no manifest names anything specific to a cluster (see FORBIDDEN),
  - no image uses ':latest' or has no tag, and no volume is a hostPath,
  - the Secret example holds placeholders only (every value contains CHANGE_ME),
  - the wiring is complete: Service selectors and named ports, ConfigMaps, Secret keys and claims that a pod refers to.

The rendered file is the output of 'kubectl kustomize'; the optional files of deploy/k8s/optional are read as they are.
Needs PyYAML.
"""

import sys
from pathlib import Path

import yaml

FORBIDDEN = ("muzai.io", "tailscale", "ts.net", "traefik", "cert-manager")
WORKLOADS = ("Deployment", "StatefulSet")
SECRET_EXAMPLE = "secret.yaml.example"


def load(path):
    with open(path, encoding="utf-8") as handle:
        return [doc for doc in yaml.safe_load_all(handle) if doc]


def pod_spec(doc):
    return doc["spec"]["template"]["spec"]


def containers(doc):
    spec = pod_spec(doc)
    return spec.get("initContainers", []) + spec["containers"]


def check_resources(doc, where, errors):
    for container in containers(doc):
        resources = container.get("resources", {})
        for kind in ("requests", "limits"):
            for res in ("cpu", "memory"):
                if res not in resources.get(kind, {}):
                    errors.append(
                        f"{where}: {doc['kind']}/{doc['metadata']['name']}, container "
                        f"{container['name']}: no resources.{kind}.{res}"
                    )


def check_images_and_volumes(doc, where, errors):
    name = f"{where}: {doc['kind']}/{doc['metadata']['name']}"
    for container in containers(doc):
        image = container["image"]
        last = image.rsplit("/", 1)[-1]
        if "@sha256:" not in image and (":" not in last or last.endswith(":latest")):
            errors.append(f"{name}: image '{image}' needs an explicit tag (not latest)")
        if container.get("imagePullPolicy") != "IfNotPresent":
            errors.append(f"{name}: container {container['name']} needs imagePullPolicy: IfNotPresent")
    for volume in pod_spec(doc).get("volumes", []):
        if "hostPath" in volume:
            errors.append(f"{name}: volume {volume['name']} is a hostPath")


def check_secret_example(docs, errors):
    secrets = [d for d in docs if d["kind"] == "Secret"]
    if len(secrets) != 1:
        errors.append(f"{SECRET_EXAMPLE}: expected one Secret, found {len(secrets)}")
        return {}
    values = secrets[0].get("stringData", {})
    if secrets[0].get("data"):
        errors.append(f"{SECRET_EXAMPLE}: use stringData with placeholders, not data")
    for key, value in values.items():
        if "CHANGE_ME" not in str(value):
            errors.append(f"{SECRET_EXAMPLE}: {key} is not a CHANGE_ME placeholder")
    return {"name": secrets[0]["metadata"]["name"], "keys": set(values)}


def of_kind(docs, *kinds):
    return [d for d in docs if d["kind"] in kinds]


def check_volumes(doc, name, config_maps, claims, errors):
    spec = pod_spec(doc)
    declared = {v["name"] for v in spec.get("volumes", [])}
    declared |= {t["metadata"]["name"] for t in doc["spec"].get("volumeClaimTemplates", [])}
    for volume in spec.get("volumes", []):
        if "configMap" in volume and volume["configMap"]["name"] not in config_maps:
            errors.append(f"{name}: ConfigMap {volume['configMap']['name']} does not exist")
        claim = volume.get("persistentVolumeClaim", {}).get("claimName")
        if claim and claim not in claims:
            errors.append(f"{name}: claim {claim} does not exist")
    for container in containers(doc):
        for mount in container.get("volumeMounts", []):
            if mount["name"] not in declared:
                errors.append(f"{name}: {container['name']} mounts the unknown volume {mount['name']}")


def check_env(doc, name, config_maps, secret, errors):
    for container in containers(doc):
        for source in container.get("envFrom", []):
            if "configMapRef" in source and source["configMapRef"]["name"] not in config_maps:
                errors.append(f"{name}: ConfigMap {source['configMapRef']['name']} does not exist")
            if "secretRef" in source:
                errors.append(f"{name}: envFrom a Secret hands over every key, name the keys one by one")
        for env in container.get("env", []):
            ref = env.get("valueFrom", {})
            cm_ref, secret_ref = ref.get("configMapKeyRef"), ref.get("secretKeyRef")
            if cm_ref and cm_ref["key"] not in config_maps.get(cm_ref["name"], set()):
                errors.append(f"{name}: {env['name']} reads {cm_ref['name']}/{cm_ref['key']}, which does not exist")
            if secret_ref and (
                secret_ref["name"] != secret.get("name") or secret_ref["key"] not in secret.get("keys", set())
            ):
                errors.append(f"{name}: {env['name']} reads {secret_ref['name']}/{secret_ref['key']}, not in {SECRET_EXAMPLE}")


def check_workload(doc, config_maps, claims, secret, errors):
    name = f"{doc['kind']}/{doc['metadata']['name']}"
    labels = doc["spec"]["template"]["metadata"].get("labels", {})
    if any(labels.get(k) != v for k, v in doc["spec"]["selector"]["matchLabels"].items()):
        errors.append(f"{name}: the selector does not match the labels of its pods")
    check_volumes(doc, name, config_maps, claims, errors)
    check_env(doc, name, config_maps, secret, errors)


def check_service(service, workloads, errors):
    name = f"Service/{service['metadata']['name']}"
    selector = service["spec"]["selector"]
    targets = [
        w for w in workloads
        if selector.items() <= w["spec"]["template"]["metadata"].get("labels", {}).items()
    ]
    if not targets:
        errors.append(f"{name}: no Deployment or StatefulSet carries its selector {selector}")
        return
    port_names = {p["name"] for c in containers(targets[0]) for p in c.get("ports", []) if "name" in p}
    for port in service["spec"]["ports"]:
        if isinstance(port["targetPort"], str) and port["targetPort"] not in port_names:
            errors.append(f"{name}: targetPort {port['targetPort']} is not a named port of the pods")


def check_ingress(ingress, services, errors):
    for rule in ingress["spec"]["rules"]:
        for path in rule["http"]["paths"]:
            backend = path["backend"]["service"]["name"]
            if backend not in services:
                errors.append(f"Ingress/{ingress['metadata']['name']}: Service {backend} does not exist")


def check_wiring(docs, secret, errors):
    config_maps = {d["metadata"]["name"]: set(d.get("data", {})) for d in of_kind(docs, "ConfigMap")}
    claims = {d["metadata"]["name"] for d in of_kind(docs, "PersistentVolumeClaim")}
    workloads = of_kind(docs, *WORKLOADS)
    for doc in workloads:
        check_workload(doc, config_maps, claims, secret, errors)
    services = of_kind(docs, "Service")
    for service in services:
        check_service(service, workloads, errors)
    for ingress in of_kind(docs, "Ingress"):
        check_ingress(ingress, {s["metadata"]["name"] for s in services}, errors)


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    rendered, directory = argv[1], Path(argv[2])
    errors = []

    # the words that must not appear in any manifest of the directory (the README may explain what is left out)
    manifests = [p for p in sorted(directory.rglob("*")) if p.suffix in (".yaml", ".yml", ".example")]
    for path in manifests:
        text = path.read_text(encoding="utf-8").lower()
        errors += [f"{path}: contains '{word}'" for word in FORBIDDEN if word in text]

    docs = load(rendered)
    secret = check_secret_example(load(directory / SECRET_EXAMPLE), errors)
    optional = [(p, d) for p in manifests if p.parent.name == "optional" for d in load(p)]
    for doc in docs:
        if doc["kind"] in WORKLOADS:
            check_resources(doc, "render", errors)
            check_images_and_volumes(doc, "render", errors)
    for path, doc in optional:
        if doc["kind"] in WORKLOADS:
            check_resources(doc, str(path), errors)
            check_images_and_volumes(doc, str(path), errors)
    check_wiring(docs + [d for _, d in optional], secret, errors)

    kinds = sorted({d["kind"] for d in docs})
    print(f"{len(docs)} objects in the render ({', '.join(kinds)}), {len(optional)} in optional/, {len(manifests)} manifest files read")
    if errors:
        print("\n".join(f"ERROR {e}" for e in errors))
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main(sys.argv)
