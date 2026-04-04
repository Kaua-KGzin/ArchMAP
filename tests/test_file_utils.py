from archmap.utils.file_utils import (
    discover_source_files,
    normalize_file_id,
    percentile,
    should_ignore_parts,
    to_file_id,
)


def test_normalize_file_id():
    assert normalize_file_id("./src/main.py") == "src/main.py"
    assert normalize_file_id("src\\main.py") == "src/main.py"


def test_should_ignore_parts():
    assert should_ignore_parts(["src", "node_modules", "package"]) is True
    assert should_ignore_parts(["src", "main", "package"]) is False
    assert should_ignore_parts(["src", "tests", "unit"]) is True
    assert should_ignore_parts(["src", "feature", "package"], {"feature"}) is True


def test_discover_source_files(tmp_path):
    # Test file path input
    single_file = tmp_path / "test.py"
    single_file.write_text("print('test')")
    assert discover_source_files(single_file) == [single_file]

    # Test directory input
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('main')")
    (tmp_path / "src" / "utils.js").write_text("console.log('utils')")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "test.js").write_text("console.log('test')")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_main.py").write_text("print('test-main')")
    (tmp_path / "examples").mkdir()
    (tmp_path / "examples" / "sample.py").write_text("print('sample')")
    (tmp_path / "site").mkdir()
    (tmp_path / "site" / "bundle.js").write_text("console.log('bundle')")

    # Text file shouldn't be picked up
    (tmp_path / "test.txt").write_text("text")

    discovered = discover_source_files(tmp_path)
    assert set(discovered) == {
        single_file,
        tmp_path / "src" / "main.py",
        tmp_path / "src" / "utils.js",
    }

    # test single file not supported
    unsupported = tmp_path / "unsupported.txt"
    unsupported.write_text("hello")
    assert discover_source_files(unsupported) == []


def test_discover_source_files_includes_direct_tests_root(tmp_path):
    tests_root = tmp_path / "tests"
    tests_root.mkdir()
    target = tests_root / "test_parser.py"
    target.write_text("print('ok')")

    assert discover_source_files(tests_root) == [target]


def test_discover_source_files_supports_extra_ignored_dirs(tmp_path):
    (tmp_path / "src").mkdir()
    kept = tmp_path / "main.py"
    kept.write_text("print('main')")
    ignored = tmp_path / "src" / "main.py"
    ignored.write_text("print('src-main')")

    assert discover_source_files(tmp_path, extra_ignored_dirs={"src"}) == [kept]


def test_discover_source_files_size_limit(tmp_path):
    small = tmp_path / "small.py"
    small.write_text("print('small')")

    large = tmp_path / "large.py"
    large.write_text("print('large')" * 1000) # ~13KB

    # Limit at 1KB (1024 bytes)
    discovered = discover_source_files(tmp_path, max_file_size_bytes=1024)
    assert discovered == [small]

    # No limit
    discovered_all = discover_source_files(tmp_path, max_file_size_bytes=0)
    assert set(discovered_all) == {small, large}


def test_to_file_id(tmp_path):
    # If the root is a file and equals the file_path
    single_file = tmp_path / "test.py"
    single_file.write_text("test")
    assert to_file_id(single_file, single_file) == "test.py"

    # If the root is a directory
    file_path = tmp_path / "src" / "main.py"
    assert to_file_id(tmp_path, file_path) == "src/main.py"


def test_percentile():
    assert percentile([], 0.5) == 0
    assert percentile([1, 2, 3], -0.1) == 1
    assert percentile([1, 2, 3], 1.5) == 3
    assert percentile([1, 2, 3], 0.5) == 2
