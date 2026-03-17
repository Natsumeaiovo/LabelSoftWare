from PySide2 import QtGui
from PySide2.QtCore import Qt
from PySide2.QtGui import QIcon
from PySide2.QtGui import Qt
from PySide2.QtWidgets import QDialog, QFormLayout, QLineEdit, QPushButton, QComboBox, \
    QVBoxLayout, QSpacerItem, QSizePolicy

from utils.QSSLoader import QSSLoader


class LabelDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("输入标签、备注、评级:")
        self.setFixedWidth(300)  # 窗口宽度
        self.setFixedHeight(190)  # 窗口高度（增加 level 输入后调高）
        self.setFont(QtGui.QFont("MicroSoft YaHei", 10))

        # 主布局
        main_layout = QVBoxLayout(self)

        # 表单布局
        form_layout = QFormLayout()

        # 标签输入
        self.label_combo = QComboBox(self)
        self.label_combo.setFixedHeight(30)  # 调整组件高度
        self.load_labels()

        # comment 输入
        self.comment_edit = QLineEdit(self)
        self.comment_edit.setFixedHeight(30)  # 调整组件高度

        # Level（级别）输入：使用 QLineEdit，不设置默认值
        self.level_edit = QLineEdit(self)
        self.level_edit.setFixedHeight(30)

        form_layout.addRow("标签:", self.label_combo)
        form_layout.addRow("备注:", self.comment_edit)
        form_layout.addRow("评级:", self.level_edit)

        # 确定按钮
        self.ok_button = QPushButton("完成", self)
        self.ok_button.setFixedHeight(35)  # 调整按钮高度
        self.ok_button.clicked.connect(self.accept)

        # 添加表单布局
        main_layout.addLayout(form_layout)

        # 添加弹性空间和按钮
        main_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))  # 顶部弹性
        main_layout.addWidget(self.ok_button, alignment=Qt.AlignCenter)
        # main_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))  # 底部弹性

        # 设置样式表
        style_file = "./QSS-master/MacOS.qss"
        style_sheet = QSSLoader.read_qss_file(style_file)
        self.setStyleSheet(style_sheet)
        self.setWindowIcon(QIcon("./Sources/intecast.ico"))

    def load_labels(self):
        # 设置 ComboBox 为可编辑模式
        self.label_combo.setEditable(True)
        try:
            with open("./Sources/label_info.txt", "r", encoding="utf-8") as file:
                labels = file.readlines()
                for label in labels:
                    self.label_combo.addItem(label.strip())
        except FileNotFoundError:
            pass

    def get_values(self):
        return (
            self.label_combo.currentText(),
            self.comment_edit.text(),
            self.level_edit.text().strip(),
        )
