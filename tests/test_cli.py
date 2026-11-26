"""The `demo` command line, driven through its entry point."""

from compass import cli, metrics, warehouse


def test_demo_reset_builds_a_warehouse_on_a_clean_path(tmp_path, capsys):
    path = tmp_path / "nested" / "compass.duckdb"

    assert cli.main(["reset", "--path", str(path), "--seed", "42"]) == 0

    con = warehouse.connect(path)
    assert metrics.query(con, ["booking_count"]).loc[0, "booking_count"] > 0
    con.close()
    assert str(path) in capsys.readouterr().out
