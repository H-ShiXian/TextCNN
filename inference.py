# -*- coding: utf-8 -*-
"""
统一推理模块

提供模型加载与单条文本预测能力，供脚本和 API 复用。
"""

import json

import jieba
import torch

from config import EMBED_DIM, DROPOUT, LABEL_PATH, MAX_LEN, MODEL_PATH, VOCAB_PATH
from model.textcnn_model import TextCNN


class TextClassifier:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        with open(VOCAB_PATH, "r", encoding="utf-8") as f:
            self.vocab = json.load(f)

        with open(LABEL_PATH, "r", encoding="utf-8") as f:
            self.label2idx = json.load(f)

        self.idx2label = {v: k for k, v in self.label2idx.items()}

        self.model = TextCNN(
            vocab_size=len(self.vocab),
            embed_dim=EMBED_DIM,
            num_classes=len(self.label2idx),
            dropout=DROPOUT,
        ).to(self.device)

        state_dict = torch.load(MODEL_PATH, map_location=self.device)
        self.model.load_state_dict(state_dict)
        self.model.eval()

    def preprocess(self, text):
        words = jieba.lcut(text)
        ids = [self.vocab.get(w, self.vocab["<UNK>"]) for w in words]

        if len(ids) < MAX_LEN:
            ids += [self.vocab["<PAD>"]] * (MAX_LEN - len(ids))
        else:
            ids = ids[:MAX_LEN]

        return ids

    def predict(self, text):
        ids = self.preprocess(text)
        x = torch.tensor([ids], dtype=torch.long, device=self.device)

        with torch.no_grad():
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1)
            confidence, pred = torch.max(probs, dim=1)

        label = self.idx2label[pred.item()]
        return {
            "label": label,
            "confidence": float(confidence.item()),
        }