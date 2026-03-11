# Visualization Workspace

This directory contains versioned visualization backends and settings for lineage data.

## Layout

- `gephi/`: Gephi projects and backend-specific guidance.
- `graphviz/`: standalone Graphviz renderer and config.
- `Makefile`: convenience targets for both backends.

## Common usage

From repo root:

```sh
make viz-gephi-open
make viz-graphviz INPUT=out/lineage_75750.json ID=75750
```

From `viz/` directly:

```sh
make gephi-open
make graphviz-render INPUT=../out/lineage_75750.json ID=75750
make graphviz-open ID=75750
```
