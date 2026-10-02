"""基于 Aho-Corasick 自动机的流式多词匹配。"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple


class Automaton:
    """对归一化后的词形集合构建自动机，支持逐字符流式输入。"""

    def __init__(self, words: Iterable[Tuple[str, str]]) -> None:
        """words: (规则ID, 已归一化词形) 序列，词形保证非空。"""
        self._goto: List[Dict[str, int]] = [{}]
        self._fail: List[int] = [0]
        self._out: List[List[Tuple[int, Set[str]]]] = [[]]
        self._state = 0
        # 相同归一化词形合并，词形 -> 规则ID 集合。
        patterns: Dict[str, Set[str]] = {}
        for rule_id, word in words:
            patterns.setdefault(word, set()).add(rule_id)
        for word in patterns:
            state = 0
            for char in word:
                nxt = self._goto[state].get(char)
                if nxt is None:
                    nxt = len(self._goto)
                    self._goto[state][char] = nxt
                    self._goto.append({})
                    self._fail.append(0)
                    self._out.append([])
                state = nxt
            self._out[state].append((len(word), patterns[word]))
        # 构建失败指针（BFS），并把失败节点的输出合并进来。
        queue: List[int] = []
        for char, nxt in self._goto[0].items():
            queue.append(nxt)
        while queue:
            state = queue.pop(0)
            for char, nxt in self._goto[state].items():
                queue.append(nxt)
                fail = self._fail[state]
                while fail and char not in self._goto[fail]:
                    fail = self._fail[fail]
                self._fail[nxt] = self._goto[fail].get(char, 0)
                self._out[nxt].extend(self._out[self._fail[nxt]])

    def feed(self, char: str) -> List[Tuple[str, int]]:
        """送入一个归一化字符，返回在此位置结束的 (规则ID, 词长) 列表。"""
        state = self._state
        while state and char not in self._goto[state]:
            state = self._fail[state]
        state = self._goto[state].get(char, 0)
        self._state = state
        return [
            (rule_id, length)
            for length, rule_ids in self._out[state]
            for rule_id in rule_ids
        ]
