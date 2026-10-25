from docspipeline import doctor


def test_required_failures_set_the_exit_code():
    ok = [doctor.Check("a", True, "", required=True), doctor.Check("b", False, "", required=False)]
    assert doctor.exit_code(ok) == 0
    assert doctor.exit_code([*ok, doctor.Check("c", False, "", required=True)]) == 1


def test_confluence_names_are_shown_but_never_values():
    env = {"CONFLUENCE_API_TOKEN": "tok-0123456789abcdef", "CONFLUENCE_SPACE_KEY": "DOCS"}
    text = doctor.format_checks(doctor.run_checks(env))
    assert "tok-0123456789abcdef" not in text and "DOCS" not in text.replace("DOCSPIPELINE", "")
    assert "CONFLUENCE_SERVER_URL" in text  # 未設定のものは名前で示す


def test_bad_mode_is_reported_not_raised():
    checks = doctor.run_checks({"DOCSPIPELINE_CONFLUENCE_MODE": "publsh"})
    mode = next(c for c in checks if c.name == "Confluence のモード")
    assert not mode.ok and "publsh" in mode.detail


def test_mmdc_is_found_from_the_environment(tmp_path):
    checks = doctor.run_checks({"DOCSPIPELINE_MMDC": "my-mmdc --flag"})
    mmdc = next(c for c in checks if c.name.startswith("mmdc"))
    assert mmdc.ok and "my-mmdc" in mmdc.detail
