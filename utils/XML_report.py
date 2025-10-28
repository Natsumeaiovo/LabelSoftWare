import os
import xml.etree.ElementTree as ET
import pandas as pd
from collections import defaultdict
from openpyxl.styles import Border, Side
import re


def parse_xml_file(xml_path):
    """解析单个XML文件，统计缺陷和检测类型"""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        defect_counts = defaultdict(int)
        has_defects = False
        pose_values = set()
        total_defects = 0  # 新增：统计缺陷总数

        for obj in root.findall('object'):
            # 统计缺陷类型
            defect_type = obj.find('name').text if obj.find('name') is not None else '未知类型'
            defect_counts[defect_type] += 1
            has_defects = True
            total_defects += 1  # 每个object标签计数

            # 收集pose值
            pose = obj.find('pose').text if obj.find('pose') is not None else 'None'
            pose_values.add(pose.lower())

        # 确定检测类型
        detection_type = "无缺陷"
        if pose_values:
            if len(pose_values) == 1:
                if 'none' in pose_values:
                    detection_type = "人工检测"
                else:
                    detection_type = "自动检测"
            else:
                detection_type = "人工+自动检测"

        return {
            'defects': dict(defect_counts) if has_defects else None,
            'detection_type': detection_type,
            'total_defects': total_defects  # 新增：返回缺陷总数
        }

    except Exception as e:
        print(f"解析文件 {xml_path} 时出错: {str(e)}")
        return None


def natural_sort_key(s):
    """自然排序键函数，处理数字编号"""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]


def add_excel_border(worksheet):
    """为Excel工作表添加边框和调整列宽"""
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )

    for row in worksheet.iter_rows():
        for cell in row:
            cell.border = thin_border

    # 调整列宽
    for col in worksheet.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2) * 1.2
        worksheet.column_dimensions[column].width = adjusted_width


def clean_folder_name(folder_name):
    """清理文件夹名，去除-XML后缀"""
    return re.sub(r'-XML$', '', folder_name, flags=re.IGNORECASE)


def clean_file_name(file_name):
    """清理文件名，去除.xml后缀"""
    return re.sub(r'\.xml$', '', file_name, flags=re.IGNORECASE)


def process_xml_folder(folder_path, output_excel):
    """处理文件夹中的所有XML文件并汇总到Excel"""
    folder_path = os.path.abspath(folder_path)
    output_excel = os.path.abspath(output_excel)
    results = []
    defect_types = set()

    # 收集XML文件路径（仅当前目录）
    xml_files = []
    try:
        cleaned_folder_path = clean_folder_name(folder_path)
        files = os.listdir(folder_path)
        for file in files:
            if file.lower().endswith('.xml'):
                full_path = os.path.join(folder_path, file)
                # 获取文件名（去除.xml后缀）
                file_part = clean_file_name(file)
                # 当前目录
                xml_files.append((cleaned_folder_path, file_part, full_path))
    except OSError as e:
        print(f"读取目录 {folder_path} 时出错: {str(e)}")
        return

        # 按自然顺序排序文件路径
    xml_files.sort(key=lambda x: natural_sort_key(x[1]))  # 只按文件名排序

    for dir_part, file_part, full_path in xml_files:
        # 解析XML文件
        parsed_data = parse_xml_file(full_path)

        if parsed_data is None:
            continue

        defects = parsed_data['defects']
        detection_type = parsed_data['detection_type']
        total_defects = parsed_data['total_defects']  # 获取缺陷总数

        # 准备结果行
        result_row = {
            '文件路径': dir_part,  # 已清理-XML后缀
            '文件名': file_part,  # 已清理.xml后缀
            '检测类型': detection_type,
            '缺陷总数': total_defects,  # 新增：缺陷总数列
        }

        if defects is not None:
            defects_str = "; ".join([f"{k}: {v}" for k, v in defects.items()])
            result_row['缺陷类型与数量'] = defects_str
            defect_types.update(defects.keys())
            for k, v in defects.items():
                result_row[k] = v
        else:
            result_row['缺陷类型与数量'] = "无"

        results.append(result_row)

    # 转换为DataFrame
    df = pd.DataFrame(results)

    # 确保所有缺陷类型都有列
    for dtype in defect_types:
        if dtype not in df.columns:
            df[dtype] = 0

    # 处理NaN值
    # for dtype in defect_types:
    #     df[dtype] = df[dtype].fillna(0).astype(int)

    # 排序列 - 固定前几列顺序，后面按缺陷类型排序
    fixed_columns = ['文件路径', '文件名', '检测类型', '缺陷总数', '缺陷类型与数量']
    other_columns = sorted(
        [col for col in df.columns if col not in fixed_columns],
        key=natural_sort_key
    )
    df = df[fixed_columns + other_columns]

    # 保存到Excel并添加样式
    if not df.empty:
        with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)

            # 获取工作表对象并添加边框
            worksheet = writer.sheets['Sheet1']
            add_excel_border(worksheet)

        print(f"处理完成! 结果已保存到 {output_excel}")
        print(f"共处理了 {len(df)} 个XML文件")

        if defect_types:
            total_defects_by_type = df.iloc[:, 5:].sum().to_dict()  # 跳过前5列
            print("\n缺陷类型总计:")
            for defect_type, count in total_defects_by_type.items():
                print(f"{defect_type}: {count}")

            # 打印缺陷总数统计
            total_all_defects = df['缺陷总数'].sum()
            print(f"\n所有文件缺陷总数: {total_all_defects}")
        else:
            print("\n所有XML文件均无缺陷")

        # 检测类型统计
        print("\n检测类型统计:")
        print(df['检测类型'].value_counts().to_string())
    else:
        print("未找到任何XML文件")


if __name__ == "__main__":
    input_folder = r"D:\dataset\haozhe-621test20251027\621test20251027-XML"
    output_excel = r"D:\dataset\output.xlsx"

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_excel), exist_ok=True)

    if not os.path.exists(input_folder):
        print(f"错误: 输入文件夹 {input_folder} 不存在")
    else:
        process_xml_folder(input_folder, output_excel)