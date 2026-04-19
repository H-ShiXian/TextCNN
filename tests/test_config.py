# -*- coding: utf-8 -*-
import unittest

from config import MAX_LEN, load_data, preprocess_text, texts_to_indices


class ConfigFunctionsTest(unittest.TestCase):
    def test_load_data_reads_pairs(self):
        texts, labels = load_data("data/test1.txt")
        self.assertTrue(len(texts) > 0)
        self.assertEqual(len(texts), len(labels))

    def test_preprocess_text_fixed_length(self):
        vocab = {"<PAD>": 0, "<UNK>": 1, "链表": 2}
        ids = preprocess_text("链表 反转", vocab, max_len=6)
        self.assertEqual(len(ids), 6)
        self.assertEqual(ids[0], 2)

    def test_texts_to_indices_batch_shape(self):
        vocab = {"<PAD>": 0, "<UNK>": 1, "链表": 2}
        indices = texts_to_indices(["链表", "不存在词"], vocab, max_len=5)
        self.assertEqual(len(indices), 2)
        self.assertEqual(len(indices[0]), 5)
        self.assertEqual(len(indices[1]), 5)

    def test_unknown_tokens_map_to_unk(self):
        vocab = {"<PAD>": 0, "<UNK>": 7}
        ids = preprocess_text("完全未知", vocab, max_len=4)
        self.assertTrue(all(token in (0, 7) for token in ids))


if __name__ == "__main__":
    unittest.main()
