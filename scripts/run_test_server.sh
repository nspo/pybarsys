#!/bin/bash
set -eu

# cd to root folder
cd "${0%/*}/.."

scripts/prepare_pybarsys.sh

echo "- Starting insecure test server"
./manage.py runserver --insecure 0.0.0.0:8000
