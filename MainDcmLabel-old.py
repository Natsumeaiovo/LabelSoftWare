# -*- coding: utf-8 -*-

"""
Time : 2024/7/26 上午9:03
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : MainDcmLabel.py
Lab: Information Group of InteCast Software Center
Function of the program:
"""
import matplotlib.pyplot as plt
from PySide2.QtWidgets import QApplication, QWidget, QFileDialog, QGraphicsView
from PySide2.QtCore import Signal, QObject, QThread, QByteArray, QTimer
from PySide2.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QSlider, QLabel, QWidget, QGraphicsScene
from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import Qt
from PySide2 import QtWidgets
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2.QtGui import QIcon
from PIL import Image
import cv2
import pydicom
import numpy as np
import os
import tifffile as tiff
from utils import DrawHist
from utils.QSSLoader import QSSLoader
from utils import SetValue
from utils import ShowDCMName
from utils import ShowImage
from utils import ToXML5D0
from utils import WindowImage
from utils.ShowImage import IMG_WIN
import DcmDealFdi5d5  # 增强dcm文件
from DcmDealFdi5d5 import *
from constants import *

windows = []


# 定义 Worker 类
class Worker(QObject):
    # 定义一个信号，当任务完成时发送 NumPy 数组
    finished = Signal(np.ndarray)

    def __init__(self, img, window_center, window_width):
        super().__init__()
        self.img = img
        self.window_center = window_center
        self.window_width = window_width

    def window_image_worker(self):
        # 执行任务
        result = WindowImage.window_image(self.img, self.window_center, self.window_width)

        # 发送 QByteArray
        self.finished.emit(result)


class GUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.thread = None
        self.worker = None

        self.quick_trans_method = None
        self.dcm_deal = DcmDealFdi5d5()  # 创建 DcmDealFdi5d5 类的实例
        self.ui = QUiLoader().load('UI/pic.ui')
        self.img = None
        self.img_enhance = None
        self.filePath = ""
        self.ongoing = False

        # self.graphics_view_layout = QVBoxLayout(self.ui.graphicsView)
        self.img_win: IMG_WIN = ShowImage.IMG_WIN(self.ui.graphicsView, self.ui.listWidget_label)  # 实例化IMG_WIN类
        # self.graphics_view_layout.addWidget(self.graphic)
        # self.graphics_view_layout.addWidget(self.graphic)

        self.ui.pushButton.clicked.connect(self.select_img)
        self.ui.pushButton_save_xml.clicked.connect(self.save_xml)

        self.value_ww_wc = SetValue.DoubleSlider(self.ui.min_slider, self.ui.max_slider, self.ui.window_width_slider,
                                                 self.ui.window_level_slider, self.ui.min_label, self.ui.max_label,
                                                 self.ui.window_width_label, self.ui.window_level_label,
                                                 self.ui.histogram)
        self.show_dcm_name = ShowDCMName.ImageNameList(self.ui.listWidget_dcm_name)

        # self.setCentralWidget(self.ui)
        # # 将 MyGraphicsView 放入 graphicsView_2 的布局中
        # self.graphics_view_layout = QVBoxLayout(self.ui.graphicsView_2)
        # self.graphics_view = bbbbbbbb.MyGraphicsView(self.ui.graphicsView_2)
        # self.graphics_view_layout.addWidget(self.graphics_view)

        """
        点击图片名 连接并传递一个QListWidgetItem 对象给 show_img 方法作为其参数。
        """
        self.ui.listWidget_dcm_name.itemClicked.connect(lambda item: self.show_img(item))

        # 最小、最大、窗宽、窗位slider 值变化信号 连接到 window_image_main
        self.ui.min_slider.valueChanged.connect(self.window_image_main)
        self.ui.max_slider.valueChanged.connect(self.window_image_main)
        self.ui.window_width_slider.valueChanged.connect(self.window_image_main)
        self.ui.window_level_slider.valueChanged.connect(self.window_image_main)

        # 图像快速处理：无、窗口化、归一化、分区增强、子图窗口化、子图归一化等radio button点击连接到show_img
        self.ui.none_dcm_label.toggled.connect(lambda: self.show_img())
        self.ui.window_dcm_label.toggled.connect(lambda: self.show_img())
        self.ui.normalize_dcm_label.toggled.connect(lambda: self.show_img())
        self.ui.partition_dcm_label.toggled.connect(lambda: self.show_img())
        self.ui.sub_window_dcm_label.toggled.connect(lambda: self.show_img())
        self.ui.sub_normalize_dcm_label.toggled.connect(lambda: self.show_img())

        # self.ui.none_dcm_label.toggled.connect(self.img_quick_trans)
        # self.ui.window_dcm_label.toggled.connect(self.img_quick_trans)
        # self.ui.normalize_dcm_label.toggled.connect(self.img_quick_trans)
        # self.ui.partition_dcm_label.toggled.connect(self.img_quick_trans)
        # self.ui.sub_window_dcm_label.toggled.connect(self.img_quick_trans)
        # self.ui.sub_normalize_dcm_label.toggled.connect(self.img_quick_trans)

        """
        当点击 reverseButton 按钮时，还会传递一个布尔值给 show_img_reverse 方法作为其参数。
        这个布尔值表示按钮的状态（True 表示按钮被选中，False 表示按钮未被选中）。
        如果想仅调用而不传递任何参数，可以使用 lambda 函数来调用该方法。
        """
        # self.ui.reverseButton.toggled.connect(self.show_img_reverse)
        self.ui.reverseButton.toggled.connect(lambda: self.show_img_reverse())

        # 初始化Timer
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.save_xml)
        self.auto_save_timer.timeout.connect(self.save_xml)
        self.ui.autoSaveButton.toggled.connect(self.auto_save_xml)

    def img_quick_trans(self):
        pass

    def select_img(self):
        filePath, _ = QFileDialog.getOpenFileName(
            self.ui,  # 父窗口对象
            "选择你要上传的图片",  # 标题
            # r"D:\测试图像",  # 起始目录
            r"D:\Project\LabelSoftware\image\dcm",
            "图片类型 (*.dcm *.png *.jpg *.bmp *.tif *.tiff)"  # 选择类型过滤项，过滤内容在括号中
        )
        if filePath == '':
            return
        self.filePath = os.path.normpath(filePath)
        self.show_img()

        # 使用 os.path.dirname 获取路径部分
        directory = os.path.dirname(self.filePath)
        # # 使用 os.path.basename 获取文件名部分
        # filename = os.path.basename(self.filePath)

        self.show_dcm_name.open_folder(directory)
        print("dire path: ", directory)

    def show_img(self, item=None):
        # 如果传了item参数(图片)，那么更改filePath为item的地址，并且不变换slider
        if item is not None:
            self.filePath = os.path.join(os.path.dirname(self.filePath), item.text())
        # 获取文件扩展名
        _, file_extension = os.path.splitext(self.filePath)

        if file_extension.lower() == '.dcm':
            ds = pydicom.dcmread(self.filePath)
            read_img = ds.pixel_array
        elif file_extension.lower() in ['.tif', '.tiff']:
            with Image.open(self.filePath) as read_img:
                read_img.seek(1)  # 跳到第二帧
                read_img = np.array(read_img)
        else:
            read_img = cv2.imread(self.filePath)
        # 检查是否需要将图像转换为灰度图
        print("read_img.shape:", len(read_img.shape))
        if len(read_img.shape) > 2:  # 如果有三个维度，则表示有多通道图像
            read_img = cv2.cvtColor(read_img, cv2.COLOR_BGR2GRAY)
        # print(read_img, read_img.shape)
        if read_img.dtype == np.int16 or read_img.dtype == np.uint16:
            max_val = 2 ** 16 - 1
        else:
            max_val = 255
        print("灰度max_val:", max_val)
        # 设置self.img为filePath所在路径
        self.img = read_img
        self.clear = True

        # 如果反色了
        if self.ui.reverseButton.isChecked() is True:
            self.show_img_reverse(isChangeSlider=False)

        # 快速处理算法
        if self.ui.none_dcm_label.isChecked() is True:
            self.img_enhance = None
            self.quick_trans_method = None
            self.window_image_main()
            print("无处理")
        elif self.ui.window_dcm_label.isChecked() is True:
            self.quick_trans_method = WINDOW_IMAGE
            self.img_enhance = self.dcm_deal.window_image(self.img)
            print("窗口化")
        elif self.ui.normalize_dcm_label.isChecked() is True:
            self.quick_trans_method = NORMALIZE
            self.img_enhance = self.dcm_deal.normalize_image(self.img)
            print("归一化")
        elif self.ui.partition_dcm_label.isChecked() is True:
            self.quick_trans_method = PARTITION_WINDOWING
            self.img_enhance = self.dcm_deal.partition_window(self.img)
            print("分区增强")
        elif self.ui.sub_window_dcm_label.isChecked() is True:
            self.quick_trans_method = SUB_WINDOW
            self.img_enhance = self.dcm_deal.sub_window(self.img)
            print("子图窗口化")
        elif self.ui.sub_normalize_dcm_label.isChecked() is True:
            self.quick_trans_method = SUB_NORMALIZE
            self.img_enhance = self.dcm_deal.sub_normalize(self.img)
            print("子图归一化")

        self.img_win.addScenes(self.img_enhance if self.img_enhance is not None else self.img, self.filePath, True)
        # 如果没有反色，那么在这里绘制histogram
        if self.ui.reverseButton.isChecked() is not True:
            DrawHist.plot_histogram(read_img)
            pixmap = QtGui.QPixmap('histogram.png')
            self.ui.histogram.setPixmap(pixmap)

    # 调整图片的窗宽窗位，使用了子线程
    def window_image_main(self):
        print("调整窗宽窗位")
        if self.ongoing:
            return
        self.ongoing = True
        window_level = self.ui.window_level_slider.value()  # 窗位
        window_width = self.ui.window_width_slider.value()  # 窗宽
        print("窗位：", window_level, "窗宽：", window_width)
        if isinstance(self.img, np.ndarray) and self.img.size > 0:
            # 当调整图片窗宽窗位时，会不断创建新的子线程
            self.thread = QThread(self)
            # print("创建一个子线程")
            # 创建 Worker 实例，并传递滑块的值
            self.worker = Worker(self.img, window_level, window_width)
            # 连接 Worker 的 finished 信号到 update_ui 槽
            self.worker.finished.connect(self.update_ui)
            # 连接线程的 started 信号到 Worker 的方法
            self.thread.started.connect(self.worker.window_image_worker)
            # 启动子线程
            self.thread.start()
            self.ongoing = False

    # 更新img_win
    def update_ui(self, array):
        self.img_win.addScenes(array, self.filePath, False)
        # self.ongoing = False

    # 图像正反色处理，修改了img为其反色，重新绘制了灰度直方图，根据参数更新slider的值
    def show_img_reverse(self, isChangeSlider=CHANGE_SLIDER):
        img_to_handle = self.img
        if isinstance(img_to_handle, np.ndarray):
            if img_to_handle.dtype == np.int16 or img_to_handle.dtype == np.uint16:
                max_val = 2 ** 16 - 1
            else:
                max_val = 255

            # 更改self.img为其反色，重新绘制灰度直方图
            self.img = max_val - self.img
            DrawHist.plot_histogram(self.img)
            pixmap = QtGui.QPixmap('histogram.png')
            self.ui.histogram.setPixmap(pixmap)

            # 更新slider的值
            pre_max_slider_value = self.ui.max_slider.value()
            if isChangeSlider == CHANGE_SLIDER:
                self.ui.max_slider.setValue(max_val - self.ui.min_slider.value())
                self.ui.min_slider.setValue(max_val - pre_max_slider_value)

            # 根据是否增强过图片来添加场景
            img_to_handle = max_val - img_to_handle
            if self.quick_trans_method is not None:
                # 如果有图片增强
                self.img_enhance = self.dcm_deal.call_method(self.quick_trans_method, img_to_handle)
                img_to_handle = self.img_enhance
                if pre_max_slider_value == self.ui.max_slider.value():
                    # 如果max_slider没有发生变化（也就是min=0,max=65535时进行反色），那么就没有worker创建，就没有finished信号，需要手动addScenes
                    self.img_win.addScenes(img_to_handle, self.filePath, False)
                else:
                    # 如果max_slider发生变化了，那么创建了worker，等待worker finished信号发送后再addScenes避免覆盖。
                    self.worker.finished.connect(lambda: self.img_win.addScenes(img_to_handle, self.filePath, False))
            else:
                # 没有增强，那么图片应该是根据滑块值变化，设置滑块值即可addScene
                if pre_max_slider_value == self.ui.max_slider.value():
                    self.img_win.addScenes(self.img, self.filePath, False)


    # def show_img_item(self, item):
    #     # 更改filePath
    #     self.filePath = os.path.join(os.path.dirname(self.filePath), item.text())
    #     self.show_img()

    # 保存标注
    def save_xml(self):
        items = self.img_win.get_scene_items()
        # 如果items为空，直接返回
        if not items:
            return
        # print("graphic上所有的items：", items, "items个数：", len(items))
        rect_items = self.img_win.get_rect_items()
        # print(rect_items, len(rect_items))
        pixmapItem = self.img_win.get_pixmapItem()
        ToXML5D0.CreatSaveXml.creat_xml(self.filePath, items, rect_items, self.img.shape, pixmapItem)

    def auto_save_xml(self, checked):
        if checked:
            self.auto_save_timer.start(300)
        else:
            self.auto_save_timer.stop()

    def get_filepath(self):
        return self.filePath


