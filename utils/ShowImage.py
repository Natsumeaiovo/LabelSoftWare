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
from PySide2.QtGui import QPen, QBrush, QColor, QIcon
from PySide2.QtGui import Qt
from PySide2.QtUiTools import QUiLoader
from PySide2.QtWidgets import QDialog, QListWidget
from PySide2.QtWidgets import QGraphicsView, QGraphicsRectItem, QGraphicsItem, QColorDialog, QInputDialog, QMenu
from PySide2.QtWidgets import QWidget, QListWidgetItem, QGraphicsPixmapItem

from utils import FromXML
from utils.ShowDCMName import ImageNameList
from widgets.LabelDialog import LabelDialog
from widgets.CustomRectItem import CustomRectItem, graphics_item_is_valid


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

        # =========================
        # Measure mode (overlay layer)
        # =========================
        self.is_measuring = False
        self._measure_points: List[QPointF] = []  # pixmapItem local coords
        self._measure_items = []  # QGraphicsItem (line/text)
        self._rect_item_interaction_state = {}  # id(item) -> (flags, acceptedButtons)

        # 参数：用于 mm 计算。由 MainDcmLabel.change_scale() 同步更新
        self.image_plate_size_um = 100.0
        self.scale_ratio = 1.0

    def set_measure_scale_params(self, image_plate_size_um: float, scale_ratio: float):
        """同步测量计算参数（保持低侵入：仅缓存，不触发重绘）。"""
        try:
            self.image_plate_size_um = float(image_plate_size_um)
        except Exception:
            # 保持旧值
            pass
        try:
            self.scale_ratio = float(scale_ratio)
        except Exception:
            pass

    def set_measure_mode(self, enabled: bool):
        """切换测量模式：开启则禁用标注框交互并接管右键；关闭则恢复并清除测量线。"""
        self.is_measuring = bool(enabled)

        # 清理未完成的点
        self._measure_points.clear()

        if self.is_measuring:
            # 和“排除坏点模式”互斥：测量优先（避免右键冲突）
            if self.is_excluding_pixels:
                self.set_exclude_mode(False)
            self.graphicsView.setCursor(Qt.CrossCursor)
            self._disable_rect_item_interactions()
        else:
            self.graphicsView.setCursor(Qt.ArrowCursor)
            self._restore_rect_item_interactions()
            self.clear_measurements()

    def clear_measurements(self):
        """清除场景内所有测量线段与文字。"""
        self._measure_points.clear()
        for it in list(self._measure_items):
            try:
                if it is not None and it.scene() is not None:
                    self.scene.removeItem(it)
            except Exception:
                pass
        self._measure_items.clear()
        self.scene.update()

    def _disable_rect_item_interactions(self):
        """测量模式下让所有标注框对鼠标不响应"""
        self._rect_item_interaction_state.clear()
        for item in self.rect_items:
            try:
                self._rect_item_interaction_state[id(item)] = (item.flags(), item.acceptedMouseButtons())
                item.setFlag(QGraphicsItem.ItemIsMovable, False)
                item.setFlag(QGraphicsItem.ItemIsSelectable, False)
                item.setAcceptedMouseButtons(Qt.NoButton)
            except Exception:
                pass

    def _restore_rect_item_interactions(self):
        """恢复测量模式前的标注框交互状态。"""
        if not self._rect_item_interaction_state:
            return
        for item in self.rect_items:
            state = self._rect_item_interaction_state.get(id(item))
            if not state:
                continue
            flags, accepted = state
            try:
                item.setFlags(flags)
                item.setAcceptedMouseButtons(accepted)
            except Exception:
                pass
        self._rect_item_interaction_state.clear()

    def _add_measurement(self, p1_local: QPointF, p2_local: QPointF):
        """在 pixmapItem 局部坐标系中添加一条测量线和长度文字。"""
        if self.pixmapItem is None:
            return

        dx = p2_local.x() - p1_local.x()
        dy = p2_local.y() - p1_local.y()
        pixel_len = float((dx * dx + dy * dy) ** 0.5)

        # 线段长度(mm)=线段像素数*image_plate_size_um/1000 * self.scale_ratio
        try:
            mm_len = pixel_len * (float(self.image_plate_size_um) / 1000.0) * float(self.scale_ratio)
        except Exception:
            mm_len = 0.0

        line_item = QtWidgets.QGraphicsLineItem(QtCore.QLineF(p1_local, p2_local), parent=self.pixmapItem)
        pen = QPen(QColor(0, 255, 0))
        pen.setWidth(2)
        line_item.setPen(pen)
        line_item.setZValue(10_000)

        text_item = QtWidgets.QGraphicsSimpleTextItem(f"{mm_len:.2f} mm", parent=self.pixmapItem)
        text_item.setBrush(QBrush(QColor(0, 255, 0)))
        text_item.setZValue(10_001)

        # 文字统一放在线段末尾（终点 p2）附近
        end_pt = p2_local
        dx2 = p2_local.x() - p1_local.x()
        dy2 = p2_local.y() - p1_local.y()
        norm = float((dx2 * dx2 + dy2 * dy2) ** 0.5)
        if norm > 1e-6:
            # 垂直方向单位向量 ( -dy, dx )
            nx = -dy2 / norm
            ny = dx2 / norm
        else:
            nx, ny = 1.0, 0.0

        offset = QPointF(nx * 8.0, ny * 8.0) + QPointF(4.0, 4.0)
        text_item.setPos(end_pt + offset)

        self._measure_items.extend([line_item, text_item])
        self.scene.update()

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
            # scene.clear() 会删除所有 QGraphicsItem（包含 CustomRectItem 的 C++ 对象）。
            # 先清理 hover 引用，避免后续 mouseMove/leave 还调用到已删除对象。
            self._clear_hover_state(force=True)
            self.scene.clear()
            self.rect_items.clear()
            self.listWidget.clear()
            self.pixmapItem = self.scene.addPixmap(self.pixmap)  # 添加图元
            self.sync_rect_info_from_items()  # 同步更新rectInfo

            # 切换图片时：测量线也应一起清掉（避免残留）
            self.clear_measurements()

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
                label, xmin, ymin, xmax, ymax, comment_pose, level, size = analysis_result
                img_width, img_height = size

                if not all([label, xmin, ymin, xmax, ymax]):
                    return

                # 将解析的数据转换为box列表
                boxes = []
                for i in range(len(label)):
                    boxes.append([
                        float(xmin[i]), float(ymin[i]), float(xmax[i]), float(ymax[i]),
                        label[i], comment_pose[i], level[i]
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
                    level = [str(b[6]) for b in boxes]

                self.rect_info_raw = [label, xmin, ymin, xmax, ymax, comment_pose, level]
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
                                                       label=lbl, comment=comment_pose[index], level=level[index],
                                                       parent=self.pixmapItem)  # 设置父项
                    # self.scene.addItem(self.current_rect) # 不再需要，因为父项已在场景中

                    self.current_rect.label = lbl
                    self.current_rect.comment = comment_pose[index]
                    self.current_rect.level = level[index]
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
        levels = []

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
            levels.append(str(getattr(item, "level", "0")))

        self.rect_info_raw = [labels, xmins, ymins, xmaxs, ymaxs, comments, levels]
        self.set_dirty()  # 在同步数据后，将数据标记为“脏”


    def set_dirty(self, dirty=True):
        """设置脏标记，表示数据已修改"""
        self.is_dirty = dirty

    def scene_MousePressEvent(self, event):
        # 测量模式：右键接管测量；左键允许拖动图片
        if self.is_measuring:
            if event.buttons() & QtCore.Qt.LeftButton:
                # 复用原逻辑：记录拖动起点
                self.preMousePosition = event.scenePos()
                event.accept()
                return

            if event.button() == Qt.RightButton and self.pixmapItem is not None:
                p_local = self.pixmapItem.mapFromScene(event.scenePos())
                self._measure_points.append(p_local)
                if len(self._measure_points) == 2:
                    p1, p2 = self._measure_points
                    self._add_measurement(p1, p2)
                    self._measure_points.clear()
                event.accept()
                return

            event.ignore()
            return

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
        if self.is_measuring:
            # 测量模式下：放行左键拖动的释放；右键不进入原右键画框/移动/resize流程
            if event.button() in (Qt.LeftButton, Qt.RightButton):
                event.accept()
                return
            event.ignore()
            return
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
        if self.is_measuring:
            # 测量模式：允许左键拖动图片
            if event.buttons() & QtCore.Qt.LeftButton and self.pixmapItem is not None:
                # 与原左键拖动逻辑一致
                self.MouseMove = event.scenePos() - self.preMousePosition
                self.preMousePosition = event.scenePos()
                self.pixmapItem.setPos(self.pixmapItem.pos() + self.MouseMove)
                event.accept()
                return

            event.ignore()
            return
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
            label, comment, level = dialog.get_values()
            self.current_rect.label = label
            self.current_rect.comment = comment
            self.current_rect.level = level
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
                level = getattr(item, "level", "0")
                listWidgetItem = QListWidgetItem(
                    f"Label: {item.label}, Level: {level}, Comment: {item.comment}, ({width}, {height})"
                )
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

        # 兼容旧格式：
        # 1) "Label: xx, Comment: yy, (w,h)"
        # 2) "Label: xx, Level: ll, Comment: yy, (w,h)"
        label = ""
        comment = ""
        level = getattr(rect_item, "level", "0")

        try:
            # 去掉末尾尺寸信息
            if ", (" in text:
                text_wo_size = text.split(", (", 1)[0]
            else:
                text_wo_size = text

            # 提取 label
            if text_wo_size.startswith("Label: "):
                after_label = text_wo_size[len("Label: "):]
            else:
                after_label = text_wo_size

            if ", Comment: " in after_label:
                head, comment = after_label.split(", Comment: ", 1)
                # head 可能包含 ", Level: "
                if ", Level: " in head:
                    label, level = head.split(", Level: ", 1)
                else:
                    label = head
            else:
                # 没有 comment 的情况
                if ", Level: " in after_label:
                    label, level = after_label.split(", Level: ", 1)
                else:
                    label = after_label
        except Exception:
            # 任何解析失败，至少不让编辑崩掉
            label = text
            comment = ""

        rect_item.update_info_label(label.strip(), comment.strip())
        rect_item.level = level.strip()

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
        """
        根据当前的排除设置，刷新所有标注框的可见性
        """
        if not self.rect_info_raw or self.pixmapItem is None:
            return

        # 任何重建/移除都会让旧 hovered_rect 变成悬空引用
        self._clear_hover_state(force=True)

        # 移除所有现有标注框
        for item in self.rect_items:
            # 从父项中移除，而不是直接从场景中移除
            if item.parentItem() == self.pixmapItem:
                item.setParentItem(None)
            self.scene.removeItem(item)
        self.rect_items.clear()

        # 重新加载标注框
        # rect_info_raw 兼容旧结构：可能没有 level
        if len(self.rect_info_raw) >= 7:
            label, xmin, ymin, xmax, ymax, comment_pose, level = self.rect_info_raw
        else:
            label, xmin, ymin, xmax, ymax, comment_pose = self.rect_info_raw
            level = ["0"] * len(label)

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
                                       level=level[index] if index < len(level) else "0",
                                       parent=self.pixmapItem)  # <-- 关键：设置父项

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
                    # delete_item 内会处理 hovered_rect 清理
                    self.hovered_rect.delete_item()
                    self.hovered_rect = None
                    return True
        return super().eventFilter(obj, event)

    def _update_hover_state(self, event):
        scene_pos = self.graphicsView.mapToScene(event.pos())
        item = self.scene.itemAt(scene_pos, QtGui.QTransform())
        if isinstance(item, CustomRectItem):
            # itemAt 返回的 item 一定是当前 scene 中的有效 item
            if item is not self.hovered_rect:
                if self.hovered_rect and graphics_item_is_valid(self.hovered_rect):
                    try:
                        self.hovered_rect.set_hovered(False)
                    except RuntimeError:
                        # 已被删除，直接断引用
                        pass
                self.hovered_rect = item
                try:
                    self.hovered_rect.set_hovered(True)
                except RuntimeError:
                    self.hovered_rect = None
        else:
            self._clear_hover_state()

    def _clear_hover_state(self, force: bool = False):
        """Clear hovered state safely.

        force=True: 不管当前是否在 drawing/moving/resizing，也强制断开引用。
        """
        if not force and (self.drawing or self.moving or self.resizing):
            # 正在交互时不做额外操作
            pass
        if self.hovered_rect:
            if graphics_item_is_valid(self.hovered_rect):
                try:
                    self.hovered_rect.set_hovered(False)
                except RuntimeError:
                    # wrapper 已悬空
                    pass
            self.hovered_rect = None

    def _set_hover_rect(self, rect_item: Optional['CustomRectItem']):
        if self.drawing or self.moving or self.resizing:
            self._clear_hover_state()
            return
        if rect_item is self.hovered_rect:
            return
        if self.hovered_rect and graphics_item_is_valid(self.hovered_rect):
            try:
                self.hovered_rect.set_hovered(False)
            except RuntimeError:
                pass
        self.hovered_rect = rect_item if graphics_item_is_valid(rect_item) else None
        if self.hovered_rect:
            try:
                self.hovered_rect.set_hovered(True)
            except RuntimeError:
                self.hovered_rect = None

    def _merge_boxes(self, boxes, img_width, img_height):
        """合并重叠或邻近的标注框（仅合并相同 label）。

        boxes: [[xmin, ymin, xmax, ymax, label, comment, level], ...] 或 comment/level 可能缺省。
        返回同结构列表。
        """
        if not boxes:
            return []

        from collections import defaultdict

        grouped_boxes = defaultdict(list)
        for box in boxes:
            # label 在索引 4
            if len(box) < 5:
                continue
            grouped_boxes[box[4]].append(box)

        final_merged_boxes = []
        width_threshold = img_width * 0.05
        height_threshold = img_height * 0.05

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
                        h_dist = max(float(current_box[0]), float(other_box[0])) - min(float(current_box[2]), float(other_box[2]))
                        v_dist = max(float(current_box[1]), float(other_box[1])) - min(float(current_box[3]), float(other_box[3]))

                        # 框重叠或间距在阈值内则合并
                        if h_dist < width_threshold and v_dist < height_threshold:
                            current_box[0] = min(float(current_box[0]), float(other_box[0]))
                            current_box[1] = min(float(current_box[1]), float(other_box[1]))
                            current_box[2] = max(float(current_box[2]), float(other_box[2]))
                            current_box[3] = max(float(current_box[3]), float(other_box[3]))

                            # 合并注释（索引 5）
                            try:
                                if len(other_box) > 5 and other_box[5] and (len(current_box) <= 5 or other_box[5] not in current_box[5]):
                                    if len(current_box) <= 5 or not current_box[5]:
                                        # 确保 current_box 至少有 comment 位
                                        while len(current_box) <= 5:
                                            current_box.append("")
                                        current_box[5] = other_box[5]
                                    else:
                                        current_box[5] = f"{current_box[5]}_{other_box[5]}"
                            except Exception:
                                pass

                            used[j] = True
                            merged_in_group = True

                    new_group.append(current_box)

                group = new_group

            final_merged_boxes.extend(group)

        return final_merged_boxes

