from __future__ import annotations

import pytest

from archmap.cli.main import main


def test_print_completion_bash(capsys):
    code = main(["--print-completion", "bash"])
    assert code == 0
    out = capsys.readouterr().out
    assert "register-python-argcomplete" in out
    assert "archmap" in out


def test_print_completion_zsh(capsys):
    code = main(["--print-completion", "zsh"])
    assert code == 0
    out = capsys.readouterr().out
    assert "register-python-argcomplete" in out


def test_print_completion_fish(capsys):
    code = main(["--print-completion", "fish"])
    assert code == 0
    out = capsys.readouterr().out
    assert "register-python-argcomplete" in out
    assert "fish" in out


def test_print_completion_invalid_shell():
    """Invalid shell choice must cause argparse to exit with code 2."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--print-completion", "powershell"])
    assert exc_info.value.code == 2


def test_print_completion_does_not_run_command(capsys):
    """--print-completion must exit before running any subcommand."""
    code = main(["--print-completion", "bash"])
    assert code == 0
    # Banner is not printed (no tty in tests) and no analysis output
    out = capsys.readouterr().out
    assert "filesAnalyzed" not in out
