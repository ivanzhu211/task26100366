# -*- coding: utf-8 -*-
"""敏感词扫描库自动化测试。"""

import json

import pytest

from sensitive_scan import Hit, Scanner


def run_scan(lexicon, text, chunk_sizes):
    """按给定块大小序列送入文本，汇总全部命中。"""
    scanner = Scanner(lexicon)
    data = text.encode("utf-8")
    hits = []
    pos = 0
    for size in chunk_sizes:
        hits.extend(scanner.feed(data[pos:pos + size]))
        pos += size
    if pos < len(data):
        hits.extend(scanner.feed(data[pos:]))
    hits.extend(scanner.finish())
    return hits


def all_chunkings(data_len):
    """常用分块方式：整块、逐字节、2/3/5 字节块。"""
    return [[data_len], [1] * data_len, [2] * data_len, [3] * data_len, [5] * data_len]


class TestFullwidthSharpS:
    """正文“Ａß-Ｂ”：Ａ(3B) ß(2B) -(1B) Ｂ(3B)，归一化为 assb。"""

    LEXICON = {"甲": ["s", "ss"], "乙": ["assb"], "丙": ["ss"]}
    TEXT = "Ａß-Ｂ"

    @pytest.mark.parametrize("chunks", all_chunkings(len("Ａß-Ｂ".encode("utf-8"))))
    def test_hits_consistent_across_chunkings(self, chunks):
        hits = run_scan(self.LEXICON, self.TEXT, chunks)
        # 甲的 s 与 ss 均落在 ß 上，去重后只交付一次 (3, 5)。
        assert hits.count(Hit("甲", 3, 5)) == 1
        # 乙的 assb 覆盖整段，中间被忽略的连字符包含在区间内。
        assert Hit("乙", 0, 9) in hits
        # 丙与甲区间相同，但规则不同，须各自交付。
        assert Hit("丙", 3, 5) in hits
        assert sorted(hits) == sorted([
            Hit("甲", 3, 5), Hit("乙", 0, 9), Hit("丙", 3, 5),
        ])


class TestHyphenatedWord:
    """词形 ab，正文为 a + 连续连字符 + b，命中覆盖整段且唯一。"""

    LEXICON = {"R": ["ab"]}
    TEXT = "a" + "-" * 7 + "b"

    @pytest.mark.parametrize("chunks", all_chunkings(len(TEXT.encode("utf-8"))))
    def test_single_hit_covering_whole_span(self, chunks):
        hits = run_scan(self.LEXICON, self.TEXT, chunks)
        assert hits == [Hit("R", 0, len(self.TEXT))]


class TestGeneral:
    def test_overlap_and_inner_word_match(self):
        # 不以空白/标点为边界：词内命中、重叠命中都要交付。
        hits = run_scan({"r1": ["bc"], "r2": ["abc"], "r3": ["cd"]}, "abcd", [4])
        assert sorted(hits) == sorted([
            Hit("r1", 1, 3), Hit("r2", 0, 3), Hit("r3", 2, 4),
        ])

    def test_casefold_and_fullwidth_in_text(self):
        hits = run_scan({"r": ["hello"]}, "ＨＥＬＬＯ", [15])
        assert hits == [Hit("r", 0, 15)]

    def test_invisible_and_space_chars_inside_span(self):
        text = "a​ b"  # a + ZWSP + 空格 + b
        hits = run_scan({"r": ["ab"]}, text, [len(text.encode("utf-8"))])
        assert hits == [Hit("r", 0, len(text.encode("utf-8")))]

    def test_partial_expansion_covers_whole_codepoint(self):
        # ß 展开为 ss，词形只用一个 s 也要覆盖 ß 的完整 2 字节。
        hits = run_scan({"r": ["s"]}, "ß", [2])
        assert hits == [Hit("r", 0, 2)]

    def test_chunk_boundary_splits_multibyte_char(self):
        data = "Ａß-Ｂ".encode("utf-8")
        hits = run_scan({"甲": ["s", "ss"], "乙": ["assb"]}, "Ａß-Ｂ",
                        [1, 2, 1, 1, 3, 1])
        assert sorted(hits) == sorted([Hit("甲", 3, 5), Hit("乙", 0, 9)])
        assert len(data) == 9

    def test_finish_with_truncated_char_raises(self):
        scanner = Scanner({"r": ["a"]})
        scanner.feed("ß".encode("utf-8")[:1])
        with pytest.raises(UnicodeDecodeError):
            scanner.finish()

    def test_empty_normalized_word_ignored(self):
        scanner = Scanner({"r": ["---", "ab"]})
        hits = scanner.feed("ab".encode("utf-8")) + scanner.finish()
        assert hits == [Hit("r", 0, 2)]

    def test_from_json(self, tmp_path):
        path = tmp_path / "lexicon.json"
        path.write_text(json.dumps({"甲": ["s", "ss"], "乙": ["assb"]}),
                        encoding="utf-8")
        scanner = Scanner.from_json(str(path))
        hits = scanner.feed("Ａß-Ｂ".encode("utf-8")) + scanner.finish()
        assert sorted(hits) == sorted([Hit("甲", 3, 5), Hit("乙", 0, 9)])
