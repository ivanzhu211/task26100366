"""Aho-Corasick 自动机，用于在归一化后的流式文本上做多模式匹配。

构造时接收的词形必须已经完成归一化（见 normalize 模块）。
"""

from collections import deque
from typing import Iterator


class Automaton:
    """增量多模式匹配器。逐字符喂入，命中时产出 (rule_id, 匹配长度)。"""

    def __init__(self, lexicon: dict[str, list[str]]) -> None:
        # transitions[state]: 字符 -> 下一状态
        self._trans: list[dict[str, int]] = [{}]
        # fail[state]: 失配回退状态
        self._fail: list[int] = [0]
        # output[state]: 在该状态结束的所有 (rule_id, 词形长度)
        self._out: list[list[tuple[str, int]]] = [[]]
        self._state = 0
        self._max_len = 0

        for rule_id, patterns in lexicon.items():
            for pat in patterns:
                if not pat:
                    raise ValueError("归一化后的词形不能为空")
                self._insert(rule_id, pat)

        self._build_fail()

    def _insert(self, rule_id: str, pat: str) -> None:
        state = 0
        for ch in pat:
            nxt = self._trans[state].get(ch)
            if nxt is None:
                nxt = len(self._trans)
                self._trans.append({})
                self._fail.append(0)
                self._out.append([])
                self._trans[state][ch] = nxt
            state = nxt
        self._out[state].append((rule_id, len(pat)))
        self._max_len = max(self._max_len, len(pat))

    def _build_fail(self) -> None:
        queue: deque[int] = deque()
        for ch, nxt in self._trans[0].items():
            self._fail[nxt] = 0
            queue.append(nxt)
        while queue:
            state = queue.popleft()
            # 合并失配节点的输出，使命中在结束时一次性全部产出
            self._out[state].extend(self._out[self._fail[state]])
            for ch, nxt in self._trans[state].items():
                queue.append(nxt)
                fallback = self._fail[state]
                while fallback and ch not in self._trans[fallback]:
                    fallback = self._fail[fallback]
                self._fail[nxt] = self._trans[fallback].get(ch, 0)

    @property
    def max_pattern_len(self) -> int:
        return self._max_len

    def feed(self, ch: str) -> Iterator[tuple[str, int]]:
        state = self._state
        while state and ch not in self._trans[state]:
            state = self._fail[state]
        state = self._trans[state].get(ch, 0)
        self._state = state
        return iter(self._out[state])
