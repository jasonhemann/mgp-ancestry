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
- `{"kind":"year","value":1973}`
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
