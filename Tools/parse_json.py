import re
import json
import os

def parse_all_question_banks(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        text_content = f.read()

    dataset = []
    current_chapter = "未分类"
    current_section = "未分类"
    current_q = None

    # 1. 预清洗：去掉特殊占位符、页码和公众号水印
    text_content = text_content.replace('', '')
    text_content = re.sub(r'公众号：做题本集结地.*', '', text_content)
    text_content = re.sub(r'·\s*第\s*\d+\s*页，共\s*\d+\s*页\s*·', '', text_content)
    
    lines = text_content.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line: continue
            
        # --- 匹配章 (例如: 第 1 章 ...) ---
        chapter_match = re.match(r'^第\s*\d+\s*章\s*(.*)', line)
        if chapter_match:
            current_chapter = line
            continue
            
        # --- 匹配节 (例如: 1.1 ...) ---
        section_match = re.match(r'^\d+\.\d+\s+(.*)', line)
        if section_match:
            current_section = line
            continue

        # --- 匹配题干 ---
        # 兼容两种格式： "(1) 题目" 或 "1. 题目"
        # 同时过滤掉一些目录行的干扰
        q_match = re.match(r'^[\(（](\d+)[\)）]\s*(.*)', line) or re.match(r'^(\d+)\.\s*(.*)', line)
        
        # 排除掉类似 "1.1" 的节标题被误判为题号
        is_section = re.match(r'^\d+\.\d+', line)

        if q_match and not is_section:
            if current_q:
                dataset.append(current_q)
            
            q_id = q_match.group(1)
            q_text = q_match.group(2).strip()
            
            current_q = {
                "source_file": os.path.basename(file_path),
                "chapter": current_chapter,
                "section": current_section,
                "id": q_id,
                "question": q_text,
                "options": {}
            }
            continue

        # --- 匹配选项 ---
        if current_q:
            # 兼容 A. B. C. D. 后面跟空格或制表符的情况
            # 能够识别一行内的多个选项
            opt_matches = re.findall(r'([A-D])[.．]\s*(.*?)(?=[A-D][.．]|$|\t)', line)
            if opt_matches:
                for opt_label, opt_content in opt_matches:
                    current_q["options"][opt_label] = opt_content.strip()
            else:
                # 如果没有选项标识符，且没有开始记录选项，则认为是题干的换行内容
                if not current_q["options"]:
                    current_q["question"] += " " + line

    # 放入最后一题
    if current_q:
        dataset.append(current_q)
        
    return dataset

# --- 批量处理多个文件 ---
files_to_process = [
    
    "【A4速刷】26肖四选择题做题本.txt"
]

all_data = []
for file in files_to_process:
    if os.path.exists(file):
        print(f"正在处理: {file}...")
        file_data = parse_all_question_banks(file)
        all_data.extend(file_data)
        print(f"  成功提取 {len(file_data)} 道题目")

# 导出汇总后的 JSON
with open('Subject_json/xiaosi1.json', 'w', encoding='utf-8') as f:
    json.dump(all_data, f, ensure_ascii=False, indent=4)

print(f"\n全部转换完成！总计 {len(all_data)} 道题目已保存至 combined_test_bank.json")