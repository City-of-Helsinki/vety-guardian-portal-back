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

### Test coverage

Run the tests with line and branch coverage:

```shell
uv run pytest --cov --cov-report=term-missing --cov-report=xml
```

`term-missing` prints each file's coverage and the lines not covered. `coverage.xml` is the report SonarCloud reads.
Migrations, test files, `testing/` folders and the startup files (`manage.py`, `asgi.py`, `wsgi.py`) are left out, see
`[tool.coverage.run]` in `pyproject.toml`.

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

Admin panel (only when `ADMIN_ENABLED=on`; enabled in dev, review and test, never in staging or production)

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
fixtures (`vtj/testing/mock_server.py`) as five families, plus one mock-only family.

Family 1:

| Role   | Henkilötunnus | Name                                  | Notes                                                                    |
| ------ | ------------- | ------------------------------------- | ------------------------------------------------------------------------ |
| Mother | `140904A998H` | Joanna Melina Haapakoski Testihenkilo | Guardian of the child, lives in Vaasa                                    |
| Father | `060999-951B` | Elias Kumpulainen Testihenkilo        | Guardian of the child, lives in Helsinki                                 |
| Child  | `040220A999K` | Veeti Konrad Kauriaistes Testihenkilo | Born 2020-02-04, no Turvakielto. Mock says Helsinki, real test VTJ Laihia |

Family 2:

| Role   | Henkilötunnus | Name                                     | Notes                                                       |
| ------ | ------------- | ---------------------------------------- | ----------------------------------------------------------- |
| Mother | `010878-998D` | Maiju Sanna-Kaisa Haapakoski Testihenkilo | Guardian of the child, lives in Järvenpää                   |
| Father | `181077-999S` | Holger Kullervo Ovaskainen Testihenkilo   | Guardian of the child, lives in Vaasa                       |
| Child  | `010321A999P` | Onni Manni Haapakoski Testihenkilo        | Born 2021-03-01, no Turvakielto. Mock says Helsinki, real test VTJ Järvenpää |

Family 3 (single parent):

| Role   | Henkilötunnus | Name                              | Notes                                                                   |
| ------ | ------------- | --------------------------------- | ----------------------------------------------------------------------- |
| Mother | `150299-902X` | Tove Maria Snellman Testihenkilo  | Only guardian of the child, lives in Varkaus                            |
| Child  | `151021A998B` | Ulrika Maria Snellman Testihenkilo | Born 2021-10-15, no Turvakielto. Mock says Helsinki, real test VTJ Varkaus |

Family 4 (Turvakielto):

| Role   | Henkilötunnus | Name                                 | Notes                                                                    |
| ------ | ------------- | ------------------------------------ | ------------------------------------------------------------------------ |
| Mother | `200798-9981` | Mette Salviantes Testihenkilo        | Guardian of the child, **active Turvakielto**, no address in VTJ         |
| Father | `111297-9991` | Karrisamuli Kauriaistes Testihenkilo | Guardian of the child, lives in Vantaa                                   |
| Child  | `100120A9502` | Lise Salviantes Testihenkilo         | Born 2020-01-10, no Turvakielto. Mock says Helsinki, real test VTJ Vantaa |

Family 5 (child with Turvakielto, single parent):

| Role   | Henkilötunnus | Name                                     | Notes                                                        |
| ------ | ------------- | ---------------------------------------- | ------------------------------------------------------------ |
| Mother | `010503A9503` | Marina Irina Larisa Testmän Testihenkilo | Only guardian of the child, lives in Helsinki                |
| Child  | `011019A9519` | Jimi Jonathan Testmän Testihenkilo       | Born 2019-10-01, **active Turvakielto**, no address in VTJ   |

Family 6 (single parent, mock only):

| Role     | Henkilötunnus | Name               | Notes                                          |
| -------- | ------------- | ------------------ | ---------------------------------------------- |
| Guardian | `290150-998L` | Siru Menninkäinen  | Only guardian of the child, lives in Helsinki  |
| Child    | `220421ATP00` | Miska Menninkäinen | Born 2021-04-22, no Turvakielto                |

