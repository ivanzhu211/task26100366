"""流式敏感词扫描器：分块接收 UTF-8 字节，逐条产出命中。"""

from __future__ import annotations

import json
from collections import deque
from typing import Dict, List, NamedTuple

from sensitive_scan.automaton import Automaton
from sensitive_scan.normalize import normalize_char, normalize_word


class Hit(NamedTuple):
    """一条命中：规则ID + 原文 UTF-8 字节区间 [start, end)。"""
    rule_id: str
    start: int
    end: int


class Scanner:
    """固定词库的增量扫描器。feed() 返回本块新确定的命中。"""

    def __init__(self, lexicon: Dict[str, List[str]]) -> None:
        patterns = []
        max_len = 1
        for rule_id, words in lexicon.items():
            for word in words:
                normalized = normalize_word(word)
                if not normalized:
                    continue
                patterns.append((rule_id, normalized))
                max_len = max(max_len, len(normalized))
        self._automaton = Automaton(patterns)
        self._buf = bytearray()
        self._base = 0
        # 最近 max_len 个归一化字符对应的原始码点字节区间。
        self._map = deque(maxlen=max_len)
        self._delivered = set()

    @classmethod
    def from_json(cls, path: str) -> "Scanner":
        """从本地 JSON 文件加载词库：{规则ID: [词形, ...], ...}。"""
        with open(path, "r", encoding="utf-8") as fh:
            lexicon = json.load(fh)
        return cls(lexicon)

    def feed(self, data: bytes) -> List[Hit]:
        """送入一块字节，返回基于当前已完整解码字符确定的全部新命中。"""
        self._buf.extend(data)
        hits: List[Hit] = []
        while self._buf:
            char, size = self._decode_one()
            if char is None:
                break
            byte_start = self._base
            byte_end = byte_start + size
            del self._buf[:size]
            self._base = byte_end
            for kept in normalize_char(char):
                self._map.append((byte_start, byte_end))
                for rule_id, length in self._automaton.feed(kept):
                    start = self._map[-length][0]
                    end = self._map[-1][1]
                    hit = Hit(rule_id, start, end)
                    if hit not in self._delivered:
                        self._delivered.add(hit)
                        hits.append(hit)
        return hits

    def finish(self) -> List[Hit]:
        """结束输入；若末尾存在不完整的 UTF-8 序列则抛出 UnicodeDecodeError。"""
        if self._buf:
            bytes(self._buf).decode("utf-8")
            raise UnicodeDecodeError(
                "utf-8", bytes(self._buf), 0, len(self._buf),
                "truncated character at end of input",
            )
        return []

    def _decode_one(self):
        """从缓冲头部解出一个完整字符，返回 (字符, 字节数)；不完整返回 (None, 0)。"""
        limit = min(4, len(self._buf))
        for size in range(1, limit + 1):
            try:
                char = bytes(self._buf[:size]).decode("utf-8")
            except UnicodeDecodeError:
                continue
            return char, size
        return None, 0
