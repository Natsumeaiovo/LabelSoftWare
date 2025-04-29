import pydicom
import numpy as np
import cv2
from scipy.fftpack import fftshift, ifftshift, fft2, ifft2
import matplotlib.pyplot as plt
import deprecated.utils as pu


def apply_clahe(image, clip_limit, tile_grid_size):
    # 将图像转换为8位（如果需要）
    if image.dtype != np.uint8:
        image = cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    # 创建CLAHE对象
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    clahe_image = clahe.apply(image)
    return clahe_image

# 非锐化掩蔽（Unsharp Masking）
def unsharp_mask(img, sigma=1.0, strength=1.5, kernel_size=(5,5), show_intermediate=False):
    # Step 1: 高斯模糊 (生成低通滤波图像)
    blurred = cv2.GaussianBlur(img, kernel_size, sigmaX=sigma)

    # Step 2: 计算细节层 (原始图像 - 模糊图像)
    detail = cv2.subtract(img, blurred)

    # Step 3: 增强细节并叠加回原图
    sharpened = cv2.addWeighted(img, 2.0, detail, strength, 0)

    # # 限制像素值在合法范围 [0,255]
    # sharpened = np.clip(sharpened, 0, 16383).astype(np.uint16)
    return sharpened


# 高频强调滤波（High-Frequency Emphasis Filtering）
def high_frequency_emphasis(
        img,
        sigma=1.5,  # 高斯滤波器标准差 (控制高频范围)
        k1=0.5,  # 低频保留系数 (0~1)
        k2=2.0,  # 高频增强系数 (>1)
):
    """
    高频强调滤波 (专为X射线图像优化)

    参数:
        image_path: 输入图像路径
        sigma: 高斯滤波标准差，越大保留的低频越多
        k1: 低频保留权重 (建议0.3~0.7)
        k2: 高频增强权重 (建议1.5~3.0)
        visualize: 可视化中间结果

    返回:
        enhanced: 增强后的图像 (uint8)
    """
    # 读取图像并归一化到[0,1]
    img = img.astype(np.float32) / 16383.0

    # Step 1: 高斯低通滤波 (获取低频成分)
    low_pass = cv2.GaussianBlur(img, (0, 0), sigmaX=sigma, sigmaY=sigma)

    # Step 2: 高频成分提取 (原始 - 低通)
    high_pass = img - low_pass

    # Step 3: 高频强调公式 (核心)
    enhanced = k1 * low_pass + k2 * high_pass  # 加权组合

    # 限制到[0,1]并转换为uint8
    enhanced = np.clip(enhanced * 16383, 0, 16383).astype(np.uint16)

    return enhanced



def guided_filter(I, p, radius=16, eps=0.01):
    # 转换输入格式
    I = np.float32(I)
    p = np.float32(p)

    # 计算局部统计量
    mean_I = cv2.boxFilter(I, cv2.CV_32F, (radius, radius))
    mean_p = cv2.boxFilter(p, cv2.CV_32F, (radius, radius))
    corr_I = cv2.boxFilter(I * I, cv2.CV_32F, (radius, radius))
    corr_Ip = cv2.boxFilter(I * p, cv2.CV_32F, (radius, radius))

    # 计算方差和协方差
    var_I = corr_I - mean_I * mean_I
    cov_Ip = corr_Ip - mean_I * mean_p

    # 计算线性系数
    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I

    # 平均系数
    mean_a = cv2.boxFilter(a, cv2.CV_32F, (radius, radius))
    mean_b = cv2.boxFilter(b, cv2.CV_32F, (radius, radius))

    # 生成基础层
    base_layer = mean_a * I + mean_b

    return base_layer


def rawimg_enhance(image, radius, eps, beta):
    # 确保输入图像是8位灰度图像
    if image.dtype != np.uint8:
        raise ValueError("Input image must be an 8-bit grayscale image!")

    # 将图像转换为浮点数
    raw_img = image.astype(np.float32)

    # 1 对数处理（Retinex分解）
    epsilon = 1e-6
    s_log = np.log(raw_img + epsilon)  # 公式(2)-(4)

    # 2 归一化到[0, 1]范围
    s_log_min = np.min(s_log)
    s_log_max = np.max(s_log)
    s_log_norm = (s_log - s_log_min) / (s_log_max - s_log_min)  # 映射到[0, 1]

    # 3 导向滤波获取基础层
    base_log = guided_filter(s_log_norm, s_log_norm, radius, eps)

    # 4 动态范围映射与细节处理，计算细节层
    detail_log = s_log_norm - base_log

    # 5 系数分配与合成
    alpha = 1  # 基础层压缩系数
    beta = beta   # 细节层增强系数
    enhanced_base = alpha * base_log
    enhanced_detail = beta * detail_log
    enhanced_log = enhanced_base + enhanced_detail

    # 6 恢复到原始范围并裁剪到[0, 1]
    enhanced_log = np.clip(enhanced_log, 0, 1)

    # 7 恢复到8位灰度图像的范围[0, 255]
    enhanced_img = (enhanced_log * 255).astype(np.uint8)

    return enhanced_img
