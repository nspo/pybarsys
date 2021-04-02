#!/bin/bash
set -eux

# cd to root folder
cd "${0%/*}/.."

scripts/prepare_pybarsys.sh
gunicorn --bind :8000 pybarsys.wsgi:application
