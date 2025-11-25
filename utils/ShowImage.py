# -*- coding: utf-8 -*-

"""
Time : 2024/7/26 上午9:04
Author : Hou Mingjun
Email : houmingjun21@163.cpm
File : ShowImage.py
Lab: Information Group of InteCast Software Center
Function of the program: 显示图片，缩放图片，并进行标签框添加
"""
import json
import os
from typing import List, Optional

import numpy as np
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets
from PySide2.QtCore import Qt, QRectF, QPointF
from PySide2.QtGui import QPen, QBrush, QColor
from PySide2.QtGui import Qt
from PySide2.QtUiTools import QUiLoader
from PySide2.QtWidgets import QDialog, QListWidget
from PySide2.QtWidgets import QGraphicsView, QGraphicsRectItem, QGraphicsItem, QColorDialog, QInputDialog, QMenu
from PySide2.QtWidgets import QWidget, QListWidgetItem, QGraphicsPixmapItem

from utils import FromXML
from utils.ShowDCMName import ImageNameList
from widgets.LabelDialog import LabelDialog


class IMG_WIN(QWidget):
    def __init__(self, ui, image_name_list: ImageNameList):
        super().__init__()
        self.img = None
        self.ui = ui
        self.graphicsView = ui.graphicsView
        self.listWidget = ui.listWidget_label
        self.is_merge = None
        self.image_name_list = image_name_list

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

        self.graphicsView.setMouseTracking(True)
        self.graphicsView.viewport().setMouseTracking(True)
        self.graphicsView.setFocusPolicy(Qt.StrongFocus)
        self.graphicsView.installEventFilter(self)
        self.graphicsView.viewport().installEventFilter(self)

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
        '''
        rect_info_raw 是在原始xml文件中所有标注框的位置信息，即[label, xmin, ymin, xmax, ymax, comment_pose]
        在缩放时需要用 rect_info_raw 来更新 rect_items，避免累计误差。但是在拖动和调整框时，注意调用 sync_rect_info_from_items
        '''
        self.rect_info_raw = None
        # 当前 scene 中的所有矩形框列表
        self.rect_items: List[CustomRectItem] = []
        self.updating_selection = False
        self.is_dirty = False  # 添加一个脏标记
        self.hovered_rect: Optional[CustomRectItem] = None

        self.is_excluding_pixels = False  # 是否处于“选择排除区域”模式
        self.exclude_rects = []  # 存储排除区域的列表
        self.auto_exclude_enabled = False
        self.load_exclude_config()  # 初始化时加载配置

    def _merge_boxes(self, boxes, img_width, img_height):
        """
        合并重叠或邻近的标注框。仅合并具有相同标签的框。
        :param boxes: 标注框列表，格式为 [[xmin, ymin, xmax, ymax, label, comment], ...]
        :param img_width: 图像宽度
        :param img_height: 图像高度
        :return: 合并后的标注框列表
        """
        if not boxes:
            return []

        # 按标签对框进行分组
        from collections import defaultdict
        grouped_boxes = defaultdict(list)
        for box in boxes:
            label = box[4]
            grouped_boxes[label].append(box)

        final_merged_boxes = []
        width_threshold = img_width * 0.05
        height_threshold = img_height * 0.05

        # 对每个分组应用合并逻辑
        for label, group in grouped_boxes.items():
            if len(group) < 2:
                final_merged_boxes.extend(group)
                continue

            merged_in_group = True
            while merged_in_group:
                merged_in_group = False
                new_group = []
                used = [False] * len(group)

                for i in range(len(group)):
                    if used[i]:
                        continue

                    current_box = list(group[i])
                    used[i] = True

                    for j in range(i + 1, len(group)):
                        if used[j]:
                            continue

                        other_box = group[j]

                        # 计算水平和垂直间距
                        h_dist = max(current_box[0], other_box[0]) - min(current_box[2], other_box[2])
                        v_dist = max(current_box[1], other_box[1]) - min(current_box[3], other_box[3])

                        # 如果框重叠或间距在阈值内，则合并
                        if h_dist < width_threshold and v_dist < height_threshold:
                            # 合并框体
                            current_box[0] = min(current_box[0], other_box[0])
                            current_box[1] = min(current_box[1], other_box[1])
                            current_box[2] = max(current_box[2], other_box[2])
                            current_box[3] = max(current_box[3], other_box[3])
                            # 合并注释 (这里简单地将它们连接起来)
                            if other_box[5] and other_box[5] not in current_box[5]:
                                if current_box[5]:
                                    current_box[5] += f"_{other_box[5]}"
                                else:
                                    current_box[5] = other_box[5]

                            used[j] = True
                            merged_in_group = True

                    new_group.append(current_box)
                group = new_group

            final_merged_boxes.extend(group)

        return final_merged_boxes

    # clear表示是否清空原有的标签框
    def addScenes(self, img, path, clear: bool, merge=False):  # 绘制图形
        # 设置鼠标焦点到图形视图上
        self.graphicsView.setFocus()
        self.is_merge = merge
        # self.org = img
        self.img = img
        self.file_path = path
        if self.pixmapItem is not None:
            originX = self.pixmapItem.x()
            originY = self.pixmapItem.y()
        else:
            originX, originY = 0, 0  # 坐标基点

        # 创建QPixmap
        if img.dtype == np.uint16:  # 假设像素数组为16位
            q_img = QtGui.QImage(img.data, img.shape[1], img.shape[0], img.strides[0],
                                 QtGui.QImage.Format_Grayscale16)
        else:  # 假设像素数组为8位
            q_img = QtGui.QImage(img.data, img.shape[1], img.shape[0], img.strides[0],
                                 QtGui.QImage.Format_Grayscale8)

        self.pixmap = QtGui.QPixmap.fromImage(q_img)
        # 如果clear为True，清空原有的标签框
        if clear:
            self.scene.clear()
            self.rect_items.clear()
            self.listWidget.clear()
            self.pixmapItem = self.scene.addPixmap(self.pixmap)  # 添加图元
            self.sync_rect_info_from_items()  # 同步更新rectInfo
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
            if os.path.exists(path_xml):
                # 从XML获取原始数据
                analysis_result = FromXML.analysis_xml(path=path_xml, return_size=True)
                if not analysis_result:
                    return
                label, xmin, ymin, xmax, ymax, comment_pose, size = analysis_result
                img_width, img_height = size

                if not all([label, xmin, ymin, xmax, ymax]):
                    return

                # 将解析的数据转换为box列表
                boxes = []
                for i in range(len(label)):
                    boxes.append([
                        float(xmin[i]), float(ymin[i]), float(xmax[i]), float(ymax[i]),
                        label[i], comment_pose[i]
                    ])

                # 如果merge为True，执行合并逻辑
                if merge:
                    boxes = self._merge_boxes(boxes, img_width, img_height)
                    # 将合并后的数据转换回原始格式
                    label = [b[4] for b in boxes]
                    xmin = [str(b[0]) for b in boxes]
                    ymin = [str(b[1]) for b in boxes]
                    xmax = [str(b[2]) for b in boxes]
                    ymax = [str(b[3]) for b in boxes]
                    comment_pose = [b[5] for b in boxes]

                self.rect_info_raw = [label, xmin, ymin, xmax, ymax, comment_pose]
                print(label, xmin, ymin, xmax, ymax)

                for index, lbl in enumerate(label):
                    # 在添加前检查是否应被排除
                    current_xmin, current_ymin, current_xmax, current_ymax = float(xmin[index]), float(
                        ymin[index]), float(xmax[index]), float(ymax[index])
                    if self.is_rect_excluded(current_xmin, current_ymin, current_xmax, current_ymax):
                        print(f"标注 '{lbl}' 位于排除区域，已忽略。")
                        continue  # 跳过此标注
                        # 直接使用原始图像坐标，因为 CustomRectItem 现在是 pixmapItem 的子项
                    # 其坐标系相对于父项。父项的缩放和移动会自动应用到子项。
                    rect_in_pixmap = QRectF(QPointF(current_xmin, current_ymin),
                                            QPointF(current_xmax, current_ymax))
                    self.current_rect = CustomRectItem(rect_in_pixmap, self,
                                                       label=lbl, comment=comment_pose[index],
                                                       parent=self.pixmapItem)  # 设置父项
                    # self.scene.addItem(self.current_rect) # 不再需要，因为父项已在场景中

                    self.current_rect.label = lbl
                    self.current_rect.comment = comment_pose[index]
                    self.current_rect.radio_start = self.ratio
                    self.rect_items.append(self.current_rect)
                    self.update_rect_items(True)
                    self.current_rect = None

    def sync_rect_info_from_items(self):
        """从当前所有rect_items同步更新rect_info_raw"""
        labels = []
        xmins = []
        ymins = []
        xmaxs = []
        ymaxs = []
        comments = []

        for item in self.rect_items:
            # item.rect() 直接返回相对于父项(pixmapItem)的坐标，这正是我们需要的原始坐标
            rect_local = item.rect()
            x_min = rect_local.left()
            y_min = rect_local.top()
            x_max = rect_local.right()
            y_max = rect_local.bottom()

            labels.append(item.label)
            xmins.append(str(x_min))
            ymins.append(str(y_min))
            xmaxs.append(str(x_max))
            ymaxs.append(str(y_max))
            comments.append(item.comment)



        self.rect_info_raw = [labels, xmins, ymins, xmaxs, ymaxs, comments]
        self.set_dirty()  # 在同步数据后，将数据标记为“脏”


    def set_dirty(self, dirty=True):
        """设置脏标记，表示数据已修改"""
        self.is_dirty = dirty

    def scene_MousePressEvent(self, event):
        # 处理中键点击 - 直接传递给下层项目
        if event.button() == Qt.MiddleButton:
            if self.is_merge:
                QtWidgets.QMessageBox.warning(self, "警告", "合并模式下无法操作标注框")
                return
            item = self.scene.itemAt(event.scenePos(), self.graphicsView.transform())
            if isinstance(item, CustomRectItem):
                # 直接调用项目的中键菜单方法
                item.showCustomMenu(event)
                event.accept()  # 明确表示事件已处理
                return
        # if event.modifiers() & QtCore.Qt.ControlModifier and event.buttons() & QtCore.Qt.LeftButton:
        if event.buttons() & QtCore.Qt.LeftButton:
            self.preMousePosition = event.scenePos()  # 获取鼠标当前位置

        # if event.button() == Qt.LeftButton and not event.modifiers() & Qt.ControlModifier:
        if event.button() == Qt.RightButton:    # 如果按下鼠标右键
            if self.is_merge:
                QtWidgets.QMessageBox.warning(self, "警告", "合并模式下无法操作标注框")
                return
            item = self.graphicsView.itemAt(event.scenePos().toPoint())
            # 如果鼠标右键在标注框上
            if isinstance(item, CustomRectItem):
                cursor_shape = item.get_cursor_shape(event.scenePos())
                if cursor_shape in [Qt.SizeHorCursor, Qt.SizeVerCursor, Qt.SizeFDiagCursor]:
                    # 如果 光标放在了标注框的边缘，那么是 resize 方框
                    self.resizing = True
                    self.resizing_rect = item
                    # 记录下调整大小操作开始时的所有必要初始状态
                    item.initial_mouse_pos = event.scenePos()  # 记录鼠标在场景中的初始位置
                    item.initial_rect = item.rect()  # 记录矩形在局部坐标中的初始几何形状
                    return
                self.preMousePosition = event.scenePos()
                self.moving = True
                self.resizing_rect = item
                # 记录拖动开始时，item 在其父坐标系中的初始位置
                item.initial_pos = item.pos()
                return
            else:
                # 将场景坐标转换为 pixmapItem 的局部坐标
                self.start_pos = self.pixmapItem.mapFromScene(event.scenePos())
                self.drawing = True
                # 创建时指定父项
                self.current_rect = CustomRectItem(QRectF(self.start_pos, self.start_pos), self, parent=self.pixmapItem)
                # self.scene.addItem(self.current_rect) # 不再需要

    def scene_mouseReleaseEvent(self, event):
        # if event.button() == Qt.LeftButton:
        if event.button() == Qt.RightButton:
            if self.drawing:
                self.drawing = False
                # 如果鼠标释放位置与点击位置相同，那么不添加方框，直接返回
                # 注意：这里比较的是场景坐标，而start_pos是局部坐标，需要转换
                end_pos_local = self.pixmapItem.mapFromScene(event.scenePos())
                if self.start_pos == end_pos_local:
                    self.drawing = False
                    if self.current_rect:
                        self.scene.removeItem(self.current_rect)
                        self.current_rect = None
                    # 如果在排除模式，重置光标
                    if self.is_excluding_pixels:
                        self.set_exclude_mode(False)
                    return
                # --- 判断当前模式 ---
                if self.is_excluding_pixels:
                    # --- 坏点排除模式 ---
                    # 保存为排除区域
                    self.save_exclude_rect(self.current_rect.rect())
                    # 从场景中移除临时矩形
                    self.scene.removeItem(self.current_rect)
                    self.current_rect = None
                    # 恢复正常模式
                    self.set_exclude_mode(False)
                    self.image_name_list.check_dcm_status(self.ui.listWidget_dcm_name)
                else:
                    # --- 正常标注 ---
                    self.label_and_comment_dialog()
                self.current_rect = None

            if self.moving or self.resizing:
                self.moving = False
                self.resizing = False
                self.resizing_rect = None
                # 同步更新rectInfo
                self.sync_rect_info_from_items()

        for rect_item in self.rect_items:
            # rect_item.prepareGeometryChange()  # 预处理几何变化
            rect_item.update()
        # 更新视图
        self.scene.update()

        # super(QtWidgets.QGraphicsScene, self).mouseReleaseEvent(event)

    def scene_mouseMoveEvent(self, event):
        if self.resizing and self.resizing_rect:
            # 如果是在 resizing 方框
            # 1. 获取鼠标在场景中的当前位置
            current_pos = event.scenePos()

            # 2. 计算从鼠标按下开始的总位移（场景坐标系）
            total_scene_delta = current_pos - self.resizing_rect.initial_mouse_pos

            # 3. 将总位移转换为父项(pixmapItem)的局部坐标系下的位移
            total_local_delta_x = total_scene_delta.x() / self.ratio
            total_local_delta_y = total_scene_delta.y() / self.ratio

            # 4. 基于矩形的初始尺寸和总的局部坐标位移，计算新矩形
            new_rect = self.resizing_rect.initial_rect.adjusted(0, 0, total_local_delta_x, total_local_delta_y)

            self.resizing_rect.setRect(new_rect.normalized())

            # 5. 更新UI信息
            self.resizing_rect.update_info(True)
            return

        item = self.graphicsView.itemAt(event.scenePos().toPoint())
        if isinstance(item, CustomRectItem):
            self._set_hover_rect(item)
            if self.moving:
                # 1. 计算鼠标从按下开始的总位移（场景坐标系）
                total_scene_delta = event.scenePos() - self.preMousePosition  # preMousePosition 在按下时已设为初始位置

                # 2. 将总位移转换为父项(pixmapItem)的局部坐标系下的位移
                total_local_delta_x = total_scene_delta.x() / self.ratio
                total_local_delta_y = total_scene_delta.y() / self.ratio
                total_local_delta = QPointF(total_local_delta_x, total_local_delta_y)

                # 3. 基于 item 的初始位置和总的局部坐标位移，计算新位置
                new_pos = item.initial_pos + total_local_delta
                item.setPos(new_pos)

                # 4. 更新UI信息 (这部分逻辑可以保留)
                item.update_info(False)

            self.graphicsView.setCursor(item.get_cursor_shape(event.scenePos()))
        else:
            self._clear_hover_state()
            self.graphicsView.setCursor(Qt.ArrowCursor)

        # if Qt.LeftButton and not event.modifiers() & Qt.ControlModifier:
        if Qt.RightButton:
            if self.drawing and self.current_rect:
                # 将场景坐标转换为 pixmapItem 的局部坐标
                current_pos = self.pixmapItem.mapFromScene(event.scenePos())
                rect = QRectF(self.start_pos, current_pos).normalized()
                self.current_rect.setRect(rect)

        # if event.modifiers() & QtCore.Qt.ControlModifier and event.buttons() & QtCore.Qt.LeftButton:
        if event.buttons() & QtCore.Qt.LeftButton:
            # print("左键移动")  # 响应测试语句
            self.MouseMove = event.scenePos() - self.preMousePosition  # 鼠标当前位置-先前位置=单次偏移量
            self.preMousePosition = event.scenePos()  # 更新当前鼠标在窗口上的位置，下次移动用
            self.pixmapItem.setPos(self.pixmapItem.pos() + self.MouseMove)  # 更新图元位置
            # for item in self.scene.items():
            #     if isinstance(item, CustomRectItem):
            #         item.setPos(item.pos() + self.MouseMove)

    # 在 IMG_WIN 类中
    def scene_wheelEvent(self, event):
        """定义滚轮方法。当鼠标在图元范围之外，以图元中心为缩放原点；当鼠标在图元之中，以鼠标悬停位置为缩放中心"""
        angle = event.delta() / 8  # 返回QPoint对象，为滚轮转过的数值，单位为1/8度
        old_ratio = self.ratio

        if angle > 0:
            self.ratio += self.zoom_step
            if self.ratio > self.zoom_max:
                self.ratio = self.zoom_max
        else:
            self.ratio -= self.zoom_step
            if self.ratio < self.zoom_min:
                self.ratio = self.zoom_min

        # 如果缩放比例没有变化，则不执行任何操作
        if self.ratio == old_ratio:
            return

        # --- 核心修改开始 ---
        # 由于 CustomRectItem 是 pixmapItem 的子项，我们只需要缩放和移动 pixmapItem 即可。
        # 子项会自动继承父项的变换（缩放和移动）。

        # 计算当前图元的边界
        w = self.pixmap.size().width() * old_ratio
        h = self.pixmap.size().height() * old_ratio
        x1 = self.pixmapItem.pos().x()
        x2 = x1 + w
        y1 = self.pixmapItem.pos().y()
        y2 = y1 + h

        old_pos = self.pixmapItem.pos()
        scale_factor = self.ratio / old_ratio

        # 判断缩放中心
        if (x1 < event.scenePos().x() < x2) and (y1 < event.scenePos().y() < y2):
            # 1. 以鼠标位置为中心缩放
            # 计算鼠标相对于图元左上角的位置
            mouse_rel_pos = event.scenePos() - old_pos
            # 计算新的偏移量，以保持鼠标下的点在屏幕上位置不变
            new_mouse_rel_pos = mouse_rel_pos * scale_factor
            offset = new_mouse_rel_pos - mouse_rel_pos
            new_pos = old_pos - offset
        else:
            # 2. 以图像中心为中心缩放
            # 计算旧的中心点
            old_center = old_pos + QPointF(w / 2, h / 2)
            # 计算新的中心点应该在哪里
            new_center = old_center
            # 计算新尺寸
            new_w = self.pixmap.size().width() * self.ratio
            new_h = self.pixmap.size().height() * self.ratio
            # 根据新中心和新尺寸计算新左上角位置
            new_pos = new_center - QPointF(new_w / 2, new_h / 2)

        # 应用新的缩放和位置
        self.pixmapItem.setScale(self.ratio)
        self.pixmapItem.setPos(new_pos)

        # 不再需要手动更新、删除或重新创建任何 CustomRectItem
        # 下面这一大段代码都可以安全删除

        # # 更新标注框  <--- 以下所有代码块都应删除
        # if self.rect_info_raw:
        #     for i, rect_item in enumerate(self.rect_items):
        #         self.scene.removeItem(rect_item)
        #     self.rect_items.clear()
        #     # ... (所有重新加载和创建 rect_item 的代码) ...
        #
        # self.update_rect_items(True)
        # self.scene.update()

        # --- 核心修改结束 ---

    def label_and_comment_dialog(self):
        dialog = LabelDialog()
        if dialog.exec_() == QDialog.Accepted:
            label, comment = dialog.get_values()
            self.current_rect.label = label
            self.current_rect.comment = comment
            self.current_rect.radio_start = self.ratio
            self.rect_items.append(self.current_rect)
            # 同步更新rectInfo
            self.sync_rect_info_from_items()
            self.update_rect_items(True)
            print("添加标注框成功！")
        else:
            # 用户取消了对话框，需要从场景中删除矩形
            if self.current_rect and self.current_rect.scene():
                self.scene.removeItem(self.current_rect)
            print("取消添加标注框")

    def update_rect_items(self, isUpdateLabel):
        """更新方框信息，包括标签信息和位置信息"""
        # 如果要更新标签信息，先把方框listWidget全部清空
        if isUpdateLabel:
            self.listWidget.clear()

        # 再遍历对rect_items列表，添加到方框listWidget中
        for item in self.rect_items:
            # 获取矩形的左上角和右下角点相对于场景的坐标
            top_left = item.rect().topLeft()
            bottom_right = item.rect().bottomRight()
            # 将场景坐标转换为pixmapItem的坐标
            # self.pixmapItem.mapFromScene(item.mapToScene(top_left))
            # self.pixmapItem.mapFromScene(item.mapToScene(bottom_right))
            x_min = int(self.pixmapItem.mapFromScene(item.mapToScene(item.rect().topLeft())).x())
            y_min = int(self.pixmapItem.mapFromScene(item.mapToScene(item.rect().topLeft())).y())
            x_max = int(self.pixmapItem.mapFromScene(item.mapToScene(item.rect().bottomRight())).x())
            y_max = int(self.pixmapItem.mapFromScene(item.mapToScene(item.rect().bottomRight())).y())
            width, height = x_max-x_min, y_max-y_min
            # 如果更新标签信息
            if isUpdateLabel:
                # print("更新listWidget！")
                listWidgetItem = QListWidgetItem(f"Label: {item.label}, Comment: {item.comment}, ({width}, {height})")
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

    def set_exclude_mode(self, enabled: bool):
        """设置或取消“选择排除区域”模式"""
        self.is_excluding_pixels = enabled
        if enabled:
            self.graphicsView.setCursor(Qt.CrossCursor)
        else:
            self.graphicsView.setCursor(Qt.ArrowCursor)

    def load_exclude_config(self):
        """从 config.json 加载排除区域"""
        config_path = os.path.join('Sources', 'config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 确保坐标是数字
                    self.exclude_rects = [
                        [float(p) for p in rect]
                        for rect in config.get('exclude_pix', [])
                    ]
            except (json.JSONDecodeError, IOError, ValueError) as e:
                print(f"加载排除区域配置失败: {e}")
                self.exclude_rects = []

    def save_exclude_rect(self, rect: QRectF):
        """将新的排除区域保存到 config.json"""
        config_path = os.path.join('Sources', 'config.json')
        os.makedirs('Sources', exist_ok=True)
        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass  # 文件存在但为空或损坏，当作新文件处理

        # 获取相对于图像原始尺寸的坐标
        # 由于绘制的矩形是 pixmapItem 的子项，其 rect() 已经是局部坐标，即原始图像坐标
        x_min = rect.left()
        y_min = rect.top()
        x_max = rect.right()
        y_max = rect.bottom()

        new_rect_coords = [x_min, y_min, x_max, y_max]

        if 'exclude_pix' not in config:
            config['exclude_pix'] = []

        config['exclude_pix'].append(new_rect_coords)

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            print(f"已保存新的排除区域: {new_rect_coords}")
            # 1. 重新加载配置
            self.load_exclude_config()

            # 2. 调用统一的、正确的刷新函数
            self.refresh_annotations()
        except IOError as e:
            print(f"保存排除区域配置失败: {e}")


    def is_rect_excluded(self, xmin, ymin, xmax, ymax) -> bool:
        """
        检查给定的矩形坐标是否与任何排除区域重叠。
        如果启用自动排除，并且标注框与任何一个排除区域有交集，则返回 True。
        """
        # 1. 如果没有启用自动排除，则不进行任何操作
        if not self.auto_exclude_enabled:
            return False
        rect_center_x = (xmin + xmax) / 2
        rect_center_y = (ymin + ymax) / 2
        for ex_rect in self.exclude_rects:
            ex_xmin, ex_ymin, ex_xmax, ex_ymax = ex_rect
            print("标注框：", xmin, xmax, ymin, ymax)
            print("排除框：", ex_xmin, ex_xmax, ex_ymin, ex_ymax)
            if ex_xmin <= rect_center_x <= ex_xmax and ex_ymin <= rect_center_y <= ex_ymax:
                return True
        return False

    def set_auto_exclude_enabled(self, enabled: bool):
        """设置是否启用自动排除功能"""
        self.auto_exclude_enabled = enabled

    def clear_and_refresh_exclusions(self):
        """清空内存中的排除区域并刷新标注视图"""
        self.exclude_rects.clear()
        print("内存中的排除区域已清空。")
        self.refresh_annotations()

    def refresh_annotations(self):
        """根据当前的排除设置，刷新所有标注框的可见性"""
        if not self.rect_info_raw or self.pixmapItem is None:
            return

        # 移除所有现有标注框
        for item in self.rect_items:
            # 从父项中移除，而不是直接从场景中移除
            if item.parentItem() == self.pixmapItem:
                item.setParentItem(None)
            self.scene.removeItem(item)
        self.rect_items.clear()

        # 重新加载标注框
        label, xmin, ymin, xmax, ymax, comment_pose = self.rect_info_raw
        for index, lbl in enumerate(label):
            current_xmin, current_ymin, current_xmax, current_ymax = float(xmin[index]), float(
                ymin[index]), float(xmax[index]), float(ymax[index])

            # 检查是否应被排除
            if self.is_rect_excluded(current_xmin, current_ymin, current_xmax, current_ymax):
                continue  # 跳过此标注

            # 1. 使用相对于父项的局部坐标创建矩形
            rect_in_pixmap = QRectF(QPointF(current_xmin, current_ymin),
                                    QPointF(current_xmax, current_ymax))

            # 2. 创建 CustomRectItem 时，明确指定父项
            rect_item = CustomRectItem(rect_in_pixmap,
                                       self,
                                       label=lbl,
                                       comment=comment_pose[index],
                                       parent=self.pixmapItem)  # <-- 关键：设置父项

            # 3. 不需要再调用 self.scene.addItem(rect_item)，因为父项会自动管理子项
            self.rect_items.append(rect_item)

        # 更新UI
        self.update_rect_items(True)
        self.scene.update()
        print("标注框已根据排除设置刷新。")

    def eventFilter(self, obj, event):
        if obj in (self.graphicsView, self.graphicsView.viewport()):
            if event.type() == QtCore.QEvent.MouseMove:
                if self.drawing or self.moving or self.resizing:
                    self._clear_hover_state()
                else:
                    self._update_hover_state(event)
            elif event.type() == QtCore.QEvent.Leave:
                self._clear_hover_state()
            elif event.type() == QtCore.QEvent.KeyPress and event.key() == Qt.Key_Delete:
                if self.hovered_rect and not self.is_merge:
                    self.hovered_rect.delete_item()
                    self.hovered_rect = None
                    return True
        return super().eventFilter(obj, event)

    def _update_hover_state(self, event):
        scene_pos = self.graphicsView.mapToScene(event.pos())
        item = self.scene.itemAt(scene_pos, QtGui.QTransform())
        if isinstance(item, CustomRectItem):
            if item is not self.hovered_rect:
                if self.hovered_rect:
                    self.hovered_rect.set_hovered(False)
                self.hovered_rect = item
                self.hovered_rect.set_hovered(True)
        else:
            self._clear_hover_state()

    def _clear_hover_state(self):
        if self.hovered_rect:
            self.hovered_rect.set_hovered(False)
            self.hovered_rect = None

    def _set_hover_rect(self, rect_item: Optional['CustomRectItem']):
        if self.drawing or self.moving or self.resizing:
            self._clear_hover_state()
            return
        if rect_item is self.hovered_rect:
            return
        if self.hovered_rect:
            self.hovered_rect.set_hovered(False)
        self.hovered_rect = rect_item
        if self.hovered_rect:
            self.hovered_rect.set_hovered(True)


class CustomRectItem(QGraphicsRectItem):
    default_pen_width = 1
    default_pen_color = QColor(Qt.red)
    default_brush_color = QColor(Qt.transparent)

    def __init__(self, rect: QRectF, img_win: 'IMG_WIN', label='', comment='', radio_start=1, parent=None):
        super().__init__(rect, parent)
        self.pen_width = CustomRectItem.default_pen_width
        self.brush_color = CustomRectItem.default_brush_color
        self.pen_color = QColor(Qt.red)
        self.img_win = img_win
        self.pixmapItem = self.img_win.get_pixmapItem()
        self.label = label
        self.comment = comment
        self._comment = comment  # 私有变量存储实际数据，comment变化时自动更新方框颜色
        self.radio_start = radio_start
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

        # 为调整大小操作初始化属性
        self.initial_mouse_pos = QPointF()
        self.initial_rect = QRectF()
        self.initial_pos = QPointF()  # 为拖动操作初始化位置属性

        # 启用实时几何变化通知
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)

        self.is_hovered = False
        self.hover_pen = QPen(QColor(Qt.white), max(self.pen_width + 1, 2))


    @property
    def comment(self):
        return self._comment

    @comment.setter
    def comment(self, value):
        """当comment被修改时自动调用该方法更新颜色"""
        self._comment = value
        self.set_pen_color_from_comment()

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
        if self.is_hovered:
            painter.setPen(self.hover_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.rect())
        super().paint(painter, option, widget)
        painter.setPen(self.default_pen_color)
        font = painter.font()
        font.setFamily("Microsoft YaHei")
        font.setPointSize(6)
        painter.setFont(font)
        # 构建要显示的文本
        display_text = self.label

        # 实时计算宽高信息
        # top_left = self.mapToScene(self.rect().topLeft())
        # bottom_right = self.mapToScene(self.rect().bottomRight())

        # x_min = int(self.pixmapItem.mapFromScene(top_left).x())
        # y_min = int(self.pixmapItem.mapFromScene(top_left).y())
        # x_max = int(self.pixmapItem.mapFromScene(bottom_right).x())
        # y_max = int(self.pixmapItem.mapFromScene(bottom_right).y())

        # width = abs(x_max - x_min)
        # height = abs(y_max - y_min)
        # display_text += f" (w, h)=({width},{height})"

        # 绘制文本，位置在框的左上角上方
        text_position = self.rect().topLeft() + QPointF(0, -5)  # 调整位置偏移
        painter.drawText(text_position, display_text)
        # self.update_info(True)    # 会导致循环调用

    def hoverMoveEvent(self, event):
        cursor = self.get_cursor_shape(event.pos())
        self.setCursor(cursor)

    def get_cursor_shape(self, pos):
        # 转换坐标到局部坐标系
        local_pos = self.mapFromScene(pos)
        rect = self.rect()
        margin = 5  # 边界的宽度，可以根据需要调整

        # 检查鼠标是否在右下角
        if abs(local_pos.x() - rect.right()) <= margin and abs(local_pos.y() - rect.bottom()) <= margin:
            return Qt.SizeFDiagCursor  # 斜向箭头，适合右下角调整

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

    def showCustomMenu(self, event):
        """中键菜单栏"""
        menu = QMenu()

        change_color_action = menu.addAction("改变颜色")
        change_color_action.triggered.connect(lambda: self.change_color())

        change_width_action = menu.addAction("改变线宽")
        change_width_action.triggered.connect(lambda: self.change_line_width())

        change_to_manual = menu.addAction("修改为人工标注")
        change_to_manual.triggered.connect(lambda: self.change_to_manual())

        # change_to_auto = menu.addAction("修改为机器标注")
        # change_to_auto.triggered.connect(lambda: self.change_to_auto())

        # 定义标签菜单
        label_menu = menu.addMenu("修改标签")
        try:
            with open("./Sources/label_info.txt", "r", encoding="utf-8") as file:
                labels = file.read().splitlines()

            for label in labels:
                if label.strip():
                    label_action = label_menu.addAction(label)
                    label_action.triggered.connect(lambda checked=False, lbl=label: self.change_label(lbl))
        except Exception as e:
            error_action = label_menu.addAction(f"读取文件错误: {str(e)}")
            error_action.setEnabled(False)

        delete_action = menu.addAction("删除")
        delete_action.triggered.connect(lambda: self.delete_item())

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
            # 查找当前项在rect_items中的索引
            if self in self.img_win.rect_items:
                index = self.img_win.rect_items.index(self)

                # 更新rectInfo，从各个列表中删除对应索引的数据
                if self.img_win.rect_info_raw:
                    label, xmin, ymin, xmax, ymax, comment_pose = self.img_win.rect_info_raw
                    if index < len(label):
                        label.pop(index)
                        xmin.pop(index)
                        ymin.pop(index)
                        xmax.pop(index)
                        ymax.pop(index)
                        comment_pose.pop(index)
                        # 重新保存更新后的rectInfo
                        self.img_win.rect_info_raw = [label, xmin, ymin, xmax, ymax, comment_pose]

                # 从scene和rect_items中删除
                scene.removeItem(self)
                self.img_win.rect_items.remove(self)
                self.img_win.update_rect_items(True)
                self.img_win.set_dirty()  # 删除后设置脏标记
                scene.update()

    def change_to_manual(self):
        """修改为人工标注"""
        self.comment = "None"
        # 修改 listWidget_label中对应的项
        if self in self.img_win.rect_items:
            self.img_win.update_rect_items(True)
            self.img_win.sync_rect_info_from_items()

    def change_to_auto(self):
        """修改为自动检测"""
        self.comment = "自动检测"
        if self in self.img_win.rect_items:
            self.img_win.update_rect_items(True)
            self.img_win.sync_rect_info_from_items()

    def change_label(self, new_label):
        """修改方框的标签"""
        self.label = new_label
        # 更新列表显示
        if self in self.img_win.rect_items:
            self.img_win.update_rect_items(True)
            self.img_win.sync_rect_info_from_items()
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
            self.update_info(True)  # 传递实时更新标志
            self.scene().update()  # 强制场景立即更新
        return super().itemChange(change, value)

    # 更新方框信息
    def update_info(self, isUpdateLabel: bool):
        # self.scene().parent().update_rect_items(isUpdateLabel)
        self.img_win.update_rect_items(isUpdateLabel)
        self.update()

    def update_info_label(self, label, comment):
        self.label = label
        self.comment = comment

    def set_hovered(self, hovered: bool):
        self.is_hovered = hovered
        self.update()

