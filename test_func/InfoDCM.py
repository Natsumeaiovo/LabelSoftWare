# -*- coding: utf-8 -*-

"""
Time : 2024/7/17 上午12:09
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : InfoDCM.py
Lab: Information Group of InteCast Software Center
Function of the program: 
"""

from pydicom import dcmread
import numpy as np
import os


def get_dcm_details(file_path):
    ds = dcmread(file_path)
    pixel_array = ds.pixel_array

    details = {
        '文件名': file_path,
        '分辨率': f"{ds.PixelSpacing[0]} x {ds.PixelSpacing[1]} pixels/mm",
        '尺寸（大小）': f"{ds.Columns} x {ds.Rows} pixels",
        '颜色模式': ds.PhotometricInterpretation,
        '位深度（位数）': ds.BitsAllocated,
        '像素间距': f"{ds.PixelSpacing[0]} x {ds.PixelSpacing[1]} mm",
        '窗口中心和窗口宽度': (ds.WindowCenter, ds.WindowWidth) if ('WindowCenter' in ds and 'WindowWidth' in ds) else '未指定',
        '研究实例UID': ds.StudyInstanceUID,
        '系列实例UID': ds.SeriesInstanceUID,
        '研究和系列信息': {
            '研究实例UID': ds.StudyInstanceUID,
            '系列实例UID': ds.SeriesInstanceUID,
            '序列号': ds.InstanceNumber if 'NumberOfFrames' in ds else '未知',
            '总序列数': ds.NumberOfFrames if 'NumberOfFrames' in ds else '未知'
        },
        '设备和软件信息': {
            '设备': ds.Manufacturer,
            '软件版本': ds.SoftwareVersions if 'SoftwareVersions' in ds else '未知'
        },
        '灰度信息': {
            '最小灰度值': np.min(pixel_array),
            '最大灰度值': np.max(pixel_array)
        }
    }

    return details


def main(directory, output_file):
    image_files = [f for f in os.listdir(directory) if f.lower().endswith('.dcm')]
    info_list = []
    for image_file in image_files:
        full_path = os.path.join(directory, image_file)
        info = get_dcm_details(full_path)
        info_list.append(info)

    with open(output_file, 'w', encoding='utf-8') as f:
        for info in info_list:
            for key, value in info.items():
                if isinstance(value, dict):
                    f.write(f"{key}:\n")
                    for sub_key, sub_value in value.items():
                        f.write(f"  {sub_key}: {sub_value}\n")
                else:
                    f.write(f"{key}: {value}\n")
            f.write("\n")


if __name__ == "__main__":
    directory = r'F:\tanshangtuxiang\621-Ti\20240424dcm'  # 修改为DCM文件夹路径
    output_file = 'Info.txt'  # 修改为输出文件路径
    main(directory, output_file)
