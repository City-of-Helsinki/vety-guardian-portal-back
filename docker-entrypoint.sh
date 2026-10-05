#!/bin/bash

set -e

# Apply database migrations
if [[ "$APPLY_MIGRATIONS" = "1" ]]; then
    echo "Applying database migrations..."
    ./manage.py migrate --noinput
fi

# Collect static files
echo "Collecting static files..."
./manage.py collectstatic --noinput

# Start server
if [[ -n "$*" ]]; then
    "$@"
else
    uwsgi --ini .prod/uwsgi.ini
fi
