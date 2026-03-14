# -*- coding: utf-8 -*-
import json
import torch
import jieba
from model.textcnn_model import TextCNN   # 导入模型


# =============================
# 1 加载词表和标签
# =============================

# 注意：这里为了简单，我们手动写一个词表
# 实际项目中应该保存词表文件再加载

# vocab = {
#     "<PAD>":0,
#     "<UNK>":1,
#     "链表":2,
#     "反转":3,
#     "二叉树":4,
#     "遍历":5,
#     "栈":6,
#     "队列":7,
#     "区别":8
# }

# # 标签映射
# label2idx = {
#     "data_structure":0,
#     "os":1,
#     "network":2,
#     "database":3
# }


# =============================
# 2 创建模型并加载参数
# =============================

# 加载 vocab
with open("vocab.json", "r", encoding="utf-8") as f:
    vocab = json.load(f)

# 加载 label
with open("label.json", "r", encoding="utf-8") as f:
    label2idx = json.load(f)


# 反向映射（数字 → 标签）
idx2label = {v:k for k,v in label2idx.items()}


vocab_size = len(vocab)
embed_dim = 50
num_classes = len(label2idx)

model = TextCNN(vocab_size, embed_dim, num_classes)

# 加载训练好的模型
model.load_state_dict(torch.load("textcnn_model.pth"))

model.eval()  # 进入预测模式


# =============================
# 3 文本预处理函数
# =============================

MAX_LEN = 6

def preprocess(text):

    # 分词
    words = jieba.lcut(text)

    ids = []

    for word in words:

        if word in vocab:
            ids.append(vocab[word])
        else:
            ids.append(vocab["<UNK>"])

    # padding
    if len(ids) < MAX_LEN:
        ids += [vocab["<PAD>"]] * (MAX_LEN - len(ids))
    else:
        ids = ids[:MAX_LEN]

    return ids


# =============================
# 4 预测函数
# =============================

def predict(text):

    # 文本预处理
    ids = preprocess(text)

    # 转 tensor
    x = torch.tensor([ids], dtype=torch.long)

    # 模型预测
    with torch.no_grad():

        outputs = model(x)

        # 取概率最大的类别
        pred = torch.argmax(outputs, dim=1).item()

    return idx2label[pred]


# =============================
# 5 测试预测
# =============================

text = "链表反转"

result = predict(text)

print("输入题目：", text)
print("预测分类：", result)