class QSSLoader:
    def __init__(self):
        pass

    @staticmethod
    def read_qss_file(qss_file_name):
        with open(qss_file_name, 'r', encoding='UTF-8') as file:
            return file.read()


def Run_MainDcmLabel():
    My_ui = GUI()
    style_file = 'QSS-master/MacOS.qss'
    # style_file = 'QSS-master/MaterialDark.qss'
    # style_file = 'QSS-master/ManjaroMix.qss'
    # style_file = 'QSS-master/Ubuntu.qss'
    # style_file = 'QSS-master/Aqua.qss'
    style_sheet = QSSLoader.read_qss_file(style_file)
    My_ui.ui.setStyleSheet(style_sheet)
    My_ui.ui.setWindowIcon(QIcon(r'Sources\intecast.ico'))
    My_ui.ui.show()
    windows.append(My_ui)


if __name__ == '__main__':
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication([])
    My_ui = GUI()
    style_file = 'QSS-master/MacOS.qss'
    # style_file = 'QSS-master/MaterialDark.qss'
    # style_file = 'QSS-master/ManjaroMix.qss'
    # style_file = 'QSS-master/Ubuntu.qss'
    # style_file = 'QSS-master/Aqua.qss'
    style_sheet = QSSLoader.read_qss_file(style_file)
    My_ui.ui.setStyleSheet(style_sheet)
    My_ui.ui.setWindowIcon(QIcon(r'Sources\intecast.ico'))
    My_ui.ui.show()
    app.exec_()
