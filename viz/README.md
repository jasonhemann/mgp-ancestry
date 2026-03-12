# Visualization Workspace

This directory contains versioned visualization backends and settings for lineage data.

## Layout

- `gephi/`: Gephi projects and backend-specific guidance.
- `graphviz/`: standalone Graphviz renderer and config.
- `Makefile`: convenience targets for both backends.

## Common usage

From repo root:

```sh
make viz-gephi-open INPUT=out/lineage_<id>_gephi/lineage_<id>.gexf
make viz-graphviz INPUT=out/lineage_<id>.json ID=<id>
```

From `viz/` directly:

```sh
make gephi-open INPUT=../out/lineage_<id>_gephi/lineage_<id>.gexf
make graphviz-render INPUT=../out/lineage_<id>.json ID=<id>
make graphviz-open ID=<id>
```
