# -*- coding: utf-8 -*-

"""
Time : 2024/7/17 上午10:29
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : GrayscaleValueDCM.py
Lab: Information Group of InteCast Software Center
Function of the program: 
"""

import pydicom
import numpy as np
from skimage.feature import graycomatrix, graycoprops
import matplotlib.pyplot as plt

# 读取DICOM文件
file_path = 'image/dcm/1.dcm'
ds = pydicom.dcmread(file_path)

# 获取像素数据
image = ds.pixel_array

# 为了简化计算，我们可以将灰度级减少到16级，这取决于你的图像和需求
num_levels = 16
image = (image * (num_levels - 1) / np.max(image)).astype(np.uint8)

# 计算灰度共生矩阵
distances = [1, 2, 3]  # 距离列表
angles = [0, np.pi/4, np.pi/2, 3*np.pi/4]  # 角度列表
properties = ['contrast', 'correlation', 'homogeneity', 'energy']

glcm = graycomatrix(image, distances, angles, levels=num_levels, symmetric=True, normed=True)

# 计算GLCM属性
stats = {}
for prop in properties:
    stats[prop] = graycoprops(glcm, prop).squeeze()

# 输出GLCM和统计属性
print("GLCM:\n", glcm)
for prop in properties:
    print(f"{prop}:\n", stats[prop])

# 可视化GLCM
plt.imshow(glcm[:, :, 0, 0], cmap='gray')
plt.title('Grey Level Co-occurrence Matrix (GLCM)')
plt.colorbar()
plt.show()
