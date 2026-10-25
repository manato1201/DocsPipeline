"""設定の誤りを、Sphinx の設定エラーとして整った形で報告する拡張。

:func:`docspipeline.config.build_config` は ``conf.py`` の中で例外を投げず、エラーの文を
``docspipeline_config_error`` に入れて返す。この拡張が、設定の読み込みが終わった時点でそれを
``sphinx.errors.ConfigError`` にする。
"""

from __future__ import annotations

from typing import Any

from sphinx.application import Sphinx
from sphinx.errors import ConfigError

from . import __version__


def _raise_config_error(app: Sphinx, config: Any) -> None:
    if config.docspipeline_config_error:
        raise ConfigError(config.docspipeline_config_error)


def setup(app: Sphinx) -> dict[str, Any]:
    """Sphinx 拡張の登録。"""
    app.add_config_value("docspipeline_config_error", "", "env")
    app.connect("config-inited", _raise_config_error, priority=100)
    return {"version": __version__, "parallel_read_safe": True, "parallel_write_safe": True}
