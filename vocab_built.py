# -*- coding: utf-8 -*-
"""
词表和标签映射构建脚本

功能：读取训练数据 → jieba 分词 → 构建词表 → 构建标签映射 → 保存到 JSON

注意：
  - 只需在训练前运行一次
  - 词表只根据训练集构建（不能用验证集/测试集的数据，防止数据泄露）
  - 生成的 vocab.json 和 label.json 被 train.py 和 evaluate_test.py 共同使用
"""

import json
import jieba
from config import TRAIN_PATH, VOCAB_PATH, LABEL_PATH, load_data


# =============================
# 1. 读取训练数据
# =============================

train_texts, train_labels = load_data(TRAIN_PATH)


# =============================
# 2. 构建词表
# =============================

# 对所有训练文本进行分词，收集全部出现过的词
all_words = []
for text in train_texts:
    all_words.extend(jieba.lcut(text))

# 初始化词表，预留两个特殊 token：
#   <PAD> (索引 0): 用于将短句子填充到统一长度，不携带实际语义
#   <UNK> (索引 1): 代替词表中不存在的未知词（测试时可能遇到训练集没出现过的词）
vocab = {"<PAD>": 0, "<UNK>": 1}
index = 2

for word in all_words:
    if word not in vocab:
        vocab[word] = index
        index += 1

# 保存词表到 JSON 文件
with open(VOCAB_PATH, "w", encoding="utf-8") as f:
    json.dump(vocab, f, ensure_ascii=False, indent=4)

print(f"词表构建完成，共 {len(vocab)} 个词")


# =============================
# 3. 构建标签映射
# =============================

# 将标签按字母排序后编号，确保每次运行结果一致
# 例如：{"computer_architecture": 0, "computer_network": 1, ...}
label_set = sorted(list(set(train_labels)))
label2idx = {label: i for i, label in enumerate(label_set)}

with open(LABEL_PATH, "w", encoding="utf-8") as f:
    json.dump(label2idx, f, ensure_ascii=False, indent=4)

print(f"标签映射：{label2idx}")
