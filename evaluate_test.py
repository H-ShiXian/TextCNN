# -*- coding: utf-8 -*-

import torch
import json
import jieba
from model.textcnn_model import TextCNN


# =============================
# 1 加载 vocab 和 label
# =============================

with open("vocab.json", "r", encoding="utf-8") as f:
    vocab = json.load(f)

with open("label.json", "r", encoding="utf-8") as f:
    label2idx = json.load(f)

idx2label = {v:k for k,v in label2idx.items()}


# =============================
# 2 加载模型
# =============================

vocab_size = len(vocab)
embed_dim = 128
num_classes = len(label2idx)

model = TextCNN(vocab_size, embed_dim, num_classes)

model.load_state_dict(torch.load("textcnn_model.pth"))

model.eval()


# =============================
# 3 文本预处理函数
# =============================

MAX_LEN = 10

def preprocess(text):

    words = jieba.lcut(text)

    ids = []

    for word in words:

        if word in vocab:
            ids.append(vocab[word])
        else:
            ids.append(vocab["<UNK>"])

    if len(ids) < MAX_LEN:
        ids += [vocab["<PAD>"]] * (MAX_LEN - len(ids))
    else:
        ids = ids[:MAX_LEN]

    return ids


# =============================
# 4 读取测试数据
# =============================

test_file = "data/test.txt"

texts = []
labels = []

with open(test_file, "r", encoding="utf-8") as f:

    for line in f:

        label, text = line.strip().split(maxsplit=1)

        texts.append(text)
        labels.append(label)


# =============================
# 5 模型预测
# =============================

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
    # else:
    #     print(pred_label)


# =============================
# 6 计算准确率
# =============================

accuracy = correct / total

print("测试样本数:", total)
print("预测正确:", correct)
print("Accuracy:", accuracy)