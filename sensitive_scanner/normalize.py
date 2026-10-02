"""字符归一化：NFKD -> casefold -> 删除 M*/P*/Cf/White_Space 字符。"""

import unicodedata

# Unicode White_Space 属性字符集（PropList.txt，稳定集合）
_WHITE_SPACE = frozenset(
    [0x0009, 0x000A, 0x000B, 0x000C, 0x000D, 0x0020, 0x0085, 0x00A0, 0x1680]
    + list(range(0x2000, 0x200B))
    + [0x2028, 0x2029, 0x202F, 0x205F, 0x3000]
)


def _keep(ch: str) -> bool:
    cat = unicodedata.category(ch)
    if cat.startswith("M") or cat.startswith("P") or cat == "Cf":
        return False
    if ord(ch) in _WHITE_SPACE:
        return False
    return True


def normalize_char(ch: str) -> str:
    """对单个 Unicode 码点做归一化，返回归一化后的字符串（可能为空）。"""
    expanded = unicodedata.normalize("NFKD", ch).casefold()
    return "".join(c for c in expanded if _keep(c))


def normalize_text(text: str) -> str:
    """对整段文本逐码点归一化并拼接。"""
    return "".join(normalize_char(ch) for ch in text)
