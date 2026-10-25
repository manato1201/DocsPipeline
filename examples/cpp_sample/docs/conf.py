"""Sample Engine の Sphinx 設定。共通の設定は DocsPipeline から読み込む。"""

from docspipeline.config import build_config

globals().update(
    build_config(
        confdir=__file__,
        project="Sample Engine",
        author="manato1201",
        package_paths=[],
        use_hou_stub=False,
        cpp_sources=["../include"],
        # 出典・ライセンスの注記。HTML のフッターと Confluence の各ページ末尾に付く。
        license_note="",
    )
)
