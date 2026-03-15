# -*- coding: utf-8 -*-
"""
模型测试脚本

功能：加载训练好的模型 → 在测试集上逐条预测 → 计算准确率

使用方法：
  训练完成后运行本脚本，检验模型在未见过的测试数据上的表现
"""

import torch
import json
import jieba
from model.textcnn_model import TextCNN
from config import (
    TEST_PATH, VOCAB_PATH, LABEL_PATH, MODEL_PATH,
    MAX_LEN, EMBED_DIM, DROPOUT,
)


# =============================
# 1. 加载词表和标签映射
# =============================

with open(VOCAB_PATH, "r", encoding="utf-8") as f:
    vocab = json.load(f)

with open(LABEL_PATH, "r", encoding="utf-8") as f:
    label2idx = json.load(f)

# 反转标签映射：index → 标签名，用于将模型的数字预测转回可读标签
idx2label = {v: k for k, v in label2idx.items()}


# =============================
# 2. 加载模型
# =============================

# 创建与训练时相同结构的模型，然后加载保存的权重
model = TextCNN(len(vocab), EMBED_DIM, len(label2idx), dropout=DROPOUT)
model.load_state_dict(torch.load(MODEL_PATH, weights_only=True))
model.eval()  # 切换到评估模式（关闭 Dropout）


# =============================
# 3. 文本预处理函数
# =============================

def preprocess(text):
    """
    将单条文本转为模型输入格式

    流程：分词 → 查词表转索引 → padding/截断到 MAX_LEN
    注意：MAX_LEN 必须与训练时一致，否则输入维度不匹配
    """
    words = jieba.lcut(text)
    ids = [vocab.get(w, vocab["<UNK>"]) for w in words]

    if len(ids) < MAX_LEN:
        ids += [vocab["<PAD>"]] * (MAX_LEN - len(ids))
    else:
        ids = ids[:MAX_LEN]

    return ids


# =============================
# 4. 读取测试数据并预测
# =============================

texts = []
labels = []

with open(TEST_PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        label, text = line.split(maxsplit=1)
        texts.append(text)
        labels.append(label)

correct = 0
total = len(texts)

for text, label in zip(texts, labels):
    ids = preprocess(text)
    x = torch.tensor([ids], dtype=torch.long)

    with torch.no_grad():
        output = model(x)
        pred = torch.argmax(output, dim=1).item()

    pred_label = idx2label[pred]
    if pred_label == label:
        correct += 1


# =============================
# 5. 输出结果
# =============================

accuracy = correct / total
print(f"测试样本数: {total}")
print(f"预测正确数: {correct}")
print(f"测试准确率: {accuracy:.4f}")
