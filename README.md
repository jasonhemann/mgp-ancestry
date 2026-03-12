# genealogy-tree

Build advisor-only ancestry DAGs from Mathematics Genealogy Project pages.

This repository is a reusable CLI tool: start from any MGP ID and traverse upward through all listed advisors.

## Setup

```sh
uv sync --group dev
source .venv/bin/activate
```

## Build advisor lineage

Run the CLI with any starting MGP ID:

```sh
genealogy-tree build <start_id>
```

Outputs (runtime artifacts, intentionally not tracked in git):

- Raw snapshots: `data/snapshots/<id>.html`
- Snapshot metadata: `data/snapshots/<id>.meta.json`
- Canonical graph JSON: `out/lineage_<start_id>.json`
- Markdown advisor lineage: `out/lineage_<start_id>.md`

`degree.year` in JSON is structured:

- `{"kind":"unknown"}`
- `{"kind":"years","values":[1973]}`
- `{"kind":"years","values":[1684,1686]}`
- `{"kind":"raw","text":"ca. 1700"}`

Key options:

```sh
genealogy-tree build <start_id> \
  --max-depth 20 \
  --max-nodes 500 \
  --stop-id 2185 \
  --stop-name "Carl Friedrich Gauß"
```

Traversal direction is upward-only: person to all listed advisors.

For deeper pulls:

```sh
genealogy-tree build <start_id> --exhaustive --max-nodes-hard 20000
```

Checkpoint/resume:

```sh
genealogy-tree build <start_id> --checkpoint-path out/checkpoint_<start_id>.json
genealogy-tree build <start_id> --resume --checkpoint-path out/checkpoint_<start_id>.json
```

Schema strictness policy (pre-alpha):

- Artifact loading is strict; deprecated shapes are rejected.
- Older outputs/checkpoints (for example with `{"kind":"year",...}` or legacy edge keys) may fail to load.
- Remedy: regenerate lineage JSON/checkpoints with a fresh `genealogy-tree build ...` run.

## Example Output

Sample full-depth Graphviz output for start ID `281144`:

- `docs/examples/lineage_281144.svg`
- `docs/examples/lineage_281144.png`

![Example lineage render](docs/examples/lineage_281144.png)

## Export to Gephi

Export an existing lineage JSON into Gephi-friendly formats:

```sh
genealogy-tree export-gephi out/lineage_<start_id>.json
```

By default this writes to `out/lineage_<start_id>_gephi/`:

- `lineage_<start_id>_nodes.csv`
- `lineage_<start_id>_edges.csv`
- `lineage_<start_id>.gexf`

Use a custom output location/prefix:

```sh
genealogy-tree export-gephi out/lineage_<start_id>.json \
  --out-dir out/gephi_<start_id> \
  --prefix lineage_<start_id>
```

## Data Policy

- Bulk snapshots and generated lineage outputs are not tracked in git.
- Visualization outputs in `viz/*/generated/` are also untracked.
- Parser fixtures in `tests/fixtures/mgp/` are intentionally minimal regression corpus files.

## Attribution and Non-Affiliation

- This project consumes publicly available MGP web pages for research tooling.
- It is not affiliated with The Mathematics Genealogy Project.
- Users should respect source-site policies and keep conservative crawl-delay settings.

## Quality checks

```sh
make check
```

Or run tools individually:

```sh
make repo-hygiene
make sync
make format
make lint
make lint-fix
make typecheck
make test
make coverage
```
