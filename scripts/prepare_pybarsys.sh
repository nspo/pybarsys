#!/bin/bash
# - Collect static files in STATIC_ROOT directory
# - Migrate the database
# - Create an initial admin user if no users exist yet

# set -eu is not possible here due to the call to read below

# change to pybarsys root
cd "${0%/*}/.."

echo "- Collecting static files in STATIC_ROOT and migrating database"
./manage.py collectstatic --no-input
./manage.py migrate

# create admin account if no user exists yet
read -r -d '' CMD_CREATE_ADMIN_IF_NONE <<- EOM

from barsys.models import *
if User.objects.count() == 0:
    u = User.objects.create_superuser(email='admin@example.com', password='example', display_name='Admin')
    u.is_buyer = False
    u.save()
    print('- Default admin account was created (Email: admin@example.com, password: example)')

EOM

./manage.py shell -c "$CMD_CREATE_ADMIN_IF_NONE"

