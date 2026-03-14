# -*- coding: utf-8 -*-

# 第一步：读取数据集

# 定义数据文件路径
file_path = "data/train.txt"

# 创建两个列表
texts = []   # 存放题目文本
labels = []  # 存放标签

# 打开文件
with open(file_path, "r", encoding="utf-8") as f:

    # 逐行读取
    for line in f:

        # 去掉换行符
        line = line.strip()

        # 按 Tab 分割
        label, text = line.split()

        # 保存标签
        labels.append(label)

        # 保存文本
        texts.append(text)

# 打印读取结果
print("文本列表：")
print(texts)

print("\n标签列表：")
print(labels)