# Gephi Backend

This backend keeps a versioned Gephi project for interactive exploration.

## Project file

- `projects/lineage_75750_explore.gephi`

## Open project

From repo root:

```sh
make viz-gephi-open
```

From `viz/`:

```sh
make gephi-open
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

Project/workspace settings in `.gephi` remain versioned here.