Log in as the mother or the father. On the first login with a new identity, Helsinki-profiili asks for an email address
and sends a confirmation code to it, so use a mailbox you can read. (https://temporarymail.com/)

### Edlevo test families (login aliases)

The VTJ mock also has Edlevo's test families. Their henkilötunnus values (e.g. `011190-TP01`) are not real Suomi.fi
test identities, so they can't be used to log in. Instead, log in with the login henkilötunnus below: when
`VTJ_MOCK_ENABLED` is on, `POST /auth/identity/` stores the family henkilötunnus on the user instead
(`LOGIN_SSN_ALIASES` in `vtj/testing/mock_server.py`). The VTJ sync and the applications then use the family
henkilötunnus, e.g. as `h1_henkilotunnus`. Aliases are ignored when the mock is off.

All families have no Turvakielto, every guardian is a guardian of the child, and everyone lives in Helsinki.

| Family | Role     | Login henkilötunnus | Family henkilötunnus | Name                          | Notes                                         |
| ------ | -------- | ------------------- | -------------------- | ----------------------------- | --------------------------------------------- |
| 1      | Guardian | `200760-9998`       | `011190-TP01`        | Tiina Testaaja                |                                               |
| 1      | Guardian | `240582-9477`       | `291190-TP10`        | Teuvo Testaaja                |                                               |
| 1      | Child    |                     | `291221ATP00`        | Tirppa Testaaja               | Born 2021-12-29                               |
| 2      | Guardian | `250582-965E`       | `110602ATP10`        | Kimmo Koodari                 | Lives with the child                          |
| 2      | Guardian | `260582-957U`       | `050398-TP00`        | Kaarina Kehittäjä             | Lives at a different address                  |
| 2      | Child    |                     | `121021ATP00`        | Kaisa Koodari                 | Born 2021-10-12                               |
| 3      | Guardian | `110180-990F`       | `201087-TP00`        | Anniina Admin                 | Single parent                                 |
| 3      | Child    |                     | `290921ATP10`        | Arttu Admin                   | Born 2021-09-29                               |
| 4      | Guardian | `050282-9687`       | `220796-TP00`        | Saana Serveri                 | Single parent                                 |
| 4      | Child    |                     | `240721ATP10`        | Sami Serveri                  | Born 2021-07-24                               |
| 5      | Guardian | `020280-968S`       | `290784-TP00`        | Jane Doe                      | Single parent                                 |
| 5      | Child    |                     | `080221ATP11`        | John Doe                      | Born 2021-02-08                               |
| 6      | Guardian | `090999-971X`       | `220889-TP10`        | Jussi-Pekka O´Connor-Virtanen | Special characters in the name                |
| 6      | Guardian | `010180-9580`       | `171099-TP00`        | Mamma Virtanen                |                                               |
| 6      | Child    |                     | `251121ATP00`        | Anna-Leena O´Connor           | Born 2021-11-25                               |
| 7      | Guardian | `090999-969V`       | `171099-TP01`        | Bertta Bitti                  |                                               |
| 7      | Guardian | `221275-966C`       | `300992-TP00`        | Barbara Bitti                 |                                               |
| 7      | Child    |                     | `170921ATP10`        | Bob Bitti                     | Born 2021-09-17                               |
| 8      | Guardian | `010180-942F`       | `180996-TP00`        | Sini Selain                   |                                               |
| 8      | Guardian | `221275-939H`       | `150596-TP11`        | Seppo Selain                  |                                               |
| 8      | Child    |                     | `210521ATP11`        | Santeri Onni Oliver Selain    | Born 2021-05-21, several first names          |
| 9      | Guardian | `170377-9585`       | `190486-TP00`        | Nelli Nolla                   |                                               |
| 9      | Guardian | `260455-999D`       | `060988-TP10`        | Niilo Nolla                   |                                               |
| 9      | Child    |                     | `140921ATP10`        | Nina Nolla                    | Born 2021-09-14                               |

The family henkilötunnus values don't pass the `Guardian`/`Dependant` henkilötunnus format validator, so editing these
records in the Django admin fails validation. The VTJ sync and the applications are not affected.

### Other test families (login aliases)

Mock families for specific test cases. They are not Edlevo test families, but they work the same way: the family
henkilötunnus values are made up, so log in with the login henkilötunnus, a DVV test person found in DVV's test data,
which `LOGIN_SSN_ALIASES` maps to the family. The portal shows the mock family's data, not the DVV test person's data.

| Family     | Role     | Login henkilötunnus | Family henkilötunnus | Name              | Notes                                                    |
| ---------- | -------- | ------------------- | -------------------- | ----------------- | -------------------------------------------------------- |
| Espoo      | Guardian | `030393-995E`       | `120388-TP00`        | Elina Espoolainen | Single parent. Login: DVV's Totti Aalto Testihenkilo     |
| Espoo      | Child    |                     | `030621ATP00`        | Eetu Espoolainen  | Born 2021-06-03                                          |

Test cases:

- **Espoo:** the family lives in Espoo, so the home municipality isn't Helsinki and the application is refused
  (`guardian/eligibility.py`).

To add a family, add it with `_add_family` and its login henkilötunnus to `LOGIN_SSN_ALIASES` in
`vtj/testing/mock_server.py`, then add its rows and test case here.

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

## Audit logging

Access to and changes of personal data are written as audit entries with `audit()` in `core/audit.py`
(django-resilient-logger). Entries are stored in the database and Platta's CronJobs send them to Platta's audit
Elastic, where they are kept for 5 years. See the `core/audit.py` docstring and `RESILIENT_LOGGER` in
`core/settings.py`.

Rules:

- Writes: call `audit()` inside the same `transaction.atomic()` as the change, so a failed audit write rolls the
  change back and fails the request.
- Reads: call `audit()` before returning the data.
- Only successful operations are logged. Refused or failed requests write no entry.
- No personal data in entries: targets are record ids and the message is a fixed English text.

Audited events:

| Endpoint | Operation | Role | Target | Message |
|---|---|---|---|---|
| `POST /auth/identity/` | READ (UPDATE when the henkilötunnus or Helsinki-profiili id changes) | OWNER | user | "Identity verified" ("Identity updated") |
| `GET /vtj/dependants/` | READ | USER | dependant | "Dependants listed" |
| `POST /preschool-application-form/for-dependant/<id>/` | CREATE (201), READ (200, existing application) | OWNER | application | "Application created", "Application opened" |
| `GET /preschool-application-form/<id>/` | READ | OWNER | application | "Application opened" |
| `PUT /preschool-application-form/<id>/` | UPDATE | OWNER | application | "Application saved", "Application submitted" (draft → submitted) |
| `GET /preschool-application-form/<id>/pdf/` | READ | OWNER | application | "Application PDF downloaded" |
| `manage.py send_applications_to_vety` | READ (`recipient`: vety-data-export-web) | SYSTEM | application | "Application sent to vety-data-export-web" |
| `GET /gdpr-api/v1/profiles/<uuid>` | READ | SYSTEM | user | "GDPR data exported" |
| `DELETE /gdpr-api/v1/profiles/<uuid>` | DELETE (none for a dry run) | SYSTEM | user | "GDPR data deleted" |

SYSTEM entries are written without the request, so they have no actor uuid, IP address or path.

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
