"""Confluence 公開まわりの設定と安全装置。

公開の設定は環境変数から読む。API トークンを設定ファイル・ログ・文書に残さないための
方針で、このモジュールはトークンの値を保持するだけでなく、出力から伏せる処理 (:func:`mask_secrets`)
も持つ。

公開には 3 つのモードがある。既定は ``local`` で、ネットワークには一切つながない。

``local``
    Confluence 形式の出力をローカルに作るだけ (公開しない)。
``dryrun``
    Confluence に接続して、何が作成・更新されるかを確認する。ページは変更しない。
``publish``
    親ページ配下へ実際に公開する。
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

MODE_ENV = "DOCSPIPELINE_CONFLUENCE_MODE"
MODES = ("local", "dryrun", "publish")

# Sphinx Confluence ビルダーが自前で読む環境変数名に揃えている。
SERVER_URL_ENV = "CONFLUENCE_SERVER_URL"
SPACE_KEY_ENV = "CONFLUENCE_SPACE_KEY"
PARENT_PAGE_ENV = "CONFLUENCE_PARENT_PAGE"
USER_ENV = "CONFLUENCE_SERVER_USER"
TOKEN_ENV = "CONFLUENCE_API_TOKEN"
TOKEN_SCOPED_ENV = "CONFLUENCE_API_TOKEN_SCOPED"
PAGE_PREFIX_ENV = "CONFLUENCE_PAGE_PREFIX"

#: ``dryrun`` / ``publish`` で必須の環境変数。値は出力に出さず、名前だけを報告する。
REQUIRED_ENV = (SERVER_URL_ENV, SPACE_KEY_ENV, PARENT_PAGE_ENV, USER_ENV, TOKEN_ENV)

#: 値を伏せる対象の環境変数。
SECRET_ENV = (TOKEN_ENV,)

_TRUE = {"1", "true", "yes", "on"}


class ConfluenceSettingsError(Exception):
    """Confluence の設定が足りない、または安全でないときの例外。"""


def current_mode(environ: Mapping[str, str] | None = None) -> str:
    """環境変数から公開モードを決める。

    Args:
        environ: 環境変数。省略すると ``os.environ``。

    Returns:
        ``local`` / ``dryrun`` / ``publish`` のいずれか。未設定なら ``local``。

    Raises:
        ConfluenceSettingsError: 未知のモードが指定されたとき。
            黙って ``local`` に倒すと、公開したつもりで公開されない事故になる。
    """
    env = os.environ if environ is None else environ
    mode = (env.get(MODE_ENV) or "local").strip().lower()
    if mode not in MODES:
        raise ConfluenceSettingsError(f"{MODE_ENV} は {', '.join(MODES)} のいずれかにしてください (指定値: {mode!r})")
    return mode


def missing_env(environ: Mapping[str, str] | None = None) -> list[str]:
    """公開に必要で、未設定の環境変数の名前を返す。"""
    env = os.environ if environ is None else environ
    return [name for name in REQUIRED_ENV if not env.get(name)]


def sphinx_settings(
    environ: Mapping[str, str] | None = None,
    *,
    footer_file: str | None = None,
) -> dict[str, Any]:
    """Sphinx Confluence ビルダーの設定を組み立てる。

    公開の可否に関わる項目は、環境変数に頼らず必ずここで明示する。ビルダーは未設定の
    ``confluence_*`` を同名の環境変数から補うので、明示しないと、環境に
    ``CONFLUENCE_PUBLISH`` が残っているだけで意図せず公開されうる。

    Args:
        environ: 環境変数。省略すると ``os.environ``。
        footer_file: 各ページの末尾に付ける XHTML ファイルのパス (出典・ライセンスの注記)。

    Returns:
        ``conf.py`` の名前空間へ取り込む設定の辞書。

    Raises:
        ConfluenceSettingsError: ``dryrun`` / ``publish`` で必須の設定が足りないとき。
    """
    env = os.environ if environ is None else environ
    mode = current_mode(env)

    settings: dict[str, Any] = {
        "confluence_publish": False,
        # 親ページの下に Sphinx の目次どおりの階層で置く。
        "confluence_page_hierarchy": True,
        # 手で作られたページを消さない・奪わない。いずれもビルダーの既定だが、
        # 安全に関わるので明示する。trample が False だと、親ページ配下の外にある同じ題名の
        # 既存ページを更新しようとした時点で、ビルダーがエラーで止まる。
        "confluence_cleanup_purge": False,
        "confluence_cleanup_archive": False,
        "confluence_publish_trample": False,
        # 未解決のインラインコメントが付いたページは更新しない (警告は出る)。
        # 人が読んで反応しているページを守る。解決済みのコメントだけなら更新する。
        "confluence_publish_skip_commented_pages": "ignored-resolved",
        "confluence_disable_notifications": True,
    }
    if footer_file:
        settings["confluence_footer_file"] = footer_file

    if mode == "local":
        return settings

    missing = missing_env(env)
    if missing:
        raise ConfluenceSettingsError(f"{mode} モードには次の環境変数が必要です: {', '.join(missing)}")

    settings.update(
        {
            "confluence_publish": True,
            "confluence_publish_dryrun": mode == "dryrun",
            "confluence_server_url": env[SERVER_URL_ENV],
            "confluence_space_key": env[SPACE_KEY_ENV],
            # 専用の親ページ配下だけを対象にする。
            "confluence_parent_page": env[PARENT_PAGE_ENV],
            "confluence_server_user": env[USER_ENV],
            "confluence_api_token": env[TOKEN_ENV],
            "confluence_api_token_scoped": env.get(TOKEN_SCOPED_ENV, "").lower() in _TRUE,
        }
    )
    prefix = env.get(PAGE_PREFIX_ENV)
    if prefix:
        # 既存ページとの題名の衝突を避けたいときに使う。
        settings["confluence_publish_prefix"] = prefix
    return settings


def mask_secrets(text: str, environ: Mapping[str, str] | None = None) -> str:
    """文字列中のトークンの値を ``***`` に置き換える。

    Args:
        text: ログなどの出力。
        environ: 環境変数。省略すると ``os.environ``。

    Returns:
        トークンを伏せた文字列。
    """
    env = os.environ if environ is None else environ
    for name in SECRET_ENV:
        value = env.get(name)
        # 極端に短い値は通常の文字列まで潰してしまうので対象外にする。
        if value and len(value) >= 8:
            text = text.replace(value, "***")
    return text
