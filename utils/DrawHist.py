# -*- coding: utf-8 -*-

"""
Time : 2024/7/26 下午1:11
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : DrawHist.py
Lab: Information Group of InteCast Software Center
Function of the program: 
"""

import pydicom
import matplotlib.pyplot as plt
import numpy as np


# 绘制直方图
def plot_histogram(pixel_array, window_left=0, window_right=65535):
    # 设置图形大小
    plt.figure(figsize=(8, 8))  # 这个设置是为了生成接近291x261像素的图像
    dpi = 100
    fig = plt.gcf()
    fig.set_size_inches(291 / dpi, 261 / dpi)

    # 不留边框
    ax = plt.gca()
    ax.axis('off')
    plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
    plt.margins(0, 0)

    # 绘制直方图
    histogram, bins = np.histogram(pixel_array.flatten(), bins=65536, range=(window_left, window_right))
    plt.plot(bins[:-1], histogram, color='r')

    # 排除像素值为0的计数，计算除了0之外的最大值
    non_zero_max_count = np.max(histogram[1:]) if histogram[1:].any() else 1
    # plt.ylim(0, non_zero_max_count * 1.1)  # 给最大值一些额外的空间
    upper_limit = min(non_zero_max_count * 1.1, 3000)  # 取1.1倍最大值和3000的较小者
    plt.ylim(0, upper_limit)  # 应用硬性上限

    # 显示直方图
    plt.xlim(0, 65535)  # 横轴范围
    plt.savefig('histogram.png', bbox_inches='tight', pad_inches=0)
    plt.close()  # 关闭matplotlib图形以释放资源
