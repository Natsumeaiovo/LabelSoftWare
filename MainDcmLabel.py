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
import shutil
import xml.etree.ElementTree as ET
from collections import defaultdict

import pydicom
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2.QtCore import Signal, QObject, QThread, QTimer
from PySide2.QtGui import QIcon
from PySide2.QtUiTools import QUiLoader
from PySide2.QtWidgets import QApplication, QMainWindow, QListWidget
from PySide2.QtWidgets import QFileDialog
from PySide2.QtWidgets import QMessageBox

from utils import DrawHist
from utils import EnhanceImage
from utils import SetValue
from utils import ShowDCMName
from utils import ShowImage
from utils import ToXML5D0
from utils import WindowImage
from utils import XML_report
from utils.DcmDealFdi5d5 import *
from utils.QSSLoader import QSSLoader
from utils.ShowImage import IMG_WIN
from widgets.EditWindow import EditWindow


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
        self.img_trans = None
        self.img_enhanced = None
        self.xml_path = ""
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
        self.ui.autoSaveButton.toggled.connect(self.auto_save_xml)

        self.ui.radioButton_enhance.clicked.connect(self.window_image_main)
        self.ui.spinBox_1.valueChanged.connect(self.window_image_main)
        self.ui.spinBox_2.valueChanged.connect(self.window_image_main)
        self.ui.spinBox_3.valueChanged.connect(self.window_image_main)
        self.ui.merge_anno.clicked.connect(self.merge_annotations)
        self.ui.revoke_merge.clicked.connect(self.remove_merge_anno)
        self.ui.auto_merge.toggled.connect(self.save_auto_merge_config)
        self.ui.generate_report.clicked.connect(self.generate_report)
        self.ui.save_cur_img.clicked.connect(self.save_cur_img)
        self.ui.exclude_pix.clicked.connect(self.start_exclude_pixels_mode)
        self.ui.auto_exclude_pix.toggled.connect(self.on_auto_exclude_toggled)
        self.ui.clean_exclude_pix.clicked.connect(self.clear_exclude_regions)
        self.ui.change_img_savepath.triggered.connect(
            lambda: self.select_and_save_path('img_save_path', "选择图像保存位置")
        )
        self.ui.change_report_savepath.triggered.connect(
            lambda: self.select_and_save_path('report_save_path', "选择报告保存位置")
        )
        self.load_config()

    def load_config(self):
        """在程序启动时加载配置"""
        config_path = os.path.join('Sources', 'config.json')
        auto_merge_state = False
        auto_exclude_state = False  # 默认为不排除
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                auto_merge_state = config.get('autoMerge', False)
                auto_exclude_state = config.get('autoExclude', False)  # 读取排除状态
            except (json.JSONDecodeError, IOError) as e:
                print(f"加载配置文件 '{config_path}' 失败: {e}")

        self.ui.auto_merge.setChecked(auto_merge_state)
        self.ui.auto_exclude_pix.setChecked(auto_exclude_state)
        self.img_win.set_auto_exclude_enabled(auto_exclude_state)  # 通知IMG_WIN

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
        self.xml_path = self.folder_path + "-XML"
        print("folder_path: ", directory)

        # 如果auto_merge被勾选，则在选择图片后执行一次合并
        if self.ui.auto_merge.isChecked():
            self.merge_annotations()

    def img_quick_trans(self, quick_trans_method, img_to_handle=None):
        """
        图像快速处理
        """
        if img_to_handle is None:
            img_to_handle = self.img
        print("快速处理：", quick_trans_method)
        if quick_trans_method == NONE or quick_trans_method is None:
            self.ui.none_dcm_label.setChecked(True)
            self.img_trans = None
            self.quick_trans_method = None
        else:
            self.quick_trans_method = quick_trans_method
            # 如果反色没有勾选则使用对应的图像增强方法，否则在反色算法中增强，避免重复运算
            # if self.ui.reverseButton.isChecked() is not True:
            #     self.img_enhance = self.img_trans_utils.call_method(self.quick_trans_method, img_to_handle)
            #     img_to_handle = self.img_enhance\
            self.img_trans = self.img_trans_utils.call_method(self.quick_trans_method, img_to_handle)
            img_to_handle = self.img_trans
        return img_to_handle

    def set_item_viewed(self, listWidget: QListWidget, file_name: str, manual_save: bool):
        """
        如果进行了手动保存，或者勾选了自动保存，那么查看图片时，将list对应item标记为已查看
        """
        if self.ui.autoSaveButton.isChecked() or manual_save:
            # 在传入的listWidget中查找对应项目
            for i in range(listWidget.count()):
                list_item = listWidget.item(i)
                if list_item.text() == file_name:
                    list_item.setIcon(QIcon('./Sources/viewed'))
                    break

    def show_img(self, item=None, filePath=None, quick_trans_method=None):
        is_item_changed = False
        if item is not None:
            self.filePath = os.path.join(os.path.dirname(self.filePath), item.text())
            filePath = self.filePath
            quick_trans_method = None
            self.set_item_viewed(self.ui.listWidget_dcm_name, item.text(), False)

        self.quick_trans_method = quick_trans_method
        # self.img_quick_trans(quick_trans_method)

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
                read_img = cv2.imdecode(np.fromfile(self.filePath, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
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
            self.img_quick_trans(quick_trans_method=NONE)
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

        # if self.img_enhance is None:
        #     self.window_image_main(quick_trans_method)
        self.img_win.addScenes(self.img_trans if self.img_trans is not None else self.img, self.filePath, True)
        self.window_image_main()

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

            # 如果图像增强按钮按下了
            if self.ui.radioButton_enhance.isChecked() is True:
                # array = EnhanceImage.high_frequency_emphasis(array, self.ui.spinBox_3.value(),
                #                                  self.ui.spinBox_4.value(),self.ui.spinBox_5.value())
                array = cv2.GaussianBlur(array, (13, 13), 0)
                array = cv2.addWeighted(array_orl, self.ui.spinBox_3.value(), array, 1 - self.ui.spinBox_3.value(), 0)
            # 不断地创建新的子线程
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
        array = self.img_quick_trans(self.quick_trans_method, array)
        self.img_enhanced = array
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

            # 反色按钮已选中情况下，进行show_img调用(切换增强算法，切换图片)
            else:
                # 如果切换了照片，那么需要对self.img进行反色
                if is_item_changed:
                    self.img = max_val - self.img
            DrawHist.plot_histogram(self.img, self.window_left, self.window_right, self.ui.reverseButton.isChecked())
            pixmap = QtGui.QPixmap('histogram.png')
            self.ui.histogram.setPixmap(pixmap)

    # 保存标注
    def save_xml(self):
        # 检查img_win中的脏标记，如果没有变化就不保存
        if not self.img_win.is_dirty and self.auto_save_timer.isActive():
            return

        print("保存标注！")
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

        # 保存成功后，重置脏标记
        self.img_win.set_dirty(False)

    def auto_save_xml(self, checked):
        if checked:
            # 启动定时器前，确保初始状态是干净的
            self.img_win.set_dirty(False)
            self.auto_save_timer.start(200)
        else:
            # 停止时，可以考虑执行一次最终保存
            if self.img_win.is_dirty:
                self.save_xml()
            self.auto_save_timer.stop()

    def get_filepath(self):
        return self.filePath

    def update_label(self):
        # 打开编辑窗口
        self.edit_window = EditWindow()
        self.edit_window.show()

    def merge_annotations(self):
        """
        合并XML标注文件中的标注框。
        1. 备份原始XML文件到meta子目录。
        2. 遍历所有XML，对其中具有相同名称（或属于特殊合并组）且位置相近的<object>进行合并。
        特殊规则:
        - "SK" 和 "SS" 视为一组。
        - "缩孔" 和 "缩松" 视为一组。
        """
        if not self.xml_path or not os.path.isdir(self.xml_path):
            print("XML路径无效，请先打开一个文件以确定路径。")
            return

        meta_path = os.path.join(self.xml_path, 'meta')

        # 1. 备份原始XML文件
        if os.path.exists(meta_path):
            print("Meta目录已存在，跳过合并操作。")
            return
        else:
            print(f"创建备份目录: {meta_path}")
            os.makedirs(meta_path)
            xml_files = [f for f in os.listdir(self.xml_path) if f.endswith('.xml')]
            for xml_file in xml_files:
                shutil.copy2(os.path.join(self.xml_path, xml_file), meta_path)
            print(f"已备份 {len(xml_files)} 个XML文件。")

        # 2. 遍历并合并XML文件中的标注
        print("开始合并标注...")
        for filename in os.listdir(self.xml_path):
            if not filename.endswith('.xml'):
                continue

            xml_file_path = os.path.join(self.xml_path, filename)
            try:
                tree = ET.parse(xml_file_path)
                root = tree.getroot()

                size_node = root.find('size')
                img_width = int(size_node.find('width').text)
                img_height = int(size_node.find('height').text)

                # 按<name>对<object>进行分组，并处理特殊合并规则
                objects_by_group = defaultdict(list)
                for obj in root.findall('object'):
                    name = obj.find('name').text
                    if name in ["SK", "SS"]:
                        group_key = "SK_SS_GROUP"
                    elif name in ["缩孔", "缩松"]:
                        group_key = "SHRINKAGE_GROUP"
                    else:
                        group_key = name
                    objects_by_group[group_key].append(obj)

                # 对每个分组进行合并处理
                for group_key, objects in objects_by_group.items():
                    if len(objects) < 2:
                        continue

                    # 使用字典追踪每个合并框包含的原始名称
                    constituent_names = {id(obj): [obj.find('name').text] for obj in objects}

                    merged = True
                    while merged:
                        merged = False
                        i = 0
                        while i < len(objects):
                            j = i + 1
                            while j < len(objects):
                                obj1 = objects[i]
                                obj2 = objects[j]

                                bndbox1 = obj1.find('bndbox')
                                bndbox2 = obj2.find('bndbox')

                                xmin1, ymin1 = int(float(bndbox1.find('xmin').text)), int(
                                    float(bndbox1.find('ymin').text))
                                xmax1, ymax1 = int(float(bndbox1.find('xmax').text)), int(
                                    float(bndbox1.find('ymax').text))
                                xmin2, ymin2 = int(float(bndbox2.find('xmin').text)), int(
                                    float(bndbox2.find('ymin').text))
                                xmax2, ymax2 = int(float(bndbox2.find('xmax').text)), int(
                                    float(bndbox2.find('ymax').text))

                                horizontal_gap = max(0, max(xmin1, xmin2) - min(xmax1, xmax2))
                                vertical_gap = max(0, max(ymin1, ymin2) - min(ymax1, ymax2))

                                if horizontal_gap < img_width * 0.05 and vertical_gap < img_height * 0.05:
                                    # 合并坐标
                                    bndbox1.find('xmin').text = str(min(xmin1, xmin2))
                                    bndbox1.find('ymin').text = str(min(ymin1, ymin2))
                                    bndbox1.find('xmax').text = str(max(xmax1, xmax2))
                                    bndbox1.find('ymax').text = str(max(ymax1, ymax2))

                                    # 合并原始名称列表
                                    obj1_id, obj2_id = id(obj1), id(obj2)
                                    constituent_names[obj1_id].extend(constituent_names[obj2_id])
                                    del constituent_names[obj2_id]

                                    # 根据合并后的名称列表，决定obj1的新名称
                                    if group_key == "SK_SS_GROUP":
                                        count_sk = constituent_names[obj1_id].count("SK")
                                        count_ss = len(constituent_names[obj1_id]) - count_sk
                                        obj1.find('name').text = "SK" if count_sk >= count_ss else "SS"
                                    elif group_key == "SHRINKAGE_GROUP":
                                        count_suokong = constituent_names[obj1_id].count("缩孔")
                                        count_suosong = len(constituent_names[obj1_id]) - count_suokong
                                        obj1.find('name').text = "缩孔" if count_suokong >= count_suosong else "缩松"

                                    # 从XML树和列表中移除obj2
                                    root.remove(obj2)
                                    objects.pop(j)
                                    merged = True
                                else:
                                    j += 1
                            i += 1

                # 将修改后的树写回原文件
                tree.write(xml_file_path, encoding='utf-8', xml_declaration=True)

            except Exception as e:
                print(f"处理文件 {filename} 时出错: {e}")

        print("XML标注合并完成")
        self.show_img(filePath=self.filePath)

    def remove_merge_anno(self):
        """
        撤销标注合并操作。
        检查是否存在meta备份目录。如果存在，则用meta目录中的文件覆盖当前XML文件。删除meta目录。
        """
        if not self.xml_path or not os.path.isdir(self.xml_path):
            return

        meta_path = os.path.join(self.xml_path, 'meta')

        # 1. 检查meta目录是否存在
        if not os.path.exists(meta_path):
            print("未找到备份目录 'meta'，无需执行撤销操作。")
            return

        try:
            print("开始撤销合并操作...")
            # 2. 删除当前XML路径下的所有XML文件
            for filename in os.listdir(self.xml_path):
                if filename.endswith('.xml'):
                    os.remove(os.path.join(self.xml_path, filename))
            print("已删除当前目录的XML文件。")

            # 3. 将meta目录中的所有文件复制回XML路径
            for filename in os.listdir(meta_path):
                shutil.copy2(os.path.join(meta_path, filename), self.xml_path)
            print("已从备份恢复XML文件。")

            # 4. 删除meta目录
            shutil.rmtree(meta_path)
            print("已删除备份目录 'meta'。")

            print("撤销合并完成。")
            # 刷新当前显示的图片和标注
            self.show_img(filePath=self.filePath)

        except Exception as e:
            print(f"撤销合并时出错: {e}")

    def save_auto_merge_config(self, checked):
        """当auto_merge按钮状态改变时，保存配置到JSON文件。"""
        config_dir = 'Sources'
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, 'config.json')

        config = {}
        # 先读取现有配置，以防覆盖其他设置
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass  # 如果文件损坏或为空，则创建一个新的

        config['autoMerge'] = checked

        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except IOError as e:
            print(f"保存配置文件 '{config_path}' 失败: {e}")

    def on_auto_exclude_toggled(self, checked):
        """当 auto_exclude_pix 按钮状态改变时，保存配置并刷新视图"""
        config_dir = 'Sources'
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, 'config.json')

        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        config['autoExclude'] = checked

        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except IOError as e:
            print(f"保存配置文件 '{config_path}' 失败: {e}")

        # 更新 IMG_WIN 的状态并刷新标注
        self.img_win.set_auto_exclude_enabled(checked)
        self.img_win.refresh_annotations()

    def clear_exclude_regions(self):
        """清空配置文件和内存中的所有排除区域，并刷新视图"""
        config_path = os.path.join('Sources', 'config.json')
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass  # 如果文件损坏或为空，则忽略

        # 清空排除区域列表
        if 'exclude_pix' in config:
            config['exclude_pix'] = []

        # 写回配置文件
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            print("配置文件中的排除区域已清空。")
        except IOError as e:
            print(f"保存配置文件失败: {e}")
            return

        # 通知 IMG_WIN 更新其内部状态并刷新标注
        self.img_win.clear_and_refresh_exclusions()

    def select_and_save_path(self, config_key, dialog_title):
        """
        打开目录选择对话框，并将选择的路径保存到 config.json 文件中。

        :param config_key: 在JSON文件中用于保存路径的键名 (例如, 'img_save_path')。
        :param dialog_title: 目录选择对话框的标题。
        """
        initial_dir = os.getcwd()  # 默认使用当前工作目录
        config_path = os.path.join('Sources', 'config.json')
        # 打开目录选择对话框
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 如果配置中有对应的路径且不为空，则使用该路径作为起始目录
                configured_path = config.get(config_key)
                if configured_path and os.path.isdir(configured_path):
                    initial_dir = configured_path
            except (json.JSONDecodeError, IOError):
                pass  # 如果配置文件读取失败，使用默认的当前工作目录

        # 打开目录选择对话框，使用initial_dir作为起始目录
        selected_dir = QFileDialog.getExistingDirectory(
            self.ui,
            dialog_title,
            initial_dir  # 使用配置文件中的目录或当前工作目录作为起始目录
        )

        # 如果用户选择了目录
        if selected_dir:
            config_dir = 'Sources'
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, 'config.json')

            config = {}
            # 首先读取现有配置，以防覆盖其他设置
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                except (json.JSONDecodeError, IOError):
                    pass  # 如果文件损坏或为空，则创建一个新的

            # 更新或添加路径配置
            config[config_key] = selected_dir

            # 将更新后的配置写回文件
            try:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
                print(f"配置已更新: {config_key} = {selected_dir}")
                QMessageBox.information(self.ui, "保存成功", f"{dialog_title}已更新为:\n{selected_dir}")
            except IOError as e:
                print(f"保存配置文件 '{config_path}' 失败: {e}")
                QMessageBox.warning(self.ui, "保存失败", f"无法保存路径配置: {e}")

    def generate_report(self):
        """
        生成缺陷报告。如果已配置报告路径，则直接使用；否则，提示用户选择并保存路径。
        """
        if not self.xml_path or not os.path.isdir(self.xml_path):
            QMessageBox.warning(self.ui, "路径无效", "XML路径无效，请先打开一个文件以确定路径。")
            return

        config_dir = 'Sources'
        config_path = os.path.join(config_dir, 'config.json')
        config = {}
        save_dir = None

        # 1. 检查配置文件中是否存在有效的报告保存路径
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                path_from_config = config.get('report_save_path')
                if path_from_config and os.path.isdir(path_from_config):
                    save_dir = path_from_config
            except (json.JSONDecodeError, IOError):
                pass

        # 2. 如果路径未配置或无效，则弹出对话框让用户选择
        if not save_dir:
            selected_dir = QFileDialog.getExistingDirectory(
                self.ui,
                "选择缺陷报告保存位置",
                self.folder_path  # 使用当前图片目录作为默认起始位置
            )

            if not selected_dir:
                QMessageBox.information(self.ui, "操作取消", "未选择报告保存位置，已取消生成报告。")
                return

            save_dir = selected_dir
            # 将新选择的路径保存回 config.json
            config['report_save_path'] = save_dir
            try:
                os.makedirs(config_dir, exist_ok=True)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
                print(f"报告保存路径已配置并保存: {save_dir}")
            except IOError as e:
                QMessageBox.warning(self.ui, "保存配置失败", f"无法保存报告路径配置: {e}")
                # 即使保存失败，本次依然继续生成报告

        # 3. 使用确定的 save_dir 生成报告
        if save_dir:
            output_excel_path = os.path.join(save_dir, "output.xlsx")

            try:
                XML_report.process_xml_folder(
                    folder_path=self.xml_path,
                    output_excel=output_excel_path
                )
                QMessageBox.information(self.ui, "成功", f"报告已成功生成并保存至:\n{output_excel_path}")
                os.startfile(save_dir)
            except Exception as e:
                print(f"生成报告时发生错误: {e}")

    def save_cur_img(self):
        """
        保存当前显示的增强后图像为JPG文件。
        如果已配置图像保存路径，则直接使用；否则，提示用户选择并保存路径。
        """
        # 1. 检查是否有可保存的图像
        if self.img_enhanced is None or not isinstance(self.img_enhanced, np.ndarray):
            QMessageBox.warning(self.ui, "无法保存", "当前没有可供保存的图像。\n请先加载并处理一张图片。")
            return
        if not self.filePath:
            QMessageBox.warning(self.ui, "无法保存", "未加载任何文件，无法确定文件名。")
            return

        config_dir = 'Sources'
        config_path = os.path.join(config_dir, 'config.json')
        config = {}
        save_dir = None

        # 2. 检查配置文件中是否存在有效的图像保存路径
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                path_from_config = config.get('img_save_path')
                if path_from_config and os.path.isdir(path_from_config):
                    save_dir = path_from_config
            except (json.JSONDecodeError, IOError):
                pass  # 配置文件读取失败，将提示用户选择

        # 3. 如果路径未配置或无效，则弹出对话框让用户选择
        if not save_dir:
            default_path = self.folder_path if self.folder_path and os.path.isdir(self.folder_path) else os.getcwd()
            selected_dir = QFileDialog.getExistingDirectory(
                self.ui,
                "选择图像保存位置",
                default_path
            )

            if not selected_dir:
                QMessageBox.information(self.ui, "操作取消", "未选择保存位置，已取消保存。")
                return

            save_dir = selected_dir
            # 将新选择的路径保存回 config.json
            config['img_save_path'] = save_dir
            try:
                os.makedirs(config_dir, exist_ok=True)
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
                print(f"图像保存路径已配置并保存: {save_dir}")
            except IOError as e:
                QMessageBox.warning(self.ui, "保存配置失败", f"无法保存图像路径配置: {e}")

        # 4. 确定文件名并保存图像
        if save_dir:
            base_name = os.path.basename(self.filePath)
            file_name_without_ext = os.path.splitext(base_name)[0]
            output_file_name = f"{file_name_without_ext}.jpg"
            full_save_path = os.path.join(save_dir, output_file_name)
            counter = 1
            while os.path.exists(full_save_path):
                output_file_name = f"{file_name_without_ext}({counter}).jpg"
                full_save_path = os.path.join(save_dir, output_file_name)
                counter += 1
            try:
                # cv2.imencode支持中文路径
                is_success, buffer = cv2.imencode(".jpg", self.img_enhanced)
                if is_success:
                    with open(full_save_path, 'wb') as f:
                        f.write(buffer)
                    QMessageBox.information(self.ui, "保存成功", f"图像已成功保存至:\n{full_save_path}")
                    print(f"图像已保存: {full_save_path}")
                else:
                    raise IOError("cv2.imencode failed")
            except Exception as e:
                print(f"保存图像时发生错误: {e}")

    def start_exclude_pixels_mode(self):
        """
        选择要排除的坏点区域
        """
        if self.img is None:
            QMessageBox.warning(self.ui, "提示", "请先加载一张图片。")
            return

        # 1. 弹出一个对话框
        QMessageBox.information(
            self.ui,
            "选择排除区域",
            "请在图像上拖动鼠标右键绘制一个矩形，以定义要排除的坏点区域。"
        )

        # 2. 设置 IMG_WIN 进入排除模式
        self.img_win.set_exclude_mode(True)


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
