from pathlib import Path

from docspipeline import docstring_coverage as dc

SOURCE = '''"""モジュールの説明。"""

__all__ = ["documented", "undocumented", "Public"]


def documented():
    """説明。"""


def undocumented():
    pass


def not_exported():
    pass


def _private():
    pass


class Public:
    """説明。"""

    def method(self):
        pass

    def _hidden(self):
        pass

    @property
    def value(self):
        """値。"""

    @value.setter
    def value(self, v):
        pass


class NotExported:
    pass
'''


def _scan(tmp_path: Path, text: str = SOURCE):
    path = tmp_path / "mod.py"
    path.write_text(text, encoding="utf-8")
    return dc.scan_file(path)


def test_missing_items_are_the_undocumented_public_ones(tmp_path):
    items = _scan(tmp_path)
    missing = {i.qualname for i in items if not i.documented}
    assert missing == {"mod.undocumented", "mod.Public.method"}


def test_all_restricts_top_level_names_only(tmp_path):
    names = {i.qualname for i in _scan(tmp_path)}
    assert "mod.not_exported" not in names
    assert "mod.NotExported" not in names
    assert "mod.Public.method" in names  # クラスの中身は __all__ の対象外


def test_private_names_and_setters_are_skipped(tmp_path):
    names = {i.qualname for i in _scan(tmp_path)}
    assert "mod._private" not in names
    assert "mod.Public._hidden" not in names
    assert sum(n == "mod.Public.value" for n in [i.qualname for i in _scan(tmp_path)]) == 1


def test_without_all_every_public_name_counts(tmp_path):
    items = _scan(tmp_path, "def a():\n    pass\n\ndef _b():\n    pass\n")
    assert {i.qualname for i in items if i.kind == "function"} == {"mod.a"}


def test_module_docstring_is_counted(tmp_path):
    items = _scan(tmp_path, "x = 1\n")
    assert [(i.kind, i.documented) for i in items] == [("module", False)]


def test_percent_and_format(tmp_path):
    report = dc.Report(tuple(_scan(tmp_path)))
    assert 0 < report.percent < 100
    text = dc.format_report(report, base=tmp_path)
    assert "mod.py:" in text and "mod.undocumented" in text
    assert "docstring のカバレッジ" in text


def test_empty_report_is_fully_covered():
    assert dc.Report(()).percent == 100.0


def test_scan_names_modules_from_the_package_root(tmp_path):
    pkg = tmp_path / "pkg"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""p."""\n', encoding="utf-8")
    (pkg / "sub" / "__init__.py").write_text('"""s."""\n', encoding="utf-8")
    (pkg / "sub" / "leaf.py").write_text('"""l."""\ndef f():\n    pass\n', encoding="utf-8")
    report = dc.scan([pkg])
    assert {i.qualname for i in report.items} >= {"pkg", "pkg.sub", "pkg.sub.leaf", "pkg.sub.leaf.f"}


def test_scan_skips_virtualenv_and_cache_dirs(tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "x.py").write_text("def f():\n    pass\n", encoding="utf-8")
    (tmp_path / "ok.py").write_text('"""d."""\n', encoding="utf-8")
    assert {i.path.name for i in dc.scan([tmp_path]).items} == {"ok.py"}
