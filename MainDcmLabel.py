# -*- coding: utf-8 -*-

"""
Time : 2024/7/26 上午9:03
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : MainDcmLabel.py
Lab: Information Group of InteCast Software Center
Function of the program: 
"""

import json
import os

import pydicom
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2.QtCore import Signal, QObject, QThread, QTimer
from PySide2.QtGui import QIcon
from PySide2.QtUiTools import QUiLoader
from PySide2.QtWidgets import QApplication, QMainWindow, QListWidgetItem, QListWidget, QWidget
from PySide2.QtWidgets import QFileDialog

from utils import DrawHist
from utils import SetValue
from utils import ShowDCMName
from utils import ShowImage
from utils import ToXML5D0
from utils import WindowImage
from utils.DcmDealFdi5d5 import *
from utils.QSSLoader import QSSLoader
from utils.ShowImage import IMG_WIN
from widgets.EditWindow import EditWindow
from utils import EnhanceImage


# 保存图片临时信息（窗宽、窗位、是否反色）
def save_img_tmp_info(image_path, window_width, window_level, reverse_checked):
    # 获取图片所在目录
    image_dir = os.path.dirname(image_path)
    # 创建./img_info下的同名目录
    info_dir = os.path.join('./img_info', os.path.basename(image_dir))
    os.makedirs(info_dir, exist_ok=True)
    # 信息文件路径
    info_file = os.path.join(info_dir, os.path.basename(image_path) + '.json')
    temp_info_file = os.path.join(info_dir, os.path.basename(image_path) + '.json.tmp')

    # 更新信息
    info_data = {
        'window_width': window_width,
        'window_level': window_level,
        'reverse_checked': reverse_checked
    }

    # 保存信息到临时文件
    with open(temp_info_file, 'w') as f:
        json.dump(info_data, f, indent=4)

    # 将临时文件重命名为目标文件
    os.replace(temp_info_file, info_file)


# 读取图片临时信息（窗宽、窗位、是否反色）
def load_img_tmp_info(image_name):
    # 获取图片所在目录
    image_dir = os.path.dirname(image_name)
    # 信息文件路径
    info_file = os.path.join('./img_info', os.path.basename(image_dir), os.path.basename(image_name) + '.json')

    if os.path.exists(info_file):
        with open(info_file, 'r') as f:
            info_data = json.load(f)
        return info_data
    return None


def guided_filter(I, p, radius=16, eps=0.01):
    # 转换输入格式
    I = np.float32(I)
    p = np.float32(p)

    # 计算局部统计量
    mean_I = cv2.boxFilter(I, cv2.CV_32F, (radius, radius))
    mean_p = cv2.boxFilter(p, cv2.CV_32F, (radius, radius))
    corr_I = cv2.boxFilter(I * I, cv2.CV_32F, (radius, radius))
    corr_Ip = cv2.boxFilter(I * p, cv2.CV_32F, (radius, radius))

    # 计算方差和协方差
    var_I = corr_I - mean_I * mean_I
    cov_Ip = corr_Ip - mean_I * mean_p

    # 计算线性系数
    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I

    # 平均系数
    mean_a = cv2.boxFilter(a, cv2.CV_32F, (radius, radius))
    mean_b = cv2.boxFilter(b, cv2.CV_32F, (radius, radius))

    # 生成基础层
    base_layer = mean_a * I + mean_b

    return base_layer


