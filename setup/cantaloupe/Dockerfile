# Cantaloupe image server of brif (INFRA-237).
# Pinned: the base by digest, the release zip by sha256 (GitHub publishes no checksum, so the value is the one read from the
# release on 2026-11-19: a bump changes both ARGs and nothing else).
FROM debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2

ARG CANTALOUPE_VERSION=5.0.8
ARG CANTALOUPE_SHA256=092df7bd53c3dc56af4610ef9c2d258e836438f7a00718b1ac3705ab29252291

# JRE only: 5.0.8 is tested on Java 21 and 25, and trixie ships 21. Fonts for the text overlays. wget and unzip fetch and
# open the release. No libturbojpeg: this keeps the image processors the 5.0.4 image had, so the answers stay the same
# (5.0.8 would use a system libturbojpeg if one were installed).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates wget unzip openjdk-21-jre-headless fontconfig fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# install cantaloupe: check the zip against the pinned hash, keep only the jar under a version-neutral name
RUN cd /tmp \
    && wget -q "https://github.com/cantaloupe-project/cantaloupe/releases/download/v${CANTALOUPE_VERSION}/cantaloupe-${CANTALOUPE_VERSION}.zip" \
    && echo "${CANTALOUPE_SHA256}  cantaloupe-${CANTALOUPE_VERSION}.zip" | sha256sum -c - \
    && unzip -q "cantaloupe-${CANTALOUPE_VERSION}.zip" \
    && mkdir -p /cantaloupe \
    && mv "cantaloupe-${CANTALOUPE_VERSION}/cantaloupe-${CANTALOUPE_VERSION}.jar" /cantaloupe/cantaloupe.jar \
    && rm -rf /tmp/cantaloupe-*

# 5.0.8 writes no log with its own logback.xml (see the file): ours is upstream's fix
COPY ./setup/cantaloupe/logback.xml /cantaloupe/logback.xml

# load test images
# COPY ./setup/cantaloupe/test_images.zip .
# RUN mkdir -p /mnt/fres/dsets/directories \
#    && unzip test_images.zip -d /mnt/fres/dsets/directories

# set & start cantaloupe
# cantaloupe.properties is mounted at runtime via k8s ConfigMap
# If running locally, mount or COPY the file manually
WORKDIR /cantaloupe
CMD ["java", "-Dcantaloupe.config=/cantaloupe/cantaloupe.properties", "-Dlogback.configurationFile=/cantaloupe/logback.xml", "-Xmx2g", "-jar", "/cantaloupe/cantaloupe.jar"]
