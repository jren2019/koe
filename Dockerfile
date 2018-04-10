FROM node:8 as webpack

WORKDIR /code
COPY package.json yarn.lock /code/
RUN yarn install

# separate installation of dependencies and the actual build into separate layers to speed-up rebuilding if source-code changes
FROM webpack as wp-build
COPY . /code
RUN yarn build-prod-posix


# Use an official Python runtime as a base image
FROM python:3

MAINTAINER Andrew Gilman

ENV PYTHONUNBUFFERED 1

ARG uid=1000

ARG http_proxy=""
ARG https_proxy=""

ENV http_proxy=$http_proxy
ENV https_proxy=$https_proxy

# backports needed to install ffmpeg
RUN echo 'deb http://httpredir.debian.org/debian jessie-backports main non-free \n\
deb-src http://httpredir.debian.org/debian jessie-backports main non-free' >> /etc/apt/sources.list

# Install extra packages.
RUN apt-get update && apt-get install -y --no-install-recommends vim mysql-client ffmpeg python-psycopg2 libxml2-dev libxmlsec1-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /

## Install any needed packages specified in requirements.txt
RUN pip install Cython numpy && pip install -r requirements.txt --no-cache-dir

# Make port 8000 available to the world outside this container
EXPOSE 8000

WORKDIR /code

COPY --from=wp-build /code .

ENTRYPOINT ["/bin/bash"]
CMD ["run_koe_app.sh"]