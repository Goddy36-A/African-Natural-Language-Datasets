"""Synthetic fixtures only: these strings are not published translations."""
import unittest
from scripts.build_uganda_corpus import align, clean, invalid, lines, range_indices


class CorpusTests(unittest.TestCase):
    def test_unicode_and_whitespace(self):
        self.assertEqual(clean("\ufeff A\u0301\t  ŋ’omu\u200b\u00ad "), "Á ŋ’omu")
        self.assertEqual(clean("Verse 12: punctuation—stays!"), "Verse 12: punctuation—stays!")

    def test_trailing_missing_verse_is_preserved(self):
        self.assertEqual(lines(b"first\r\n\r\nlast\r\n\r\n"), ["first", "", "last", ""])
        self.assertEqual(lines(b"first\nlast"), ["first", "last"])

    def test_missing_verse_never_shifts_alignment(self):
        rows, rejected, stats = align(
            ["GEN 1:1", "GEN 1:2", "GEN 1:3"],
            ["English A", "", "English C"], ["Target A", "Target B", "Target C"])
        self.assertEqual([r["verse_id"] for r in rows], ["GEN 1:1", "GEN 1:3"])
        self.assertEqual(rows[-1]["translation"]["lug"], "Target C")
        self.assertEqual(rejected, [{"verse_id": "GEN 1:2", "reason": "empty"}])
        self.assertEqual(stats["retained_pairs"] + stats["rejected_rows"], 3)

    def test_entire_merged_range_is_excluded_on_either_side(self):
        refs = [f"MAT 1:{i}" for i in range(1, 5)]
        for english, target in [
            (["Merged", "<range>", "<range>", "Last"], ["a", "b", "c", "d"]),
            (["a", "b", "c", "d"], ["Merged", "<range>", "<range>", "Last"])
        ]:
            rows, rejected, _ = align(refs, english, target)
            self.assertEqual([r["verse_id"] for r in rows], ["MAT 1:4"])
            self.assertEqual(len(rejected), 3)
        self.assertEqual(range_indices(["<range>", "text"]), {0})

    def test_bad_counts_and_references_fail_closed(self):
        for refs, eng, lug in [
            (["GEN 1:1"], ["a", "b"], ["c"]),
            (["GEN 1:1", "GEN 1:1"], ["a", "b"], ["c", "d"]),
            (["garbage"], ["a"], ["b"]),
            ([], [], [])
        ]:
            with self.assertRaises(ValueError):
                align(refs, eng, lug)

    def test_deduplication_is_pairwise_not_monolingual(self):
        rows, rejected, _ = align(
            ["GEN 1:1", "GEN 1:2", "GEN 1:3"],
            ["Same", "Same", "Same"], ["Target", "Target", "Different"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rejected[0]["reason"], "duplicate_pair")

    def test_residual_markup_and_corruption(self):
        for text in ["<b>word</b>", "\\v word", "bad\ufffd", "bad\x00", "123"]:
            self.assertIsNotNone(invalid(text))
        self.assertIsNone(invalid("ŋ’Á punctuation!"))

    def test_quality_flags_do_not_silently_remove_text(self):
        rows, _, _ = align(["GEN 1:1"], ["Same"], ["Same"])
        self.assertEqual(rows[0]["quality_flags"], ["identical_text"])


if __name__ == "__main__":
    unittest.main()
