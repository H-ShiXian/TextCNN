# -*- coding: utf-8 -*-
"""
TextCNN 模型实现

参考论文：Convolutional Neural Networks for Sentence Classification (Kim, 2014)

核心思想：
  1. Embedding：   将每个词映射为一个稠密向量
  2. 多尺度卷积：   用不同大小的滑动窗口（2/3/4）提取 n-gram 特征
  3. Max Pooling：  从每个卷积结果中取最大值，提取最显著的特征
  4. 全连接分类：   将拼接后的特征向量映射到各分类

数据流示意：
  文本 → Embedding → Conv2d(多尺度) → ReLU → MaxPool → 拼接 → Dropout → FC → 分类结果
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class TextCNN(nn.Module):

    def __init__(self, vocab_size, embed_dim, num_classes, dropout=0.5):
        """
        参数:
            vocab_size:  词表大小
            embed_dim:   词向量维度（每个词用多少维的向量表示）
            num_classes: 分类类别数
            dropout:     Dropout 概率（训练时随机屏蔽神经元的比例）
        """
        super(TextCNN, self).__init__()

        # ---- Embedding 层 ----
        # 作用：将词的整数索引转换为稠密向量
        # 例如：词索引 42 → [0.1, -0.3, 0.7, ...] (embed_dim 维的向量)
        self.embedding = nn.Embedding(vocab_size, embed_dim)

        # ---- 多尺度卷积层 ----
        # 使用 3 种不同大小的卷积核（窗口大小 2, 3, 4）
        # 窗口=2 捕获相邻两个词的关系（bigram），窗口=3 捕获三个词（trigram），以此类推
        # 每种窗口各 100 个卷积核，相当于学习 100 种不同的特征模式
        self.convs = nn.ModuleList([
            nn.Conv2d(in_channels=1, out_channels=100, kernel_size=(k, embed_dim))
            for k in [2, 3, 4]
        ])

        self.bns = nn.ModuleList([
            nn.BatchNorm1d(100)
            for _ in [2, 3, 4]
        ])

        # ---- Dropout 层 ----
        # 训练时随机将一部分神经元输出置零，防止模型过度依赖某些特征（过拟合）
        # 测试时自动关闭，不影响预测
        self.dropout = nn.Dropout(dropout)

        # ---- 全连接层 ----
        # 输入维度 = 100(每种卷积核的输出) × 3(三种窗口大小) = 300
        # 输出维度 = 类别数
        self.fc = nn.Linear(300, num_classes)

    def forward(self, x):
        """
        前向传播

        参数:
            x: (batch_size, seq_len) — 一批文本的索引序列
        返回:
            (batch_size, num_classes) — 每个样本属于各类别的得分
        """
        # 1. Embedding: 索引 → 向量
        x = self.embedding(x)          # → (batch_size, seq_len, embed_dim)

        # 2. 增加通道维度，适配 Conv2d 的输入格式 (N, C, H, W)
        x = x.unsqueeze(1)             # → (batch_size, 1, seq_len, embed_dim)

        # 3. 每种卷积核分别处理：卷积 → 激活 → 池化
        conv_results = []
        # for conv ,bn in zip(self.convs,self.bns):
        #     c = F.relu(conv(x))         # 卷积 + ReLU → (batch_size, 100, new_len, 1)
        #     c = c.squeeze(3)            # 去掉最后一维 → (batch_size, 100, new_len)
        #     c = bn(c) 
        #     p = F.max_pool1d(c, c.size(2))  # 最大池化 → (batch_size, 100, 1)
        #     p = p.squeeze(2)            # 去掉最后一维 → (batch_size, 100)
        #     conv_results.append(p)

        for conv, bn in zip(self.convs, self.bns):

            c = conv(x)          # Conv

            c = c.squeeze(3)     # (batch, 100, new_len)

            c = bn(c)            # BN  ← 这里

            c = F.relu(c)        # ReLU

            p = F.max_pool1d(c, c.size(2))

            p = p.squeeze(2)

            conv_results.append(p)

        # 4. 拼接三种卷积核的结果
        x = torch.cat(conv_results, dim=1)  # → (batch_size, 300)

        # 5. Dropout 正则化
        x = self.dropout(x)

        # 6. 全连接层，输出分类得分
        out = self.fc(x)                # → (batch_size, num_classes)

        return out
