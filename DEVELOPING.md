# Developing `mgp-ancestry`

## Environment

```sh
uv sync --group dev
source .venv/bin/activate
```

## Runtime Artifact Policy

- Do not track files under `out/` or `data/snapshots/`.
- Visualization scratch output under `viz/*/generated/` is also untracked.
- Guard script:

```sh
bash scripts/check_tracked_runtime_artifacts.sh
```

## Quality Gates

```sh
make check
```

Or run individually:

```sh
make repo-hygiene
make lint
make typecheck
make test
make coverage
```

## Formatting and Lint Fixes

```sh
make format
make lint-fix
```
