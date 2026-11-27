"""The `demo` command line, driven through its entry point."""

from compass import cli, metrics, warehouse


def test_demo_reset_builds_a_warehouse_on_a_clean_path(tmp_path, capsys):
    path = tmp_path / "nested" / "compass.duckdb"

    assert cli.main(["reset", "--path", str(path), "--seed", "42"]) == 0

    con = metrics.connect(path)
    assert metrics.query(con, ["booking_count"]).loc[0, "booking_count"] > 0
    con.close()
    assert str(path) in capsys.readouterr().out


def test_demo_setup_builds_the_warehouse_and_flags_a_missing_api_key(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    path = tmp_path / "compass.duckdb"

    assert cli.main(["setup", "--path", str(path)]) == 0

    con = metrics.connect(path)
    assert metrics.query(con, ["policy_count"]).loc[0, "policy_count"] > 0
    con.close()
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().out


def test_demo_setup_confirms_a_present_api_key_without_printing_it(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    assert cli.main(["setup", "--path", str(tmp_path / "compass.duckdb")]) == 0

    out = capsys.readouterr().out
    assert "ANTHROPIC_API_KEY is set" in out
    assert "sk-ant-test" not in out
