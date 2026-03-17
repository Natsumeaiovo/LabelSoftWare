# -*- coding: utf-8 -*-

"""
Time : 2024/8/10 下午6:15
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : FromXML.py
Lab: Information Group of InteCast Software Center
Function of the program:
"""

import xml.etree.ElementTree as ET


# utils/FromXML.py


def analysis_xml(path, return_size=False):
    # 解析XML文件
    tree = ET.parse(path)
    root = tree.getroot()
    label = []
    comment_pose = []
    level = []
    xmin = []
    ymin = []
    xmax = []
    ymax = []

    # 提取所有对象（标注框）的信息
    for obj in root.findall('.//object'):
        name_node = obj.find('name')
        pose_node = obj.find('pose')
        level_node = obj.find('level')

        label.append(name_node.text if name_node is not None else "")
        comment_pose.append(pose_node.text if pose_node is not None else "")

        # 兼容旧 XML：没有 level 时使用默认值 0
        if level_node is None or level_node.text is None or str(level_node.text).strip() == "":
            level.append("0")
        else:
            level.append(str(level_node.text).strip())

        bndbox = obj.find('bndbox')
        if bndbox:
            xmin.append(bndbox.find('xmin').text)
            ymin.append(bndbox.find('ymin').text)
            xmax.append(bndbox.find('xmax').text)
            ymax.append(bndbox.find('ymax').text)

    if return_size:
        size_tag = root.find('size')
        if size_tag is not None:
            width = int(size_tag.find('width').text)
            height = int(size_tag.find('height').text)
            return label, xmin, ymin, xmax, ymax, comment_pose, level, (width, height)
        else:
            # 如果没有size标签，返回None
            return label, xmin, ymin, xmax, ymax, comment_pose, level, None
    else:
        return label, xmin, ymin, xmax, ymax, comment_pose, level
