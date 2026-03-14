# -*- coding: utf-8 -*-
import json
import jieba




def load_data(file_path):
    texts = []
    labels = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            label, text = line.split(maxsplit=1)  # 防止文本中有空格
            labels.append(label)
            texts.append(text)
    return texts, labels

train_texts, train_labels = load_data("data/train.txt")





# =============================
# 1 准备数据
# =============================

# file_path = "data/train.txt"


# texts = []
# labels = []

# # 读取数据
# with open(file_path, "r", encoding="utf-8") as f:
#     for line in f:
#         line = line.strip()
#         label, text = line.split(maxsplit=1)
#         labels.append(label)
#         texts.append(text)
#         words = jieba.lcut(text)
#         all_words.extend(words)


# 构建词表
all_words = []
for text in train_texts:
    all_words.extend(jieba.lcut(text))

vocab = {"<PAD>":0, "<UNK>":1}
index = 2
for word in all_words:
    if word not in vocab:
        vocab[word] = index
        index += 1

# 保存词表

with open("data/vocab.json", "w", encoding="utf-8") as f:
    json.dump(vocab, f, ensure_ascii=False, indent=4)

# 标签映射
label_set = sorted(list(set(train_labels)))
label2idx = {label:i for i, label in enumerate(label_set)}
with open("data/label.json", "w", encoding="utf-8") as f:
    json.dump(label2idx, f, ensure_ascii=False, indent=4)

