from docspipeline import cli, confluence, diagrams


def run(*argv):
    return cli.main(list(argv))


def test_init_creates_a_python_project_scaffold(tmp_path, capsys):
    src = tmp_path / "src" / "tool"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text('"""t."""\n', encoding="utf-8")
    (src / "core.py").write_text('"""c."""\n', encoding="utf-8")
    (src / "_internal.py").write_text("", encoding="utf-8")
    assert run("init", str(tmp_path), "--project", "Tool 日本語", "--author", "me", "--package", "../src") == 0

    docs = tmp_path / "docs"
    conf = (docs / "conf.py").read_text(encoding="utf-8")
    compile(conf, "conf.py", "exec")  # 構文が正しい
    assert "project='Tool 日本語'" in conf and "package_paths=['../src']" in conf
    api = (docs / "api.rst").read_text(encoding="utf-8")
    assert ".. automodule:: tool\n   :no-members:" in api
    assert ".. automodule:: tool.core" in api
    assert "_internal" not in api
    assert "   api" in (docs / "index.rst").read_text(encoding="utf-8")
    assert (docs / "page-template.rst.tmpl").exists()
    assert "_build/" in (docs / ".gitignore").read_text(encoding="utf-8")
    assert not (docs / "cpp.rst").exists()
    workflow = (tmp_path / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    assert "docspipeline coverage src" in workflow
    assert "doxygen" not in workflow.lower()
    assert "@@" not in workflow and "@@" not in conf


def test_init_title_rule_counts_wide_characters(tmp_path):
    run("init", str(tmp_path), "--project", "日本語", "--author", "me")
    lines = (tmp_path / "docs" / "index.rst").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "日本語" and len(lines[1]) >= 6


def test_init_with_cpp_adds_doxygen_everywhere(tmp_path):
    assert run("init", str(tmp_path), "--project", "E", "--author", "me", "--cpp", "../include") == 0
    assert (tmp_path / "docs" / "cpp.rst").exists()
    assert "cpp_sources=['../include']" in (tmp_path / "docs" / "conf.py").read_text(encoding="utf-8")
    assert "apt-get install -y doxygen" in (tmp_path / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")


def test_init_refuses_to_overwrite_without_force(tmp_path, capsys):
    assert run("init", str(tmp_path), "--project", "A", "--author", "me") == 0
    (tmp_path / "docs" / "overview.rst").write_text("手で書いた内容", encoding="utf-8")
    assert run("init", str(tmp_path), "--project", "A", "--author", "me") == 1
    assert (tmp_path / "docs" / "overview.rst").read_text(encoding="utf-8") == "手で書いた内容"
    assert run("init", str(tmp_path), "--project", "A", "--author", "me", "--force") == 0
    assert (tmp_path / "docs" / "overview.rst").read_text(encoding="utf-8") != "手で書いた内容"


def test_coverage_command_fails_under_threshold(tmp_path, capsys):
    (tmp_path / "m.py").write_text("def f():\n    pass\n", encoding="utf-8")
    assert run("coverage", str(tmp_path)) == 0
    assert run("coverage", str(tmp_path), "--fail-under", "50") == 1


def test_check_diagrams(tmp_path, capsys):
    (tmp_path / "a.drawio").write_text("<x/>", encoding="utf-8")
    (tmp_path / "b.drawio").write_text("<x/>", encoding="utf-8")
    (tmp_path / "b.drawio.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "c.drawio").write_text("<x/>", encoding="utf-8")
    (tmp_path / "c.svg").write_text("<svg/>", encoding="utf-8")
    assert run("check-diagrams", str(tmp_path)) == 1
    assert [p.name for p in diagrams.find_missing_exports(tmp_path)] == ["a.drawio"]


def test_publish_beyond_local_requires_settings_and_stops_before_building(tmp_path, monkeypatch, capsys):
    for name in confluence.REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    called = []
    monkeypatch.setattr(cli, "_run", lambda *a, **k: called.append(a) or 0)
    assert run("publish", str(tmp_path), "--mode", "publish") == 2
    assert run("publish", str(tmp_path), "--mode", "dryrun") == 2
    assert called == []
    assert "CONFLUENCE_API_TOKEN" in capsys.readouterr().err


def test_publish_local_never_runs_the_connection_test(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: commands.append((list(cmd), env)) or 0)
    assert run("publish", str(tmp_path)) == 0
    assert len(commands) == 1
    cmd, env = commands[0]
    assert "connection-test" not in cmd and "confluence" in cmd
    assert env == {"DOCSPIPELINE_CONFLUENCE_MODE": "local"}


def test_publish_runs_connection_test_first_and_stops_on_failure(tmp_path, monkeypatch):
    for name in confluence.REQUIRED_ENV:
        monkeypatch.setenv(name, "x" * 12)
    commands = []
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: commands.append(list(cmd)) or 1)
    assert run("publish", str(tmp_path), "--mode", "publish") == 1
    assert len(commands) == 1 and "connection-test" in commands[0]


def test_build_never_publishes_even_if_the_environment_asks_to(tmp_path, monkeypatch):
    # 環境変数にモードが残っていても、build / linkcheck は local 固定 (意図しない公開を防ぐ)
    monkeypatch.setenv("DOCSPIPELINE_CONFLUENCE_MODE", "publish")
    commands = []
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: commands.append((list(cmd), env)) or 0)
    assert run("build", str(tmp_path), "-b", "confluence") == 0
    assert run("linkcheck", str(tmp_path)) == 0
    for _, env in commands:
        assert env["DOCSPIPELINE_CONFLUENCE_MODE"] == "local"


def test_require_mermaid_sets_the_policy(tmp_path, monkeypatch):
    commands = []
    monkeypatch.setattr(cli, "_run", lambda cmd, env=None: commands.append((list(cmd), env)) or 0)
    run("build", str(tmp_path), "--require-mermaid")
    cmd, env = commands[0]
    assert env["DOCSPIPELINE_MERMAID_MISSING"] == "error"
    assert "-W" in cmd and "--keep-going" in cmd
    run("build", str(tmp_path), "--no-strict")
    assert "-W" not in commands[1][0]


def test_doctor_reports_without_leaking_values(monkeypatch, capsys):
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "tok-0123456789abcdef")
    code = run("doctor")
    out = capsys.readouterr().out
    assert code == 0  # このテスト環境には、必須の Sphinx などが入っている
    assert "Sphinx" in out and "tok-0123456789abcdef" not in out
    assert "未設定: " in out and "CONFLUENCE_API_TOKEN" not in out.split("未設定: ")[1]


def test_run_masks_the_token_in_child_output(monkeypatch, capsys):
    monkeypatch.setenv("CONFLUENCE_API_TOKEN", "tok-0123456789abcdef")
    import sys

    code = cli._run([sys.executable, "-c", "print('leak: tok-0123456789abcdef')"])
    out = capsys.readouterr().out
    assert code == 0 and "tok-0123456789abcdef" not in out and "leak: ***" in out
