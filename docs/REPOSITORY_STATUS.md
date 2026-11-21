# Repository status and scope audit

## Audited baseline

- Repository: `HelaFaye/mi50-duct_shroud-sim-`
- Branch: `main`
- Baseline commit: `227ced78fa3fe52926d0108a0a40638814dd8c70`
- Audited local checkout: `~/Downloads/mi50-duct_shroud-sim`
- Tracked source snapshot: 28 files
- Local working tree: clean; only generated Python bytecode caches were ignored
- Overlay checksum manifest: all five entries verified successfully

The file inventory was enumerated from the working tree and compared with the published Git tree. The project `.gitignore` contains `*.pyc`; no global `core.excludesfile` was configured. Thus the absent CAD/CFD files are not being hidden by the observed ignore configuration.

## Present capabilities

| Area | Checked-in files | Status |
|---|---|---|
| Fan/system operating point | `analysis/fan_operating_point.py`, `tests/test_fan_operating_point.py` | Implemented; 17 tests |
| Fan data | `data/fan_curves/arctic_p9_max_4300rpm_digitized.csv`, `data/fan_curves/README.md` | Approximate manual P–Q chart digitization |
| System curve | `data/system_curves/mi50_system_curve_template.csv` | Header-only template; no measured MI50 data |
| Photogrammetry scale fitting | `scripts/photogrammetry_scale_fit.py`, `tests/test_photogrammetry_scale_fit.py` | Implemented; 4 tests |
| Mechanical identity / provenance | `data/mi50_envelope.json`, `mi50_envelope.json`, `MI50_PUBLIC_REFERENCE_MODELS.md`, `PUBLIC_SOURCES.md`, `docs/` | Documentation/data present; verify against each physical specimen |
| Browser content | `site/index.html`, `site/docs/` | Static site files present; inspect dependencies before claiming an integrated CAD editor |
| CFD | `simulation/README.md` | Planning/documentation only; no validated CFD case or fluid mesh present |

## Absent from the audited checkout

The following paths are referenced by the older README but do not exist in the audited tree:

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
python3 -m unittest discover -s tests -v

# Check patch whitespace after applying a future overlay
git diff --check
```

## Engineering boundaries

- The 2 mmH₂O at 50 CFM quadratic reference is a hypothetical screening input, not measured MI50 resistance.
- The fan curve's intermediate points are manually digitized; treat them as approximate.
- The system-curve CSV is a template, not a measurement dataset.
- The ideal bulk-air temperature rise is not a GPU junction/HBM/VRM temperature prediction.
- The current fan model assumes identical parallel fans with equal flow sharing and one fixed-speed steady-state fan curve.
- No uncertainty interval is defensible until the curve and instrument uncertainty inputs are explicitly supplied.

## Next work

1. Add automated CI for the existing 21-test suite.
2. Implement uncertainty-aware fan/system curve inputs and operating-point propagation without assigning invented uncertainty values.
3. Implement sensitivity studies for RPM and system resistance, keeping manufacturer affinity-law scaling assumptions explicit.
4. Restore or develop the missing CAD/CFD assets from verified source material.
