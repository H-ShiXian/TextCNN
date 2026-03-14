import json
import os

def convert_json_to_txt_final(json_file_path):
    """
    将 JSON 转换为特定格式：纯文件名 + TAB + 题干和选项拼接
    """
    if not os.path.exists(json_file_path):
        print(f"找不到文件: {json_file_path}")
        return

    # 1. 路径处理
    file_dir = os.path.dirname(json_file_path) # 获取目录路径
    file_full_name = os.path.basename(json_file_path) # 获取带后缀的文件名
    pure_name = os.path.splitext(file_full_name)[0] # 获取不带后缀的纯名称 (如 computer_architecture)
    
    output_path = os.path.join(file_dir, f"{pure_name}.txt")

    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        output_lines = []
        
        for item in data:
            # 2. 拼接题干 (去除换行符，确保一行一道题)
            question = item.get("question", "").replace("\n", " ").strip()
            
            # 3. 拼接选项 A. xxx B. xxx
            options_dict = item.get("options", {})
            options_list = []
            for label in ["A", "B", "C", "D"]:
                if label in options_dict:
                    # 也可以去掉选项里的换行符
                    opt_content = str(options_dict[label]).replace("\n", " ").strip()
                    options_list.append(f"{label}. {opt_content}")
            
            options_str = " ".join(options_list)
            
            # 4. 组合最终行内容：纯文件名 + TAB + 题干 + 空格 + 选项串
            combined_content = f"{question} {options_str}".strip()
            # 注意这里：左侧只放纯文件名 pure_name
            final_line = f"{pure_name}\t{combined_content}"
            
            output_lines.append(final_line)

        # 5. 写入 TXT 文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(output_lines))
            
        print(f"转换成功！生成文件: {output_path}")
        # print(f"每行预览: {pure_name}\t{output_lines[0][:30]}...")

    except Exception as e:
        print(f"处理时发生错误: {e}")

# --- 运行示例 ---
# 假设你的文件在这个路径
target_file = r"Subject_data\xiaosi.json"

if __name__ == "__main__":
    convert_json_to_txt_final(target_file)