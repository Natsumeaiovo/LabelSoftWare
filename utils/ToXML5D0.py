# -*- coding: utf-8 -*-

"""
Time : 2024/8/8 下午6:53
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : ToXML5D0.py
Lab: Information Group of InteCast Software Center
Function of the program: 
"""
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import os


class CreatSaveXml():
    def __init__(self):
        pass

    # 先判断节点个数，再用循环找到他们的参数和值
    @staticmethod
    def creat_xml(path, items, rect_items, image_size, pixmapItem, using="dcm", database="None", isManual=False):
        root = ET.Element("annotation")
        ET.SubElement(root, "folder").text = os.path.basename(os.path.dirname(path))
        ET.SubElement(root, "filename").text = os.path.basename(path)
        ET.SubElement(root, "path").text = path

        source = ET.SubElement(root, "source")
        ET.SubElement(source, "database").text = database

        size = ET.SubElement(root, "size")
        if using == "dcm":
            ET.SubElement(size, "width").text = str(image_size[1])
            ET.SubElement(size,"height").text = str(image_size[0])
        else:
            ET.SubElement(size, "width").text = str(3008)
            ET.SubElement(size, "height").text = str(2512)
        ET.SubElement(size, "depth").text = "1"

        ET.SubElement(root, "segmented").text = "None"

        for index, item in enumerate(rect_items):
            object = ET.SubElement(root, "object")
            if using == "dcm":
                ET.SubElement(object, "name").text = str(item.label)
                ET.SubElement(object, "pose").text = str(item.comment)
            else:
                ET.SubElement(object, "name").text = str(item)
                ET.SubElement(object, "pose").text = str("自动检测")
            ET.SubElement(object, "truncated").text = "None"
            ET.SubElement(object, "difficult").text = "None"

            bndbox = ET.SubElement(object, "bndbox")
            if using == "dcm":
                ET.SubElement(bndbox, "xmin").text = str(float(pixmapItem.mapFromScene(
                    item.mapToScene(item.rect().topLeft())).x()))
                ET.SubElement(bndbox, "ymin").text = str(float(pixmapItem.mapFromScene(
                    item.mapToScene(item.rect().topLeft())).y()))
                ET.SubElement(bndbox, "xmax").text = str(float(pixmapItem.mapFromScene(
                    item.mapToScene(item.rect().bottomRight())).x()))
                ET.SubElement(bndbox, "ymax").text = str(float(pixmapItem.mapFromScene(
                    item.mapToScene(item.rect().bottomRight())).y()))
            else:
                print(pixmapItem)
                print(rect_items)
                ET.SubElement(bndbox, "xmin").text = str(pixmapItem[0][index])
                ET.SubElement(bndbox, "ymin").text = str(pixmapItem[1][index])
                ET.SubElement(bndbox, "xmax").text = str(pixmapItem[2][index])
                ET.SubElement(bndbox, "ymax").text = str(pixmapItem[3][index])

        # 如果isManual为True，添加viewed标签
        if isManual:
            ET.SubElement(root, "viewed").text = "true"
        tree = ET.ElementTree(root)
        save_xml_path = os.path.join(os.path.dirname(os.path.dirname(path)), os.path.basename(os.path.dirname(path))+"-XML")
        if not os.path.exists(save_xml_path):
            os.makedirs(save_xml_path)
        xml_name, suffix = os.path.splitext(os.path.basename(path))
        xml_path_name = os.path.join(save_xml_path, xml_name + ".xml")

        # Pretty print the XML
        xml_str = ET.tostring(root, encoding='utf-8')
        parsed_str = minidom.parseString(xml_str)
        pretty_xml_as_str = parsed_str.toprettyxml(indent="\t")

        with open(xml_path_name, "w", encoding='utf-8') as f:
            f.write(pretty_xml_as_str)
