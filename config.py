# -*- coding: utf-8 -*-
"""
项目配置文件

集中管理所有共享的常量和工具函数，确保各文件之间参数一致。
修改超参数时只需改这一个文件即可。
"""

import jieba
import json
import os


# =============================
# 文件路径配置
# =============================

TRAIN_PATH = "data/train.txt"      # 训练集路径
VAL_PATH   = "data/val.txt"        # 验证集路径
TEST_PATH  = "data/test.txt"       # 测试集路径
VOCAB_PATH = "data/vocab.json"     # 词表路径
LABEL_PATH = "data/label.json"     # 标签映射路径
MODEL_PATH = "data/textcnn_model.pth"  # 模型保存路径
DB_PATH    = "data/app.db"             # 业务数据库路径
MODEL_VERSION = "textcnn-v1"          # 当前推理模型版本
DEMO_PASSWORD = os.getenv("TEXTCNN_DEMO_PASSWORD", "demo123456")
ADMIN_PASSWORD = os.getenv("TEXTCNN_ADMIN_PASSWORD", "admin123456")


# =============================
# 模型超参数
# =============================

MAX_LEN       = 30      # 文本统一长度（短的补 PAD，长的截断）
EMBED_DIM     = 128     # 词向量维度
BATCH_SIZE    = 16      # 每批训练样本数
NUM_EPOCHS    = 50      # 训练轮数
LEARNING_RATE = 0.001   # 学习率
DROPOUT       = 0.5     # Dropout 概率（防止过拟合）


# =============================
# 工具函数
# =============================

def load_data(file_path):
    """
    读取数据文件

    文件格式：每行 "标签 文本内容"，用第一个空格分隔
    例如：operating_system 什么是进程调度

    返回:
        texts:  文本列表
        labels: 标签列表
    """
    texts = []
    labels = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            label, text = line.split(maxsplit=1)
            labels.append(label)
            texts.append(text)
    return texts, labels


def texts_to_indices(texts, vocab, max_len=MAX_LEN):
    """
    将文本列表转换为索引序列

    处理流程：
    1. jieba 分词：  "什么是进程" → ["什么", "是", "进程"]
    2. 查词表转索引：["什么", "是", "进程"] → [23, 5, 88]
    3. padding/截断：[23, 5, 88] → [23, 5, 88, 0, 0, ..., 0]  (补到 max_len)

    参数:
        texts:   文本列表
        vocab:   词表字典 {词: 索引}
        max_len: 统一序列长度

    返回:
        二维列表，每个元素是一个长度为 max_len 的索引序列
    """
    index_texts = []
    for text in texts:
        words = jieba.lcut(text)
        ids = [vocab.get(w, vocab["<UNK>"]) for w in words]

        # padding（补零）或截断
        if len(ids) < max_len:
            ids += [vocab["<PAD>"]] * (max_len - len(ids))
        else:
            ids = ids[:max_len]

        index_texts.append(ids)
    return index_texts


def load_vocab(path=VOCAB_PATH):
    """加载词表文件。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_labels(path=LABEL_PATH):
    """加载标签映射文件。"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def preprocess_text(text, vocab, max_len=MAX_LEN):
    """将单条文本转换为固定长度的索引序列。"""
    words = jieba.lcut(text)
    ids = [vocab.get(w, vocab["<UNK>"]) for w in words]

    if len(ids) < max_len:
        ids += [vocab["<PAD>"]] * (max_len - len(ids))
    else:
        ids = ids[:max_len]

    return ids
