#!/bin/bash

# Run a simple test server to test local non-docker pybarsys setup
set -eu

# cd to root folder
cd "${0%/*}/.."

scripts/prepare_pybarsys.sh

echo "- Starting insecure test server"
./manage.py runserver --insecure 0.0.0.0:8000
