# -*- coding: utf-8 -*-

"""
Time : 2024/7/26 下午9:39
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : WindowImage.py
Lab: Information Group of InteCast Software Center
Function of the program: 
"""

import numpy as np


def window_image(img, window_center, window_width):
    min_val = window_center - (window_width / 2)
    max_val = window_center + (window_width / 2)
    return np.clip((img - min_val) / (max_val - min_val) * 255, 0, 255).astype(np.uint8)
