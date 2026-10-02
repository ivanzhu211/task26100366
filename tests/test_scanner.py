import json
import os
import random
import tempfile
import unittest

from sensitive_scanner import Hit, Scanner, normalize_char, normalize_text


def scan_with_chunks(lexicon, data: bytes, chunk_sizes):
    """按给定块大小序列喂入，返回按交付顺序排列的命中列表。"""
    scanner = Scanner(lexicon)
    hits = []
    pos = 0
    sizes = iter(chunk_sizes)
    while pos < len(data):
        size = next(sizes, 1)
        hits.extend(scanner.feed(data[pos:pos + size]))
        pos += size
    hits.extend(scanner.finish())
    return hits


def all_chunkings(data: bytes):
    """整段一次、逐字节、以及若干混合分块方式。"""
    n = len(data)
    yield "whole", [n]
    yield "bytewise", [1] * n
    yield "pairs", [2] * n
    yield "threes", [3] * n
    yield "mixed", [1, 4, 2, 7, 3, 5]


class NormalizeTest(unittest.TestCase):
    def test_fullwidth_and_casefold(self):
        self.assertEqual(normalize_char("Ａ"), "a")
        self.assertEqual(normalize_char("ß"), "ss")
        self.assertEqual(normalize_char("Ｂ"), "b")

    def test_ignored_categories(self):
        self.assertEqual(normalize_char("-"), "")        # Pd
        self.assertEqual(normalize_char("​"), "")   # Cf
        self.assertEqual(normalize_char("　"), "")  # White_Space
        self.assertEqual(normalize_char("́"), "")   # Mn
        self.assertEqual(normalize_char("。"), "")        # Po

    def test_combining_mark_after_nfkd(self):
        self.assertEqual(normalize_char("é"), "e")
        self.assertEqual(normalize_text("Ａß-Ｂ"), "assb")


class SpecScenarioTest(unittest.TestCase):
    LEXICON = {"甲": ["s", "ss"], "乙": ["assb"], "丙": ["ss"]}
    TEXT = "Ａß-Ｂ"

    def test_hits_and_ranges(self):
        hits = scan_with_chunks(self.LEXICON, self.TEXT.encode("utf-8"), [999])
        # 甲：s/ss 在 ß 上去重为一条；乙：assb 覆盖全文；丙：自己的 ss 命中
        self.assertCountEqual(
            hits, [Hit("甲", 3, 5), Hit("乙", 0, 9), Hit("丙", 3, 5)]
        )

    def test_chunking_invariance(self):
        data = self.TEXT.encode("utf-8")
        results = {}
        for name, sizes in all_chunkings(data):
            results[name] = scan_with_chunks(self.LEXICON, data, sizes)
        reference = results["whole"]
        for name, hits in results.items():
            self.assertEqual(hits, reference, f"分块方式 {name} 结果不一致")

    def test_hyphenated_word(self):
        text = "a" + "-" * 20 + "b"
        data = text.encode("utf-8")
        reference = None
        for name, sizes in all_chunkings(data):
            hits = scan_with_chunks({"R": ["ab"]}, data, sizes)
            self.assertEqual(hits, [Hit("R", 0, len(data))], f"分块方式 {name}")
            if reference is None:
                reference = hits
            self.assertEqual(hits, reference)


class StreamingTest(unittest.TestCase):
    def test_split_multibyte_char(self):
        # 逐字节喂入时多字节字符被截断，命中不得丢失或错位
        data = "ＸＡßＢＹ".encode("utf-8")
        hits = scan_with_chunks({"R": ["assb"]}, data, [1] * len(data))
        self.assertEqual(hits, [Hit("R", 3, 11)])

    def test_hits_delivered_per_chunk(self):
        scanner = Scanner({"R": ["ab"]})
        self.assertEqual(scanner.feed("xa-".encode()), [])
        hits = scanner.feed("bz".encode())
        self.assertEqual(hits, [Hit("R", 1, 4)])
        self.assertEqual(scanner.finish(), [])

    def test_overlapping_and_prefix_suffix(self):
        hits = scan_with_chunks({"R": ["aa", "aaa"]}, b"aaaa", [4])
        self.assertEqual(
            sorted(hits),
            [Hit("R", 0, 2), Hit("R", 0, 3), Hit("R", 1, 3), Hit("R", 1, 4), Hit("R", 2, 4)],
        )

    def test_same_range_different_rules(self):
        hits = scan_with_chunks({"A": ["x"], "B": ["x"]}, b"x", [1])
        self.assertEqual(sorted(hits), [Hit("A", 0, 1), Hit("B", 0, 1)])

    def test_partial_expansion_covers_whole_codepoint(self):
        # ß 展开为 ss，词形 s 命中其中一半也要覆盖 ß 的完整字节
        data = "ß".encode("utf-8")  # 字节 0..2
        hits = scan_with_chunks({"R": ["s"]}, data, [1, 1])
        self.assertEqual(hits, [Hit("R", 0, 2)])

    def test_ignored_chars_inside_range_only(self):
        # 前后被忽略的字符不进入区间，中间的进入
        hits = scan_with_chunks({"R": ["ab"]}, "-a-b-".encode(), [99])
        self.assertEqual(hits, [Hit("R", 1, 4)])

    def test_feed_after_finish_raises(self):
        scanner = Scanner({"R": ["a"]})
        scanner.finish()
        with self.assertRaises(RuntimeError):
            scanner.feed(b"a")

    def test_empty_pattern_rejected(self):
        with self.assertRaises(ValueError):
            Scanner({"R": ["---"]})

    def test_from_json_file(self):
        lexicon = {"甲": ["s", "ss"], "乙": ["assb"]}
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as fh:
            json.dump(lexicon, fh, ensure_ascii=False)
            path = fh.name
        try:
            scanner = Scanner.from_json_file(path)
            hits = scanner.feed("Ａß-Ｂ".encode("utf-8")) + scanner.finish()
            self.assertEqual(
                sorted(hits), [Hit("乙", 0, 9), Hit("甲", 3, 5)]
            )
        finally:
            os.unlink(path)


class RandomChunkingFuzzTest(unittest.TestCase):
    """随机正文 + 随机分块，结果须与整段一次喂入完全一致。"""

    ALPHABET = ["a", "b", "s", "Ａ", "ß", "é", "-", "—", "　", "​", "Ｂ", "1"]
    LEXICON = {"R1": ["s", "ss", "assb"], "R2": ["ab", "b1"], "R3": ["ss"]}

    def test_random_chunkings(self):
        rng = random.Random(20261003)
        for trial in range(50):
            text = "".join(rng.choice(self.ALPHABET) for _ in range(rng.randint(0, 40)))
            data = text.encode("utf-8")
            reference = scan_with_chunks(self.LEXICON, data, [len(data) or 1])
            for _ in range(5):
                sizes = []
                remaining = len(data)
                while remaining > 0:
                    size = rng.randint(1, remaining)
                    sizes.append(size)
                    remaining -= size
                hits = scan_with_chunks(self.LEXICON, data, sizes or [1])
                self.assertEqual(
                    hits, reference, f"trial={trial} text={text!r} sizes={sizes}"
                )

if __name__ == "__main__":
    unittest.main()
