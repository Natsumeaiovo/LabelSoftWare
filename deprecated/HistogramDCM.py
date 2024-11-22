# -*- coding: utf-8 -*-

"""
Time : 2024/7/17 上午10:08
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : HistogramDCM.py
Lab: Information Group of InteCast Software Center
Function of the program: 
"""

import os
import pydicom
import numpy as np
import matplotlib.pyplot as plt


def plot_histograms(directory, output_directory):
    # 确保输出目录存在
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    # 遍历指定的文件夹
    for filename in os.listdir(directory):
        if filename.endswith('.dcm'):
            filepath = os.path.join(directory, filename)

            # 使用pydicom读取DICOM文件
            ds = pydicom.dcmread(filepath)

            # 获取图像像素值
            image_data = ds.pixel_array

            # 计算灰度直方图
            histogram, bins = np.histogram(image_data.flatten(), bins=65536, range=(0, 65536))
            histogram_new = []
            for i in histogram:
                if i > 2500:
                    i = 2500
                histogram_new.append(i)

            # 绘制直方图
            plt.figure()
            plt.title('Grayscale Histogram')
            plt.xlabel('Pixel Value')
            plt.ylabel('Frequency')
            plt.plot(bins[:-1], histogram_new, color='r')
            plt.xlim([0, 65536])
            plt.ylim(bottom=0)

            # 保存直方图到文件
            histogram_filename = f"{os.path.splitext(filename)[0]}_histogram.png"
            histogram_filepath = os.path.join(output_directory, histogram_filename)
            plt.savefig(histogram_filepath)
            plt.close()


# 指定输入和输出目录
input_directory = 'image/dcm621'
output_directory = 'image621/histogram'

plot_histograms(input_directory, output_directory)
