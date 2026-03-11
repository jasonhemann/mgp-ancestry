from __future__ import annotations

import json
from pathlib import Path

from genealogy_tree import cli


def _write_snapshot(snapshot_dir: Path, person_id: str, html: str) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    html_path = snapshot_dir / f"{person_id}.html"
    meta_path = snapshot_dir / f"{person_id}.meta.json"
    html_path.write_text(html, encoding="utf-8")
    meta_path.write_text(
        json.dumps(
            {
                "id": person_id,
                "url": f"https://genealogy.math.ndsu.nodak.edu/id.php?id={person_id}",
                "fetched_at_utc": "2026-03-10T00:00:00+00:00",
                "sha256": "test",
                "http_status": 200,
                "content_length": len(html),
                "parser_version": "test",
            }
        ),
        encoding="utf-8",
    )


def test_cli_build_from_local_snapshot(tmp_path: Path):
    html = """
    <html>
      <head><title>Demo Person - The Mathematics Genealogy Project</title></head>
      <body>
        <h2 style=\"text-align: center;\">Demo Person</h2>
        <div style=\"line-height: 30px; text-align: center; margin-bottom: 1ex\">
          <span>Ph.D. <span style=\"color:#006633\">Demo University</span> 2000</span>
          <img alt=\"Nowhere\" />
        </div>
        <div style=\"text-align: center\"><span id=\"thesisTitle\">Demo thesis</span></div>
        <p style=\"text-align: center\">Advisor: Unknown</p>
      </body>
    </html>
    """
    snapshot_dir = tmp_path / "snapshots"
    out_dir = tmp_path / "out"
    _write_snapshot(snapshot_dir, "1", html)

    exit_code = cli.main(
        [
            "build",
            "1",
            "--snapshot-dir",
            str(snapshot_dir),
            "--out-dir",
            str(out_dir),
            "--max-depth",
            "0",
        ]
    )

    assert exit_code == 0
    assert (out_dir / "lineage_1.json").exists()
    assert (out_dir / "lineage_1.md").exists()


def test_cli_exhaustive_resolve_defaults():
    parser = cli._build_parser()
    args = parser.parse_args(["build", "1", "--exhaustive"])
    config = cli._resolve_traversal_config(args)
    assert config.exhaustive is True
    assert config.max_depth is None
    assert config.max_nodes is None
    assert config.direction == "advisor"


def test_cli_resume_from_checkpoint(tmp_path: Path):
    html_1 = """
    <html><head><title>P1 - The Mathematics Genealogy Project</title></head><body>
      <h2 style="text-align: center;">P1</h2>
      <div style="line-height: 30px; text-align: center; margin-bottom: 1ex">
        <span>Ph.D. <span style="color:#006633">U1</span> 2001</span><img alt="X" />
      </div>
      <div style="text-align: center"><span id="thesisTitle">T1</span></div>
      <p style="text-align: center">Advisor 1: <a href="id.php?id=2">P2</a></p>
    </body></html>
    """
    html_2 = """
    <html><head><title>P2 - The Mathematics Genealogy Project</title></head><body>
      <h2 style="text-align: center;">P2</h2>
      <div style="line-height: 30px; text-align: center; margin-bottom: 1ex">
        <span>Ph.D. <span style="color:#006633">U2</span> 1990</span><img alt="X" />
      </div>
      <div style="text-align: center"><span id="thesisTitle">T2</span></div>
      <p style="text-align: center">Advisor 1: <a href="id.php?id=3">P3</a></p>
    </body></html>
    """
    html_3 = """
    <html><head><title>P3 - The Mathematics Genealogy Project</title></head><body>
      <h2 style="text-align: center;">P3</h2>
      <div style="line-height: 30px; text-align: center; margin-bottom: 1ex">
        <span>Ph.D. <span style="color:#006633">U3</span> 1980</span><img alt="X" />
      </div>
      <div style="text-align: center"><span id="thesisTitle">T3</span></div>
      <p style="text-align: center">Advisor: Unknown</p>
    </body></html>
    """
    snapshot_dir = tmp_path / "snapshots"
    out_dir = tmp_path / "out"
    checkpoint = out_dir / "checkpoint.json"
    _write_snapshot(snapshot_dir, "1", html_1)
    _write_snapshot(snapshot_dir, "2", html_2)
    _write_snapshot(snapshot_dir, "3", html_3)

    first_exit = cli.main(
        [
            "build",
            "1",
            "--snapshot-dir",
            str(snapshot_dir),
            "--out-dir",
            str(out_dir),
            "--max-nodes",
            "1",
            "--checkpoint-path",
            str(checkpoint),
        ]
    )
    assert first_exit == 0
    checkpoint_payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert checkpoint_payload["complete"] is False

    second_exit = cli.main(
        [
            "build",
            "1",
            "--snapshot-dir",
            str(snapshot_dir),
            "--out-dir",
            str(out_dir),
            "--max-nodes",
            "10",
            "--checkpoint-path",
            str(checkpoint),
            "--resume",
        ]
    )
    assert second_exit == 0
    payload = json.loads((out_dir / "lineage_1.json").read_text(encoding="utf-8"))
    assert set(payload["nodes"].keys()) == {"1", "2", "3"}


def test_cli_bidirectional_traversal_from_snapshot(tmp_path: Path):
    html_1 = """
    <html><head><title>P1 - The Mathematics Genealogy Project</title></head><body>
      <h2 style="text-align: center;">P1</h2>
      <div style="line-height: 30px; text-align: center; margin-bottom: 1ex">
        <span>Ph.D. <span style="color:#006633">U1</span> 2001</span><img alt="X" />
      </div>
      <div style="text-align: center"><span id="thesisTitle">T1</span></div>
      <p style="text-align: center">Advisor: Unknown</p>
      <p style="text-align: center">Students:</p>
      <table style="margin-left: auto; margin-right: auto">
        <tr><th>Name</th><th>School</th><th>Year</th><th>Descendants</th></tr>
        <tr><td><a href="id.php?id=2">P2</a></td><td>U1</td><td>2015</td><td></td></tr>
      </table>
    </body></html>
    """
    html_2 = """
    <html><head><title>P2 - The Mathematics Genealogy Project</title></head><body>
      <h2 style="text-align: center;">P2</h2>
      <div style="line-height: 30px; text-align: center; margin-bottom: 1ex">
        <span>Ph.D. <span style="color:#006633">U2</span> 2015</span><img alt="X" />
      </div>
      <div style="text-align: center"><span id="thesisTitle">T2</span></div>
      <p style="text-align: center">Advisor: Unknown</p>
    </body></html>
    """
    snapshot_dir = tmp_path / "snapshots"
    out_dir = tmp_path / "out"
    _write_snapshot(snapshot_dir, "1", html_1)
    _write_snapshot(snapshot_dir, "2", html_2)

    exit_code = cli.main(
        [
            "build",
            "1",
            "--snapshot-dir",
            str(snapshot_dir),
            "--out-dir",
            str(out_dir),
            "--max-depth",
            "1",
            "--direction",
            "both",
        ]
    )
    assert exit_code == 0
    payload = json.loads((out_dir / "lineage_1.json").read_text(encoding="utf-8"))
    assert payload["config"]["direction"] == "both"
    assert payload["stats"]["student_edge_count"] == 1
    assert set(payload["nodes"].keys()) == {"1", "2"}
