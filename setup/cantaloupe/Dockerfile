FROM debian:latest

ENV JAVA_HOME=/opt/jdk
ENV PATH=$PATH:/opt/jdk/bin

# install java
RUN apt-get clean \
    && apt-get update \
    && apt-get install -qy unzip wget

RUN apt update \
    && apt install -qy default-jdk

# install cantaloupe
RUN cd /tmp \
    && wget https://github.com/cantaloupe-project/cantaloupe/releases/download/v5.0.4/cantaloupe-5.0.4.zip \
    && unzip cantaloupe-5.0.4.zip \
    && mv cantaloupe-5.0.4 /cantaloupe

# import libjpeg-turbo library
RUN mkdir -p /opt/libjpeg-turbo/lib
COPY ./setup/cantaloupe/libjpeg-turbo-2.1.1.tar.gz /tmp/libjpeg-turbo-2.1.1.tar.gz
RUN cd /tmp \
    && tar -xvzf libjpeg-turbo-2.1.1.tar.gz \
    && mv libjpeg-turbo-2.1.1 /opt/libjpeg-turbo/lib

# load test images
COPY ./setup/cantaloupe/test_images.zip .
RUN mkdir -p /mnt/fres/dsets/directories \
    && unzip test_images.zip -d /mnt/fres/dsets/directories

# set & start cantaloupe
COPY ./setup/cantaloupe/cantaloupe.properties /cantaloupe/cantaloupe.properties
CMD cd /cantaloupe \
    && java -Dcantaloupe.config=/cantaloupe/cantaloupe.properties -Xmx2g -jar /cantaloupe/cantaloupe-5.0.4.jar
