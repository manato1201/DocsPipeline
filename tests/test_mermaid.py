import stat
import sys
import textwrap

import pytest

from docspipeline import mmdc


def _fake_mmdc(path, *, ok=True):
    """-o の出力先に、固定の SVG を書くだけの偽 mmdc。"""
    body = textwrap.dedent(
        f"""\
        #!{sys.executable}
        import sys
        args = sys.argv[1:]
        if not {ok!r}:
            print("boom", file=sys.stderr)
            sys.exit(3)
        out = args[args.index("-o") + 1]
        open(out, "w").write('<svg xmlns="http://www.w3.org/2000/svg"/>')
        """
    )
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return [str(path)]


def test_render_writes_an_svg_and_reuses_it(tmp_path):
    cmd = _fake_mmdc(tmp_path / "mmdc")
    out = mmdc.render("flowchart LR\n A-->B", tmp_path / "out", cmd=cmd)
    assert out.suffix == ".svg" and out.read_text().startswith("<svg")
    mtime = out.stat().st_mtime_ns
    again = mmdc.render("flowchart LR\n A-->B", tmp_path / "out", cmd=cmd)
    assert again == out and again.stat().st_mtime_ns == mtime
    assert not list((tmp_path / "out").glob("*.part"))


def test_different_code_gets_a_different_file(tmp_path):
    cmd = _fake_mmdc(tmp_path / "mmdc")
    a = mmdc.render("flowchart LR\n A-->B", tmp_path / "out", cmd=cmd)
    b = mmdc.render("flowchart LR\n A-->C", tmp_path / "out", cmd=cmd)
    assert a != b


def test_render_failure_reports_the_reason(tmp_path):
    cmd = _fake_mmdc(tmp_path / "mmdc", ok=False)
    with pytest.raises(mmdc.MermaidRenderError, match="boom"):
        mmdc.render("x", tmp_path / "out", cmd=cmd)
    assert not list((tmp_path / "out").glob("*.svg"))


def test_missing_executable_is_a_render_error(tmp_path):
    with pytest.raises(mmdc.MermaidRenderError):
        mmdc.render("x", tmp_path / "out", cmd=[str(tmp_path / "nope")])


def test_find_mmdc_prefers_explicit_setting_then_env_then_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.delenv(mmdc.MMDC_ENV, raising=False)
    assert mmdc.find_mmdc(None, tmp_path) is None

    local = tmp_path / "node_modules" / ".bin"
    local.mkdir(parents=True)
    (local / "mmdc").write_text("")
    assert mmdc.find_mmdc(None, tmp_path) == [str(local / "mmdc")]

    monkeypatch.setenv(mmdc.MMDC_ENV, "npx --no-install mmdc")
    assert mmdc.find_mmdc(None, tmp_path) == ["npx", "--no-install", "mmdc"]
    assert mmdc.find_mmdc("custom --flag", tmp_path) == ["custom", "--flag"]
