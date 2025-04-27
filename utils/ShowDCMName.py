# -*- coding: utf-8 -*-

"""
Time : 2024/7/26 下午10:47
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : ShowDCMName.py
Lab: Information Group of InteCast Software Center
Function of the program: 
"""

import os
import re

from PySide2 import QtCore
from PySide2.QtGui import QIcon, QPixmap
from PySide2.QtWidgets import QMainWindow, QListWidget, QListWidgetItem, QWidget, QHBoxLayout, QLabel


class ImageNameList(QMainWindow):
    def __init__(self, list_widget: QListWidget):
        super().__init__()
        self.list_widget = list_widget
        self.list_widget.setIconSize(QtCore.QSize(8, 8))

    def check_xml_has_object(self, xml_file_path: str) -> bool:
        """检查XML文件是否包含object标签"""
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            # 查找所有object标签
            objects = root.findall('.//object')
            return len(objects) > 0
        except Exception as e:
            print(f"检查XML文件出错: {e}")
            return False

    def check_xml_viewed_status(self, xml_file_path: str) -> bool:
        """检查XML文件是否存在且包含viewed标签且值为true"""
        if not os.path.exists(xml_file_path):
            return False

        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(xml_file_path)
            root = tree.getroot()
            # 查找viewed标签
            viewed_tag = root.find('viewed')
            return viewed_tag is not None and viewed_tag.text.lower() == 'true'
        except Exception as e:
            print(f"检查XML文件viewed状态出错: {e}")
            return False

    def open_folder(self, folder_path):
        print("folder_path", folder_path)
        if folder_path:
            self.current_folder_path = folder_path  # 保存当前文件夹路径
            self.list_widget.clear()
            file_names = os.listdir(folder_path)
            file_names = sorted(file_names, key=self.natural_sort_key)

            for file_name in file_names:
                if file_name.endswith((".dcm", ".png", ".jpg", ".bmp", ".tif", ".tiff")):
                    print(file_name, "file_name")
                    # 创建一个QListWidgetItem对象
                    item = QListWidgetItem(file_name)
                    # 将item添加到list_widget
                    self.list_widget.addItem(item)

            # 在添加完所有项目后，更新它们的显示状态
            self.check_dcm_status(self.list_widget)

    def check_dcm_status(self, listWidget: QListWidget):
        """更新列表项的状态显示，包括是否查看过以及是否有object标签"""
        # 获取父目录和文件夹名
        parent_dir = os.path.dirname(self.current_folder_path)
        folder_name = os.path.basename(self.current_folder_path)
        # 构建对应的XML目录路径
        xml_folder_path = os.path.join(parent_dir, folder_name + "-XML")

        for i in range(listWidget.count()):
            list_item: QListWidgetItem = listWidget.item(i)
            # listWidget.item(i).setTextColor(QtCore.Qt.transparent)  # 文本颜色设为透明
            file_name = list_item.text()

            # 获取XML文件路径
            xml_file_name = os.path.splitext(file_name)[0] + ".xml"
            xml_file_path = os.path.join(xml_folder_path, xml_file_name)

            # 查看状态图标
            viewed = self.check_xml_viewed_status(xml_file_path)
            list_item.setIcon(QIcon('./Sources/viewed' if viewed else './Sources/not_viewed'))

            # 创建一个只包含对象图标的自定义widget
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(0, 0, 5, 0)  # 减小左边距，保留右边距
            # 添加弹性空间，将图标推到最右侧
            layout.addStretch(1)

            # 对象标注状态图标
            if os.path.exists(xml_file_path):
                has_object = self.check_xml_has_object(xml_file_path)
                object_icon = QLabel()
                object_pixmap = QPixmap('./Sources/has_defect' if has_object else './Sources/no_defect')
                object_icon.setPixmap(object_pixmap.scaled(12, 12, QtCore.Qt.KeepAspectRatio))
                layout.addWidget(object_icon)

            # 设置自定义widget
            listWidget.setItemWidget(list_item, widget)

    def update_item_status(self, listWidget: QListWidget, file_name: str):
        """更新单个列表项的状态显示"""
        # 查找对应项目
        for i in range(listWidget.count()):
            item = listWidget.item(i)
            if item.text() == file_name:
                # 获取XML文件路径
                parent_dir = os.path.dirname(self.current_folder_path)
                folder_name = os.path.basename(self.current_folder_path)
                xml_folder_path = os.path.join(parent_dir, folder_name + "-XML")
                xml_file_name = os.path.splitext(file_name)[0] + ".xml"
                xml_file_path = os.path.join(xml_folder_path, xml_file_name)

                # 设置查看状态图标
                viewed = self.check_xml_viewed_status(xml_file_path)
                item.setIcon(QIcon('./Sources/viewed' if viewed else './Sources/not_viewed'))

                # 创建一个只包含对象图标的自定义widget
                widget = QWidget()
                layout = QHBoxLayout(widget)
                layout.setContentsMargins(0, 0, 5, 0)

                # 添加弹性空间，将图标推到最右侧
                layout.addStretch(1)

                # 对象标注状态图标
                if os.path.exists(xml_file_path):
                    has_object = self.check_xml_has_object(xml_file_path)
                    object_icon = QLabel()
                    object_pixmap = QPixmap('./Sources/has_defect' if has_object else './Sources/no_defect')
                    object_icon.setPixmap(object_pixmap.scaled(12, 12, QtCore.Qt.KeepAspectRatio))
                    layout.addWidget(object_icon)

                # 设置自定义widget
                listWidget.setItemWidget(item, widget)
                break

    def natural_sort_key(self, s):
        # 将文件名转换为可以用于自然排序的键
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]
