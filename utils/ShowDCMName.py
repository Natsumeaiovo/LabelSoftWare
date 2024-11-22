# -*- coding: utf-8 -*-

"""
Time : 2024/7/26 下午10:47
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : ShowDCMName.py
Lab: Information Group of InteCast Software Center
Function of the program: 
"""

import sys
import re
import os
from PySide2.QtWidgets import QApplication, QMainWindow, QFileDialog, QListWidget, QVBoxLayout, QWidget, QPushButton

class DicomViewer(QMainWindow):
    def __init__(self, listWidget_dcm_name):
        super().__init__()
        self.list_widget = listWidget_dcm_name


    def open_folder(self, folder_path):
        print("folder_path", folder_path)
        if folder_path:
            self.list_widget.clear()
            file_names = os.listdir(folder_path)
            file_names = sorted(file_names, key=self.natural_sort_key)
            for file_name in file_names:
                if file_name.endswith((".dcm", ".png", ".jpg", ".bmp", ".tif", ".tiff")):
                    print(file_name, "file_name")
                    self.list_widget.addItem(file_name)


    def natural_sort_key(self, s):
        # 将文件名转换为可以用于自然排序的键
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]


