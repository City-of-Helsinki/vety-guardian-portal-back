#!/bin/bash

set -e

if [[ -z "$SKIP_DATABASE_CHECK" || "$SKIP_DATABASE_CHECK" = "0" ]]; then
  until nc -z -v -w30 "$DB_HOST" "${DB_PORT:-5432}"
  do
    echo "Waiting for postgres database connection..."
    sleep 1
  done
  echo "Database is up!"
fi

# Apply database migrations
if [[ "$APPLY_MIGRATIONS" = "1" ]]; then
    echo "Applying database migrations..."
    ./manage.py migrate --noinput
fi

# Start server
if [[ -n "$*" ]]; then
    "$@"
else
    uwsgi --ini .prod/uwsgi.ini
fi
