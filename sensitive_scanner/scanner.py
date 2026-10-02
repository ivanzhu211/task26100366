"""流式敏感词扫描器：按任意字节边界分块喂入 UTF-8 正文，产出命中。"""

import codecs
import json
from collections import deque
from typing import NamedTuple

from .automaton import Automaton
from .normalize import normalize_char


class Hit(NamedTuple):
    rule_id: str
    start: int  # 原文 UTF-8 字节起点（包含）
    end: int    # 原文 UTF-8 字节终点（不包含）


class Scanner:
    """一次扫描使用固定词库；正文与扫描状态仅驻留内存。

    用法：
        scanner = Scanner.from_json_file("lexicon.json")
        for hit in scanner.feed(chunk):
            ...  # 逐条消费
        for hit in scanner.finish():
            ...
    """

    def __init__(self, lexicon: dict[str, list[str]]) -> None:
        normalized = {
            rule_id: ["".join(normalize_char(c) for c in pat) for pat in patterns]
            for rule_id, patterns in lexicon.items()
        }
        for rule_id, patterns in normalized.items():
            for pat in patterns:
                if not pat:
                    raise ValueError(f"规则 {rule_id!r} 含有归一化后为空的词形")
        self._automaton = Automaton(normalized)
        self._decoder = codecs.getincrementaldecoder("utf-8")()
        self._offset = 0  # 下一个待解码字符的起始字节偏移
        # 最近若干归一化字符对应的原文字节区间，长度上限为最长词形
        self._recent: deque[tuple[int, int]] = deque(
            maxlen=max(self._automaton.max_pattern_len, 1)
        )
        self._delivered: set[tuple[str, int, int]] = set()
        self._finished = False

    @classmethod
    def from_json_file(cls, path: str) -> "Scanner":
        """从本地 JSON 词库构造。格式：{"规则ID": ["词形", ...], ...}"""
        with open(path, "r", encoding="utf-8") as fh:
            lexicon = json.load(fh)
        if not isinstance(lexicon, dict):
            raise ValueError("词库 JSON 须为 {规则ID: [词形, ...]} 的对象")
        return cls(lexicon)

    def feed(self, data: bytes) -> list[Hit]:
        """喂入一个字节块，返回本块处理后可确定的全部命中。"""
        if self._finished:
            raise RuntimeError("扫描已结束，不能再喂入数据")
        return self._consume(self._decoder.decode(data, final=False))

    def finish(self) -> list[Hit]:
        """声明输入结束，冲刷剩余状态，返回最后一批命中。"""
        if self._finished:
            raise RuntimeError("扫描已结束")
        self._finished = True
        return self._consume(self._decoder.decode(b"", final=True))

    def _consume(self, text: str) -> list[Hit]:
        hits: list[Hit] = []
        for ch in text:
            byte_start = self._offset
            byte_end = byte_start + len(ch.encode("utf-8"))
            self._offset = byte_end
            for norm_ch in normalize_char(ch):
                self._recent.append((byte_start, byte_end))
                for rule_id, length in self._automaton.feed(norm_ch):
                    start = self._recent[-length][0]
                    end = byte_end
                    key = (rule_id, start, end)
                    if key not in self._delivered:
                        self._delivered.add(key)
                        hits.append(Hit(rule_id, start, end))
        return hits
