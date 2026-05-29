# old_code archive policy

This folder stores exploratory and legacy artifacts that are not part of the
runtime pipeline.

Rules:
- No production logic should be imported from this folder.
- Keep only notebooks/scripts needed for historical reference.
- Prefer moving temporary experiments out of the repository.
- Runtime code must live under `code/ltsbikeplan/`.

Kept content:
- Legacy notebooks for thesis/research reproducibility.
- `legacy_scripts/` for one-off historical utilities.
- `resources/` for legacy notebook inputs (`bna_scoring.json`, `destinations.json`).

Removed noise:
- Transient caches and generated temporary files should not be kept here.
