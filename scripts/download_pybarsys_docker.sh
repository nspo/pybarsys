#!/bin/bash

# Download pybarsys setup files and set it up for usage with docker-compose in the current folder
set -eu

### Helper functions

# prompt for confirmation from user
prompt_confirm() {
  while true; do
    read -r -n 1 -p "${1:-Continue?} [y/n]: " REPLY
    case $REPLY in
      [yY]) echo ; return 0 ;;
      [nN]) echo ; return 1 ;;
      *) printf " \033[31m %s \n\033[0m" "invalid input"
    esac
  done
}

# helpers for comparing version strings
version_string_lte() {
    [  "$1" = "`echo -e "$1\n$2" | sort -V | head -n1`" ]
}

version_string_lt() {
    [ "$1" = "$2" ] && return 1 || version_string_lte $1 $2
}

###

### Variables
DIRECTORY=$(pwd)/
#BASE_URL=https://raw.githubusercontent.com/nspo/pybarsys/master/
BASE_URL=https://raw.githubusercontent.com/nspo/pybarsys/feature/docker/
DOCKER_COMPOSE_VERSION_MIN=1.27.1 # min version to have docker-compose schema version 3.9
DOCKER_COMPOSE_INSTALL_URL=https://docs.docker.com/compose/install/
###

echo "[Pybarsys installer]"
echo "[INFO] This script will set up pybarsys for usage with docker-compose in the current folder: $DIRECTORY"

# check whether current dir is empty
if [ "$(ls -A $DIRECTORY)" ]; then
    echo "[ERROR] The current directory is not empty but pybarsys can only be installed into an empty directory to not override any files. Aborting."
    exit 1
fi

# check if docker-compose is installed
if ! command -v docker-compose &> /dev/null
then
    echo "[ERROR] docker-compose could not be found. Please install docker and docker-compose first: $DOCKER_COMPOSE_INSTALL_URL"
    exit 1
fi

# check whether docker-compose is up-to-date
DOCKER_COMPOSE_VERSION=$(docker-compose --version | awk '{print $3}' | sed 's/,//')
if version_string_lt $DOCKER_COMPOSE_VERSION $DOCKER_COMPOSE_VERSION_MIN ; then
    echo "[ERROR] docker-compose is outdated. Your version is $DOCKER_COMPOSE_VERSION but the minimum is $DOCKER_COMPOSE_VERSION_MIN. Please update docker-compose: $DOCKER_COMPOSE_INSTALL_URL"
    exit 1
fi

prompt_confirm "Continue?" || exit 1

# download nginx and docker-compose files
mkdir nginx
wget $BASE_URL/nginx/pybarsys.conf -O nginx/pybarsys.conf
wget $BASE_URL/docker-compose.yml

# download .env example and generate a SECRET_KEY
wget $BASE_URL/.env.example -O- | grep -v SECRET_KEY > .env
echo SECRET_KEY=$(tr -dc 'a-z0-9!@#$%^&*(-_=+)' < /dev/urandom | head -c50) >> .env

# create empty db file so it can be mounted into container
touch db.sqlite3

echo "[INFO] Yay! Pybarsys was successfully set up in the current folder."
echo "[INFO] To start pybarsys, run 'sudo docker-compose up' in the current folder."
echo "[INFO] If everything works, cancel with CTRL+C and start it in the background with 'sudo docker-compose up -d'"
