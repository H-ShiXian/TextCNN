# -*- coding: utf-8 -*-
"""
TextCNN 训练脚本

流程：加载数据 → 文本转索引 → 构建 DataLoader → 训练模型 → 保存最优模型

使用方法：
  1. 先运行 vocab_built.py 构建词表和标签映射
  2. 再运行本脚本进行训练
"""

import torch
from torch.utils.data import Dataset, DataLoader
from model.textcnn_model import TextCNN
from config import (
    TRAIN_PATH, VAL_PATH, TEST_PATH, MODEL_PATH,
    EMBED_DIM, BATCH_SIZE, NUM_EPOCHS, LEARNING_RATE, DROPOUT,
    load_data, texts_to_indices, load_vocab, load_labels,
)


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


def load_vocab_and_labels():
    """加载词表和标签映射。"""
    return load_vocab(), load_labels()


def build_dataloaders(vocab, label2idx):
    """读取数据并构建训练/验证/测试 DataLoader。"""
    train_texts, train_labels = load_data(TRAIN_PATH)
    val_texts, val_labels = load_data(VAL_PATH)
    test_texts, test_labels = load_data(TEST_PATH)

    train_indices = texts_to_indices(train_texts, vocab)
    val_indices = texts_to_indices(val_texts, vocab)
    test_indices = texts_to_indices(test_texts, vocab)

    train_label_indices = [label2idx[label] for label in train_labels]
    val_label_indices = [label2idx[label] for label in val_labels]
    test_label_indices = [label2idx[label] for label in test_labels]

    train_dataset = TextDataset(train_indices, train_label_indices)
    val_dataset = TextDataset(val_indices, val_label_indices)
    test_dataset = TextDataset(test_indices, test_label_indices)

    # shuffle=True: 每轮训练开始前打乱数据顺序，有助于模型学习更稳定
    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=BATCH_SIZE, shuffle=False)

    return train_loader, val_loader, test_loader


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
    return correct / total if total > 0 else 0.0


def train_one_epoch(model, data_loader, criterion, optimizer, device):
    """执行单轮训练并返回平均 loss。"""
    model.train()
    total_loss = 0.0

    for batch_texts, batch_labels in data_loader:
        batch_texts = batch_texts.to(device)
        batch_labels = batch_labels.to(device)

        optimizer.zero_grad()
        outputs = model(batch_texts)
        loss = criterion(outputs, batch_labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    return total_loss / len(data_loader)


def train_model(model, train_loader, val_loader, device):
    """执行完整训练流程，并在验证集最优时保存模型。"""
    criterion = torch.nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    best_val_acc = 0.0

    for epoch in range(NUM_EPOCHS):
        avg_loss = train_one_epoch(model, train_loader, criterion, optimizer, device)
        val_acc = evaluate(model, val_loader, device)
        print(f"Epoch [{epoch + 1}/{NUM_EPOCHS}], Loss: {avg_loss:.4f}, Val Acc: {val_acc:.4f}")

        # 保存验证集上表现最好的模型（防止过拟合导致后期模型反而变差）
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), MODEL_PATH)
            print(f"  -> 最优模型已保存 (Val Acc: {val_acc:.4f})")

    return best_val_acc


def main():
    # 自动选择设备：有 GPU 用 GPU，没有就用 CPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"使用设备: {device}")

    vocab, label2idx = load_vocab_and_labels()
    train_loader, val_loader, test_loader = build_dataloaders(vocab, label2idx)

    model = TextCNN(
        vocab_size=len(vocab),
        embed_dim=EMBED_DIM,
        num_classes=len(label2idx),
        dropout=DROPOUT,
    ).to(device)

    best_val_acc = train_model(model, train_loader, val_loader, device)

    best_state = torch.load(MODEL_PATH, map_location=device)
    model.load_state_dict(best_state)
    test_acc = evaluate(model, test_loader, device)

    print(f"\n训练完成！最佳验证准确率: {best_val_acc:.4f}")
    print(f"测试集准确率: {test_acc:.4f}")


if __name__ == "__main__":
    main()
