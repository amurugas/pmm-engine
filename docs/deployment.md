# Deployment decision for an engineering office

## Recommendation

Use an intranet calculation service as the primary deployment and keep a
signed standalone executable as a controlled fallback. Excel and the browser
must call the same versioned API contract, so the solver is not duplicated.

For approximately 150 engineers this is materially easier to govern than 150
independent Python or executable installations:

| Concern | Intranet service | Standalone executable |
|---|---|---|
| Solver version | One controlled release | Desktop version drift unless centrally managed |
| Repeat-run speed | Warm processes and shared caches | Fast only after local process startup |
| Updates | Deploy once | Package and distribute to every workstation |
| Audit trail | Central request hash, version, user, and timing | Must collect logs from desktops |
| Network outage | Unavailable without redundancy | Continues to work |
| Sensitive models | Remain on company network | Remain on the workstation |
| Support burden | Server operations plus thin VBA | Windows packaging, antivirus, installs, updates |

## Request flow

```text
Excel workbook
  -> POST /api/v1/analyze (versioned JSON over intranet HTTPS)
  -> IIS/reverse proxy with Windows authentication
  -> warm PMM API workers
  -> fresh sectional analysis in the warm worker
  -> JSON response: capacities, DCRs, warnings, plots, calculation report
  -> Excel bulk-writes result arrays and refreshes charts
```

The POST endpoint is headless: it does not create a browser window, load web
assets, or render charts. The HTML viewer is only served when someone opens it
with a browser. Excel requests omit the optional 3D onion surface.

`POST /api/v1/report` runs the same versioned calculation and returns a PDF
attachment. Report generation is separate from normal Excel analysis, so PDF
layout work is incurred only when the workbook or viewer explicitly requests
the printable report.

The normal single-section request should be synchronous. Introduce asynchronous
jobs only for large portfolio or batch runs that exceed an agreed response-time
limit.

## Production topology

1. Run the Python API in a Linux container or managed Windows service on two
   internal hosts, if the office requires high availability.
2. Put IIS or the company's standard reverse proxy in front for TLS, hostname,
   request-size limits, and authentication.
3. Use integrated Windows authentication or the company's normal identity
   layer. Do not store shared API passwords in VBA.
4. Begin with two to four API workers and load-test realistic simultaneous
   runs. Worker count should follow measured CPU and memory use rather than the
   total number of engineers.
5. Log engine version, API version, normalized input hash, elapsed time,
   warnings, and authenticated user. Logging full geometry should be optional
   and governed by the company's retention rules.
6. Expose health and version endpoints so Excel can fail clearly before sending
   a calculation.

FastAPI/Uvicorn is a suitable production HTTP layer because it supports
multiple workers; the current dependency-free local server is a development
adapter using the same request structure. Production should add formal request
schemas, generated API documentation, authentication integration, metrics,
and graceful worker restart.

## Performance policy

The current service deliberately performs a fresh calculation for every POST
and retains no result cache. This keeps execution and audit behavior simple;
the returned input hash still identifies the exact request. The Python worker
stays warm, so imports and process startup are not repeated for each workbook.

Introduce capacity-level caching only if representative office load testing
shows it is necessary. If that threshold is reached, key cached data by the
normalized geometry, materials, design-code settings, and solver tolerances—
not by an unreviewed workbook filename or user-local path.

## Excel client

Use `WinHttp.WinHttpRequest.5.1` from VBA, apply explicit timeouts, send and
receive arrays in one request, and update worksheet ranges in bulk. Avoid one
HTTP request per load combination or per interaction point. `PMMHttpClient.bas`
contains the initial transport and health check.

The endpoint URL should be stored in one named workbook cell or managed config:

- development: `http://127.0.0.1:3000`
- production: `https://pmm.company.internal`

The workbook should verify the returned engine/API version and input hash, then
show them in the printable calculation.

## Standalone fallback

Package the same API server and web assets as a signed Windows executable. It
should bind only to `127.0.0.1`, and Excel should switch to it only when the
intranet health check fails and company policy allows offline calculations.
The fallback must display its engine version and warn when it is older than the
workbook's approved minimum. Central software distribution should update it.

Do not build a separate standalone calculation implementation; that would
create two validation targets and undermine the main benefit of the service.
