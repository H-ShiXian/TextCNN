# -*- coding: utf-8 -*-

# 第五步：Padding（统一序列长度）

import jieba


# =============================
# 1 读取数据并构建词表
# =============================

file_path = "data/train.txt"

all_words = []

texts = []
labels = []


with open(file_path, "r", encoding="utf-8") as f:

    for line in f:

        line = line.strip()

        label, text = line.split()

        labels.append(label)

        texts.append(text)

        words = jieba.lcut(text)

        all_words.extend(words)


# 创建词表
vocab = {}

vocab["<PAD>"] = 0
vocab["<UNK>"] = 1

index = 2


for word in all_words:

    if word not in vocab:

        vocab[word] = index
        index += 1


# =============================
# 2 文本转 index
# =============================

index_texts = []

for text in texts:

    words = jieba.lcut(text)

    ids = []

    for word in words:

        if word in vocab:

            ids.append(vocab[word])

        else:

            ids.append(vocab["<UNK>"])

    index_texts.append(ids)


# =============================
# 3 Padding
# =============================

# 设定最大句子长度
MAX_LEN = 6

padded_texts = []


for seq in index_texts:

    # 如果句子长度小于 MAX_LEN
    if len(seq) < MAX_LEN:

        # 需要补多少个 PAD
        pad_length = MAX_LEN - len(seq)

        # 添加 PAD (0)
        seq = seq + [vocab["<PAD>"]] * pad_length

    else:

        # 如果句子太长就截断
        seq = seq[:MAX_LEN]

    padded_texts.append(seq)


# =============================
# 4 打印结果
# =============================

for i in range(3):

    print("原始文本：", texts[i])

    print("分词结果：", jieba.lcut(texts[i]))

    print("index序列：", index_texts[i])

    print("padding后：", padded_texts[i])

    print()