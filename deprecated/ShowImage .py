# -*- coding: utf-8 -*-

"""
Time : 2024/7/26 上午9:04
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : ShowImage.py
Lab: Information Group of InteCast Software Center
Function of the program: 显示图片，缩放图片，并进行标签框添加
"""

import os
from typing import List

import numpy as np
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets
from PySide2.QtCore import Qt, QRectF, QPointF
from PySide2.QtGui import QPen, QBrush, QColor
from PySide2.QtGui import Qt
from PySide2.QtWidgets import QDialog, QListWidget
from PySide2.QtWidgets import QGraphicsView, QGraphicsRectItem, QGraphicsItem, QColorDialog, QInputDialog, QMenu
from PySide2.QtWidgets import QWidget, QListWidgetItem, QGraphicsPixmapItem

from utils import FromXML
from utils import ToXML5D0
from widgets.LabelDialog import LabelDialog


class IMG_WIN(QWidget):
    def __init__(self, graphicsView: QGraphicsView, listWidget: QListWidget):
        super().__init__()
        self.graphicsView = graphicsView
        self.listWidget = listWidget

        self.graphicsView.setStyleSheet("padding: 0px; border: 0px;")  # 内边距和边界去除
        self.scene = QtWidgets.QGraphicsScene(self)
        self.graphicsView.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)  # 改变对齐方式

        self.graphicsView.setSceneRect(0, 0, self.graphicsView.viewport().width(),
                                       self.graphicsView.height())  # 设置图形场景大小和图形视图大小一致
        self.graphicsView.setScene(self.scene)
        # self.graphicsView.setRenderHint(QPainter.Antialiasing)
        self.scene.mousePressEvent = self.scene_MousePressEvent  # 接管图形场景的鼠标事件
        self.scene.mouseReleaseEvent = self.scene_mouseReleaseEvent
        self.scene.mouseMoveEvent = self.scene_mouseMoveEvent
        self.scene.wheelEvent = self.scene_wheelEvent

        self.listWidget.itemSelectionChanged.connect(self.on_list_selection_changed)
        self.listWidget.itemChanged.connect(self.on_item_changed)
        self.scene.selectionChanged.connect(self.on_rect_selection_changed)

        self.ratio = 1  # 缩放初始比例
        self.zoom_step = 0.1  # 缩放步长
        self.zoom_max = 100  # 缩放最大值
        self.zoom_min = 0.1  # 缩放最小值
        self.pixmapItem = None

        self.drawing = False  # 是否在绘制方框
        self.moving = False  # 鼠标是否在移动
        self.resizing = False  # 是否在resize方框
        self.start_pos = QtCore.QPointF()
        self.current_rect: CustomRectItem = None
        self.resizing_rect = None
        self.rect_items: List[CustomRectItem] = []
        self.updating_selection = False


    # clear表示是否清空原有的标签框
    def addScenes(self, img, path, clear: bool):  # 绘制图形
        # self.org = img
        if self.pixmapItem is not None:
            originX = self.pixmapItem.x()
            originY = self.pixmapItem.y()
        else:
            originX, originY = 0, 0  # 坐标基点

        # 创建QPixmap
        if img.dtype == np.uint16:  # 假设像素数组为16位
            q_img = QtGui.QImage(img.data, img.shape[1], img.shape[0], img.strides[0], QtGui.QImage.Format_Grayscale16)
        else:  # 假设像素数组为8位
            q_img = QtGui.QImage(img.data, img.shape[1], img.shape[0], img.strides[0], QtGui.QImage.Format_Grayscale8)

        self.pixmap = QtGui.QPixmap.fromImage(q_img)
        # 如果clear为True，清空原有的标签框
        if clear:
            self.scene.clear()
            self.rect_items.clear()
            self.listWidget.clear()
            self.pixmapItem = self.scene.addPixmap(self.pixmap)  # 添加图元
        else:
            for item in self.scene.items():
                # 检查每个项是否为 QGraphicsPixmapItem
                if isinstance(item, QGraphicsPixmapItem):
                    # 替换 pixmap
                    item.setPixmap(self.pixmap)
                    break  # 如果找到了就停止搜索
        self.pixmapItem.setScale(self.ratio)
        self.pixmapItem.setTransformationMode(QtCore.Qt.SmoothTransformation)
        self.pixmapItem.setPos(originX, originY)

        # 若读取更换新文件，加载XML文件；否则pass
        if clear:
            save_xml_path = os.path.join(os.path.dirname(os.path.dirname(path)),
                                         os.path.basename(os.path.dirname(path)) + "-XML")
            xml_name, suffix = os.path.splitext(os.path.basename(path))
            path_xml = os.path.join(save_xml_path, xml_name + ".xml")
            xml_file_path = str(path_xml)
            if os.path.exists(path_xml):
                label, xmin, ymin, xmax, ymax, comment_pose = FromXML.analysis_xml(path=path_xml)
                print(label, xmin, ymin, xmax, ymax)
                for index, label in enumerate(label):
                    x1 = self.pixmapItem.pos().x() + float(xmin[index]) * self.ratio
                    y1 = self.pixmapItem.pos().y() + float(ymin[index]) * self.ratio
                    x2 = self.pixmapItem.pos().x() + float(xmax[index]) * self.ratio
                    y2 = self.pixmapItem.pos().y() + float(ymax[index]) * self.ratio
                    self.current_rect = CustomRectItem(QRectF(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2)), self,
                                                       label=label, comment=comment_pose[index])
                    self.scene.addItem(self.current_rect)

                    self.current_rect.label = label
                    self.current_rect.comment = comment_pose[index]
                    self.current_rect.radio_start = self.ratio
                    self.rect_items.append(self.current_rect)
                    self.update_rect_items(True)
                    self.current_rect = None
        else:
            pass

    def scene_MousePressEvent(self, event):
        # if event.modifiers() & QtCore.Qt.ControlModifier and event.buttons() & QtCore.Qt.LeftButton:
        if event.buttons() & QtCore.Qt.LeftButton:
            self.preMousePosition = event.scenePos()  # 获取鼠标当前位置

        # if event.button() == Qt.LeftButton and not event.modifiers() & Qt.ControlModifier:
        if event.button() == Qt.RightButton:
            item = self.graphicsView.itemAt(event.scenePos().toPoint())
            # 如果鼠标右键在标注框上
            if isinstance(item, CustomRectItem):
                cursor_shape = item.get_cursor_shape(event.scenePos())
                if cursor_shape in [Qt.SizeHorCursor, Qt.SizeVerCursor]:
                    self.resizing = True
                    self.resizing_rect = item
                    self.start_pos = event.scenePos()
                    self.orig_rect = item.rect()
                    return
                self.preMousePosition = event.scenePos()
                self.moving = True
                self.resizing_rect = item
                return
            else:
                self.start_pos = event.scenePos()
                # 正在绘制方框
                self.drawing = True
                self.current_rect = CustomRectItem(QRectF(self.start_pos, self.start_pos), self)
                self.scene.addItem(self.current_rect)

    def scene_mouseReleaseEvent(self, event):
        # if event.button() == Qt.LeftButton:
        if event.button() == Qt.RightButton:
            if self.drawing:
                # 如果鼠标释放位置与点击位置相同，那么不添加方框，直接返回
                if self.start_pos == event.scenePos():
                    self.drawing = False
                    self.scene.removeItem(self.current_rect)
                    self.current_rect = None
                    return
                self.drawing = False
                self.label_and_comment_dialog()
                self.current_rect = None

            if self.moving:
                self.moving = False

            if self.resizing:
                self.resizing = False
                self.resizing_rect = None

        # super(QtWidgets.QGraphicsScene, self).mouseReleaseEvent(event)

    def scene_mouseMoveEvent(self, event):
        if self.resizing and self.resizing_rect:
            current_pos = event.scenePos()
            delta = current_pos - self.start_pos
            new_rect = self.resizing_rect.rect().adjusted(0, 0, delta.x(), delta.y())
            self.resizing_rect.setRect(new_rect)
            self.start_pos = current_pos
            self.resizing_rect.update_info(False)
            return

        item = self.graphicsView.itemAt(event.scenePos().toPoint())
        if isinstance(item, CustomRectItem):
            if self.moving:
                if Qt.LeftButton and not event.modifiers() & Qt.ControlModifier and self.moving:
                    item.setPos(item.pos() + event.scenePos() - self.preMousePosition)
                    item.update_info(False)
                    self.preMousePosition = event.scenePos()

            self.graphicsView.setCursor(item.get_cursor_shape(event.scenePos()))
        else:
            self.graphicsView.setCursor(Qt.ArrowCursor)

        # if Qt.LeftButton and not event.modifiers() & Qt.ControlModifier:
        if Qt.RightButton:
            if self.drawing and self.current_rect:
                current_pos = event.scenePos()
                rect = QRectF(self.start_pos, current_pos).normalized()
                self.current_rect.setRect(rect)

        # if event.modifiers() & QtCore.Qt.ControlModifier and event.buttons() & QtCore.Qt.LeftButton:
        if event.buttons() & QtCore.Qt.LeftButton:
            # print("左键移动")  # 响应测试语句
            self.MouseMove = event.scenePos() - self.preMousePosition  # 鼠标当前位置-先前位置=单次偏移量
            self.preMousePosition = event.scenePos()  # 更新当前鼠标在窗口上的位置，下次移动用
            self.pixmapItem.setPos(self.pixmapItem.pos() + self.MouseMove)  # 更新图元位置
            for item in self.scene.items():
                if isinstance(item, CustomRectItem):
                    item.setPos(item.pos() + self.MouseMove)

    def scene_wheelEvent(self, event):
        """定义滚轮方法。当鼠标在图元范围之外，以图元中心为缩放原点；当鼠标在图元之中，以鼠标悬停位置为缩放中心"""
        angle = event.delta() / 8  # 返回QPoint对象，为滚轮转过的数值，单位为1/8度
        if angle > 0:
            # print("滚轮上滚")
            self.ratio += self.zoom_step  # 缩放比例自加
            if self.ratio > self.zoom_max:
                self.ratio = self.zoom_max
            else:
                w = self.pixmap.size().width() * (self.ratio - self.zoom_step)
                h = self.pixmap.size().height() * (self.ratio - self.zoom_step)
                x1 = self.pixmapItem.pos().x()  # 图元左位置
                x2 = self.pixmapItem.pos().x() + w  # 图元右位置
                y1 = self.pixmapItem.pos().y()  # 图元上位置
                y2 = self.pixmapItem.pos().y() + h  # 图元下位置
                if event.scenePos().x() > x1 and event.scenePos().x() < x2 \
                        and event.scenePos().y() > y1 and event.scenePos().y() < y2:  # 判断鼠标悬停位置是否在图元中
                    # print('在内部')
                    self.pixmapItem.setScale(self.ratio)  # 缩放
                    a1 = event.scenePos() - self.pixmapItem.pos()  # 鼠标与图元左上角的差值
                    a2 = self.ratio / (self.ratio - self.zoom_step) - 1  # 对应比例
                    delta = a1 * a2
                    for item in self.scene.items():
                        if isinstance(item, CustomRectItem):
                            bounding_item = item.boundingRect()
                            item.setTransformOriginPoint(bounding_item.topLeft())
                            item.setScale(self.ratio / item.radio_start)  # 缩放
                            item.setPos(item.pos() - delta + self.pixmapItem.mapFromScene(
                                item.mapToScene(item.rect().topLeft())) * self.ratio * (
                                                self.zoom_step / (self.ratio - self.zoom_step)))
                            # item.setPos(item.pos() - delta)
                            # pos_x = item.pos().x()
                            # pos_y = item.pos().y()
                            # pos_real_x = item.rect().x()
                            # pos_real_y = item.rect().y()
                            # top_left = item.rect().topLeft()
                            # top_left_img = self.pixmapItem.mapFromScene(item.mapToScene(top_left))
                            # new_pos_x = top_left_img.x() * self.ratio + self.pixmapItem.pos().x() - pos_real_x + pos_x
                            # new_pos_y = top_left_img.y() * self.ratio + self.pixmapItem.pos().y() - pos_real_y + pos_y
                            # item.setPos(new_pos_x, new_pos_y)
                            # print(f"(new_pos_x, new_pos_y) = ({new_pos_x, new_pos_y})")
                            print("_________________________________________")
                            print(f"bounding_item.topLeft():{bounding_item.topLeft()}")
                            print(f"self.radio:{self.ratio}")
                            print(f"图片坐标：{self.pixmapItem.pos()}")
                            print(
                                f"右下坐标：（{self.pixmapItem.pos().x() + 3008 * self.ratio}, {self.pixmapItem.pos().y() + 2512 * self.ratio} ")
                            print(f"方框坐标pos：{item.pos()}")
                            print(f"方框坐标pos_2：{item.mapToScene(item.pos())}")
                            print(f"方框rect_1:{item.rect()}")
                            print(f"方框rect_2:{item.mapToScene(item.rect())}")
                            print(
                                f"相对pixmapItem坐标：{self.pixmapItem.mapFromScene(item.mapToScene(item.rect().topLeft()))}")
                            print(
                                f"新的缩放位置{self.pixmapItem.mapToScene(self.pixmapItem.mapFromScene(item.mapToScene(item.rect().topLeft())))}")
                            print("_________________________________________\n\n")

                            # # 获取矩形的左上角和右下角点相对于场景的坐标
                            # top_left_scene = item.mapToScene(item.rect().topLeft())
                            # bottom_right_scene = item.mapToScene(item.rect().bottomRight())
                            #
                            # # 将场景坐标转换为 pixmapItem 的坐标
                            # top_left_img = self.pixmapItem.mapFromScene(top_left_scene)
                            # bottom_right_img = self.pixmapItem.mapFromScene(bottom_right_scene)
                            #
                            # # 计算新的缩放后的位置
                            # new_top_left = self.pixmapItem.mapToScene(top_left_img)
                            # new_bottom_right = self.pixmapItem.mapToScene(bottom_right_img)
                            #
                            # # 计算新的矩形区域并设置 CustomRectItem 的位置
                            # new_rect = QRectF(new_top_left, new_bottom_right)
                            # item.setRect(new_rect)
                            # item.setPos(new_top_left)
                    # ----------------------------分维度计算偏移量-----------------------------
                    # delta_x = a1.x()*a2
                    # delta_y = a1.y()*a2
                    # self.pixmapItem.setPos(self.pixmapItem.pos().x() - delta_x,
                    #                        self.pixmapItem.pos().y() - delta_y)  # 图元偏移
                    # -------------------------------------------------------------------------
                    self.pixmapItem.setPos(self.pixmapItem.pos() - delta)

                else:
                    # print('在外部')  # 以图元中心缩放
                    self.pixmapItem.setScale(self.ratio)  # 缩放
                    delta_x = (self.pixmap.size().width() * self.zoom_step) / 2  # 图元偏移量
                    delta_y = (self.pixmap.size().height() * self.zoom_step) / 2

                    for item in self.scene.items():
                        if isinstance(item, CustomRectItem):
                            bounding_item = item.boundingRect()
                            item.setTransformOriginPoint(bounding_item.topLeft())
                            item.setScale(self.ratio / item.radio_start)  # 缩放
                            item.setPos(item.pos().x() - delta_x + self.pixmapItem.mapFromScene(
                                item.mapToScene(item.rect().topLeft())).x() * self.ratio * (
                                                self.zoom_step / (self.ratio - self.zoom_step)),
                                        item.pos().y() - delta_y + self.pixmapItem.mapFromScene(
                                            item.mapToScene(item.rect().topLeft())).y() * self.ratio * (
                                                self.zoom_step / (self.ratio - self.zoom_step)))

                            # pos_x = item.pos().x()
                            # pos_y = item.pos().y()
                            # pos_real_x = item.rect().x()
                            # pos_real_y = item.rect().y()
                            # top_left = item.rect().topLeft()
                            # top_left_img = self.pixmapItem.mapFromScene(item.mapToScene(top_left))
                            # new_pos_x = top_left_img.x() * self.ratio + self.pixmapItem.pos().x() - pos_real_x + pos_x
                            # new_pos_y = top_left_img.y() * self.ratio + self.pixmapItem.pos().y() - pos_real_y + pos_y
                            # item.setPos(new_pos_x, new_pos_y)
                            # print(f"(new_pos_x, new_pos_y) = ({new_pos_x, new_pos_y})")

                            print(f"bounding_item.topLeft():{bounding_item.topLeft()}")
                            print(f"self.radio:{self.ratio}")
                            print(f"图片坐标：{self.pixmapItem.pos()}")
                            print(
                                f"右下坐标：（{self.pixmapItem.pos().x() + 3008 * self.ratio}, {self.pixmapItem.pos().y() + 2512 * self.ratio} ")
                            print(f"方框坐标pos：{item.pos()}")
                            print(f"方框坐标pos_2：{item.mapToScene(item.pos())}")
                            print(f"方框rect_1:{item.rect()}")
                            print(f"方框rect_2:{item.mapToScene(item.rect())}")
                            print(
                                f"相对pixmapItem坐标：{self.pixmapItem.mapFromScene(item.mapToScene(item.rect().topLeft()))}")
                            print(
                                f"新的缩放位置{self.pixmapItem.mapToScene(self.pixmapItem.mapFromScene(item.mapToScene(item.rect().topLeft())))}")
                            print("_________________________________________\n\n")
                    self.pixmapItem.setPos(self.pixmapItem.pos().x() - delta_x,
                                           self.pixmapItem.pos().y() - delta_y)  # 图元偏移

        else:
            # print("滚轮下滚")
            self.ratio -= self.zoom_step
            if self.ratio < self.zoom_min:
                self.ratio = self.zoom_min
            else:
                w = self.pixmap.size().width() * (self.ratio + self.zoom_step)
                h = self.pixmap.size().height() * (self.ratio + self.zoom_step)
                x1 = self.pixmapItem.pos().x()
                x2 = self.pixmapItem.pos().x() + w
                y1 = self.pixmapItem.pos().y()
                y2 = self.pixmapItem.pos().y() + h
                # print(x1, x2, y1, y2)
                if event.scenePos().x() > x1 and event.scenePos().x() < x2 \
                        and event.scenePos().y() > y1 and event.scenePos().y() < y2:
                    # print('在内部')
                    self.pixmapItem.setScale(self.ratio)  # 缩放
                    a1 = event.scenePos() - self.pixmapItem.pos()  # 鼠标与图元左上角的差值
                    a2 = self.ratio / (self.ratio + self.zoom_step) - 1  # 对应比例
                    delta = a1 * a2
                    for item in self.scene.items():
                        if isinstance(item, CustomRectItem):
                            bounding_item = item.boundingRect()
                            item.setTransformOriginPoint(bounding_item.topLeft())
                            item.setScale(self.ratio / item.radio_start)  # 缩放
                            item.setPos(item.pos() - delta - self.pixmapItem.mapFromScene(
                                item.mapToScene(item.rect().topLeft())) * self.ratio * (
                                                self.zoom_step / (self.ratio + self.zoom_step)))

                            # pos_x = item.pos().x()
                            # pos_y = item.pos().y()
                            # pos_real_x = item.rect().x()
                            # pos_real_y = item.rect().y()
                            # top_left = item.rect().topLeft()
                            # top_left_img = self.pixmapItem.mapFromScene(item.mapToScene(top_left))
                            # new_pos_x = top_left_img.x() * self.ratio + self.pixmapItem.pos().x() - pos_real_x + pos_x
                            # new_pos_y = top_left_img.y() * self.ratio + self.pixmapItem.pos().y() - pos_real_y + pos_y
                            # item.setPos(new_pos_x, new_pos_y)
                            # print(f"(new_pos_x, new_pos_y) = ({new_pos_x, new_pos_y})")

                            print("_________________________________________")
                            print(f"bounding_item.topLeft():{bounding_item.topLeft()}")
                            print(f"self.radio:{self.ratio}")
                            print(f"图片坐标：{self.pixmapItem.pos()}")
                            print(
                                f"右下坐标：（{self.pixmapItem.pos().x() + 3008 * self.ratio}, {self.pixmapItem.pos().y() + 2512 * self.ratio} ")

                            print(f"方框坐标pos：{item.pos()}")
                            print(f"方框坐标pos_2：{item.mapToScene(item.pos())}")
                            print(f"方框rect_1:{item.rect()}")
                            print(f"方框rect_2:{item.mapToScene(item.rect())}")
                            print(
                                f"相对pixmapItem坐标：{self.pixmapItem.mapFromScene(item.mapToScene(item.rect().topLeft()))}")
                            print(
                                f"新的缩放位置{self.pixmapItem.mapToScene(self.pixmapItem.mapFromScene(item.mapToScene(item.rect().topLeft())))}")
                            print("_________________________________________\n\n")
                    # ----------------------------分维度计算偏移量-----------------------------
                    # delta_x = a1.x()*a2
                    # delta_y = a1.y()*a2
                    # self.pixmapItem.setPos(self.pixmapItem.pos().x() - delta_x,
                    #                        self.pixmapItem.pos().y() - delta_y)  # 图元偏移
                    # -------------------------------------------------------------------------
                    self.pixmapItem.setPos(self.pixmapItem.pos() - delta)
                else:
                    # print('在外部')
                    self.pixmapItem.setScale(self.ratio)
                    delta_x = (self.pixmap.size().width() * self.zoom_step) / 2
                    delta_y = (self.pixmap.size().height() * self.zoom_step) / 2
                    for item in self.scene.items():
                        if isinstance(item, CustomRectItem):
                            bounding_item = item.boundingRect()
                            item.setTransformOriginPoint(bounding_item.topLeft())
                            item.setScale(self.ratio / item.radio_start)  # 缩放

                            item.setPos(item.pos().x() + delta_x - self.pixmapItem.mapFromScene(
                                item.mapToScene(item.rect().topLeft())).x() * self.ratio * (
                                                self.zoom_step / (self.ratio + self.zoom_step)),
                                        item.pos().y() + delta_y - self.pixmapItem.mapFromScene(
                                            item.mapToScene(item.rect().topLeft())).y() * self.ratio * (
                                                self.zoom_step / (self.ratio + self.zoom_step)))

                            # pos_x = item.pos().x()
                            # pos_y = item.pos().y()
                            # pos_real_x = item.rect().x()
                            # pos_real_y = item.rect().y()
                            # top_left = item.rect().topLeft()
                            # top_left_img = self.pixmapItem.mapFromScene(item.mapToScene(top_left))
                            # new_pos_x = top_left_img.x() * self.ratio + self.pixmapItem.pos().x() - pos_real_x + pos_x
                            # new_pos_y = top_left_img.y() * self.ratio + self.pixmapItem.pos().y() - pos_real_y + pos_y
                            # item.setPos(new_pos_x, new_pos_y)
                            # print(f"(new_pos_x, new_pos_y) = ({new_pos_x, new_pos_y})")

                            print("_________________________________________")
                            print(f"bounding_item.topLeft():{bounding_item.topLeft()}")
                            print(f"self.radio:{self.ratio}")
                            print(f"图片坐标：{self.pixmapItem.pos()}")
                            print(
                                f"右下坐标：（{self.pixmapItem.pos().x() + 3008 * self.ratio}, {self.pixmapItem.pos().y() + 2512 * self.ratio} ")

                            print(f"方框坐标pos：{item.pos()}")
                            print(f"方框坐标pos_2：{item.mapToScene(item.pos())}")
                            print(f"方框rect_1:{item.rect()}")
                            print(f"方框rect_2:{item.mapToScene(item.rect())}")
                            print(
                                f"相对pixmapItem坐标：{self.pixmapItem.mapFromScene(item.mapToScene(item.rect().topLeft()))}")
                            print(
                                f"新的缩放位置{self.pixmapItem.mapToScene(self.pixmapItem.mapFromScene(item.mapToScene(item.rect().topLeft())))}")
                            print("_________________________________________\n\n")
                    # for item in self.scene.items():
                    #     if isinstance(item, CustomRectItem):
                    #         item.setScale(self.ratio)
                    self.pixmapItem.setPos(self.pixmapItem.pos().x() + delta_x, self.pixmapItem.pos().y() + delta_y)

    def label_and_comment_dialog(self):
        dialog = LabelDialog()
        if dialog.exec_() == QDialog.Accepted:
            label, comment = dialog.get_values()
            self.current_rect.label = label
            self.current_rect.comment = comment
            self.current_rect.radio_start = self.ratio
            self.rect_items.append(self.current_rect)
            self.update_rect_items(True)
            print("添加标注框成功！")

    def update_rect_items(self, isUpdateLabel):
        """更新方框信息，包括标签信息和位置信息"""
        # 如果要更新标签信息，先把方框listWidget全部清空
        if isUpdateLabel:
            print("更新标签信息！")
            self.listWidget.clear()

        # 再遍历对rect_items列表，添加到方框listWidget中
        for item in self.rect_items:
            # 获取矩形的左上角和右下角点相对于场景的坐标
            top_left = item.rect().topLeft()
            bottom_right = item.rect().bottomRight()
            # 将场景坐标转换为pixmapItem的坐标
            self.pixmapItem.mapFromScene(item.mapToScene(top_left))
            self.pixmapItem.mapFromScene(item.mapToScene(bottom_right))
            # 如果更新标签信息
            if isUpdateLabel:
                listWidgetItem = QListWidgetItem(f"Label: {item.label}, Comment: {item.comment}")
                listWidgetItem.setFlags(listWidgetItem.flags() | Qt.ItemIsEditable)
                self.listWidget.addItem(listWidgetItem)

    def on_list_selection_changed(self):
        if self.updating_selection:
            return
        selected_items = self.listWidget.selectedItems()
        for i, rect_item in enumerate(self.rect_items):
            if selected_items and self.listWidget.row(selected_items[0]) == i:
                rect_item.setSelected(True)
                # rect_item.setPen(QtGui.QPen(QtGui.QColor(255, 0, 0)))  # Highlight color
            else:
                rect_item.setSelected(False)
                # rect_item.setPen(QtGui.QPen(QtGui.QColor(255, 0, 0)))  # Default color

    def on_item_changed(self, item):
        index = self.listWidget.row(item)
        rect_item = self.rect_items[index]
        text = item.text()
        if ", Comment: " in text:
            label, comment = text.split(", Comment: ")
            label = label.replace("Label: ", "")
            rect_item.update_info_label(label, comment)
        else:
            rect_item.update_info_label(text, "")  # handle case if no comment is provided

    def on_rect_selection_changed(self):
        self.updating_selection = True
        selected_rects = [item for item in self.rect_items if item.isSelected()]
        if selected_rects:
            selected_rect = selected_rects[0]
            index = self.rect_items.index(selected_rect)
            self.listWidget.setCurrentRow(index)
        else:
            self.listWidget.clearSelection()
        self.updating_selection = False

    def get_scene_items(self):
        return self.scene.items()

    def get_rect_items(self):
        return self.rect_items

    def get_pixmapItem(self):
        return self.pixmapItem

    # def save_xml(self):
    #     items = self.get_scene_items()
    #     rect_items = self.get_rect_items()
    #     pixmapItem = self.get_pixmapItem()
    #     ToXML5D0.CreatSaveXml.creat_xml(self.filePath, items, rect_items, self.img)


