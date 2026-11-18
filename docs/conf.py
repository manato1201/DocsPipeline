"""DocsPipeline 自身の文書の Sphinx 設定 (最初の対象として、自分の道具で自分を文書化する)。"""

from docspipeline.config import build_config

config = build_config(
    confdir=__file__,
    project="DocsPipeline",
    author="manato1201",
    package_paths=["../"],
    license_note="参照した外部の資料は、構造と考え方だけを取り入れ、コード・画像・文章は写していません。",
)

# Sphinx / docutils の型は、この文書では解説しない (リンク先を持たない) ので警告から外す
config["nitpick_ignore_regex"] += [(r"py:.*", r"(sphinx|docutils)(\..*)?")]
# 自分の HTML 版にだけ、ちいさな動き (読み進みの帯・コピーの結果の表示) を足す。
# ファイルは docspipeline/static/ にあり、他のプロジェクトへは配らない (読み込むかは、その conf.py が決める)
config["html_css_files"] = ["dp_motion.css"]
config["html_js_files"] = ["dp_motion.js"]
globals().update(config)
