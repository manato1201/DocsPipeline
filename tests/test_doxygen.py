from docspipeline import doxygen


def test_doxyfile_makes_xml_only_and_quotes_paths():
    text = doxygen.make_doxyfile("My Engine", ["/src/a b", "/src/c"], "/out", ["Q_OBJECT=", "FOO"])
    lines = dict(line.split(" = ", 1) for line in text.strip().splitlines())
    assert lines["PROJECT_NAME"] == '"My Engine"'
    assert lines["INPUT"] == '"/src/a b" "/src/c"'
    assert lines["GENERATE_XML"] == "YES"
    assert lines["GENERATE_HTML"] == "NO"
    assert lines["PREDEFINED"] == "Q_OBJECT= FOO"
    assert lines["WARN_IF_DOC_ERROR"] == "YES"
