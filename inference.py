# -*- coding: utf-8 -*-
"""
统一推理模块

提供模型加载与单条文本预测能力，供脚本和 API 复用。
"""

import torch

from config import EMBED_DIM, DROPOUT, MAX_LEN, MODEL_PATH, load_labels, load_vocab, preprocess_text
from model.textcnn_model import TextCNN


class TextClassifier:
    def __init__(self, vocab=None, label2idx=None, model_path=MODEL_PATH, device=None):
        self.device = device or torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.vocab = vocab or load_vocab()
        self.label2idx = label2idx or load_labels()

        self.idx2label = {v: k for k, v in self.label2idx.items()}

        self.model = TextCNN(
            vocab_size=len(self.vocab),
            embed_dim=EMBED_DIM,
            num_classes=len(self.label2idx),
            dropout=DROPOUT,
        ).to(self.device)

        state_dict = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()

    @classmethod
    def from_files(cls):
        """保持与旧调用方式兼容的工厂方法。"""
        return cls(vocab=load_vocab(), label2idx=load_labels(), model_path=MODEL_PATH)

    def preprocess(self, text):
        return preprocess_text(text, self.vocab, max_len=MAX_LEN)

    def predict_proba(self, text):
        ids = self.preprocess(text)
        x = torch.tensor([ids], dtype=torch.long, device=self.device)

        with torch.no_grad():
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1).squeeze(0)

        return {
            self.idx2label[idx]: float(probs[idx].item())
            for idx in range(probs.shape[0])
        }

    def predict(self, text):
        score_map = self.predict_proba(text)
        label, confidence = max(score_map.items(), key=lambda x: x[1])
        return {
            "label": label,
            "confidence": float(confidence),
        }