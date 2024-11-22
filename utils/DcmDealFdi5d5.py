# -*- coding: utf-8 -*-

"""
Time : 2024/11/9 下午4:57
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : DcmDealFdi5d5.py
Lab: Information Group of InteCast Software Center
Function of the program: 不同增强方法
"""
import cv2
import numpy as np
from PIL import Image

from constants import *


class DcmDealFdi5d5:
    method_dict = None

    def __init__(self):
        self.method_dict = {
            WINDOW_IMAGE: self.window_image,
            NORMALIZE: self.normalize_image,
            PARTITION_WINDOWING: self.partition_window,
            SUB_WINDOW: self.sub_window,
            SUB_NORMALIZE: self.sub_normalize
        }

    def call_method(self, method_name: str, image):
        method = self.method_dict.get(method_name)
        if method:
            return method(image)
        else:
            return None

    def window_image(self, image):
        window_center = np.mean(image)
        window_width = np.std(image) * 2
        min_val = window_center - (window_width / 2)
        max_val = window_center + (window_width / 2)
        return np.clip((image - min_val) / (max_val - min_val) * 255, 0, 255).astype(np.uint8)

    def normalize_image(self, image):
        return cv2.normalize(image, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    def partition_window(self, pixel_array, step=5500, output_dir='image/png/different'):
        """
        处理DICOM图像，应用窗口化，并保存结果到指定目录。
        """

        # 获取最大和最小灰度值
        min_gray_value = pixel_array.min()
        max_gray_value = pixel_array.max()

        # 计算区间
        intervals = []
        start = min_gray_value
        while start < max_gray_value:
            end = min(start + step, max_gray_value)
            intervals.append((start, end))
            start = end

        enhanced_pixel_array = np.zeros_like(pixel_array, dtype=np.uint8)
        # 对每个区间进行处理
        for i, interval in enumerate(intervals):
            mask = np.logical_and(pixel_array >= interval[0], pixel_array <= interval[1])
            interval_data = pixel_array[mask]

            # # 计算最大最小值
            # if interval_data.size != 0:
            #     interval_min = interval_data.min()
            #     interval_max = interval_data.max()
            # else:
            #     interval_min = interval[0]
            #     interval_max = interval[1]
            # print(f"Interval {interval[0]} to {interval[1]}: Min={interval_min}, Max={interval_max}")

            # 计算平均值和标准差
            # 计算窗口中心和宽度
            if interval_data.size != 0:
                mean = np.mean(interval_data)
                std_dev = np.std(interval_data) * 2
                min_val = mean - (std_dev / 2)
                max_val = mean + (std_dev / 2)
            else:
                min_val = interval[0]
                max_val = interval[1]

            # 避免除数为零的情况
            if max_val == min_val:
                # 如果区间宽度为零，直接将所有像素设置为255（或根据需求设置为0）
                enhanced_pixel_array[mask] = 255  # 或者可以使用0，表示区间内的像素值相同
            else:
                # 应用窗口化增强
                enhanced_interval = np.clip((pixel_array - min_val) / (max_val - min_val) * 255, 0, 255).astype(
                    np.uint8)

                # 将增强结果合并到最终图像
                enhanced_pixel_array[mask] = enhanced_interval[mask]
        return enhanced_pixel_array

    def sub_window(self, image):
        # Scale the image by a factor of 3
        height, width = image.shape
        factor = 1 / 2
        # Adjust dimensions to the nearest multiple of 416
        new_height = round((height * factor) / 416) * 416
        new_width = round((width * factor) / 416) * 416
        image_resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

        # Calculate number of sub-images
        num_subimages_x = new_width // 416
        num_subimages_y = new_height // 416
        crops = []
        for i in range(num_subimages_y):
            for j in range(num_subimages_x):
                # Crop sub-image
                sub_image = image_resized[i * 416:(i + 1) * 416, j * 416:(j + 1) * 416]
                crops.append(sub_image)

        enhanced_crops = [self.window_image(crop) for crop in crops]

        result = Image.new('L', (new_width, new_height), color=0)
        index = 0
        for i in range(num_subimages_y):
            for j in range(num_subimages_x):
                left = j * 416
                upper = i * 416
                right = (j + 1) * 416
                lower = (i + 1) * 416
                crop_image = Image.fromarray(enhanced_crops[index])
                result.paste(crop_image, (left, upper, right, lower))
                index += 1
        result = np.array(result)
        result = cv2.resize(result, (width, height), interpolation=cv2.INTER_LINEAR)
        return result

    def sub_normalize(self, image):
        # Scale the image by a factor of 3
        height, width = image.shape
        factor = 1 / 2
        # Adjust dimensions to the nearest multiple of 416
        new_height = round((height * factor) / 416) * 416
        new_width = round((width * factor) / 416) * 416
        image_resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

        # Calculate number of sub-images
        num_subimages_x = new_width // 416
        num_subimages_y = new_height // 416
        crops = []
        for i in range(num_subimages_y):
            for j in range(num_subimages_x):
                # Crop sub-image
                sub_image = image_resized[i * 416:(i + 1) * 416, j * 416:(j + 1) * 416]
                crops.append(sub_image)

        enhanced_crops = [self.normalize_image(crop) for crop in crops]

        result = Image.new('L', (new_width, new_height), color=0)
        index = 0
        for i in range(num_subimages_y):
            for j in range(num_subimages_x):
                left = j * 416
                upper = i * 416
                right = (j + 1) * 416
                lower = (i + 1) * 416
                crop_image = Image.fromarray(enhanced_crops[index])
                result.paste(crop_image, (left, upper, right, lower))
                index += 1
        result = np.array(result)
        result = cv2.resize(result, (width, height), interpolation=cv2.INTER_LINEAR)
        return result
