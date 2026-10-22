# HKI-Vety Guardian Portal Backend

## Requirements

- Python 3.14
- [uv](https://docs.astral.sh/uv/)
- Docker
- PostgreSQL 17

## Setting up development environment

### Environment and dependencies

Install [uv](https://docs.astral.sh/uv/) and initialize environment

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

Copy environment variables example and fill out the `.env` file with the correct values.

- DB\_\*

```shell
cp -v .env.example .env
```

### Pre-commit hooks

Install and activate the pre-commit hooks to automatically run linting, formatting, and tests on every commit:

```shell
uv run pre-commit install
```

The hooks run **ruff**, and **pytest** before each commit. You can also run them manually against all files:

```shell
uv run pre-commit run --all-files
```

Or run each step manually

```shell
uv run ruff check .
uv run ruff check --fix .
uv run ruff format --check .
uv run pytest
```

### Database

Create database container

```shell
docker run --name hki-vety-guardian-db -p 5433:5432 -e POSTGRES_USER=vetyuser -e POSTGRES_PASSWORD=vetypw -e POSTGRES_DB=vetyguardiandb -d postgres:17
```

Create database

```shell
uv run python manage.py migrate
```

Create superuser

```shell
uv run python manage.py createsuperuser
```

### Start development environment

```shell
uv run python manage.py runserver 8001
```

Admin panel

http://localhost:8001/admin/

API documentation

http://localhost:8001/schema/swagger-ui/

### Login (Helsinki-profiili)

The API authenticates requests with Helsinki Tunnistus API tokens ([django-helusers](https://github.com/City-of-Helsinki/django-helusers) `ApiTokenAuthentication`).
Set `TOKEN_AUTH_*` and `HELSINKI_PROFILE_API_*` in `.env` (see `.env.example`).

After login the frontend calls `POST /auth/identity/` with the user's Helsinki-profiili API token. The backend reads
the henkilötunnus from the profile's `verifiedPersonalInformation` (Suomi.fi-verified) and stores it on the user.
The VTJ and application endpoints use that henkilötunnus as the guardian; they return 403 until it is set.

Note: the VTJ mock only knows the henkilötunnus values in its fixtures, so a fixture is needed for the Suomi.fi test identity you log in with.

### Login test users

In the test environment Suomi.fi login goes through the test identification service (https://testi.apro.tunnistus.fi/).
Its default identity `210281-9988` is not in the VTJ mock, so `/vtj/` endpoints return "person not found" for it.

These identities from DVV's test data (https://testiaineisto.fi/testiaineistorivit/henkilot) are in the VTJ mock
fixtures (`vtj/testing/mock_server.py`) as one family:

| Role   | Henkilötunnus | Name                                  | Notes                           |
| ------ | ------------- | ------------------------------------- | ------------------------------- |
| Mother | `140904A998H` | Joanna Melina Haapakoski Testihenkilo | Guardian of the child           |
| Father | `060999-951B` | Elias Kumpulainen Testihenkilo        | Guardian of the child           |
| Child  | `040220A999K` | Veeti Konrad Kauriaistes Testihenkilo | Born 2020-02-04, no Turvakielto |

Log in as the mother or the father. On the first login with a new identity, Helsinki-profiili asks for an email address
and sends a confirmation code to it, so use a mailbox you can read. (https://temporarymail.com/)

### Run VTJ mock server for development environment

```shell
uv run python -m vtj.testing.mock_server 8080
```

Alternatively, serve the mock from the Django app itself (used in dev and review environments, so no separate container is needed):

```shell
VTJ_MOCK_ENABLED=on
VTJ_HEL_ENDPOINT=http://localhost:8001/vtj-mock/api/HenkilonTunnuskysely
```

Never enable `VTJ_MOCK_ENABLED` in production.

### Manage database for testing

Project has custom commands in

`guardian/management/commands/<COMMAND>.py`

Simple exmple command: 'test_command.py'

```
uv run python manage.py help test_command
uv run python manage.py test_command
```

Command to delete "PreschoolApplication" data from development database: 'db_delete_all_PreschoolApplication.py'

```
uv run python manage.py db_delete_all_PreschoolApplication
```

Command to delete the data linked to a child's or guardian's henkilötunnus: 'db_delete_by_hetu.py'. Deletes their
applications and VTJ person records (`Dependant`, `Guardian`). With a guardian's hetu, all of the guardian's dependants
and their applications are deleted. `--yes` skips the confirmation prompt.

```
uv run python manage.py db_delete_by_hetu 010170-999X
```

### Test-data API for e2e tests

The same deletes are available over HTTP so e2e tests can clean up after each test. The API is routed only when
`TEST_DATA_API_ENABLED` is on, and every request must send `TEST_DATA_API_KEY` in the `X-Test-Data-Api-Key` header.
It is not in the OpenAPI schema.

```
# Data linked to a child's or guardian's henkilötunnus
curl -X POST http://localhost:8001/test-data/delete/ \
  -H "X-Test-Data-Api-Key: $TEST_DATA_API_KEY" -H "Content-Type: application/json" \
  -d '{"hetu": "010170-999X"}'

# All rows from the PreschoolApplication table
curl -X POST http://localhost:8001/test-data/delete-all/ -H "X-Test-Data-Api-Key: $TEST_DATA_API_KEY"
```

Both return the number of deleted rows, e.g. `{"applications": 1, "dependants": 2, "guardians": 1}`.

Never enable `TEST_DATA_API_ENABLED` in production.

## OpenAPI schema

The APIs are documented using [drf-spectacular](https://drf-spectacular.readthedocs.io/en/latest). Which generates the OpenAPI schema from the Django Rest Framework views.

The schema is used to generate TypeScript types for the frontend applications.

## Project Structure

```text
vety-guardian-portal-back/
├── authentication/        # User authentication and custom user model
│   └── ...
│
├── core/                  # Main Django project configuration
│   └── ...
│
├── guardian/              # REST API used by the React frontend
│   └── ...
│
├── integrations/          # Communication with external services and servers
│   ├── ...
│   └── ...
│
└── README.md              # Project documentation
```
