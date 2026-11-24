#!/usr/bin/env python3
"""Extract ARCTIC "PQ Curve for CFD" workbook tables (P8 Max, P12 Max, P14 Max).

The workbooks are not redistributed. Download them from ARCTIC's support
pages (URLs in docs/ARCTIC_CFD_WORKBOOK_PROVENANCE.md) and pass the folder:

    python3 scripts/extract_arctic_cfd_workbooks.py --source-dir ~/Downloads

For each fan this writes two files under data/fan_curves/:

* ``<id>_source.csv``: every populated table row, verbatim (cached cell
  text, no reformatting), with its worksheet row number. Nothing is removed,
  even rows that break the solver contract.
* ``<id>.csv``: the solver-ready curve. It equals the source table except for
  the transformations declared in TRANSFORMS below, each with a reason. The
  test suite re-derives the solver CSV from the source CSV and checks that no
  undeclared change exists.

Each workbook's SHA-256 is pinned. A changed upstream file is refused rather
than silently re-extracted.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "fan_curves"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

WORKBOOKS = {
    "arctic_p8_max_3000rpm_manufacturer_cfd": {
        "filename": "P8 Max-PQ Curve for CFD.xlsx",
        "url": "https://support.arctic.de/products/p8max/techdocs/P8%20Max-PQ%20Curve%20for%20CFD.xlsx",
        "sha256": "de8c7c521543583bc71f770069f21092d0d66b9d70405c40a9f5988d68a5e02d",
        "sheet": "xl/worksheets/sheet2.xml",  # the "Sheet1" CFD template; "PQ Curve" duplicates it
        "rpm": 3000,
    },
    "arctic_p12_max_3300rpm_manufacturer_cfd": {
        "filename": "P12 MAX - PQ Curve for CFD.XLSX",
        "url": "https://support.arctic.de/products/p12-max/techdocs/P12%20MAX%20-%20PQ%20Curve%20for%20CFD.XLSX",
        "sha256": "6f16b0ffd220570f8371c810badc2753b3842f6fd23728abe6008bce1fb2504e",
        "sheet": "xl/worksheets/sheet1.xml",
        "rpm": 3300,
    },
    "arctic_p14_max_2800rpm_manufacturer_cfd": {
        "filename": "P14 Max - PQ Curve for CFD.XLSX",
        "url": "https://support.arctic.de/products/p14-max/techdocs/P14%20Max%20-%20PQ%20Curve%20for%20CFD.XLSX",
        "sha256": "bad2a6338415b61e7669d7bb49b3723125c223ee794015ab52dde77863bcf432",
        "sheet": "xl/worksheets/sheet1.xml",
        "rpm": 2800,
    },
}

# Declared source -> solver transformations, keyed by worksheet row number.
TRANSFORMS = {
    "arctic_p8_max_3000rpm_manufacturer_cfd": {
        18: ("drop", None,
             "exact duplicate of row 17 (6.51 CFM, 4.73 mmH2O); the solver needs strictly increasing flow"),
    },
    "arctic_p12_max_3300rpm_manufacturer_cfd": {
        21: ("set_pressure", "0",
             "terminal row reads 0.02 mmH2O at 83.84 CFM; the solver needs a 0 mmH2O free-air endpoint. "
             "Only the last segment (71.25-83.84 CFM, below 1.46 mmH2O) changes"),
    },
    "arctic_p14_max_2800rpm_manufacturer_cfd": {},
}

TABLE_FIRST_ROW = 14
TABLE_LAST_ROW = 36
META_CELLS = {"C6": "model", "C7": "rpm", "C8": "outer_diameter_mm", "C9": "hub_diameter_mm"}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cell_text(cell: ET.Element, shared: list[str]) -> str | None:
    value = cell.findtext("m:v", namespaces=NS)
    if value is not None and cell.get("t") == "s":
        return shared[int(value)]
    return value


def read_workbook(data: bytes, sheet: str) -> tuple[dict[str, str], list[tuple[int, str, str]]]:
    """Return (metadata, [(worksheet_row, flow_text, pressure_text), ...])."""
    try:
        with ZipFile(io.BytesIO(data)) as archive:
            shared: list[str] = []
            if "xl/sharedStrings.xml" in archive.namelist():
                for si in ET.fromstring(archive.read("xl/sharedStrings.xml")).findall("m:si", NS):
                    shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
            root = ET.fromstring(archive.read(sheet))
    except (BadZipFile, KeyError) as exc:
        raise ValueError(f"cannot read worksheet {sheet}: {exc}") from exc

    cells: dict[str, ET.Element] = {}
    for cell in root.iter(f"{{{NS['m']}}}c"):
        cells[cell.get("r", "")] = cell
    meta = {name: _cell_text(cells[ref], shared) for ref, name in META_CELLS.items() if ref in cells}
    header = _cell_text(cells["B12"], shared) if "B12" in cells else None
    if not header or not header.startswith("Flow rate (ft^3/min)"):
        raise ValueError(f"unexpected flow header in B12: {header!r}")
    meta["flow_header"] = header

    rows: list[tuple[int, str, str]] = []
    ended = False
    for r in range(TABLE_FIRST_ROW, TABLE_LAST_ROW + 1):
        flow = _cell_text(cells[f"B{r}"], shared) if f"B{r}" in cells else None
        pressure = _cell_text(cells[f"C{r}"], shared) if f"C{r}" in cells else None
        if flow is None and pressure is None:
            ended = True
            continue
        if ended or flow is None or pressure is None:
            raise ValueError(f"non-contiguous or incomplete table row {r}")
        if not re.fullmatch(r"-?[0-9.Ee+-]+", flow) or not re.fullmatch(r"-?[0-9.Ee+-]+", pressure):
            raise ValueError(f"non-numeric table row {r}: {flow!r}, {pressure!r}")
        rows.append((r, flow, pressure))
    if len(rows) < 2:
        raise ValueError("fewer than two table rows")
    return meta, rows


def apply_transforms(rows: list[tuple[int, str, str]], transforms: dict) -> list[tuple[str, str]]:
    """Apply only the declared per-row transformations."""
    seen = set()
    out: list[tuple[str, str]] = []
    for r, flow, pressure in rows:
        action = transforms.get(r)
        if action is None:
            out.append((flow, pressure))
            continue
        seen.add(r)
        kind, value, _reason = action
        if kind == "drop":
            continue
        if kind == "set_pressure":
            out.append((flow, value))
            continue
        raise ValueError(f"unknown transform {kind!r}")
    missing = set(transforms) - seen
    if missing:
        raise ValueError(f"declared transforms reference absent rows: {sorted(missing)}")
    return out


def render(header: list[str], rows) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-dir", type=Path, default=Path.home() / "Downloads")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(ROOT))
    from analysis.fan_operating_point import FanCurve  # noqa: E402

    status = 0
    for fan_id, spec in WORKBOOKS.items():
        path = args.source_dir / spec["filename"]
        if not path.is_file():
            print(f"skip {fan_id}: {path} not found")
            status = 2
            continue
        data = path.read_bytes()
        if _sha256(data) != spec["sha256"]:
            print(f"ERROR {fan_id}: workbook SHA-256 {_sha256(data)} != pinned {spec['sha256']}", file=sys.stderr)
            status = 2
            continue
        meta, rows = read_workbook(data, spec["sheet"])
        if str(spec["rpm"]) != meta.get("rpm"):
            print(f"ERROR {fan_id}: workbook RPM {meta.get('rpm')} != {spec['rpm']}", file=sys.stderr)
            status = 2
            continue
        source_csv = render(["worksheet_row", "flow_cfm", "static_pressure_mmh2o"], rows)
        solver_csv = render(["flow_cfm", "static_pressure_mmh2o"], apply_transforms(rows, TRANSFORMS[fan_id]))
        (OUT_DIR / f"{fan_id}_source.csv").write_bytes(source_csv)
        solver_path = OUT_DIR / f"{fan_id}.csv"
        solver_path.write_bytes(solver_csv)
        curve = FanCurve.from_csv(solver_path)  # raises if the solver contract is not met
        print(f"{fan_id}: {len(rows)} source rows -> {len(curve.points)} solver points; "
              f"shutoff {curve.shutoff_pressure_mmh2o} mmH2O, free air {curve.free_air_flow_cfm} CFM; "
              f"meta {meta}; source sha256 {_sha256(source_csv)}; solver sha256 {_sha256(solver_csv)}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
