# Caching service

A FastAPI microservice that builds payloads from two lists of strings. Each
string goes through a slow "transformer function" (a stand-in for an external
service), and the transformed strings from the two lists are interleaved.
Transformer results and finished payloads are both cached in SQLite, so the
transformer only ever runs on strings the service has never seen, and an
identical request gets back the identifier it was given the first time.

A small CLI, `cache-cli`, exercises the service from the command line.

## Quick start

With Docker:

```sh
docker compose up -d --build     # serves on http://localhost:8765
docker compose down              # stop; add -v to also delete the cached data
```

Or locally with [uv](https://docs.astral.sh/uv/):

```sh
uv sync
uv run cache-test                # serves on http://localhost:8000
```

Without a key, the service accepts any request and logs a warning; see
[Authentication](#authentication) to require one.

Then try it:

```sh
uv run cache-cli -i examples/sample.json -r 3
```

```text
{"iteration": 1, "id": "fb6203ce-…", "created": true,  "output": "FIRST STRING, OTHER STRING, …", "elapsed_ms": 642.3}
{"iteration": 2, "id": "fb6203ce-…", "created": false, "output": "FIRST STRING, OTHER STRING, …", "elapsed_ms": 6.1}
{"iteration": 3, "id": "fb6203ce-…", "created": false, "output": "FIRST STRING, OTHER STRING, …", "elapsed_ms": 5.4}
```

The first iteration pays for six transformer calls. The later ones reuse the
stored payload, so the id stays the same and the request is much faster.

The CLI targets the Docker port (8765) by default. Against a local
`uv run cache-test`, pass `-h http://localhost:8000`.

To use an API key, set it for both the service and the CLI:

```sh
export CACHE_TEST_API_KEY=change-me CACHE_CLI_API_KEY=change-me
docker compose up -d --build
uv run cache-cli -i examples/sample.json
```

## API

Interactive docs are at `/docs` while the service runs.

### Authentication

Two settings control authentication:

| `CACHE_TEST_API_KEY` | `CACHE_TEST_API_KEY_REQUIRED` | Result |
| --- | --- | --- |
| set | either | Requests to `/payload` must send the key |
| unset | `false` (default) | Any request is accepted; a warning is logged at startup |
| unset | `true` | The service refuses to start |

Authentication is optional by default, so local runs and the quick start need
no setup. For a real deployment, set `CACHE_TEST_API_KEY_REQUIRED=true`: a
missing key then stops the service at startup instead of leaving it open.

Clients send the key in an `X-API-Key` header. A missing or wrong key gets a 401 in the usual envelope,
before the body is validated, so unauthenticated callers learn nothing about
the expected input:

```json
{"requestId": "…", "message": "Invalid or missing API key", "status": 401, "data": null, "errors": null}
```

`/health` needs no key, so the Docker health check works without credentials.
The interactive docs have an "Authorize" button for entering the key.

### `POST /payload`

```json
{
  "list_1": ["first string", "second string", "third string"],
  "list_2": ["other string", "another string", "last string"]
}
```

Both lists must be non-empty and the same length.

| Status | Meaning |
| --- | --- |
| 201 | Payload created; `data.id` is its identifier |
| 200 | The same input was seen before; `data.id` is the existing identifier |
| 401 | Missing or wrong API key (only when a key is configured) |
| 422 | Invalid input (lists missing, empty, different lengths, or not strings) |
| 502 | The transformer failed |

### `GET /payload/{id}`

| Status | Meaning |
| --- | --- |
| 200 | `data.output` is the payload |
| 401 | Missing or wrong API key (only when a key is configured) |
| 404 | No payload with this id |
| 422 | The id is not a UUID |

Successful reads send `Cache-Control: private, max-age=3600`, so the client
can serve repeat reads from its own cache without reaching the service.
`private` stops shared proxies from storing it, because they would then hand
the payload to callers without a key.

### Response envelope

Every response, success or error, has the same shape:

```json
{
  "requestId": "570b7858f1f0463f946ae0e5e7a85d5a",
  "message": "Payload retrieved",
  "status": 200,
  "data": {"output": "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"},
  "errors": null
}
```

On validation errors, `errors` lists the field and reason for each problem,
without echoing the input back:

```json
{"requestId": "…", "message": "Invalid request", "status": 422, "data": null,
 "errors": [{"field": "body", "message": "list_1 and list_2 must have the same length"}]}
```

`requestId` matches the `X-Request-ID` response header. A caller can send
its own `X-Request-ID` (letters, digits, `.`, `_`, `-`, up to 128 characters)
to trace a request across systems; otherwise the service generates one.

`GET /health` returns `{"status": "ok"}` in the same envelope. Docker uses it
as the health check.

## CLI

```text
cache-cli [-h|--host URL] [-r|--repeat N] [-i|--input FILE|-] [-j|--json JSON] [-o|--output FILE|-] [--help]
```

| Option | Default | Meaning |
| --- | --- | --- |
| `-h`, `--host` | `http://localhost:8765` | URL of the service |
| `-r`, `--repeat` | `1` | Number of iterations (positive integer) |
| `-i`, `--input` | stdin | JSON input file, `-` for stdin |
| `-j`, `--json` | | JSON input given inline; can't be combined with `--input` |
| `-o`, `--output` | stdout | Output file, `-` for stdout |
| `--api-key` | | API key sent as `X-API-Key`. Prefer `CACHE_CLI_API_KEY`, which stays out of shell history and process listings. |
| `--help` | | Show help |

Each iteration creates the payload and reads it back, then writes one JSON
line. Input is validated against the same schema as the API before any
request is sent.

```sh
uv run cache-cli -j '{"list_1": ["a", "b"], "list_2": ["c", "d"]}'
cat examples/sample.json | uv run cache-cli -r 5 -o results.jsonl
```

Exit codes: `0` on success, `2` for invalid arguments or input, `1` when a
request fails or the output can't be written. Errors go to stderr and include
the server's message and request id, for example:

```text
cache-cli: server responded 502: Transformer failed: upstream timeout (request id 3f2a…)
```

Every option can also be set through an environment variable with the
`CACHE_CLI_` prefix, for example `CACHE_CLI_HOST`.

## Configuration

The service reads `CACHE_TEST_*` environment variables:

| Variable | Default | Meaning |
| --- | --- | --- |
| `CACHE_TEST_DATABASE_URL` | `sqlite:///./cache.db` | SQLAlchemy URL. The Docker image uses `sqlite:////data/cache.db` on a volume. Only SQLite is tested; see the PostgreSQL note under shortcuts. |
| `CACHE_TEST_TRANSFORMER_DELAY_SECONDS` | `0.1` | Delay of the simulated transformer per call, so the benefit of caching is visible. Must not be negative. |
| `CACHE_TEST_API_KEY` | unset | Key clients must send as `X-API-Key`; enforced whenever set. Compose reads it from your shell or a `.env` file, which is gitignored. |
| `CACHE_TEST_API_KEY_REQUIRED` | `false` | `true` makes the service refuse to start without a key. With `false`, it runs open and logs a warning. |

## Design

### Following one request

`POST /payload` goes through four layers, each with one job:

1. **`api/payload.py`** validates the body (`schemas/payload.py`), calls the
   service, and picks 201 or 200 depending on whether the payload is new.
2. **`services/payload.py`** holds the caching logic:
   - It hashes both lists (SHA-256 of their JSON form) and looks the hash up.
     A hit returns the existing payload right away, without touching the
     transformation cache or the transformer.
   - Otherwise it collects the distinct strings from both lists, loads the
     ones already in the transformation cache in **one query**, and calls the
     transformer only for the rest.
   - It interleaves the results, stores the payload, and returns it.
3. **`repositories/`** contains the SQL: `transformer_repo.py` for cached
   transformations and `payload_repo.py` for payloads.
4. **`models.py`** defines two tables: `transformations` (input → output,
   keyed by input) and `payloads` (id, input hash, output; the hash is unique).
   Alembic migrations in `migrations/` create and evolve them.

`utils/envelope.py` wraps every response and maps exceptions to status codes.
`main.py` wires it together in a `create_app(settings, transformer)` factory,
so tests can pass in their own database and transformer.

### Why it's built this way

- **Minimal transformer calls.** Strings are deduplicated within a request
  ("a" appearing three times is transformed once) and across requests (via the
  `transformations` table). A repeated request skips the transformer entirely.
- **Results survive failures.** If the transformer fails halfway through a
  request, the results it already produced are still saved, so a retry
  doesn't pay for them again.
- **The input hash covers list structure, not just content.** Hashing the lists
  as JSON means `["a,b"]` and `["a", "b"]` can never collide, which naive
  string joining would allow.
- **Concurrent requests don't fail on duplicates.** Inserts use
  `ON CONFLICT DO NOTHING` and then read the row back
  (`repositories/_inserts.py`). If two requests store the same payload or
  transformation at once, both end up with the same row and the same id.
- **Clear error categories.** A `TransformerError` means the external service
  failed and becomes a 502. Anything else is a bug and becomes a 500 with a
  generic message; the traceback stays in the server log, tagged with the
  request id.
- **The payload output is stored, not recomputed on read.** It's a small
  string, and storing it means reads never depend on the transformation cache.

## Shortcuts and assumptions

- **The response envelope differs from the spec's sample.** The spec shows
  `GET /payload/{id}` returning a bare `{"output": "..."}`; here it is
  `data.output` inside the envelope. Every endpoint answers in one format,
  including errors, and carries a request id for tracing. The output string
  itself is exactly as specified.
- **`-h` means `--host`; help is `--help` only.** The spec assigns `-h` to
  both. Host is needed on nearly every call and every other value option has
  a short form, so `-h` goes to host (as in `psql` and `mysql`).
- **The transformer is simulated.** `SimulatedTransformer` upper-cases its
  input after a delay. It's assumed to be deterministic, which is what makes
  caching its results safe.
- **No cache eviction or TTL.** Because the transformer is deterministic,
  cached results never go stale. A real deployment might cap the table size.
- **Concurrent requests can still duplicate transformer calls.** Two requests
  with the same *new* string at the same moment may both call the
  transformer. The conflict-tolerant inserts keep the data correct, but don't
  save the extra call. Preventing it would need a lock per input or reserving
  the row before calling the transformer.
- **HTTP caching repeats the original request id.** A cached read returns the
  `requestId` of the request that filled the cache. The one-hour `max-age`
  limits this, and keeps the window short should payloads ever become
  deletable.
- **The 502 message includes the transformer's error text.** That helps with
  debugging here. With a real external service, it should be replaced with a
  fixed message so internal details don't reach clients.
- **One shared API key.** It's enough to keep the service from being open to
  anyone, but every client shares the key. There is no per-client identity,
  rotation without downtime, or rate limiting; a real deployment would use
  per-client keys or OAuth behind an API gateway. The key also travels in
  plain text, so anything beyond localhost needs TLS in front (for example a
  reverse proxy). Authentication is optional by default to keep the quick
  start to one command; a startup warning makes that visible, and
  `CACHE_TEST_API_KEY_REQUIRED=true` makes a missing key a startup error.
- **Only SQLite is tested.** The code avoids SQLite-only SQL: the
  conflict-tolerant inserts have a PostgreSQL variant, and the migrations use
  batch mode only on SQLite. Running on PostgreSQL would still need a driver
  (for example `psycopg`) and a test run against a real server, which this
  project doesn't include.
- **Migrations run on startup.** The app applies pending Alembic migrations
  when it starts, which keeps a single-instance deployment to one command.
  With several instances, they would move to a separate deploy step so
  instances don't race to apply them. Databases created before migrations
  existed are detected and marked as being at the first revision.
- **Input size isn't limited.** Very large lists would hit SQLite's limit on
  bound parameters in the cache lookup. Production code would batch the lookup
  and cap the request size.

## Development

```sh
uv run pytest          # unit and integration tests
uv run ruff check      # lint
uv run ruff format     # format
```

CI (`.github/workflows/ci.yml`) runs the lint, the format check and the tests
on every push and pull request.

To change the schema, edit `models.py`, then generate a migration and review
it before committing:

```sh
uv run alembic revision --autogenerate -m "Describe the change"
```

The app applies it on its next start. `tests/test_migrations.py` fails if the
models and migrations ever drift apart.

- `tests/test_repository.py`, `tests/test_service.py`: unit tests for the
  persistence and caching logic, using an in-memory database and a
  transformer that counts its calls.
- `tests/test_api.py`: integration tests from HTTP down to a real SQLite file,
  including restarting the app to show the cache persists, and every error
  path through the envelope.
- `tests/test_cli.py`: argument parsing and validation, plus the CLI running
  against the app in-process.
- `tests/test_migrations.py`: the migrations build the schema, match the
  models, can run repeatedly, and adopt databases from before migrations.
