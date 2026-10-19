# OAB Stable dataset

Frozen Stable-track instances (fixed seeds; see `manifest.json`). Run as
an implicit Harbor dataset:

```bash
harbor run -p tasks -a "<agent>" -m "<model>"        # all tasks
harbor run -p tasks/bank-recon-missing-fee -a oracle # solvability check
```

Files:

- `dataset.toml` — explicit Harbor dataset manifest for publishing /
  `harbor sync`; local runs use the directory (`harbor run -p tasks`).
  Task digests replicate Harbor's `Packager.compute_content_hash`, so
  `harbor sync tasks` reports no changes.
- `manifest.json` / `manifest.schema.json` — task catalog with family,
  seed, generator version, and content digest per task.
- `metric.py` — Harbor dataset metric: Verified Task Completion Rate
  plus per-layer means (see ../docs/metrics.md).

Do not edit task directories by hand. They are generated:
`uv run oab generate --all` regenerates tasks, digests, and this
dataset's files deterministically. CI enforces that committed tasks
match the generators and that `tests/grader.py` copies match
`src/oab/_verifier_core.py`.
