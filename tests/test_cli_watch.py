from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from archmap.cli.commands import _get_project_mtimes, run_watch


@patch("archmap.utils.file_utils.discover_source_files")
def test_get_project_mtimes(mock_discover) -> None:
    mock_file = MagicMock(spec=Path)
    mock_file.__str__.return_value = "test.py"
    mock_file.stat.return_value.st_mtime = 12345.6
    mock_discover.return_value = [mock_file]

    mtimes = _get_project_mtimes(Path("."))

    assert mtimes == {"test.py": 12345.6}


@patch("archmap.cli.commands.time.sleep")
@patch("archmap.cli.commands._get_project_mtimes")
@patch("archmap.cli.commands.analyze_project")
@patch("archmap.cli.commands.print_summary")
@patch("archmap.cli.commands._print_watch_diff")
def test_run_watch_detects_change(
    mock_diff,
    mock_summary,
    mock_analyze,
    mock_mtimes,
    mock_sleep,
) -> None:
    mock_mtimes.side_effect = [
        {"a.py": 1.0},
        {"a.py": 2.0},
        KeyboardInterrupt(),
    ]

    args = MagicMock()
    args.path = "."
    args.interval = 0.001
    args.parallel = True

    run_watch(args)

    assert mock_analyze.call_count == 2
    mock_diff.assert_called_once()
