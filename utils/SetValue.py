# -*- coding: utf-8 -*-

"""
Time : 2024/7/26 上午8:38
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : SetValue.py
Lab: Information Group of InteCast Software Center
Function of the program:
"""


from PySide2.QtWidgets import QApplication, QWidget, QVBoxLayout, QSlider, QLabel
from PySide2.QtCore import Qt, QRect
from PySide2.QtGui import QPainter, QPen, QBrush, QColor
from PySide2.QtCore import QTimer

class DoubleSliderLabel(QLabel):
    def __init__(self, *args, **kwargs):
        super(DoubleSliderLabel, self).__init__(*args, **kwargs)
        self.min_value = 0
        self.max_value = 65535
        # 防抖
        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.print_values)
        # self.histogram = histogram

    def set_values(self, min_value, max_value):
        self.min_value = min_value
        self.max_value = max_value
        self.update()
        self.debounce_timer.start(300)

    def print_values(self):
        print(self.min_value, self.max_value)

    def paintEvent(self, event):
        super(DoubleSliderLabel, self).paintEvent(event)
        painter = QPainter(self)

        # 获取控件的宽度和高度
        width = self.width()
        height = self.height()
        # width = 11261
        # height = 11
        # print(width, height)

        # 根据最小值和最大值计算竖线的位置
        min_x = int(width * (self.min_value / 65535.0))
        max_x = int(width * (self.max_value / 65535.0))

        # 设置笔刷和画笔
        pen = QPen(QColor(0, 0, 0), 2)
        brush = QBrush(QColor(200, 200, 200, 100), Qt.BDiagPattern)
        painter.setPen(pen)

        # 绘制竖线
        painter.drawLine(min_x, 0, min_x, height)
        painter.drawLine(max_x, 0, max_x, height)

        # 填充网格
        painter.setBrush(brush)
        if min_x > 0:
            painter.drawRect(0, 0, min_x, height)
        if max_x < width:
            painter.drawRect(max_x, 0, width - max_x, height)

        painter.end()


class DoubleSlider(QWidget):
    def __init__(self, min_slider, max_slider, window_width_slider, window_level_slider, min_label, max_label,
                 window_width_label, window_level_label, histogram):
        super().__init__()
        self.min_slider = min_slider
        self.max_slider = max_slider
        self.window_width_slider = window_width_slider
        self.window_level_slider = window_level_slider
        self.min_label = min_label
        self.max_label = max_label
        self.window_width_label = window_width_label
        self.window_level_label = window_level_label
        self.histogram = histogram

        # 灰度最小值和最大值slider值变化信号连接到update_values_from_min_max槽
        self.min_slider.valueChanged.connect(self.update_values_from_min_max)
        self.max_slider.valueChanged.connect(self.update_values_from_min_max)

        # Custom QLabel with vertical lines and grid
        self.custom_label = DoubleSliderLabel(self.histogram)
        self.custom_label.setFixedHeight(self.histogram.height())
        self.custom_label.setFixedWidth(self.histogram.width())

        # 窗宽窗位slider值变化信号连接到update_values_from_width_level
        self.window_width_slider.valueChanged.connect(self.update_values_from_width_level)
        self.window_level_slider.valueChanged.connect(self.update_values_from_width_level)


    def update_values_from_min_max(self):
        min_value = self.min_slider.value()
        max_value = self.max_slider.value()

        if min_value > max_value:
            if self.sender() == self.min_slider:
                self.max_slider.blockSignals(True)
                self.max_slider.setValue(min_value)
                self.max_slider.blockSignals(False)
                max_value = min_value
            else:
                self.min_slider.blockSignals(True)
                self.min_slider.setValue(max_value)
                self.min_slider.blockSignals(False)
                min_value = max_value

        window_width = max_value - min_value
        window_level = min_value + window_width // 2

        self.window_width_slider.blockSignals(True)
        self.window_width_slider.setValue(window_width)
        self.window_width_slider.blockSignals(False)

        self.window_level_slider.blockSignals(True)
        self.window_level_slider.setValue(window_level)
        self.window_level_slider.blockSignals(False)

        self.min_label.setText(f'最小值: {min_value}')
        self.max_label.setText(f'最大值: {max_value}')
        self.window_width_label.setText(f'窗宽: {window_width}')
        self.window_level_label.setText(f'窗位: {window_level}')

        self.custom_label.set_values(min_value, max_value)


    def update_values_from_width_level(self):
        window_width = self.window_width_slider.value()
        window_level = self.window_level_slider.value()

        min_value = window_level - window_width // 2
        max_value = window_level + window_width // 2

        if min_value < 0:
            min_value = 0
            max_value = window_width
        if max_value > 65535:
            max_value = 65535
            min_value = 65535 - window_width

        self.min_slider.blockSignals(True)
        self.min_slider.setValue(min_value)
        self.min_slider.blockSignals(False)

        self.max_slider.blockSignals(True)
        self.max_slider.setValue(max_value)
        self.max_slider.blockSignals(False)

        self.min_label.setText(f'最小值: {min_value}')
        self.max_label.setText(f'最大值: {max_value}')

        self.window_width_label.setText(f'窗宽: {window_width}')
        self.window_level_label.setText(f'窗位: {window_level}')

        self.custom_label.set_values(min_value, max_value)
