# -*- coding: utf-8 -*-
import json
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import jieba
from model.textcnn_model import TextCNN  # 导入我们上一步写好的 TextCNN




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
val_texts, val_labels = load_data("data/val.txt")
test_texts, test_labels = load_data("data/test.txt")



# # 构建词表
# all_words = []
# for text in train_texts:
#     all_words.extend(jieba.lcut(text))

# vocab = {"<PAD>":0, "<UNK>":1}
# index = 2
# for word in all_words:
#     if word not in vocab:
#         vocab[word] = index
#         index += 1

# # 保存词表

# with open("vocab.json", "w", encoding="utf-8") as f:
#     json.dump(vocab, f, ensure_ascii=False, indent=4)

# # 标签映射
# label_set = sorted(list(set(train_labels)))
# label2idx = {label:i for i, label in enumerate(label_set)}
# with open("label.json", "w", encoding="utf-8") as f:
#     json.dump(label2idx, f, ensure_ascii=False, indent=4)



# 读取 vocab
with open("data/vocab.json", "r", encoding="utf-8") as f:
    vocab = json.load(f)

# 读取 label
with open("data/label.json", "r", encoding="utf-8") as f:
    label2idx = json.load(f)
label_set = sorted(list(set(train_labels)))


MAX_LEN = 30  # 你可以根据数据调整长度

def texts_to_indices(texts, vocab, max_len=MAX_LEN):
    index_texts = []
    for text in texts:
        words = jieba.lcut(text)
        ids = [vocab.get(w, vocab["<UNK>"]) for w in words]
        if len(ids) < max_len:
            ids += [vocab["<PAD>"]] * (max_len - len(ids))
        else:
            ids = ids[:max_len]
        index_texts.append(ids)
    return index_texts

train_indices = texts_to_indices(train_texts, vocab)
val_indices = texts_to_indices(val_texts, vocab)
test_indices = texts_to_indices(test_texts, vocab)

train_label_indices = [label2idx[label] for label in train_labels]
val_label_indices = [label2idx[label] for label in val_labels]
test_label_indices = [label2idx[label] for label in test_labels]




# =============================
# 2 创建 Dataset
# =============================

class TextDataset(Dataset):
    def __init__(self, texts, labels):
        self.texts = texts
        self.labels = labels

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        return torch.tensor(self.texts[idx], dtype=torch.long), torch.tensor(self.labels[idx], dtype=torch.long)

train_dataset = TextDataset(train_indices, train_label_indices)
val_dataset = TextDataset(val_indices, val_label_indices)
test_dataset = TextDataset(test_indices, test_label_indices)

train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False)



def evaluate(model, data_loader, device):
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
# 3 创建模型
# =============================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = TextCNN(len(vocab), 128, len(label_set)).to(device)
criterion = torch.nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

num_epochs = 50
for epoch in range(num_epochs):
    model.train()
    total_loss = 0
    for batch_texts, batch_labels in train_loader:
        batch_texts = batch_texts.to(device)
        batch_labels = batch_labels.to(device)

        optimizer.zero_grad()
        outputs = model(batch_texts)
        loss = criterion(outputs, batch_labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    val_acc = evaluate(model, val_loader, device)
    print(f"Epoch [{epoch+1}/{num_epochs}], Loss: {total_loss/len(train_loader):.4f}, Val Acc: {val_acc:.4f}")



# vocab_size = len(vocab)
# embed_dim = 128
# num_classes = len(label_set)

# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# mozel = TextCNN(vocab_size, embed_dim, num_classes).to(device)

# # =============================
# # 4 定义损失函数和优化器
# # =============================

# criterion = nn.CrossEntropyLoss()   # 交叉熵损失
# optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

# =============================
# 5 训练模型
# =============================

# num_epochs = 15

# for epoch in range(num_epochs):
#     model.train()
#     total_loss = 0
#     for batch_texts, batch_labels in dataloader:
#         batch_texts = batch_texts.to(device)
#         batch_labels = batch_labels.to(device)

#         optimizer.zero_grad()           # 清空梯度
#         outputs = model(batch_texts)    # 前向传播
#         loss = criterion(outputs, batch_labels)  # 计算损失
#         loss.backward()                 # 反向传播
#         optimizer.step()                # 更新参数

#         total_loss += loss.item()

#     print(f"Epoch [{epoch+1}/{num_epochs}], Loss: {total_loss/len(dataloader):.4f}")

# =============================
# 6 保存模型
# =============================

torch.save(model.state_dict(), "data/textcnn_model.pth")
print("模型训练完成并保存！")