# Graphviz Backend

This backend provides a standalone renderer for lineage JSON.

## Renderer

- `renderer/render_graphviz.py`

It reads `out/lineage_<id>.json`, collapses parallel edges by `(source,target)`, and emits a vertical DAG.
Depth-derived rank groups are intentionally not forced, so `dot` can reduce crossings more aggressively.

Default orientation is `rankdir=BT`:

- junior/start person near the bottom
- older advisors above

Default crossing controls:

- `newrank=true`
- `remincross=true`
- `mclimit=10`

## Config

- `config/vertical_ancestry.json`

Use `--config` to override defaults.

## Run

From repo root:

```sh
make viz-graphviz INPUT=out/lineage_<id>.json ID=<id>
```

From `viz/`:

```sh
make graphviz-render INPUT=../out/lineage_<id>.json ID=<id>
make graphviz-open ID=<id>
```

Direct script:

```sh
python3 viz/graphviz/renderer/render_graphviz.py \
  --input out/lineage_<id>.json \
  --output-dir viz/graphviz/generated/<id> \
  --format all
```
