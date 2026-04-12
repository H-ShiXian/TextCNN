# -*- coding: utf-8 -*-
"""
命令行预测脚本（复用统一推理模块）
"""

from inference import TextClassifier

classifier = TextClassifier()


def predict(text):
    return classifier.predict(text)


if __name__ == "__main__":
    text = "链表反转"
    result = predict(text)

    print("输入题目：", text)
    print("预测分类：", result["label"])
    print("置信度：", f"{result['confidence']:.4f}")