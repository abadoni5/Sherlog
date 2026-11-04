from pathlib import Path

from typer.testing import CliRunner

from sherlog import __version__
from sherlog.cli.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_version_flag_prints_version():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_gitignore_protects_secrets_and_runtime_data():
    lines = (ROOT / ".gitignore").read_text().splitlines()
    for entry in (".env", "sherlog.local.toml", ".sherlog/", "runs/"):
        assert entry in lines
