# genealogy-tree

## To activate env

```sh
uv sync --group dev
source .venv/bin/activate
```

## To deactivate

```sh
deactivate
```

## Build advisor lineage

Run the CLI with a starting MGP ID:

```sh
genealogy-tree build 75750
```

Outputs:

- Raw snapshots: `data/snapshots/<id>.html`
- Snapshot metadata: `data/snapshots/<id>.meta.json`
- Canonical graph JSON: `out/lineage_<start_id>.json`
- Markdown advisor lineage: `out/lineage_<start_id>.md`

`degree.year` in JSON is a structured value:

- `{"kind":"unknown"}`
- `{"kind":"years","values":[1973]}`
- `{"kind":"years","values":[1684,1686]}`
- `{"kind":"raw","text":"ca. 1700"}`

Key options:

```sh
genealogy-tree build 75750 \
  --max-depth 20 \
  --max-nodes 500 \
  --stop-id 2185 \
  --stop-name "Carl Friedrich Gauß"
```

Traversal direction is upward-only: person to all listed advisors.

Use exhaustive mode when you intentionally want to traverse further:

```sh
genealogy-tree build 75750 --exhaustive --max-nodes-hard 20000
```

Checkpoint/resume:

```sh
# start run and persist progress
genealogy-tree build 75750 --checkpoint-path out/checkpoint_75750.json

# continue from saved progress
genealogy-tree build 75750 --resume --checkpoint-path out/checkpoint_75750.json
```

Schema strictness policy (pre-alpha):

- Artifact loading is strict; deprecated shapes are rejected.
- Older outputs/checkpoints (for example with `{"kind":"year",...}` or legacy edge keys) may fail to load.
- Remedy: regenerate lineage JSON/checkpoints with a fresh `genealogy-tree build ...` run.

## Export to Gephi

Export an existing lineage JSON into Gephi-friendly formats:

```sh
genealogy-tree export-gephi out/lineage_75750.json
```

By default this writes to `out/lineage_75750_gephi/`:

- `lineage_75750_nodes.csv`
- `lineage_75750_edges.csv`
- `lineage_75750.gexf`

Use a custom output location/prefix:

```sh
genealogy-tree export-gephi out/lineage_75750.json \
  --out-dir out/gephi_75750 \
  --prefix lineage_75750
```

## Quality checks

```sh
make check
```

Or run tools individually:

```sh
make sync
make format
make lint
make lint-fix
make typecheck
make test
make coverage
```
