import random

# ==============================
# 1 四大类标签
# ==============================

labels = {
    "data_structure": [
        "栈", "队列", "链表", "顺序表", "二叉树", "AVL树", "红黑树",
        "哈希表", "图", "最小生成树", "Dijkstra算法",
        "快速排序", "堆排序", "归并排序", "B树"
    ],

    "operating_system": [
        "进程", "线程", "进程调度", "死锁",
        "信号量", "PV操作", "虚拟内存",
        "分页存储", "页面置换算法", "LRU算法",
        "系统调用", "临界区"
    ],

    "computer_network": [
        "TCP", "UDP", "IP协议", "HTTP协议",
        "DNS", "ARP协议", "ICMP协议",
        "TCP三次握手", "TCP四次挥手",
        "滑动窗口", "拥塞控制"
    ],

    "computer_architecture": [
        "CPU", "控制器", "指令周期",
        "流水线技术", "Cache", "主存",
        "虚拟地址", "RISC", "CISC",
        "总线", "中断", "DMA"
    ]
}

# ==============================
# 2 问题模板
# ==============================

templates = [

    "什么是{}",
    "{}的概念是什么",
    "{}的基本原理是什么",
    "{}的主要作用是什么",
    "{}的定义是什么",

    "简述{}",
    "如何理解{}",
    "{}的工作原理是什么",
    "{}有什么特点",

    "{}在计算机系统中的作用是什么",
    "{}解决了什么问题",
    "{}的实现原理是什么"
]

# ==============================
# 3 前缀（用于数据增强）
# ==============================

prefix = [
    "",
    "请问",
    "简要说明",
    "简述",
    "在操作系统中",
    "在计算机系统中"
]


# ==============================
# 4 生成数据
# ==============================

max_items = 4000  # 设定最大条数

def generate_balanced_data(total_count):
    dataset = []
    # 计算每个类别需要生成的数量
    items_per_label = total_count // len(labels)
    
    for label, topics in labels.items():
        count_for_this_label = 0
        while count_for_this_label < items_per_label:
            # 随机组合
            topic = random.choice(topics)
            temp = random.choice(templates)
            p = random.choice(prefix)
            
            question = p + temp.format(topic)
            dataset.append(f"{label}\t{question}")
            count_for_this_label += 1
            
    return dataset

# 生成总计 max_items 条数据
final_dataset = generate_balanced_data(max_items)
random.shuffle(final_dataset)

# 保存
with open("data/train.txt", "w", encoding="utf-8") as f:
    for line in final_dataset:
        f.write(line + "\n")

print(f"数据生成完成！共生成 {len(final_dataset)} 条。")










# max_items = 500  # 设定最大条数

# dataset = []

# for label, topics in labels.items():

#     for topic in topics:

#         for temp in templates:

#             for p in prefix:

#                 if len(dataset) >= max_items:
#                     break # 达到数量后退出循环

#                 question = p + temp.format(topic)

#                 dataset.append(f"{label}\t{question}")


# # ==============================
# # 5 打乱数据
# # ==============================

# random.shuffle(dataset)


# # ==============================
# # 6 保存文件
# # ==============================

# with open("data/dev.txt", "w", encoding="utf-8") as f:
#     for line in dataset:
#         f.write(line + "\n")

# print("数据生成完成！")
# print("生成数据量:", len(dataset))