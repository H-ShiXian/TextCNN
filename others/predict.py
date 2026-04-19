# -*- coding: utf-8 -*-
"""
命令行预测脚本（复用统一推理模块）
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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