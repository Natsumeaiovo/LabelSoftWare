import os

from PySide2 import QtGui
from PySide2.QtGui import QIcon, QFont, QGuiApplication
from PySide2.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QAbstractItemView, QHBoxLayout, QSpacerItem, QSizePolicy, QTableWidgetItem, QHeaderView, QStyle
)
from PySide2.QtCore import Qt

from utils.QSSLoader import QSSLoader


class EditWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("编辑标签")
        self.resize(500, 400)  # 设置默认窗口大小


        # 布局
        self.layout = QVBoxLayout(self)

        # qss
        style_file = './QSS-master/MacOS.qss'
        style_sheet = QSSLoader.read_qss_file(style_file)
        self.setStyleSheet(style_sheet)
        self.setWindowIcon(QIcon('./Sources/intecast.ico'))
        self.setFont(QtGui.QFont("MicroSoft YaHei", 10))

        # 表格
        self.table = QTableWidget(0, 2, self)  # 两列表格，第二列放删除按钮
        self.table.setHorizontalHeaderLabels(["标签", ""])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # 第一列填充剩余空间
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)  # 第二列按内容调整
        self.table.setAlternatingRowColors(True)  # 交替颜色
        self.layout.addWidget(self.table)
        font = QFont("MicroSoft YaHei", 10)
        self.table.setFont(font)
        header_font = QFont("宋体", 10, QFont.Bold)  # 表头字体加粗
        self.table.horizontalHeader().setFont(header_font)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.table)

        # 底部按钮布局
        self.button_layout = QHBoxLayout()
        self.button_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding))  # 左间距
        self.add_button = QPushButton("新增标签", self)
        self.add_button.setFixedWidth(120)  # 固定按钮宽度
        self.add_button.setFixedHeight(30)  # 固定按钮高度
        self.button_layout.addWidget(self.add_button)
        self.button_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Expanding))  # 右间距
        self.layout.addLayout(self.button_layout)

        # 初始化数据
        self.file_path = "./Sources/label_info.txt"
        self.load_labels()

        # 绑定事件
        self.table.itemChanged.connect(self.save_labels)
        self.add_button.clicked.connect(self.add_new_label)

    def load_labels(self):
        """从文件加载标签到表格"""
        if not os.path.exists(self.file_path):
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            open(self.file_path, 'w').close()

        with open(self.file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()

        self.table.setRowCount(0)  # 清空表格
        for line in lines:
            self.add_table_row(line.strip())

    def add_table_row(self, label):
        """向表格添加一行"""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 第一列为标签
        item = QTableWidgetItem(label)
        item.setFlags(item.flags() | Qt.ItemIsEditable)  # 可编辑
        self.table.setItem(row, 0, item)

        # 第二列为删除按钮
        delete_button = QPushButton("删除")
        delete_button.setFixedWidth(60)  # 限制删除按钮宽度
        delete_button.clicked.connect(lambda: self.delete_row(row))  # 绑定删除事件
        self.table.setCellWidget(row, 1, delete_button)

    def save_labels(self, item=None):
        """实时保存表格中的标签到文件"""
        labels = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0):  # 检查是否存在有效项
                labels.append(self.table.item(row, 0).text())

        with open(self.file_path, 'w', encoding='utf-8') as file:
            file.write("\n".join(labels))

    def add_new_label(self):
        """新增一个标签"""
        self.add_table_row("新标签")  # 添加一个默认标签
        self.table.scrollToBottom()  # 滚动到新增行

    def delete_row(self, row):
        """删除指定行"""
        self.table.removeRow(row)  # 从表格中移除行
        self.save_labels()  # 保存更新后的标签
