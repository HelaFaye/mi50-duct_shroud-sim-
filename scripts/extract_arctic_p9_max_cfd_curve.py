#!/usr/bin/env python3
"""Extract the validated ARCTIC P9 Max 4300 RPM CFD workbook P-Q table.

The source workbook is deliberately not redistributed in this repository.
This script validates its SHA-256, extracts the ten positive-pressure points
from worksheet rows 14-23, and verifies the exact canonical CSV bytes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import math
import re
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path.home() / "Downloads" / "arctic_p9_max_pq_curve_for_cfd.xlsx"
DEFAULT_OUTPUT = ROOT / "data" / "fan_curves" / "arctic_p9_max_4300rpm_manufacturer_cfd.csv"
EXPECTED_WORKBOOK_SHA256 = "0d323c1ddc730919366df477a298f9d0cdbcee88d0a70e00674a47697d2d8854"
EXPECTED_CSV_SHA256 = "d1c9123afa5bc3c95226cea0a57b58dc4bdc2a63d20e279fea4b5d09d15ae922"
NAMESPACE = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_points(workbook: Path) -> list[tuple[str, str]]:
    try:
        with ZipFile(workbook) as archive:
            xml_bytes = archive.read("xl/worksheets/sheet1.xml")
    except (BadZipFile, KeyError) as exc:
        raise ValueError(f"cannot read expected XLSX worksheet: {exc}") from exc

    root = ET.fromstring(xml_bytes)
    sheet_data = root.find("m:sheetData", NAMESPACE)
    if sheet_data is None:
        raise ValueError("worksheet has no sheetData element")

    rows: dict[int, dict[str, ET.Element]] = {}
    for row in sheet_data.findall("m:row", NAMESPACE):
        row_number = int(row.attrib["r"])
        if 14 <= row_number <= 23:
            cells: dict[str, ET.Element] = {}
            for cell in row.findall("m:c", NAMESPACE):
                match = re.fullmatch(r"([A-Z]+)([0-9]+)", cell.attrib.get("r", ""))
                if match:
                    cells[match.group(1)] = cell
            rows[row_number] = cells

    if sorted(rows) != list(range(14, 24)):
        raise ValueError(
            f"expected worksheet rows 14-23 exactly; found {sorted(rows)}"
        )

    points: list[tuple[str, str]] = []
    for row_number in range(14, 24):
        cells = rows[row_number]
        if "B" not in cells or "C" not in cells:
            raise ValueError(f"missing flow/pressure cells in worksheet row {row_number}")
        flow = cells["B"].findtext("m:v", namespaces=NAMESPACE)
        pressure = cells["C"].findtext("m:v", namespaces=NAMESPACE)
        if flow is None or pressure is None:
            raise ValueError(f"missing numeric cached value in worksheet row {row_number}")
        points.append((flow, pressure))
    return points


def render_csv(points: list[tuple[str, str]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["flow_cfm", "static_pressure_mmh2o"])
    writer.writerows(points)
    return stream.getvalue().encode("utf-8")


def validate_points(points: list[tuple[str, str]]) -> None:
    if len(points) != 10:
        raise ValueError(f"expected 10 retained points, found {len(points)}")
    numeric: list[tuple[float, float]] = []
    for index, (flow_text, pressure_text) in enumerate(points, start=14):
        try:
            flow, pressure = float(flow_text), float(pressure_text)
        except ValueError as exc:
            raise ValueError(f"non-numeric point in worksheet row {index}") from exc
        if not math.isfinite(flow) or not math.isfinite(pressure):
            raise ValueError(f"non-finite point in worksheet row {index}")
        numeric.append((flow, pressure))

    if numeric[0][0] != 0.0 or numeric[0][1] <= 0.0:
        raise ValueError("invalid shutoff endpoint")
    if not math.isclose(numeric[-1][0], 58.25, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(f"unexpected free-air flow: {numeric[-1][0]}")
    if not math.isclose(numeric[-1][1], 0.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"unexpected free-air pressure: {numeric[-1][1]}")

    for previous, current in zip(numeric, numeric[1:]):
        if current[0] <= previous[0]:
            raise ValueError("flow coordinates are not strictly increasing")
        if current[1] < 0.0 or current[1] > previous[1]:
            raise ValueError("pressure is negative or not non-increasing")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                        help=f"source XLSX (default: {DEFAULT_SOURCE})")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"canonical CSV (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    if not args.source.is_file():
        print(f"ERROR: source workbook not found: {args.source}", file=sys.stderr)
        return 2

    workbook_hash = sha256(args.source.read_bytes())
    if workbook_hash != EXPECTED_WORKBOOK_SHA256:
        print(f"ERROR: unexpected workbook SHA-256: {workbook_hash}", file=sys.stderr)
        return 2

    try:
        points = extract_points(args.source)
        validate_points(points)
        csv_bytes = render_csv(points)
    except (ET.ParseError, OSError, ValueError) as exc:
        print(f"ERROR: extraction/validation failed: {exc}", file=sys.stderr)
        return 2

    csv_hash = sha256(csv_bytes)
    if csv_hash != EXPECTED_CSV_SHA256:
        print(f"ERROR: extracted CSV SHA-256 mismatch: {csv_hash}", file=sys.stderr)
        return 2

    if args.output.exists():
        existing_hash = sha256(args.output.read_bytes())
        if existing_hash != EXPECTED_CSV_SHA256:
            print(
                f"ERROR: refusing to overwrite different existing file: {args.output} "
                f"(SHA-256 {existing_hash})",
                file=sys.stderr,
            )
            return 2
        print(f"Canonical CSV already matches: {args.output}")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(csv_bytes)
        print(f"Created: {args.output}")

    print(f"Retained points: {len(points)}")
    print(f"Shutoff: {float(points[0][0]):.9f} CFM, {float(points[0][1]):.9f} mmH2O")
    print(f"Free air: {float(points[-1][0]):.9f} CFM, {float(points[-1][1]):.9f} mmH2O")
    print(f"Workbook SHA-256: {workbook_hash}")
    print(f"CSV SHA-256: {csv_hash}")
    print("Flow-column notation C=0.95 remains unresolved; no additional factor was applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
