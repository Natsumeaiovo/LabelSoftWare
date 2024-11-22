# -*- coding: utf-8 -*-

"""
Time : 2024/7/25 下午2:47
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : MainRead.py
Lab: Information Group of InteCast Software Center
Function of the program: 
"""

from PySide2.QtWidgets import QApplication, QWidget, QFileDialog
from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import Qt
from PySide2 import QtWidgets
from PySide2 import QtCore
from PySide2 import QtGui
import cv2
import pydicom
import numpy as np
import os

class IMG_WIN(QWidget):
    def __init__(self,graphicsView):
        super().__init__()
        self.graphicsView=graphicsView

        self.graphicsView.setStyleSheet("padding: 0px; border: 0px;")  # 内边距和边界去除
        self.scene = QtWidgets.QGraphicsScene(self)
        self.graphicsView.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)  # 改变对齐方式

        self.graphicsView.setSceneRect(0, 0, self.graphicsView.viewport().width(),
                                          self.graphicsView.height())  # 设置图形场景大小和图形视图大小一致
        self.graphicsView.setScene(self.scene)

        self.scene.mousePressEvent = self.scene_MousePressEvent  # 接管图形场景的鼠标事件
        # self.scene.mouseReleaseEvent = self.scene_mouseReleaseEvent
        self.scene.mouseMoveEvent = self.scene_mouseMoveEvent
        self.scene.wheelEvent = self.scene_wheelEvent

        self.ratio = 1  # 缩放初始比例
        self.zoom_step = 0.1  # 缩放步长
        self.zoom_max = 100  # 缩放最大值
        self.zoom_min = 0.0002  # 缩放最小值
        self.pixmapItem=None

    def addScenes(self, img):  # 绘制图形
        self.org = img
        if self.pixmapItem is not None:
            originX = self.pixmapItem.x()
            originY = self.pixmapItem.y()
        else:
            originX, originY = 0, 0  # 坐标基点

        self.scene.clear()

        # 创建QPixmap
        if img.dtype == np.uint16:  # 假设像素数组为16位
            qimg = QtGui.QImage(img.data, img.shape[1], img.shape[0], img.strides[0], QtGui.QImage.Format_Grayscale16)
        else:  # 假设像素数组为8位
            qimg = QtGui.QImage(img.data, img.shape[1], img.shape[0], img.strides[0], QtGui.QImage.Format_Grayscale8)

        self.pixmap = QtGui.QPixmap.fromImage(qimg)

        self.pixmapItem = self.scene.addPixmap(self.pixmap)
        self.pixmapItem.setScale(self.ratio)
        self.pixmapItem.setTransformationMode(QtCore.Qt.SmoothTransformation)
        self.pixmapItem.setPos(originX, originY)


    # def scene_mouseReleaseEvent(self, event):
    #     if event.button() == QtCore.Qt.LeftButton:  # 左键释放
    #         print("鼠标左键释放")  # 响应测试语句
    #     if event.button() == QtCore.Qt.RightButton:  # 右键释放
    #         print("鼠标右键释放")  # 响应测试语句


    def scene_MousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:  # 左键按下
            # print("鼠标左键单击")  # 响应测试语句
            # print(event.scenePos())
            self.preMousePosition = event.scenePos()  # 获取鼠标当前位置
        # if event.button() == QtCore.Qt.RightButton:  # 右键按下
        #     print("鼠标右键单击")  # 响应测试语句

    def scene_mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton:
            # print("左键移动")  # 响应测试语句
            self.MouseMove = event.scenePos() - self.preMousePosition  # 鼠标当前位置-先前位置=单次偏移量
            self.preMousePosition = event.scenePos()  # 更新当前鼠标在窗口上的位置，下次移动用
            self.pixmapItem.setPos(self.pixmapItem.pos() + self.MouseMove)  # 更新图元位置

    # 定义滚轮方法。当鼠标在图元范围之外，以图元中心为缩放原点；当鼠标在图元之中，以鼠标悬停位置为缩放中心
    def scene_wheelEvent(self, event):
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
                    a2=self.ratio/(self.ratio- self.zoom_step)-1    # 对应比例
                    delta = a1 * a2
                    self.pixmapItem.setPos(self.pixmapItem.pos() - delta)
                    # ----------------------------分维度计算偏移量-----------------------------
                    # delta_x = a1.x()*a2
                    # delta_y = a1.y()*a2
                    # self.pixmapItem.setPos(self.pixmapItem.pos().x() - delta_x,
                    #                        self.pixmapItem.pos().y() - delta_y)  # 图元偏移
                    # -------------------------------------------------------------------------

                else:
                    # print('在外部')  # 以图元中心缩放
                    self.pixmapItem.setScale(self.ratio)  # 缩放
                    delta_x = (self.pixmap.size().width() * self.zoom_step) / 2  # 图元偏移量
                    delta_y = (self.pixmap.size().height() * self.zoom_step) / 2
                    self.pixmapItem.setPos(self.pixmapItem.pos().x() - delta_x,
                                           self.pixmapItem.pos().y() - delta_y)  # 图元偏移
        else:
            # print("滚轮下滚")
            self.ratio -= self.zoom_step
            if self.ratio < 0.2:
                self.ratio = 0.2
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
                    a2=self.ratio/(self.ratio+ self.zoom_step)-1    # 对应比例
                    delta = a1 * a2
                    self.pixmapItem.setPos(self.pixmapItem.pos() - delta)
                    # ----------------------------分维度计算偏移量-----------------------------
                    # delta_x = a1.x()*a2
                    # delta_y = a1.y()*a2
                    # self.pixmapItem.setPos(self.pixmapItem.pos().x() - delta_x,
                    #                        self.pixmapItem.pos().y() - delta_y)  # 图元偏移
                    # -------------------------------------------------------------------------
                else:
                    # print('在外部')
                    self.pixmapItem.setScale(self.ratio)
                    delta_x = (self.pixmap.size().width() * self.zoom_step) / 2
                    delta_y = (self.pixmap.size().height() * self.zoom_step) / 2
                    self.pixmapItem.setPos(self.pixmapItem.pos().x() + delta_x, self.pixmapItem.pos().y() + delta_y)

class GUI(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = QUiLoader().load('UI/pic.ui')
        self.graphic=IMG_WIN(self.ui.graphicsView)	# 实例化IMG_WIN类
        self.ui.pushButton.clicked.connect(self.select_img)

    def select_img(self):
        filePath, _ = QFileDialog.getOpenFileName(
            self.ui,  # 父窗口对象
            "选择你要上传的图片",  # 标题
            r"E:\picture\test",  # 起始目录
            "图片类型 (*.dcm *.png *.jpg *.bmp)"  # 选择类型过滤项，过滤内容在括号中
        )
        if filePath == '':
            return

        # 获取文件扩展名
        _, file_extension = os.path.splitext(filePath)

        if file_extension.lower() == '.dcm':
            ds = pydicom.dcmread(filePath)
            img = ds.pixel_array
        else:
            img = cv2.imread(filePath)

        # 检查是否需要将图像转换为灰度图
        if len(img.shape) > 2:  # 如果有三个维度，则表示有多通道图像
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        print(img, img.shape)
        self.graphic.addScenes(img)


if __name__ == '__main__':
    app = QApplication([])
    My_ui = GUI()
    My_ui.ui.show()
    app.exec_()

