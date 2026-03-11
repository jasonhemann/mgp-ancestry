# Graphviz Backend

This backend provides a standalone renderer for lineage JSON.

## Renderer

- `renderer/render_graphviz.py`

It reads `out/lineage_<id>.json`, collapses parallel edges by `(source,target)`, and emits a layered vertical DAG.

Default orientation is `rankdir=BT`:

- junior/start person near the bottom
- older advisors above

## Config

- `config/vertical_ancestry.json`

Use `--config` to override defaults.

## Run

From repo root:

```sh
make viz-graphviz INPUT=out/lineage_75750.json ID=75750
```

From `viz/`:

```sh
make graphviz-render INPUT=../out/lineage_75750.json ID=75750
make graphviz-open ID=75750
```

Direct script:

```sh
python3 viz/graphviz/renderer/render_graphviz.py \
  --input out/lineage_75750.json \
  --output-dir viz/graphviz/generated/75750 \
  --format all
```