def rawimg_enhance(ds):
    raw_img = ds.pixel_array.astype(np.float64)

    # 1 对数处理（Retinex分解）
    # 添加epsilon防止log(0)
    epsilon = 1e-6
    s_log = np.log(raw_img + epsilon)  # 公式(2)-(4)

    # 2 归一化到[-1,1]范围
    # 计算当前对数图像的范围
    s_log_min = np.min(s_log)
    s_log_max = np.max(s_log)
    # 线性映射到[-1,1]
    s_log_1 = 2 * (s_log - s_log_min) / (s_log_max - s_log_min) - 1  # 专利中的归一化步骤

    # 3 导向滤波获取基础层
    base_log = guided_filter(s_log_1, s_log_1, radius=16, eps=0.01)
    # 映射回原始对数域
    base_ys_log = (base_log + 1) * (s_log_max - s_log_min) / 2 + s_log_min

    # 4 动态范围映射与细节处理，计算细节层（公式(6)）
    detail_log = s_log - base_ys_log

    # 5 系数分配与合成（公式7-8）
    alpha = 0.5
    beta = 2.0
    enhanced_base = alpha * base_ys_log  # 基础层动态范围压缩
    enhanced_detail = beta * detail_log  # 细节层增强
    enhanced_log = enhanced_base + enhanced_detail

    # 6 结果输出（公式9）
    # 指数变换恢复线性域
    enhanced_linear = np.exp(enhanced_log)

    # 恢复原始数值范围
    original_min = np.min(raw_img)
    original_max = np.max(raw_img)
    enhanced_norm = (enhanced_linear - np.min(enhanced_linear)) / \
                    (np.max(enhanced_linear) - np.min(enhanced_linear)) * \
                    (original_max - original_min) + original_min

    # DICOM格式兼容处理
    if ds.PixelRepresentation == 0:  # 无符号整型
        enhanced_img = np.clip(enhanced_norm, 0, 2 ** ds.BitsStored - 1)
        output_img = enhanced_img.astype(ds.pixel_array.dtype)
    else:  # 有符号整型（如CT值）
        enhanced_img = np.clip(enhanced_norm, -2 ** (ds.BitsStored - 1), 2 ** (ds.BitsStored - 1) - 1)
        output_img = enhanced_img.astype(ds.pixel_array.dtype)
    return output_img


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
        self.img_trans_utils = DcmDealFdi5d5()  # 创建 DcmDealFdi5d5 类的实例
        self.ui = QUiLoader().load('UI/pic.ui')
        self.img = None
        self.img_enhance = None
        self.folder_path = ""
        self.filePath = ""
        self.ongoing = False
        self.window_left = 0
        self.window_right = 65535

        # self.graphics_view_layout = QVBoxLayout(self.ui.graphicsView)
        self.img_win: IMG_WIN = ShowImage.IMG_WIN(self.ui.graphicsView, self.ui.listWidget_label)  # 实例化IMG_WIN类
        # self.graphics_view_layout.addWidget(self.graphic)
        # self.graphics_view_layout.addWidget(self.graphic)

        self.ui.pushButton.clicked.connect(self.select_img)
        self.ui.pushButton_save_xml.clicked.connect(self.save_xml)
        self.ui.updateLabel.clicked.connect(self.update_label)

        self.value_ww_wc = SetValue.DoubleSlider(self.ui.min_slider, self.ui.max_slider, self.ui.window_width_slider,
                                                 self.ui.window_level_slider, self.ui.min_label, self.ui.max_label,
                                                 self.ui.window_width_label, self.ui.window_level_label,
                                                 self.ui.histogram)
        self.image_name_list = ShowDCMName.ImageNameList(self.ui.listWidget_dcm_name)

        # self.setCentralWidget(self.ui)
        # # 将 MyGraphicsView 放入 graphicsView_2 的布局中
        # self.graphics_view_layout = QVBoxLayout(self.ui.graphicsView_2)
        # self.graphics_view = bbbbbbbb.MyGraphicsView(self.ui.graphicsView_2)
        # self.graphics_view_layout.addWidget(self.graphics_view)

        """
        点击图片名 连接并传递一个QListWidgetItem 对象给 show_img 方法作为其参数。
        """
        self.ui.listWidget_dcm_name.itemClicked.connect(
            lambda item: self.show_img(item)
        )

        # 最小、最大、窗宽、窗位slider 值变化信号 连接到 window_image_main
        self.ui.min_slider.valueChanged.connect(self.window_image_main)
        self.ui.max_slider.valueChanged.connect(self.window_image_main)
        self.ui.window_width_slider.valueChanged.connect(self.window_image_main)
        self.ui.window_level_slider.valueChanged.connect(self.window_image_main)

        # 图像快速处理：无、窗口化、归一化、分区增强、子图窗口化、子图归一化等radio button点击连接到show_img
        # self.ui.none_dcm_label.toggled.connect(lambda: self.show_img())
        # self.ui.window_dcm_label.toggled.connect(lambda: self.show_img())
        # self.ui.normalize_dcm_label.toggled.connect(lambda: self.show_img())
        # self.ui.partition_dcm_label.toggled.connect(lambda: self.show_img())
        # self.ui.sub_window_dcm_label.toggled.connect(lambda: self.show_img())
        # self.ui.sub_normalize_dcm_label.toggled.connect(lambda: self.show_img())

        self.ui.none_dcm_label.clicked.connect(
            lambda: self.show_img(quick_trans_method=self.ui.none_dcm_label.text()))
        self.ui.window_dcm_label.clicked.connect(
            lambda: self.show_img(quick_trans_method=self.ui.window_dcm_label.text()))
        self.ui.normalize_dcm_label.clicked.connect(
            lambda: self.show_img(quick_trans_method=self.ui.normalize_dcm_label.text()))
        self.ui.partition_dcm_label.clicked.connect(
            lambda: self.show_img(quick_trans_method=self.ui.partition_dcm_label.text()))
        self.ui.sub_window_dcm_label.clicked.connect(
            lambda: self.show_img(quick_trans_method=self.ui.sub_window_dcm_label.text()))
        self.ui.sub_normalize_dcm_label.clicked.connect(
            lambda: self.show_img(quick_trans_method=self.ui.sub_normalize_dcm_label.text()))

        """
        当点击 reverseButton 按钮时，还会传递一个布尔值给 show_img_reverse 方法作为其参数。
        这个布尔值表示按钮的状态（True 表示按钮被选中，False 表示按钮未被选中）。
        如果想仅调用而不传递任何参数，可以使用 lambda 函数来调用该方法。
        """
        # self.ui.reverseButton.toggled.connect(lambda: self.show_img_reverse(CHANGE_SLIDER))
        self.ui.reverseButton.clicked.connect(lambda: self.show_img_reverse(CHANGE_SLIDER))

        # 初始化Timer
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.save_xml)
        self.auto_save_timer.timeout.connect(self.save_xml)
        self.ui.autoSaveButton.toggled.connect(self.auto_save_xml)

        self.ui.spinBox_1.valueChanged.connect(self.window_image_main)
        self.ui.spinBox_2.valueChanged.connect(self.window_image_main)
        self.ui.spinBox_3.valueChanged.connect(self.window_image_main)
        self.ui.radioButton_enhance.clicked.connect(self.window_image_main)

    def select_img(self):
        """
        选择图片并显示
        """
        # 尝试读取上次打开的目录
        last_dir_file = os.path.join("temp", "last_dir.txt")
        os.makedirs("temp", exist_ok=True)
        # 设置默认目录为当前目录
        initial_dir = os.getcwd()
        # 如果存在上次记录的目录，则使用该目录
        if os.path.exists(last_dir_file):
            try:
                with open(last_dir_file, "r") as f:
                    saved_dir = f.read().strip()
                if os.path.isdir(saved_dir):
                    initial_dir = saved_dir
            except Exception as e:
                print(f"读取上次目录出错: {e}")

        filePath, _ = QFileDialog.getOpenFileName(
            self.ui,  # 父窗口对象
            "选择要浏览的图片目录",  # 标题
            initial_dir,  # 起始目录
            "图片类型 (*.dcm *.png *.jpg *.bmp *.tif *.tiff)"  # 选择类型过滤项，过滤内容在括号中
        )
        if filePath == '':
            return
        self.filePath = os.path.normpath(filePath)
        print("filePath" + filePath)
        self.show_img(filePath=self.filePath)

        # 使用 os.path.dirname 获取路径部分
        directory = os.path.dirname(self.filePath)
        # # 使用 os.path.basename 获取文件名部分
        # filename = os.path.basename(self.filePath)

        # 保存当前打开的目录路径到temp文件
        try:
            with open(last_dir_file, "w") as f:
                f.write(directory)
        except Exception as e:
            print(f"保存目录路径出错: {e}")

        self.image_name_list.open_folder(directory)
        self.folder_path = directory
        print("dire path: ", directory)

    def img_quick_trans(self, quick_trans_method):
        """
        图像快速处理
        """
        print("快速处理：", quick_trans_method)
        if quick_trans_method == NONE or quick_trans_method is None:
            self.ui.none_dcm_label.setChecked(True)
            self.img_enhance = None
            self.quick_trans_method = None
        else:
            self.quick_trans_method = quick_trans_method
            # 如果反色没有勾选则使用对应的图像增强方法，否则在反色算法中增强，避免重复运算
            if self.ui.reverseButton.isChecked() is not True:
                self.img_enhance = self.img_trans_utils.call_method(self.quick_trans_method, self.img)

    # 如果进行了手动保存，或者勾选了自动保存，那么查看图片时，将list对应item标记为已查看
    def set_item_viewed(self, listWidget: QListWidget, file_name: str, manual_save: bool):
        # 在传入的listWidget中查找对应项目
        for i in range(listWidget.count()):
            list_item = listWidget.item(i)
            if list_item.text() == file_name:
                if self.ui.autoSaveButton.isChecked() or manual_save:
                    list_item.setIcon(QIcon('./Sources/viewed'))
                break

    def show_img(self, item=None, filePath=None, quick_trans_method=None):
        is_item_changed = False
        if item is not None:
            self.filePath = os.path.join(os.path.dirname(self.filePath), item.text())
            filePath = self.filePath
            quick_trans_method = None
            self.set_item_viewed(self.ui.listWidget_dcm_name, item.text(), False)

        if quick_trans_method is not None:
            self.img_quick_trans(quick_trans_method)
        # 如果传了item参数(图片)，那么更改filePath为item的地址，并且不变换slider
        if filePath is not None:
            is_item_changed = True
            # 如果filePath不为空，那么从filePath读取img
            _, file_extension = os.path.splitext(self.filePath)

            if file_extension.lower() == '.dcm':
                ds = pydicom.dcmread(self.filePath)
                read_img = ds.pixel_array
                # 原始图像增强
                # output_img = rawimg_enhance(ds)
                # read_img = output_img
                self.window_left = int(ds.WindowCenter) - int(ds.WindowWidth) / 2
                self.window_right = int(ds.WindowCenter) + int(ds.WindowWidth) / 2
            elif file_extension.lower() in ['.tif', '.tiff']:
                with Image.open(self.filePath) as read_img:
                    # 如果tif只有一帧，那么直接读取
                    if read_img.n_frames == 1:
                        read_img = np.array(read_img)
                    else:
                        read_img.seek(1)  # 跳到第二帧
                    read_img = np.array(read_img)
            else:
                read_img = cv2.imread(self.filePath)
            # 检查是否需要将图像转换为灰度图
            print("read_img.shape:", len(read_img.shape))
            if len(read_img.shape) > 2:  # 如果有三个维度，则表示有多通道图像
                read_img = cv2.cvtColor(read_img, cv2.COLOR_BGR2GRAY)
            # 设置self.img为filePath所在路径
            self.img = read_img
            if self.img.dtype == np.int16 or self.img.dtype == np.uint16:
                max_val = 2 ** 16 - 1
            else:
                max_val = 255
            self.clear = True

            # 读取并应用保存的窗宽、窗位和反色按钮状态信息
            self.img_quick_trans(None)
            image_info = load_img_tmp_info(self.filePath)
            if image_info:
                self.ui.reverseButton.setChecked(image_info['reverse_checked'])
                self.ui.window_width_slider.setValue(image_info['window_width'])
                self.ui.window_level_slider.setValue(image_info['window_level'])
            else:
                if self.ui.reverseButton.isChecked():
                    self.ui.min_slider.setValue(max_val - self.img.max())
                    self.ui.max_slider.setValue(max_val - self.img.min())
                else:
                    self.ui.min_slider.setValue(self.img.min())
                    self.ui.max_slider.setValue(self.img.max())

        # 如果反色了
        if self.ui.reverseButton.isChecked() is True:
            # 如果item改变了
            self.show_img_reverse(NOT_CHANGE_SLIDER, is_item_changed)
            return

        if self.img_enhance is None:
            self.window_image_main()
        self.img_win.addScenes(self.img_enhance if self.img_enhance is not None else self.img, self.filePath, True)

        # self.img_win.addScenes(self.img_enhance if self.img_enhance is not None else self.img, self.filePath, True)
        # 如果没有反色，那么在这里绘制histogram
        if self.ui.reverseButton.isChecked() is not True:
            DrawHist.plot_histogram(self.img, self.window_left, self.window_right, self.ui.reverseButton.isChecked())
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
        reverse_checked = self.ui.reverseButton.isChecked()  # 是否反色
        print("窗位：", window_level, "窗宽：", window_width)
        if isinstance(self.img, np.ndarray) and self.img.size > 0:
            array = self.img
            array_orl = self.img
            # if self.ui.spinBox_3.value() != 0:
            #     array = EnhanceImage.unsharp_mask(array, self.ui.spinBox_3.value(),
            #                                      self.ui.spinBox_4.value(),(int(self.ui.spinBox_5.value()),int(self.ui.spinBox_5.value())))
            self.ui.enhance_label_1.setText(f'对比限制:{self.ui.spinBox_1.value()}')
            self.ui.enhance_label_2.setText(f'对比区域:{self.ui.spinBox_2.value()}')
            self.ui.enhance_label_3.setText(f'图像锐化:{self.ui.spinBox_3.value()}')

            if self.ui.radioButton_enhance.isChecked() is True:
                # array = EnhanceImage.high_frequency_emphasis(array, self.ui.spinBox_3.value(),
                #                                  self.ui.spinBox_4.value(),self.ui.spinBox_5.value())
                array = cv2.GaussianBlur(array, (13, 13), 0)
                array = cv2.addWeighted(array_orl, self.ui.spinBox_3.value(), array, 1 - self.ui.spinBox_3.value(), 0)
            # 当调整图片窗宽窗位时，会不断创建新的子线程
            self.thread = QThread(self)
            # print("创建一个子线程")
            # 创建 Worker 实例，并传递滑块的值
            self.worker = Worker(array, window_level, window_width)
            # 连接 Worker 的 finished 信号到 update_ui 槽
            self.worker.finished.connect(self.update_ui)
            # 连接线程的 started 信号到 Worker 的方法
            self.thread.started.connect(self.worker.window_image_worker)
            # 启动子线程
            self.thread.start()
            self.ongoing = False

        # 保存当前界面信息
        save_img_tmp_info(self.filePath, window_width, window_level, reverse_checked)

    # 更新img_win
    def update_ui(self, array):
        if self.ui.spinBox_1.value() != 0:
            if self.ui.radioButton_enhance.isChecked() is True:
                array = EnhanceImage.apply_clahe(array, self.ui.spinBox_1.value(),
                                             (int(self.ui.spinBox_2.value()), int(self.ui.spinBox_2.value())))
            # array = EnhanceImage.unsharp_mask(array, self.ui.spinBox_2.value(), self.ui.spinBox_3.value())
            # array = EnhanceImage.apply_hef(array, self.ui.spinBox_1.value(), self.ui.spinBox_2.value(), self.ui.spinBox_3.value())
            # array = EnhanceImage.clahe(array, int(self.ui.spinBox_1.value()), int(self.ui.spinBox_2.value()),
            #                                int(self.ui.spinBox_3.value()))
            # array = EnhanceImage.rawimg_enhance(array, self.ui.spinBox_1.value(), self.ui.spinBox_2.value(), self.ui.spinBox_3.value())
        self.img_win.addScenes(array, self.filePath, False)
        # self.ongoing = False

    # 图像正反色处理，修改了img为其反色，重新绘制了灰度直方图，根据参数更新slider的值
    def show_img_reverse(self, isChangeSlider=CHANGE_SLIDER, is_item_changed=False):
        if isinstance(self.img, np.ndarray):
            if self.img.dtype == np.int16 or self.img.dtype == np.uint16:
                max_val = 2 ** 16 - 1
            else:
                max_val = 255

            # 按下反色按钮
            if isChangeSlider == CHANGE_SLIDER:
                # 将self.img的反色传给reverse_img，重新绘制灰度直方图
                pre_max_slider_value = self.ui.max_slider.value()
                self.img = max_val - self.img
                self.ui.max_slider.setValue(max_val - self.ui.min_slider.value())
                self.ui.min_slider.setValue(max_val - pre_max_slider_value)
                self.window_image_main()
                # 如果有图片增强
                if self.quick_trans_method is not None:
                    self.img_enhance = self.img_trans_utils.call_method(self.quick_trans_method, self.img)
                    self.worker.finished.connect(
                        lambda: self.img_win.addScenes(self.img_enhance, self.filePath, False))

            # 反色按钮已选中情况下，进行show_img调用(切换增强算法，切换图片)
            else:
                # 如果切换了照片，那么需要对self.img进行反色
                if is_item_changed:
                    self.img = max_val - self.img
                # 如果有图片增强
                if self.quick_trans_method is not None:
                    self.img_enhance = self.img_trans_utils.call_method(self.quick_trans_method, self.img)
                    self.img_win.addScenes(self.img_enhance, self.filePath, clear=is_item_changed)
                else:
                    self.img_win.addScenes(self.img, self.filePath, clear=is_item_changed)
                    self.window_image_main()
            DrawHist.plot_histogram(self.img, self.window_left, self.window_right, self.ui.reverseButton.isChecked())
            pixmap = QtGui.QPixmap('histogram.png')
            self.ui.histogram.setPixmap(pixmap)

    # 保存标注
    def save_xml(self):
        # print("保存标注！")
        file_name = os.path.basename(self.filePath)  # 从路径中提取文件名
        self.set_item_viewed(self.ui.listWidget_dcm_name, file_name, True)
        items = self.img_win.get_scene_items()
        # 如果items为空，直接返回
        if not items:
            return
        # print("graphic上所有的items：", items, "items个数：", len(items))
        rect_items = self.img_win.get_rect_items()
        # print(rect_items, len(rect_items))
        pixmapItem = self.img_win.get_pixmapItem()
        ToXML5D0.CreatSaveXml.creat_xml(self.filePath, items, rect_items, self.img.shape, pixmapItem, isManual=True)
        self.image_name_list.update_item_status(self.ui.listWidget_dcm_name, file_name)

    def auto_save_xml(self, checked):
        if checked:
            self.auto_save_timer.start(100)
        else:
            self.auto_save_timer.stop()

    def get_filepath(self):
        return self.filePath

    def update_label(self):
        # 打开编辑窗口
        self.edit_window = EditWindow()
        self.edit_window.show()


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
    My_ui.ui.setWindowIcon(QIcon('./Sources/intecast.ico'))
    My_ui.ui.show()
    app.exec_()
