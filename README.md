# Voyage


## Plan of architeccture:
1. Fetch New merge request = GitHub Actions
2. Schemathesis = test case generation
3. confirmation of all tests and verification = Berozgar engineer
4. making a report = ReportLab (PDF)

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
