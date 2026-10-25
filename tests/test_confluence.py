import pytest

from docspipeline import confluence

FULL = {
    "CONFLUENCE_SERVER_URL": "https://example.atlassian.net/wiki/",
    "CONFLUENCE_SPACE_KEY": "DOCS",
    "CONFLUENCE_PARENT_PAGE": "Auto Docs",
    "CONFLUENCE_SERVER_USER": "me@example.com",
    "CONFLUENCE_API_TOKEN": "tok-0123456789abcdef",
}


def test_default_mode_is_local():
    assert confluence.current_mode({}) == "local"


@pytest.mark.parametrize("mode", ["local", "dryrun", "publish", " PUBLISH "])
def test_valid_modes(mode):
    assert confluence.current_mode({confluence.MODE_ENV: mode}) == mode.strip().lower()


def test_typo_in_mode_is_an_error_not_a_silent_local():
    with pytest.raises(confluence.ConfluenceSettingsError):
        confluence.current_mode({confluence.MODE_ENV: "publsh"})


def test_local_never_publishes_even_if_the_environment_says_so():
    # ビルダーは未設定の confluence_* を同名の環境変数で補う。明示的に False にしている。
    env = {**FULL, "CONFLUENCE_PUBLISH": "1"}
    settings = confluence.sphinx_settings(env)
    assert settings["confluence_publish"] is False
    assert "confluence_server_url" not in settings
    assert "confluence_api_token" not in settings


def test_local_keeps_the_safety_settings():
    settings = confluence.sphinx_settings({})
    assert settings["confluence_cleanup_purge"] is False
    assert settings["confluence_cleanup_archive"] is False
    assert settings["confluence_publish_trample"] is False
    assert settings["confluence_page_hierarchy"] is True


def test_dryrun_connects_but_does_not_apply():
    settings = confluence.sphinx_settings({**FULL, confluence.MODE_ENV: "dryrun"})
    assert settings["confluence_publish"] is True
    assert settings["confluence_publish_dryrun"] is True
    assert settings["confluence_parent_page"] == "Auto Docs"
    assert settings["confluence_api_token_scoped"] is False


def test_publish_applies():
    settings = confluence.sphinx_settings(
        {**FULL, confluence.MODE_ENV: "publish", "CONFLUENCE_API_TOKEN_SCOPED": "true", "CONFLUENCE_PAGE_PREFIX": "[auto] "}
    )
    assert settings["confluence_publish"] is True
    assert settings["confluence_publish_dryrun"] is False
    assert settings["confluence_api_token_scoped"] is True
    assert settings["confluence_publish_prefix"] == "[auto] "


@pytest.mark.parametrize("missing", sorted(FULL))
def test_publish_requires_every_setting_and_reports_names_only(missing):
    env = {k: v for k, v in FULL.items() if k != missing}
    env[confluence.MODE_ENV] = "publish"
    with pytest.raises(confluence.ConfluenceSettingsError) as exc:
        confluence.sphinx_settings(env)
    assert missing in str(exc.value)
    assert FULL["CONFLUENCE_API_TOKEN"] not in str(exc.value)


def test_parent_page_is_mandatory_so_publishing_is_always_scoped():
    assert "CONFLUENCE_PARENT_PAGE" in confluence.REQUIRED_ENV


def test_footer_file_is_passed_through():
    assert confluence.sphinx_settings({}, footer_file="/x/footer.xhtml")["confluence_footer_file"] == "/x/footer.xhtml"


def test_mask_secrets():
    text = "auth failed for token tok-0123456789abcdef (user me@example.com)"
    masked = confluence.mask_secrets(text, FULL)
    assert "tok-0123456789abcdef" not in masked
    assert "***" in masked
    assert "me@example.com" in masked


def test_mask_secrets_ignores_trivially_short_values():
    assert confluence.mask_secrets("a b c", {"CONFLUENCE_API_TOKEN": "a"}) == "a b c"
