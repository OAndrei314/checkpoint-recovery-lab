import json

from checkpoint_lab.cli import main


def test_cli_json_and_invalid_input(tmp_path, capsys):
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(dict(useful_seconds=100, intervals_seconds=[30, 60],
                                    checkpoint_seconds=5, recovery_seconds=10)))
    assert main([str(path), "--json"]) == 0
    results = json.loads(capsys.readouterr().out)
    assert results[0]["interval_seconds"] == 60
    assert results[0]["total_seconds"] == 105
    path.write_text('{"intervals_seconds": []}')
    assert main([str(path)]) == 2
    assert "at least one" in capsys.readouterr().err
