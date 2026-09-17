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

### Run VTJ mock server for development environment

```shell
uv run python -m vtj.testing.mock_server 8080
```

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
