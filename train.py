# -*- coding: utf-8 -*-
"""
TextCNN 训练脚本

流程：加载数据 → 文本转索引 → 构建 DataLoader → 训练模型 → 保存最优模型

使用方法：
  1. 先运行 vocab_built.py 构建词表和标签映射
  2. 再运行本脚本进行训练
"""

import json
import torch
from torch.utils.data import Dataset, DataLoader
from model.textcnn_model import TextCNN
from config import (
    TRAIN_PATH, VAL_PATH, TEST_PATH,
    VOCAB_PATH, LABEL_PATH, MODEL_PATH,
    EMBED_DIM, BATCH_SIZE, NUM_EPOCHS, LEARNING_RATE, DROPOUT,
    load_data, texts_to_indices,
)


# =============================
# 1. 加载数据
# =============================

train_texts, train_labels = load_data(TRAIN_PATH)
val_texts, val_labels = load_data(VAL_PATH)
test_texts, test_labels = load_data(TEST_PATH)

# 加载预构建的词表和标签映射（由 vocab_built.py 生成）
with open(VOCAB_PATH, "r", encoding="utf-8") as f:
    vocab = json.load(f)

with open(LABEL_PATH, "r", encoding="utf-8") as f:
    label2idx = json.load(f)

label_set = sorted(list(set(train_labels)))


# =============================
# 2. 文本转索引
# =============================

# 将原始文本转换为固定长度的整数序列，作为模型输入
train_indices = texts_to_indices(train_texts, vocab)
val_indices = texts_to_indices(val_texts, vocab)
test_indices = texts_to_indices(test_texts, vocab)

# 将标签字符串转换为整数索引
train_label_indices = [label2idx[label] for label in train_labels]
val_label_indices = [label2idx[label] for label in val_labels]
test_label_indices = [label2idx[label] for label in test_labels]


# =============================
# 3. 构建 Dataset 和 DataLoader
# =============================

class TextDataset(Dataset):
    """
    自定义 PyTorch 数据集

    PyTorch 训练需要通过 Dataset + DataLoader 来组织数据：
      - Dataset:    定义如何获取单条数据
      - DataLoader: 自动把数据打包成小批次（batch），支持打乱和多线程加载
    """
    def __init__(self, texts, labels):
        self.texts = texts
        self.labels = labels

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        return (
            torch.tensor(self.texts[idx], dtype=torch.long),
            torch.tensor(self.labels[idx], dtype=torch.long),
        )


train_dataset = TextDataset(train_indices, train_label_indices)
val_dataset = TextDataset(val_indices, val_label_indices)
test_dataset = TextDataset(test_indices, test_label_indices)

# shuffle=True: 每轮训练开始前打乱数据顺序，有助于模型学习更稳定
train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)


# =============================
# 4. 评估函数
# =============================

def evaluate(model, data_loader, device):
    """
    在指定数据集上计算模型准确率

    注意：
      - model.eval()  关闭 Dropout，确保评估结果稳定
      - torch.no_grad() 不计算梯度，节省显存
    """
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for batch_texts, batch_labels in data_loader:
            batch_texts = batch_texts.to(device)
            batch_labels = batch_labels.to(device)
            outputs = model(batch_texts)
            _, predicted = torch.max(outputs, 1)
            correct += (predicted == batch_labels).sum().item()
            total += batch_labels.size(0)
    return correct / total


# =============================
# 5. 训练模型
# =============================

# 自动选择设备：有 GPU 用 GPU，没有就用 CPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"使用设备: {device}")

# 初始化模型
model = TextCNN(len(vocab), EMBED_DIM, len(label_set), dropout=DROPOUT).to(device)

# 损失函数：多分类交叉熵，衡量预测概率分布与真实标签的差距
criterion = torch.nn.CrossEntropyLoss()

# 优化器：Adam，自适应学习率优化器，比 SGD 更容易收敛
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

# 记录最佳验证准确率，只保存表现最好的模型
best_val_acc = 0.0

for epoch in range(NUM_EPOCHS):
    # --- 训练阶段 ---
    model.train()   # 切换到训练模式（启用 Dropout）
    total_loss = 0

    for batch_texts, batch_labels in train_loader:
        batch_texts = batch_texts.to(device)
        batch_labels = batch_labels.to(device)

        optimizer.zero_grad()                    # 清空上一步的梯度
        outputs = model(batch_texts)             # 前向传播：输入 → 预测
        loss = criterion(outputs, batch_labels)  # 计算预测与真实标签的差距
        loss.backward()                          # 反向传播：计算每个参数的梯度
        optimizer.step()                         # 根据梯度更新模型参数

        total_loss += loss.item()

    # --- 验证阶段 ---
    val_acc = evaluate(model, val_loader, device)
    avg_loss = total_loss / len(train_loader)
    print(f"Epoch [{epoch + 1}/{NUM_EPOCHS}], Loss: {avg_loss:.4f}, Val Acc: {val_acc:.4f}")

    # 保存验证集上表现最好的模型（防止过拟合导致后期模型反而变差）
    if val_acc > best_val_acc:
        best_val_acc = val_acc
        torch.save(model.state_dict(), MODEL_PATH)
        print(f"  → 最优模型已保存 (Val Acc: {val_acc:.4f})")

print(f"\n训练完成！最佳验证准确率: {best_val_acc:.4f}")
