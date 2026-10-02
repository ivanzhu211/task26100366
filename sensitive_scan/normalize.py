"""按码点归一化：NFKD -> casefold -> 删除 M*/P*/Cf/White_Space 字符。"""

from __future__ import annotations

import unicodedata

# Unicode White_Space 属性对应的码点集合。
_WHITE_SPACE: frozenset[int] = frozenset(
    [0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0x85, 0xA0, 0x1680]
    + list(range(0x2000, 0x200B))
    + [0x2028, 0x2029, 0x202F, 0x205F, 0x3000]
)


def _kept(char: str) -> bool:
    category = unicodedata.category(char)
    if category.startswith("M") or category.startswith("P") or category == "Cf":
        return False
    return ord(char) not in _WHITE_SPACE


def normalize_char(char: str) -> str:
    """对单个原始码点做 NFKD + casefold，返回删除忽略字符后的结果（可为空）。"""
    expanded = unicodedata.normalize("NFKD", char).casefold()
    return "".join(ch for ch in expanded if _kept(ch))


def normalize_word(word: str) -> str:
    """对词形逐码点归一化并连接结果。"""
    return "".join(normalize_char(ch) for ch in word)