class CustomRectItem(QGraphicsRectItem):
    default_pen_width = 3
    default_pen_color = QColor(Qt.red)
    default_brush_color = QColor(Qt.transparent)

    def __init__(self, rect: QRectF, img_win: IMG_WIN, label='', comment='', radio_start=1):
        super().__init__(rect)
        self.width_height_info = None
        self._width_height_info = None  # 私有变量存储实际数据，变化时自动更新方框颜色
        self.pen_width = CustomRectItem.default_pen_width
        self.brush_color = CustomRectItem.default_brush_color
        self.pen_color = QColor(Qt.red)
        self.img_win = img_win
        self.pixmapItem = self.img_win.get_pixmapItem()
        self.label = label
        self.comment = comment
        self._comment = comment  # 私有变量存储实际数据，comment变化时自动更新方框颜色
        self.radio_start = radio_start
        self.set_width_height()
        self.setFlags(QGraphicsRectItem.ItemIsSelectable |
                      QGraphicsRectItem.ItemIsMovable |
                      QGraphicsRectItem.ItemIsFocusable |
                      QGraphicsRectItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.set_pen_color_from_comment()   # 根据 comment 设置笔的颜色

        self.pen = QPen(self.pen_color, self.pen_width)
        self.brush = QBrush(self.brush_color)

        self.setPen(self.pen)
        self.setBrush(self.brush)

        self.resize_anchor = None
        self.orig_rect = rect
        self.orig_pos = QPointF(0, 0)

        # 启用实时几何变化通知
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        # 调用一个线程持续监听self.comment的值，如果改变自动触发set_pen_color_from_comment方法

    def set_width_height(self):
        """计算并设置width_height_info"""
        if not self.scene() or not self.pixmapItem:
            return
        x_min = int(self.pixmapItem.mapFromScene(
            self.mapToScene(self.rect().topLeft())).x())
        y_min = int(self.pixmapItem.mapFromScene(
            self.mapToScene(self.rect().topLeft())).y())
        x_max = int(self.pixmapItem.mapFromScene(
            self.mapToScene(self.rect().bottomRight())).x())
        y_max = int(self.pixmapItem.mapFromScene(
            self.mapToScene(self.rect().bottomRight())).y())
        # 直接操作内部变量，避免调用setter
        self._width_height_info = [x_min, y_min, x_max, y_max]
        self.update()  # 手动触发重绘


    @property
    def comment(self):
        return self._comment

    @property
    def width_height_info(self):
        """获取最新的宽高信息"""
        if self.scene() and self.pixmapItem:
            self.set_width_height()
        return self._width_height_info
    @comment.setter
    def comment(self, value):
        """当comment被修改时自动调用该方法更新颜色"""
        self._comment = value
        self.set_pen_color_from_comment()

    @width_height_info.setter
    def width_height_info(self, value):
        """当width_height_info被修改时自动触发set_width_height方法"""
        self._width_height_info = value

    def set_pen_color_from_comment(self):
        """根据comment_pose设置方框的颜色"""
        if self._comment == '自动检测':
            self.default_pen_color = QColor(Qt.blue)
            self.pen_color = QColor(Qt.blue)  # 自动检测设置为蓝色
        else:
            self.default_pen_color = QColor(Qt.red)
            self.pen_color = QColor(Qt.red)  # 其他情况设置为红色

        # 更新笔设置
        self.pen = QPen(self.pen_color, self.pen_width)
        self.setPen(self.pen)
        # 强制更新视图
        if self.scene():
            self.scene().update()

    def paint(self, painter, option, widget):
        """重写paint方法，添加缺陷标签label，和缺陷位置信息"""
        super().paint(painter, option, widget)
        painter.setPen(self.default_pen_color)
        font = painter.font()
        font.setFamily("Microsoft YaHei")
        font.setPointSize(12)
        painter.setFont(font)
        # 构建要显示的文本
        display_text = self.label

        # 如果存在pos_info信息，计算并添加尺寸信息
        if self.width_height_info and len(self.width_height_info) >= 4:
            x1, y1, x2, y2 = self.width_height_info[0:4]
            width = abs(x2 - x1)
            height = abs(y2 - y1)
            display_text += f" (w, h)=({width},{height})"

        # 绘制文本，位置在框的左上角上方
        text_position = self.rect().topLeft() + QPointF(0, -7)  # 调整位置偏移
        painter.drawText(text_position, display_text)

    def hoverMoveEvent(self, event):
        cursor = self.get_cursor_shape(event.pos())
        self.setCursor(cursor)

    def get_cursor_shape(self, pos):
        # 转换坐标到局部坐标系
        local_pos = self.mapFromScene(pos)
        rect = self.rect()
        margin = 5  # 边界的宽度，可以根据需要调整

        # 检查是否在边线上
        # if abs(local_pos.x() - rect.left()) <= margin or abs(local_pos.x() - rect.right()) <= margin:
        if abs(local_pos.x() - rect.right()) <= margin:
            return Qt.SizeHorCursor
        elif abs(local_pos.y() - rect.bottom()) <= margin:
            return Qt.SizeVerCursor

        # 检查是否在内部
        if rect.contains(local_pos):
            return Qt.SizeAllCursor

        return Qt.ArrowCursor

    def contextMenuEvent(self, event):
        """右键菜单栏"""
        menu = QMenu()

        change_color_action = menu.addAction("Change Color")
        change_color_action.triggered.connect(lambda: self.change_color())

        change_width_action = menu.addAction("Change Line Width")
        change_width_action.triggered.connect(lambda: self.change_line_width())

        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(lambda: self.delete_item())

        change_to_manual = menu.addAction("修改为人工标注")
        change_to_manual.triggered.connect(lambda: self.change_to_manual())

        change_to_auto = menu.addAction("修改为机器标注")
        change_to_auto.triggered.connect(lambda: self.change_to_auto())

        # 定义一个二级菜单，里面读取项目根目录./Sources/label_info.txt下的每一行作为一个选项，选中该选项则修改当前的方框的label为该值
        label_menu = menu.addMenu("修改标签")
        # 尝试读取标签信息文件
        try:
            with open("./Sources/label_info.txt", "r", encoding="utf-8") as file:
                labels = file.read().splitlines()

            # 只添加非空行
            for label in labels:
                if label.strip():
                    label_action = label_menu.addAction(label)
                    # 使用 lambda 函数，并通过 default 参数传递当前循环的 label 值
                    label_action.triggered.connect(lambda checked=False, lbl=label: self.change_label(lbl))
        except Exception as e:
            # 其他异常处理
            error_action = label_menu.addAction(f"读取文件错误: {str(e)}")
            error_action.setEnabled(False)

        # 显示菜单
        menu.exec_(event.screenPos())

    def change_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.update_style(pen_color=color)
            CustomRectItem.default_pen_color = color

    def change_line_width(self):
        # 创建一个临时的 QWidget 用于显示对话框
        temp_widget = QWidget()
        temp_widget.setWindowModality(Qt.ApplicationModal)
        temp_widget.hide()  # 隐藏窗口，因为我们只关心对话框

        # 获取新的线宽
        width, ok = QInputDialog.getInt(temp_widget, "Line Width", "Enter new line width:", self.pen_width, 1, 10)
        if ok:
            self.update_style(pen_width=width)
            CustomRectItem.default_pen_width = width

        temp_widget.deleteLater()  # 清理临时窗口

    def update_style(self, pen_width=None, pen_color=None, brush_color=None):
        if pen_width is not None:
            self.pen_width = pen_width
        if pen_color is not None:
            self.pen_color = pen_color
        if brush_color is not None:
            self.brush_color = brush_color

        self.setPen(QPen(self.pen_color, self.pen_width))
        self.setBrush(QBrush(self.brush_color))

    def delete_item(self):
        scene = self.scene()
        if scene is not None:
            scene.removeItem(self)
            # 删除listWidget_label中对应的项
            if self in self.img_win.rect_items:
                self.img_win.rect_items.remove(self)
                self.img_win.update_rect_items(True)

    def change_to_manual(self):
        self.comment = "None"
        # 修改 listWidget_label中对应的项
        if self in self.img_win.rect_items:
            self.img_win.update_rect_items(True)

    def change_to_auto(self):
        self.comment = "自动检测"
        if self in self.img_win.rect_items:
            self.img_win.update_rect_items(True)

    def change_label(self, new_label):
        """修改方框的标签"""
        self.label = new_label
        # 更新列表显示
        if self in self.img_win.rect_items:
            self.img_win.update_rect_items(True)
        # 强制场景更新以显示新标签
        if self.scene():
            self.scene().update()

    # 如果方框item的变化属于位置变化，那么更新方框信息
    def itemChange(self, change, value):
        # 实时响应位置/变换变化
        if change in (QGraphicsItem.ItemPositionChange,  # 位置即将改变
                      QGraphicsItem.ItemTransformChange,  # 变换即将改变
                      QGraphicsItem.ItemPositionHasChanged,  # 位置已改变（确保全覆盖）
                      QGraphicsItem.ItemTransformHasChanged):  # 变换已改变
            self.set_width_height()  # 更新宽高信息
            self.update_info(True)  # 传递实时更新标志
            self.scene().update()  # 强制场景立即更新
        return super().itemChange(change, value)

    # 更新方框信息
    def update_info(self, isUpdateLabel: bool):
        # self.scene().parent().update_rect_items(isUpdateLabel)
        self.img_win.update_rect_items(isUpdateLabel)

    def update_info_label(self, label, comment):
        self.label = label
        self.comment = comment
