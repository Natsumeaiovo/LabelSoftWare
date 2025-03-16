import json
import os

def split_temp_info(info_file):
    # 读取现有信息
    if os.path.exists(info_file):
        with open(info_file, 'r') as f:
            info_data = json.load(f)
    else:
        print(f"文件 {info_file} 不存在")
        return

    # 获取信息文件所在目录
    info_dir = os.path.dirname(info_file)

    # 遍历信息并保存到单独的文件中
    for image_name, data in info_data.items():
        # 创建单独的json文件路径
        single_info_file = os.path.join(info_dir, f"{image_name}.json")

        # 保存信息到单独的文件
        with open(single_info_file, 'w') as f:
            json.dump({
                'window_width': data['window_width'],
                'window_level': data['window_level'],
                'reverse_checked': data['reverse_checked']
            }, f, indent=4)

# 示例调用
split_temp_info('../img_info/fourth-884dcm/temp_info.json')