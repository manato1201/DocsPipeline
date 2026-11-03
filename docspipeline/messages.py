"""利用者に見せるメッセージの書き方。

エラーは、**何が起きた / なぜ / 次にどうする** の 3 行にそろえる。ローカルの道具の失敗は、原因が利用者の環境
(入れていない道具・打ち間違い・設定の不足) にあることが多く、「次の一手」まで書いてあると、迷わずに直せる。

このモジュールは、文字列を作るだけの純粋な関数だけを持つ (表示は呼び出し側)。Sphinx にも依存しない。
"""

from __future__ import annotations


def format_error(what: str, why: str, next_step: str, *, label: str = "エラー") -> str:
    """エラーを、何が起きた / なぜ / 次にどうする、の 3 行にして返す。

    Args:
        what: 何が起きたか。パスなど、どれのことかを含める。
        why: なぜ起きたか (考えられる原因)。
        next_step: 利用者が次にすること。コマンドや、確かめる場所を書く。
        label: 1 行目の見出し (``エラー`` / ``失敗`` / ``中止`` / ``中断``)。

    Returns:
        改行を含む文字列 (末尾に改行は付けない)。

    Raises:
        ValueError: ``what``・``why``・``next_step`` のいずれかが空のとき。
            書き手が、原因と次の一手を考えずに済ませないため。
    """
    for name, value in (("what", what), ("why", why), ("next_step", next_step)):
        if not value.strip():
            raise ValueError(f"{name} は空にできません (何が起きた / なぜ / 次にどうする、の 3 つを書く)")
    return f"{label}: {what}\n  原因: {why}\n  次の一手: {next_step}"


def format_elapsed(seconds: float) -> str:
    """経過時間を、人が読む形にする (``12.3 秒`` / ``1 分 5 秒``)。

    Args:
        seconds: 経過した秒数。負の値は 0 として扱う。
    """
    seconds = max(seconds, 0.0)
    if round(seconds, 1) < 60:  # 59.96 が「60.0 秒」にならないように、丸めてから比べる
        return f"{seconds:.1f} 秒"
    minutes, rest = divmod(round(seconds), 60)
    return f"{minutes} 分 {rest} 秒"
