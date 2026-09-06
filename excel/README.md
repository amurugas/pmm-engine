# Windows Excel integration

## Existing Stage 4 shear-wall workbook

The legacy four-stage workbook can keep its CTI creation, result parsing,
stress checks, charts, and output ranges unchanged. Only the old
`spColumn.CLI.exe` launch is replaced by a synchronous request to the local PMM
Engine.

Install the package and start the service before opening Excel:

```powershell
py -m pip install -e .
pmm-web --host 127.0.0.1 --port 3000
```

Create a patched copy of the supplied workbook (Excel must allow **Trust access
to the VBA project object model** while this one-time command runs):

```powershell
.\excel\Patch-Stage4Workbook.ps1 `
  -InputWorkbook '.\PMM\Concrete Shear Wall PMM 4 - Design - Step 2 Design v3_11.xlsm' `
  -OutputWorkbook '.\output\Concrete Shear Wall PMM 4 - Design - Step 2 Design v3_11 - PMM Engine.xlsm' `
  -LoadingDirectory '.\PMM\1 - Loading\Loading' `
  -GeometryDirectory '.\PMM\2 - Geometry\Geometry' `
  -ReinforcementDirectory '.\PMM\3 - Reinforcement\Reinforcement - Step 2 Design' `
  -AnalysisDirectory '.\PMM\4 - Design\spCol - Step 2 Design'
```

The patch replaces the `local_3RunAnalysis` VBA module, imports
`PMMHttpClient`, and changes only the executable preflight/error handling in
the Batch and Run One macros. The server writes the same `.out`,
`-factored.txt`, and optional `.txt - error.log` names expected by the existing
Stage 4 result macros. See `docs/stage4_spcolumn_compatibility.md` for the file
contract, sign mapping, and benchmark results.

The workbook interface uses xlwings so VBA only launches Python. Engineering
logic is not duplicated in macros or worksheet formulas.

## Setup

From Windows PowerShell in the repository:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
py -m pip install -e ".[dev,excel]"
xlwings addin install
```

Open the starter workbook, save it as an `.xlsm` file, import `PMMBridge.bas`
in the VBA editor, and assign `RunPMMAnalysis` to a button. The workbook must
retain these sheets and cells:

- `Inputs!B4:B12`: width, depth, f'c, fy, clear cover, tie size, longitudinal
  bar size, maximum bar spacing, and PMM angular step.
- `Demands!A4:D...`: load label, Pu (kip), Mux (kip-ft), and Muy (kip-ft).
- `Results!A4:H...`: calculated demand results.
- `PM Data!A4:D...`: factored PMx and PMy data.
- `Contours!A4:E...`: demand-specific constant-Pu contours.
- `Calculations!A1:A...`: printable step-by-step engineering calculation.

Assign `RunPMMAnalysis` to the analysis button and `PrintPMMCalculation` to the
print-calculation button. The latter refreshes the results, formats the page,
and opens Excel Print Preview.

The CLI provides the same calculation path without Excel:

```powershell
pmm-engine examples\starter_input.json result.json
```

For a shared office deployment, import `PMMHttpClient.bas` and configure the
workbook to call `/api/v1/analyze` on the intranet host. The module uses built-in
Windows WinHTTP, explicit timeouts, and the current Windows credentials. The
workbook still needs a reviewed JSON parser and range-mapping layer; see
`docs/deployment.md` before treating this transport as production-ready.

The same module can save a print-ready report by posting the calculation JSON
to `/api/v1/report` through `SavePMMReportJson`. Add an optional report member
such as `{"selected_load_label": "LC-2"}` under the top-level `report` object
to choose the load used for the constant-Pu and strain/stress pages.
