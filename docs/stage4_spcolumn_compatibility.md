# Stage 4 spColumn compatibility

## Scope

This adapter replaces only the Stage 4 `spColumn.CLI.exe` invocation in
`Concrete Shear Wall PMM 4 - Design - Step 2 Design v3_11.xlsm`. The workbook
continues to:

- create the `-Bi`, `-X`, and `-Y` CTI files;
- read the generated `.out`, `-factored.txt`, and error-log files;
- calculate stresses, boundary-zone checks, warnings, summaries, and charts;
- use its existing directory names, pier IDs, row layout, and Run controls.

The replacement VBA call is synchronous. This removes the legacy polling race:
when `local_RunAnalysis` returns, the output files have been atomically
published and are ready for the unchanged parser.

## Local service contract

Start the service on loopback:

```powershell
py -m pip install -e .
pmm-web --host 127.0.0.1 --port 3000
```

VBA posts this payload to `POST /api/v1/spcolumn/compat`:

```json
{"input_path":"C:\\absolute\\path\\PIER-Bi.cti"}
```

The endpoint deliberately accepts requests only from a loopback client because
it reads and writes local file paths. It parses the workbook CTI and publishes:

- `PIER-Bi.out`
- `PIER-Bi-factored.txt`
- `PIER-Bi.txt - error.log` only when a demand exceeds the section capacity

Uniaxial `-X` and `-Y` runs use the same naming rule. Existing artifacts are
replaced atomically; a stale error log is removed after a passing analysis.

## Coordinate and sign mapping

The general PMM mechanics kernel uses positive compression and resultants
`Mx = sum(F*y)` and `My = -sum(F*x)`. The supplied spColumn v10.10 files use a
different neutral-axis reference and expose the opposite moment signs.

The compatibility adapter therefore applies exactly this boundary mapping:

```text
theta_engine = theta_spColumn - 90 degrees
Mx_spColumn  = -Mx_engine
My_spColumn  = -My_engine
```

This conversion is confined to `spcolumn_compat.py`; it does not alter the
engine's native convention or any workbook inputs. At a fixed axial load, the
moment-capacity check uses the outermost intersection of the demand ray and the
factored interaction contour, matching spColumn's Moment Capacity method when
the phi transition produces a locally folded sampled contour.

## Supplied-file validation

The adapter was checked against
`PMM/4 - Design/spCol - Step 1 Minimums/PMM-A1--L1-Bi.cti` and its supplied
spColumn v10.10 outputs:

- section area, centroid, inertias, and total reinforcing area matched;
- all 132 demand rows had the same pass/failure category;
- DCR values matched at the workbook's displayed two-decimal precision;
- maximum compared capacity-component relative error was about 0.03%;
- maximum neutral-axis-depth difference was about 0.07 in;
- the 2,520-row factored surface matched with about 0.14% 99th-percentile
  vector error (the maximum was about 0.89% at a near-zero pure-tension moment).

The copied project set contains concave orthogonal wall polygons. The adapter
triangulates a simple concave exterior ring before analytical compression-block
integration. The current compatibility boundary supports one exterior
concrete region with discrete reinforcing bars and no internal concrete voids,
which covers the supplied 354 loading/geometry cases. A CTI containing an
internal void is rejected clearly rather than analyzed under a different
section assumption.

## Workbook patch contents

- `excel/Stage4LocalRunAnalysis.bas`: drop-in `local_3RunAnalysis` replacement
- `excel/PMMHttpClient.bas`: health check and local compatibility request
- `excel/Patch-Stage4Workbook.ps1`: creates a patched workbook copy and can set
  the four named directory cells

The patch script does not modify the source workbook. Use `-Force` only when
you intentionally want to replace an already generated patched copy.
