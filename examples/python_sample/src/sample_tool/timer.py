"""時間の計測。"""

from __future__ import annotations

import time


class Stopwatch:
    """経過時間を測るストップウォッチ。

    Examples:
        >>> sw = Stopwatch()
        >>> sw.start()
        >>> elapsed = sw.stop()

    Attributes:
        laps: ``lap`` で記録した経過秒数。
    """

    def __init__(self) -> None:
        """空のストップウォッチを作る。"""
        self.laps: list[float] = []
        self._started: float | None = None

    def start(self) -> None:
        """計測を始める。

        Raises:
            RuntimeError: すでに計測中のとき。
        """
        if self._started is not None:
            raise RuntimeError("すでに計測中です")
        self._started = time.perf_counter()

    def stop(self) -> float:
        """計測を止めて、経過秒数を返す。

        Returns:
            :meth:`start` からの経過秒数。

        Raises:
            RuntimeError: 計測を始めていないとき。
        """
        if self._started is None:
            raise RuntimeError("計測が始まっていません")
        elapsed = time.perf_counter() - self._started
        self._started = None
        self.laps.append(elapsed)
        return elapsed


def measure(func) -> tuple[object, float]:
    """関数を 1 回呼んで、結果と所要秒数を返す。

    Args:
        func: 引数なしで呼べる関数。

    Returns:
        ``(func の戻り値, 所要秒数)``。
    """
    sw = Stopwatch()
    sw.start()
    result = func()
    return result, sw.stop()
