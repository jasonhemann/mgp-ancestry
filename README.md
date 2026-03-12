# genealogy-tree

Build advisor-only ancestry DAGs from Mathematics Genealogy Project pages.

This repository is a reusable CLI tool: start from any MGP ID and traverse upward through all listed advisors.

## Quickstart

```sh
uv sync --group dev
source .venv/bin/activate
genealogy-tree build <start_id>
```

Key options:

```sh
genealogy-tree build <start_id> \
  --max-depth 20 \
  --max-nodes 500 \
  --stop-id 2185 \
  --stop-name "Carl Friedrich Gauß"
```

Traversal direction is upward-only: person to all listed advisors.

See all options:

```sh
genealogy-tree build --help
```

## Example Output

Sample full-depth Graphviz output for start ID `281144`:

- `docs/examples/lineage_281144.svg`
- `docs/examples/lineage_281144.png`

![Example lineage render](docs/examples/lineage_281144.png)

## Visualization

Export an existing lineage JSON into Gephi-friendly formats:

```sh
genealogy-tree export-gephi out/lineage_<start_id>.json
```

```sh
make viz-graphviz INPUT=out/lineage_<start_id>.json ID=<start_id> FORMAT=png
```

See all export options:

```sh
genealogy-tree export-gephi --help
```

## Attribution and Non-Affiliation

- This project consumes publicly available MGP web pages for research tooling.
- It is not affiliated with The Mathematics Genealogy Project.
- Users should respect source-site policies and conservative crawl-delay settings.

## For Contributors

Developer details are in [DEVELOPING.md](DEVELOPING.md).
