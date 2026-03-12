# Releasing `genealogy-tree` (GitHub-only v0)

## Preconditions

- Local branch is up to date with `origin/master`.
- Runtime artifacts are not tracked (`out/`, `data/snapshots/`).

## 1) Optionally refresh visualization examples

```sh
source .venv/bin/activate
genealogy-tree build <start_id> --max-depth 50 --max-nodes 200000 --max-nodes-hard 300000
make viz-graphviz INPUT=out/lineage_<start_id>.json ID=<start_id> FORMAT=svg
make viz-graphviz INPUT=out/lineage_<start_id>.json ID=<start_id> FORMAT=png
```

## 2) Validate repository quality gates

```sh
source .venv/bin/activate
make check
```

## 3) Verify clean tracked state

```sh
git status --short
git ls-files out data/snapshots
```

Expected:

- `git status --short` has only intentional release changes.
- `git ls-files out data/snapshots` returns no paths.

## 4) Tag and publish on GitHub

```sh
git tag v0.1.0
git push origin master --tags
```

Create a GitHub release from tag `v0.1.0` with release notes summarizing:

- CLI capabilities
- strict schema policy
- generic visualization workflow (`Graphviz`, `Gephi import`)
