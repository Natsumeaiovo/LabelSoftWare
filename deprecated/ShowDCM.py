# -*- coding: utf-8 -*-

"""
Time : 2024/7/16 下午9:43
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : ShowDCM.py
Lab: Information Group of InteCast Software Center
Function of the program:
"""

import pydicom
import cv2
import numpy as np

# 读取 DICOM 文件
dcm_file_path = 'image/dcm/1.dcm'
dcm_data = pydicom.dcmread(dcm_file_path)

# 提取图像数据
image_data = dcm_data.pixel_array

# 检查图像数据的范围
print(f"Original Data Range: {image_data.min()} - {image_data.max()}")

# # 方法1：设置窗口和层级以调整显示范围（可根据实际情况调整）
# window_center = np.mean(image_data)  # 确定显示范围的中心值，设为图像数据的平均值
# window_width = np.std(image_data) * 2  # 确定显示范围的宽度，设为图像数据标准差的两倍
# min_val = window_center - (window_width / 2)
# max_val = window_center + (window_width / 2)
# rescaled_image = np.clip((image_data - min_val) / (max_val - min_val) * 255, 0, 255)
# rescaled_image = np.uint8(rescaled_image)

# # 方法2：如果图像数据的值范围不是 0-255，需要进行归一化处理
# image_data = cv2.normalize(image_data, None, 0, 255, cv2.NORM_MINMAX)
# image_data = np.uint8(image_data)


# 指定显示的宽度和高度
width, height = 800, 600  # 例如，800x600像素

# 调整图像大小
resized_image = cv2.resize(image_data, (width, height))

# 显示图像
cv2.imshow('DICOM Image', resized_image)
cv2.waitKey(0)
cv2.destroyAllWindows()

# 保存图像为 PNG 格式
output_path = 'output_image.png'
cv2.imwrite(output_path, resized_image)

print(f"Image saved as {output_path}")


