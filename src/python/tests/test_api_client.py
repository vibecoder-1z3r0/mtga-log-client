import json
import sqlite3

import requests

from seventeenlands import api_client


def test_no_op_api_client_never_hits_the_network(monkeypatch):
    def fail_post(*args, **kwargs):
        raise AssertionError("NoOpApiClient must never make a network request")

    monkeypatch.setattr(requests, "post", fail_post)

    client = api_client.NoOpApiClient(host="https://example.invalid")
    response = client.submit_rank({"token": "t", "rank_data": {}})

    assert response is None


def test_dump_api_client_stdout(capsys):
    client = api_client.DumpApiClient(host="https://example.invalid", dump_stdout=True)

    client.submit_rank({"token": "t", "rank_data": {"foo": "bar"}})

    out = capsys.readouterr().out.strip()
    parsed = json.loads(out)
    assert parsed["endpoint"] == "api/client/add_rank"
    assert parsed["blob"] == {"token": "t", "rank_data": {"foo": "bar"}}


def test_dump_api_client_stdout_disabled_by_default(capsys):
    client = api_client.DumpApiClient(host="https://example.invalid")

    client.submit_rank({"token": "t", "rank_data": {}})

    assert capsys.readouterr().out == ""


def test_dump_api_client_file(tmp_path):
    dump_file = tmp_path / "dump.jsonl"
    client = api_client.DumpApiClient(
        host="https://example.invalid", dump_file=str(dump_file)
    )

    client.submit_deck_submission({"token": "t", "deck": "x"})
    client.submit_deck_submission({"token": "t", "deck": "y"})

    lines = dump_file.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["blob"]["deck"] == "x"
    assert json.loads(lines[1])["blob"]["deck"] == "y"


def test_dump_api_client_sqlite(tmp_path):
    db_path = tmp_path / "dump.sqlite3"
    client = api_client.DumpApiClient(
        host="https://example.invalid", dump_sqlite=str(db_path)
    )

    client.submit_game_result({"token": "t", "result": "win"})

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT endpoint, blob FROM submissions").fetchall()
    assert len(rows) == 1
    endpoint, blob = rows[0]
    assert endpoint == "api/client/add_game"
    assert json.loads(blob) == {"token": "t", "result": "win"}


def test_dump_api_client_sqlite_accumulates_rows(tmp_path):
    db_path = tmp_path / "dump.sqlite3"
    client = api_client.DumpApiClient(
        host="https://example.invalid", dump_sqlite=str(db_path)
    )

    client.submit_rank({"token": "t", "rank_data": {"n": 1}})
    client.submit_rank({"token": "t", "rank_data": {"n": 2}})

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
    assert count == 2


def test_dump_api_client_all_destinations_at_once(tmp_path, capsys):
    dump_file = tmp_path / "dump.jsonl"
    db_path = tmp_path / "dump.sqlite3"
    client = api_client.DumpApiClient(
        host="https://example.invalid",
        dump_stdout=True,
        dump_file=str(dump_file),
        dump_sqlite=str(db_path),
    )

    client.submit_rank({"token": "t", "rank_data": {}})

    assert capsys.readouterr().out.strip() != ""
    assert dump_file.read_text().strip() != ""
    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0] == 1


def test_dump_api_client_never_hits_the_network(monkeypatch, tmp_path):
    def fail_post(*args, **kwargs):
        raise AssertionError("DumpApiClient must never make a network request")

    monkeypatch.setattr(requests, "post", fail_post)

    client = api_client.DumpApiClient(
        host="https://example.invalid",
        dump_stdout=True,
        dump_file=str(tmp_path / "dump.jsonl"),
        dump_sqlite=str(tmp_path / "dump.sqlite3"),
    )

    client.submit_rank({"token": "t", "rank_data": {}})
