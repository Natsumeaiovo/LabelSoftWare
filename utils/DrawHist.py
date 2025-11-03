import numpy as np
import matplotlib.pyplot as plt


def plot_histogram(pixel_array, window_left=0, window_right=65535, is_reversed=False):
    """
    绘制像素值的灰度直方图并保存为图像
    """
    # 设置图形大小
    plt.figure(figsize=(8, 8))
    dpi = 100
    fig = plt.gcf()
    fig.set_size_inches(291 / dpi, 261 / dpi)

    # 不留边框
    ax = plt.gca()
    ax.axis('off')
    plt.subplots_adjust(top=1, bottom=0, right=1, left=0, hspace=0, wspace=0)
    plt.margins(0, 0)

    # 确定直方图bins和范围
    bits = 16 if pixel_array.dtype == np.uint16 or pixel_array.dtype == np.int16 else 8
    num_bins = 2 ** bits

    # 动态调整直方图范围
    if is_reversed:
        # 反色时可能需要调整窗口范围
        window_left_adjusted = min(window_left, pixel_array.min())
        window_right_adjusted = max(window_right, pixel_array.max())
        hist_range = (65535-window_right, 65535-window_left)
    else:
        hist_range = (window_left, window_right)

    print("直方图范围", hist_range)

    # 绘制直方图
    histogram, bins = np.histogram(pixel_array.flatten(), bins=num_bins, range=hist_range)
    plt.plot(bins[:-1], histogram, color='r')

    # 计算非零区域的最大值，用于设置y轴范围
    # 排除直方图的第一个值(通常为背景)后计算最大值
    start_idx = 1 if not is_reversed else 0
    end_idx = -1 if is_reversed else None  # 反色时排除最后一个值

    if histogram[start_idx:end_idx].size > 0:
        max_count = np.max(histogram[start_idx:end_idx])
    else:
        max_count = 1

    # 设置y轴上限
    upper_limit = min(max_count * 1.1, 2000)
    plt.ylim(0, upper_limit)

    # 使用计算得到的 hist_range 作为 x 轴范围（替代之前的固定 0-65535 / 0-255）
    x_min, x_max = hist_range
    plt.xlim(x_min, x_max)

    # 保存直方图
    plt.savefig('histogram.png', bbox_inches='tight', pad_inches=0)
    plt.close()