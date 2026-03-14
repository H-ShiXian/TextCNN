import random

# 五个科目文件
files = {
    "操作系统": "Subject_data/operating_system.txt",
    "计算机网络": "Subject_data/computer_network.txt",
    "数据结构": "Subject_data/data_structure.txt",
    "组成原理": "Subject_data/computer_architecture.txt",
    "肖四政治": "Subject_data/xiaosi.txt"
}

train_ratio = 0.8
val_ratio = 0.1
test_ratio = 0.1

train_data = []
val_data = []
test_data = []

for label, file in files.items():

    with open(file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    random.shuffle(lines)

    n = len(lines)

    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))

    train = lines[:train_end]
    val = lines[train_end:val_end]
    test = lines[val_end:]

    for text in train:
        train_data.append(f"{text}\t{label}")

    for text in val:
        val_data.append(f"{text}\t{label}")

    for text in test:
        test_data.append(f"{text}\t{label}")


with open("train.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(train_data))

with open("val.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(val_data))

with open("test.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(test_data))

print("数据集划分完成")