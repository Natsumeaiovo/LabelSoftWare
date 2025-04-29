import pydicom
import numpy as np
from scipy.signal import convolve2d
import matplotlib.pyplot as plt

# 读取DICOM文件
dcm_path = r'D:\TEST\621dcm\1 (375).dcm'  # 替换为你的DCM文件路径
ds = pydicom.dcmread(dcm_path)
image = ds.pixel_array

# 归一化处理到0-255范围
image_normalized = image.astype(np.float64)
image_normalized = (image_normalized - np.min(image_normalized)) / \
                  (np.max(image_normalized) - np.min(image_normalized)) * 255
image_uint8 = image_normalized.astype(np.uint8)

# 定义锐化卷积核
sharpen_kernel = np.array([
    [0, -1, 0],
    [-1,  5, -1],  # 中心权重越大，锐化效果越强
    [-0, -1, 0]
])

# 执行卷积操作
sharpened = convolve2d(image_uint8, sharpen_kernel, mode='same', boundary='symm')

# 裁剪并转换为uint8
sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)

# 显示对比图
plt.figure(figsize=(10, 5))

plt.subplot(1, 2, 1)
plt.imshow(image_uint8, cmap='gray')
plt.title('Original Image')
plt.axis('off')

plt.subplot(1, 2, 2)
plt.imshow(sharpened, cmap='gray')
plt.title('Sharpened Image')
plt.axis('off')

plt.tight_layout()
plt.show()