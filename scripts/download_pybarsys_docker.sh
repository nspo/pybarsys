#!/bin/bash

# Download pybarsys setup files and set it up for usage with Docker Compose in the current folder
set -eu

### Helper functions

# prompt for confirmation from user
prompt_confirm() {
  while true; do
    read -r -n 1 -p "${1:-Continue?} [y/n]: " REPLY
    case $REPLY in
      [yY]) echo; return 0 ;;
      [nN]) echo; return 1 ;;
      *) printf " \033[31m %s \n\033[0m" "invalid input"
    esac
  done
}

# helpers for comparing version strings
version_string_lte() {
    [ "$1" = "$(echo -e "$1\n$2" | sort -V | head -n1)" ]
}

version_string_lt() {
    [ "$1" = "$2" ] && return 1 || version_string_lte "$1" "$2"
}

###

### Variables
DIRECTORY="$(pwd)/"
# PYBARSYS_BASE_URL can be set to download from another branch/commit (used by CI)
BASE_URL="${PYBARSYS_BASE_URL:-https://raw.githubusercontent.com/nspo/pybarsys/master/}"
DOCKER_COMPOSE_VERSION_MIN="1.27.1"
DOCKER_COMPOSE_INSTALL_URL="https://docs.docker.com/compose/install/"
###

echo "[Pybarsys installer]"
echo "[INFO] This script will set up pybarsys for usage with Docker Compose in the current folder: $DIRECTORY"
echo "[INFO] Files will be downloaded from: $BASE_URL"

# check whether current dir is empty
if [ "$(ls -A "$DIRECTORY")" ]; then
    echo "[ERROR] The current directory is not empty but pybarsys can only be installed into an empty directory to not override any files. Aborting."
    exit 1
fi

# Determine Compose command
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
    DOCKER_COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || docker compose version | awk '{print $4}' | sed 's/v//')
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
    DOCKER_COMPOSE_VERSION=$(docker-compose --version | awk '{print $3}' | sed 's/,//')
else
    echo "[ERROR] Neither 'docker compose' nor 'docker-compose' could be found."
    echo "[ERROR] Please install Docker and Docker Compose first: $DOCKER_COMPOSE_INSTALL_URL"
    exit 1
fi

echo "[INFO] Using Compose command: $COMPOSE_CMD"
echo "[INFO] Compose version: $DOCKER_COMPOSE_VERSION"

# check whether compose is up-to-date
if version_string_lt "$DOCKER_COMPOSE_VERSION" "$DOCKER_COMPOSE_VERSION_MIN"; then
    echo "[ERROR] Docker Compose is outdated. Your version is $DOCKER_COMPOSE_VERSION but the minimum is $DOCKER_COMPOSE_VERSION_MIN."
    echo "[ERROR] Please update Docker Compose: $DOCKER_COMPOSE_INSTALL_URL"
    exit 1
fi

prompt_confirm "Continue?" || exit 1

echo "[INFO] Setting up nginx configuration and docker-compose.yml"
mkdir nginx
curl -sSL "$BASE_URL/nginx/pybarsys.conf" -o nginx/pybarsys.conf
curl -sSL "$BASE_URL/docker-compose.yml" -o docker-compose.yml

echo "[INFO] Installing .env configuration file and generating custom SECRET_KEY"
curl -sSL "$BASE_URL/.env.example" | grep -v SECRET_KEY > .env
echo "SECRET_KEY=$(tr -dc 'a-z0-9!@#%^&*(-_=+)' < /dev/urandom | head -c50)" >> .env

echo "[INFO] Creating empty database file so it can be mounted into container"
touch db.sqlite3

echo "------"
echo "[INFO] Yay! Pybarsys was successfully set up in the current folder."
echo "[INFO] To start pybarsys, run:"
echo
echo "       sudo $COMPOSE_CMD up"
echo
echo "[INFO] If everything works, cancel with CTRL+C and start it in the background with:"
echo
echo "       sudo $COMPOSE_CMD up -d"
