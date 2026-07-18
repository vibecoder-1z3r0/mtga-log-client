import json
import pathlib
import sqlite3
import sys
from typing import Any

import requests
from conftest import write_rank_log

from seventeenlands import mtga_follower


def _run_main(monkeypatch: Any, args: list[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["mtga_follower", *args])
    mtga_follower.main()


def _json_lines(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.startswith("{")]


def test_no_token_makes_no_network_call(monkeypatch, rank_log_file):
    def fail(*args, **kwargs):
        raise AssertionError("must not hit the network with --no-token")

    monkeypatch.setattr(requests, "post", fail)
    monkeypatch.setattr(requests, "get", fail)

    _run_main(
        monkeypatch,
        ["--no-token", "--once", "--local-log-files", str(rank_log_file)],
    )


def test_stdout_dump_prints_submission(monkeypatch, rank_log_file, capsys):
    _run_main(
        monkeypatch,
        ["--stdout-dump", "--once", "--local-log-files", str(rank_log_file)],
    )

    lines = _json_lines(capsys.readouterr().out)
    assert len(lines) == 1
    assert lines[0]["endpoint"] == "api/client/add_rank"
    assert lines[0]["blob"]["player_id"] == "test-user"


def test_file_dump_writes_submission(monkeypatch, rank_log_file, tmp_path):
    dump_file = tmp_path / "dump.jsonl"

    _run_main(
        monkeypatch,
        [
            "--file-dump",
            str(dump_file),
            "--once",
            "--local-log-files",
            str(rank_log_file),
        ],
    )

    lines = dump_file.read_text().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["blob"]["player_id"] == "test-user"


def test_sqlite_dump_writes_submission(monkeypatch, rank_log_file, tmp_path):
    db_file = tmp_path / "dump.sqlite3"

    _run_main(
        monkeypatch,
        [
            "--sqlite-dump",
            str(db_file),
            "--once",
            "--local-log-files",
            str(rank_log_file),
        ],
    )

    conn = sqlite3.connect(db_file)
    rows = conn.execute("SELECT endpoint, blob FROM submissions").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "api/client/add_rank"


def test_all_dump_flags_together(monkeypatch, rank_log_file, tmp_path, capsys):
    dump_file = tmp_path / "dump.jsonl"
    db_file = tmp_path / "dump.sqlite3"

    _run_main(
        monkeypatch,
        [
            "--stdout-dump",
            "--file-dump",
            str(dump_file),
            "--sqlite-dump",
            str(db_file),
            "--once",
            "--local-log-files",
            str(rank_log_file),
        ],
    )

    assert len(_json_lines(capsys.readouterr().out)) == 1
    assert dump_file.read_text().strip() != ""
    conn = sqlite3.connect(db_file)
    assert conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 1


def test_file_dump_alone_implies_no_token_and_no_network(
    monkeypatch, rank_log_file, tmp_path
):
    def fail(*args, **kwargs):
        raise AssertionError("--file-dump must not hit the network")

    monkeypatch.setattr(requests, "post", fail)
    monkeypatch.setattr(requests, "get", fail)

    _run_main(
        monkeypatch,
        [
            "--file-dump",
            str(tmp_path / "dump.jsonl"),
            "--once",
            "--local-log-files",
            str(rank_log_file),
        ],
    )


def test_multiple_local_log_files_are_all_processed(
    monkeypatch, tmp_path: pathlib.Path, capsys
):
    log1 = write_rank_log(tmp_path / "a.log", player_id="user-a")
    log2 = write_rank_log(tmp_path / "b.log", player_id="user-b")

    _run_main(
        monkeypatch,
        [
            "--stdout-dump",
            "--once",
            "--local-log-files",
            str(log1),
            str(log2),
        ],
    )

    lines = _json_lines(capsys.readouterr().out)
    player_ids = {line["blob"]["player_id"] for line in lines}
    assert player_ids == {"user-a", "user-b"}


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def test_real_upload_path_still_works_without_no_token(monkeypatch, rank_log_file):
    """Regression check: a normal --token run still reaches the real ApiClient."""
    posted_urls = []

    def fake_get(url: str, params: Any = None, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(200, json.dumps({"min_version": "0.0.0"}))

    def fake_post(url: str, **kwargs: Any) -> _FakeResponse:
        posted_urls.append(url)
        return _FakeResponse(200, "{}")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(requests, "post", fake_post)

    _run_main(
        monkeypatch,
        [
            "--token",
            "11111111-1111-4111-8111-111111111111",
            "--once",
            "--local-log-files",
            str(rank_log_file),
        ],
    )

    assert any(url.endswith("api/client/add_rank") for url in posted_urls)
