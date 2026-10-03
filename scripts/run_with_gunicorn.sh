#!/bin/bash

# Run pybarsys with gunicorn (intended for production use together with nginx or apache)
set -eux

# cd to root folder
cd "${0%/*}/.."

scripts/prepare_pybarsys.sh

# Deliberately a single worker (gunicorn's default): EasyVerein invoice runs track
# their progress in an in-process registry, and the guard against invoicing the same
# user twice lives there as well. With several workers a progress poll can land on a
# worker that knows nothing about the job, which invites a re-run and bills members
# twice in EasyVerein. Move that registry to the cache or database before scaling up.
gunicorn --bind :8000 pybarsys.wsgi:application
