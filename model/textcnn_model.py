# -*- coding: utf-8 -*-

# 第六步：实现 TextCNN 模型

import torch
import torch.nn as nn
import torch.nn.functional as F


# 定义 TextCNN 类
class TextCNN(nn.Module):

    def __init__(self, vocab_size, embed_dim, num_classes):

        # 调用父类初始化
        super(TextCNN, self).__init__()

        # =========================
        # 1 Embedding 层
        # =========================

        # vocab_size：词表大小
        # embed_dim：词向量维度

        self.embedding = nn.Embedding(vocab_size, embed_dim)

        # =========================
        # 2 卷积层
        # =========================

        # 定义多个卷积核（不同窗口大小）

        self.convs = nn.ModuleList([

            # 卷积核大小 = 2
            nn.Conv2d(
                in_channels=1,
                out_channels=100,
                kernel_size=(2, embed_dim)
            ),

            # 卷积核大小 = 3
            nn.Conv2d(
                in_channels=1,
                out_channels=100,
                kernel_size=(3, embed_dim)
            ),

            # 卷积核大小 = 4
            nn.Conv2d(
                in_channels=1,
                out_channels=100,
                kernel_size=(4, embed_dim)
            )

        ])

        # =========================
        # 3 全连接层
        # =========================

        # 100个卷积核 * 3种窗口大小

        self.fc = nn.Linear(300, num_classes)


    # 前向传播
    def forward(self, x):

        # x shape:
        # (batch_size , seq_len)

        # =========================
        # 1 Embedding
        # =========================

        x = self.embedding(x)

        # shape
        # (batch_size , seq_len , embed_dim)

        # =========================
        # 2 增加通道维度
        # =========================

        x = x.unsqueeze(1)

        # shape
        # (batch_size , 1 , seq_len , embed_dim)

        # =========================
        # 3 卷积 + ReLU
        # =========================

        conv_results = []

        for conv in self.convs:

            c = F.relu(conv(x))

            # shape
            # (batch_size , 100 , new_seq_len , 1)

            c = c.squeeze(3)

            # shape
            # (batch_size , 100 , new_seq_len)

            # =========================
            # 4 Max Pooling
            # =========================

            p = F.max_pool1d(c, c.size(2))

            # shape
            # (batch_size , 100 , 1)

            p = p.squeeze(2)

            # shape
            # (batch_size , 100)

            conv_results.append(p)

        # =========================
        # 5 拼接特征
        # =========================

        x = torch.cat(conv_results, dim=1)

        # shape
        # (batch_size , 300)

        # =========================
        # 6 全连接层
        # =========================

        out = self.fc(x)

        # shape
        # (batch_size , num_classes)

        return out