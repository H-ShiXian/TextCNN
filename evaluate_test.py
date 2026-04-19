# -*- coding: utf-8 -*-
"""
模型测试脚本

功能：加载训练好的模型 → 在测试集上逐条预测 → 计算准确率

使用方法：
  训练完成后运行本脚本，检验模型在未见过的测试数据上的表现
"""

import torch
from model.textcnn_model import TextCNN
from config import (
    TEST_PATH, MODEL_PATH, EMBED_DIM, DROPOUT,
    load_data, load_labels, load_vocab, preprocess_text,
)


# =============================
# 1. 加载词表和标签映射
# =============================

vocab = load_vocab()
label2idx = load_labels()

# 反转标签映射：index → 标签名，用于将模型的数字预测转回可读标签
idx2label = {v: k for k, v in label2idx.items()}


# =============================
# 2. 加载模型
# =============================

# 创建与训练时相同结构的模型，然后加载保存的权重
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = TextCNN(len(vocab), EMBED_DIM, len(label2idx), dropout=DROPOUT).to(device)
model.load_state_dict(torch.load(MODEL_PATH, map_location=device, weights_only=True))
model.eval()  # 切换到评估模式（关闭 Dropout）


# =============================
# 3. 文本预处理函数
# =============================

def preprocess(text):
    """将单条文本转为模型输入格式。"""
    return preprocess_text(text, vocab)


# =============================
# 4. 读取测试数据并预测
# =============================

texts, labels = load_data(TEST_PATH)

correct = 0
total = len(texts)

for text, label in zip(texts, labels):
    ids = preprocess(text)
    x = torch.tensor([ids], dtype=torch.long, device=device)

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
