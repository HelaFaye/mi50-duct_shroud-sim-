# Repository status and scope audit

## Audited baseline

- Repository: `HelaFaye/mi50-duct_shroud-sim-`
- Stable branch: `main`
- Initial audited commit: `227ced78fa3fe52926d0108a0a40638814dd8c70`
- Current tested baseline commit: `eca4f4493e4df18843932a3e755299645ef1822f`
- Audited local checkout: `~/Downloads/mi50-duct_shroud-sim`
- Source snapshot at initial audit: 28 tracked files; the CI workflow and this status document were subsequently added.
- The project `.gitignore` contains `*.pyc`; no global `core.excludesfile` was configured during the audit.

The file inventory was enumerated from the working tree and compared with the published Git tree. The absent CAD/CFD files are not being hidden by the observed ignore configuration.

## Present capabilities

| Area | Checked-in files | Status |
|---|---|---|
| Fan/system operating point | `analysis/fan_operating_point.py`, `tests/test_fan_operating_point.py` | Implemented; 17 tests |
| Fan data | ARCTIC P9 Max manufacturer-workbook curve and historical digitization; Noctua NF-A14 manufacturer curve; Cybenetics NF-A14x25 G2 raw 72-point dataset; `data/fan_curves/README.md` | P9 remains canonical; NF-A14 is solver-ready at 1500 RPM; G2 measurements preserved raw pending an approved derivation method |
| System curve | `data/system_curves/mi50_system_curve_template.csv` | Header-only template; no measured MI50 data |
| Photogrammetry scale fitting | `scripts/photogrammetry_scale_fit.py`, `tests/test_photogrammetry_scale_fit.py` | Implemented; 4 tests |
| Mechanical identity / provenance | `data/mi50_envelope.json`, `mi50_envelope.json`, `MI50_PUBLIC_REFERENCE_MODELS.md`, `PUBLIC_SOURCES.md`, `docs/` | Documentation/data present; verify against each physical specimen |
| Browser content | `site/index.html`, `site/docs/` | Static site files present; inspect dependencies before claiming an integrated CAD editor |
| CFD | `simulation/README.md` | Planning/documentation only; no validated CFD case or fluid mesh present |
| Automated Python CI | `.github/workflows/tests.yml` | Implemented; Python 3.10, 3.12, and 3.14 jobs passed in run 44953907969 |

## Absent from the audited checkout

The following paths are referenced by the older project description but do not exist in the audited tree:

- `cad/openscad/` and its OpenSCAD model sources
- `models/reference/` and reference STL meshes
- `analysis/duct_sizing.py`
- `analysis/noise_budget.py`
- `data/fan_catalog.csv`
- `docs/AIRFLOW_DESIGN.md`
- `docs/GEOMETRY_AND_ROADMAP.md`
- `docs/WEB_EDITOR.md`

Do not recreate these as empty placeholders or claim they are restored. Recover them from a trusted backup/source revision, or implement and validate them as new work.

## Verification commands

```bash
# Confirm the current branch and worktree state
git status --short --branch
git log -1 --oneline --decorate

# Enumerate actual files (excluding Git internals)
find . -path './.git' -prune -o -type f -print | sort

# Run the standard-library test suite
python3 -m compileall -q analysis scripts tests
python3 -m unittest discover -s tests -v

git diff --check
```

## Engineering boundaries

- The 2 mmH₂O at 50 CFM quadratic reference is a hypothetical screening input, not measured MI50 resistance.
- The canonical P9 Max curve is extracted from the manufacturer CFD workbook; it has ten points, unresolved `C=0.95` flow notation, and no published pointwise uncertainty. The manual digitization is retained separately for comparison.
- The system-curve CSV is a template, not a measurement dataset.
- The ideal bulk-air temperature rise is not a GPU junction/HBM/VRM temperature prediction.
- The current fan model assumes identical parallel fans with equal flow sharing and one fixed-speed steady-state fan curve.
- No uncertainty interval is defensible until the curve and instrument uncertainty inputs, distributions, and correlations are explicitly supplied.

## Development tracking

The current plan and work log are maintained in:

- [`DEVELOPMENT_PLAN.md`](DEVELOPMENT_PLAN.md) — milestones and acceptance gates.
- [`PROGRESS.md`](PROGRESS.md) — tested baseline, completed work, active work, and dated log.

The next engineering milestone is M1: specify uncertainty semantics and the fan/system curve input-data contract. Do not begin Monte Carlo implementation until the uncertainty types, distribution assumptions, correlations, and physically valid curve-sampling method are documented and reviewed.
