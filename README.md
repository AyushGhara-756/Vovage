# Voyage


## Plan of architeccture:
1. Fetch New merge request = GitHub Actions
2. EvoMaster + Noir = schema discovery and API fuzzing
3. confirmation of all tests and verification = Berozgar engineer
4. making a report = ReportLab (PDF)

## CI: EvoMaster fuzzing

The GitHub Actions workflow in `.github/workflows/evomaster.yml` fuzzes the
Flask backend on every pull request, every push to `main`, and on manual
dispatch.

The pipeline:

1. Installs Python dependencies and Noir.
2. Generates an OpenAPI 3 schema from `backend/` with Noir.
3. Starts `python -m backend` on `127.0.0.1:6050`.
4. Runs EvoMaster in black-box mode against the live API.
5. Fails the job on distinct 500 faults.
6. Runs the Python unittest suite EvoMaster generated.
7. Uploads the generated tests, statistics, schema, and logs as artifacts.

### What is fuzzed

The GitHub-dependent endpoints are excluded because they make real network
calls and need GitHub App credentials:

- `/api/analysis/scan`
- `/api/structure/files`

No GitHub App secrets are required for the workflow because those endpoints
are excluded. The workflow therefore exercises the local API surface, currently
`/api/test/` and `/api/analysis/health`. Update `endpointExclude` in `em.yaml`
when the fuzzable surface changes.

### Artifacts

Each run uploads:

- `generated_tests/` — EvoMaster's Python unittest suite and interactive report (`index.html`)
- `statistics.csv` — coverage and fault metrics
- `openapi.json` — Noir-generated schema
- `evomaster.log`, `backend.log`, `noir.log`
- `process_data/` when EvoMaster produces it

### Run locally

With the virtualenv active and Noir installed:

```bash
pip install -r requirements.txt -r requirements-test.txt
./scripts/run_evomaster.sh
```

The default search budget is 120 seconds. Override it with `MAX_TIME`:

```bash
MAX_TIME=300s ./scripts/run_evomaster.sh
```

`em.yaml` holds the project defaults. `scripts/run_evomaster.sh` regenerates
`openapi.json`, starts and stops the backend, runs EvoMaster, checks the fault
statistics, and executes the generated tests.

## Noir analysis API

The backend can download a GitHub repository with the GitHub App installation
token, run [Noir](https://github.com/owasp-noir/noir) against it, and return the
discovered endpoints and files as JSON.

### Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `NOIR_BIN` | `noir` | Path to the Noir executable |
| `NOIR_TIMEOUT` | `180` | Scan timeout in seconds |
| `MAX_REPO_ARCHIVE_BYTES` | `209715200` (200 MB) | Maximum repository tarball size |

### `GET /api/analysis/health`

Reports whether Noir is available.

```json
{
  "noir": {
    "available": true,
    "version": "1.5.0"
  }
}
```

### `POST /api/analysis/scan`

Downloads the repository tarball, scans it with Noir, and returns normalized
repository-relative results. Temporary files are removed after the request.

```json
{
  "installation_id": 179208968,
  "owner": "Omat100",
  "repo": "VoyageTest",
  "ref": "main",
  "passive_scan": false
}
```

`ref` and `passive_scan` are optional. Response:

```json
{
  "repository": {
    "owner": "Omat100",
    "repo": "VoyageTest",
    "ref": "main"
  },
  "summary": {
    "file_count": 82,
    "endpoint_count": 36
  },
  "files": ["README.md", "src/app.py"],
  "endpoints": [
    {
      "endpoint": "/api/example/{id}",
      "method": "GET",
      "params": ["id", "verbose"],
      "body": {}
    },
    {
      "endpoint": "/api/example",
      "method": "POST",
      "params": [],
      "body": {
        "name": "",
        "email": ""
      }
    }
  ],
  "passive_results": [],
  "errors": []
}
```

Each endpoint uses:

- `endpoint` — the route URL
- `method` — one of `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, `OPTIONS`
- `params` — non-body parameter names (`query`, `path`, `header`, `cookie`)
- `body` — `json`, `form`, and `body` parameters as `name -> value`

Endpoints with methods outside the enum are skipped, and `endpoint_count`
reflects only the returned endpoints.

Status codes:

- `400` invalid or missing request fields
- `401`/`403`/`404` GitHub authentication or repository access failure
- `413` repository archive too large
- `502` Noir failed or returned invalid output
- `503` Noir is not installed
- `504` Noir scan timed out

### Tests

```bash
python -m unittest discover -s backend/tests -v
```
