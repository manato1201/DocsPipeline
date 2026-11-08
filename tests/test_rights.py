"""README の「権利」の表 (コード・文章・図・名前を層で分けて書く) が、リポジトリの実態と食い違わないこと。"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
LAYERS = ("コード", "文章", "図", "名前", "第三者のもの")


def _rights_rows() -> dict[str, list[str]]:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "\n## 権利\n" in text, "README に「権利」の節がありません"
    section = text.split("\n## 権利\n", 1)[1].split("\n## ", 1)[0]
    rows = {}
    for line in section.splitlines():
        if line.startswith("| ") and not line.startswith(("| 層", "|---")):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows[cells[0]] = cells[1:]
    return rows


def test_every_layer_has_its_own_row_with_a_target_and_a_status():
    rows = _rights_rows()
    assert tuple(rows) == LAYERS
    for layer, cells in rows.items():
        assert len(cells) == 2 and all(cells), layer  # 対象と、権利・ライセンス


def test_the_license_claim_matches_whether_a_license_file_exists():
    """LICENSE が無いのに「MIT」などと書かない / LICENSE を足したのに「未決定」のまま残さない。"""
    has_license = any((ROOT / name).is_file() for name in LICENSE_NAMES)
    rows = _rights_rows()
    for layer in ("コード", "文章", "図"):
        undecided = "未決定" in rows[layer][1]
        assert undecided == (not has_license), (
            f"{layer}: LICENSE が{'ある' if has_license else '無い'}のに、表は"
            f"{'未決定' if undecided else '決定済み'}になっている"
        )


def test_every_path_named_in_the_table_exists():
    for layer, (target, _status) in _rights_rows().items():
        for path in re.findall(r"`([^`]+/[^`]*)`", target):
            assert any(ROOT.glob(path.rstrip("/") + "*")), f"{layer}: {path} が無い"


def test_third_party_notice_named_in_the_table_exists():
    _target, status = _rights_rows()["第三者のもの"]
    for path in re.findall(r"`([^`]+LICENSE[^`]*)`", status):
        assert (ROOT / path).is_file(), path
