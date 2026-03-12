# Gephi Backend

This backend documents a generic Gephi workflow for interactive exploration.
Project files are intentionally local/untracked.

## Open project

Generate Gephi export files first:

```sh
genealogy-tree export-gephi out/lineage_<id>.json
```

Then open Gephi with the generated GEXF:

```sh
make viz-gephi-open INPUT=out/lineage_<id>_gephi/lineage_<id>.gexf
```

## Recommended Gephi settings

1. Import merge strategy for parallel edges: `Sum`.
2. Use Inspector plugin for hover details.
3. For clutter reduction:
   - `Preview -> Edges -> Rescale weight` with fixed min/max.
   - Keep node labels off by default and inspect on hover.
4. For duplicate advisor links on multi-degree people, rely on merge strategy to avoid parallel-edge clutter.

## Global Gephi state note

Gephi stores some global settings outside the repo:

- `~/Library/Application Support/gephi/0.10`

Project/workspace settings in `.gephi` are local unless you choose to track one explicitly.
