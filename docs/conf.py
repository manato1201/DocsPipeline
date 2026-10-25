"""DocsPipeline 自身の文書の Sphinx 設定 (最初の対象として、自分の道具で自分を文書化する)。"""

from docspipeline.config import build_config

globals().update(
    build_config(
        confdir=__file__,
        project="DocsPipeline",
        author="manato1201",
        package_paths=["../"],
        license_note="参照した外部の資料は、構造と考え方だけを取り入れ、コード・画像・文章は写していません。",
    )
)

# Sphinx / docutils の型は、この文書では解説しない (リンク先を持たない) ので警告から外す
nitpick_ignore_regex += [(r"py:.*", r"(sphinx|docutils)(\..*)?")]
