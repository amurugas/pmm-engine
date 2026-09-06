import json
from pathlib import Path
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import Request, urlopen

import pytest

from pmm_engine.spcolumn_compat import analyze_cti, parse_cti, run_cti_file
from pmm_engine.webapp import PMMRequestHandler


CTI = """#spColumn Text Input (CTI) File
[spColumn Version]
10.00
[Project]
Compatibility Test
[Column ID]
L-WALL
[Engineer]
QA
[User Options]
0,0,8,2,0,0,0,0,2,0,0,2,0,-1,3,-1,4,2,0,7,0,0,0,0,0,13,0
[Material Properties]
4,3605,3.4,0.85,0.003,60,29000,0,0,0,0.002069
[Reduction Factors]
0.8,0.9,0.65,0.1,0
[External Points]
1
7
0,0
30,0
30,10
10,10
10,40
0,40
0,0
[Internal Points]
0
[Reinforcement Bars]
4
0.79,2,2
0.79,28,2
0.79,8,38
0.79,2,38
[Factored Loads]
2
100,50,20
1000000,1,1
"""


def test_cti_parser_reads_stage4_irregular_section() -> None:
    model = parse_cti(CTI)

    assert model.axis == 2
    assert len(model.vertices) == 6
    assert len(model.bars) == 4
    assert len(model.loads) == 2
    assert model.vertices[0] != model.vertices[-1]


def test_compatibility_artifacts_match_vba_contract_and_signs() -> None:
    artifacts = analyze_cti(CTI, depth_sample_count=81)
    report = artifacts.report_text
    factored_lines = artifacts.factored_text.splitlines()

    assert " STRUCTUREPOINT output-contract marker v10-compatible" in report
    assert "Ag    600" in report
    assert "Total steel area As = 3.16" in report
    assert "Pmax" in report
    assert artifacts.error_text is not None
    assert len(factored_lines) == 1 + 70 * 36

    fields = factored_lines[1 + 49 * 36].split("\t")
    assert float(fields[0]) == pytest.approx(0.0, abs=1e-6)
    assert float(fields[4]) == 0.0
    # spColumn angle zero corresponds to the engine's -90-degree normal and
    # both engine moment resultants must be negated for the workbook contract.
    assert float(fields[1]) > 0.0


def test_run_cti_file_publishes_expected_stage4_filenames(tmp_path: Path) -> None:
    input_path = tmp_path / "L-WALL-Bi.cti"
    input_path.write_text(CTI)

    result = run_cti_file(input_path)

    assert Path(result["output_path"]).is_file()
    assert Path(result["factored_path"]).is_file()
    assert Path(result["error_path"]).is_file()
    assert (tmp_path / "L-WALL-Bi.out").read_text().startswith(" PMM ENGINE")
    assert (tmp_path / "L-WALL-Bi-factored.txt").read_text().startswith(
        "Axial Force\tMoment X\tMoment Y"
    )
    report_bytes = (tmp_path / "L-WALL-Bi.out").read_bytes()
    factored_bytes = (tmp_path / "L-WALL-Bi-factored.txt").read_bytes()
    assert b"\r\n STRUCTUREPOINT output-contract marker" in report_bytes
    assert b"\n" not in report_bytes.replace(b"\r\n", b"")
    assert b"\n" not in factored_bytes.replace(b"\r\n", b"")


def test_local_server_runs_cti_file_for_vba_client(tmp_path: Path) -> None:
    input_path = tmp_path / "L-WALL-Bi.cti"
    input_path.write_text(CTI)
    server = ThreadingHTTPServer(("127.0.0.1", 0), PMMRequestHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps({"input_path": str(input_path)}).encode()
        request = Request(
            f"http://127.0.0.1:{server.server_port}/api/v1/spcolumn/compat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert payload["ok"] is True
    assert payload["result"]["demand_count"] == 2
    assert (tmp_path / "L-WALL-Bi.out").is_file()
