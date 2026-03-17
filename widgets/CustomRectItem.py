from PySide2 import QtWidgets
from PySide2.QtCore import Qt, QRectF, QPointF
from PySide2.QtGui import QPen, QBrush, QColor, QIcon
from PySide2.QtGui import Qt
from PySide2.QtWidgets import QGraphicsRectItem, QGraphicsItem, QColorDialog, QInputDialog, QMenu
from PySide2.QtWidgets import QWidget


def graphics_item_is_valid(item) -> bool:
    """
    检查 QGraphicsItem 的底层 C++ 对象是否仍然有效。
    在 PySide2 中，如果底层对象已删除，访问属性会抛出 RuntimeError。
    """
    if item is None:
        return False
    try:
        # 尝试访问一个轻量级方法。如果对象已删除，PySide2 会在此处抛出 RuntimeError
        # 注意：这里并不一定要 item.scene() 不为 None，只要能访问不报错说明 C++ 对象还活着
        # 但通常 update 逻辑依赖于 scene 存在，所以此处维持原逻辑用来判断是否在场景中也是合理的
        item.scene()
        return True
    except RuntimeError:
        # 捕获 Internal C++ object ... already deleted
        return False

class CustomRectItem(QGraphicsRectItem):
    default_pen_width = 1
    default_pen_color = QColor(Qt.red)
    default_brush_color = QColor(Qt.transparent)

    def __init__(self, rect: QRectF, img_win: 'IMG_WIN', label='', comment='', level='0', radio_start=1, parent=None):
        super().__init__(rect, parent)
        self.pen_width = CustomRectItem.default_pen_width
        self.brush_color = CustomRectItem.default_brush_color
        self.pen_color = QColor(Qt.red)
        self.img_win = img_win
        self.pixmapItem = self.img_win.get_pixmapItem()
        self.label = label
        self.comment = comment
        self.level = str(level) if level is not None else '0'
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

        # 新增：评级
        change_level_action = menu.addAction("评级")
        change_level_action.triggered.connect(lambda: self.change_level())

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
        # 删除前如果它正处于 hovered 状态，先让 IMG_WIN 断开引用
        if hasattr(self, "img_win") and self.img_win is not None:
            try:
                if getattr(self.img_win, "hovered_rect", None) is self:
                    self.img_win._clear_hover_state(force=True)
            except Exception:
                pass

        scene = self.scene()
        if scene is not None:
            # 查找当前项在rect_items中的索引
            if self in self.img_win.rect_items:
                index = self.img_win.rect_items.index(self)

                # 更新rectInfo，从各个列表中删除对应索引的数据
                if self.img_win.rect_info_raw:
                    if len(self.img_win.rect_info_raw) >= 7:
                        label, xmin, ymin, xmax, ymax, comment_pose, level = self.img_win.rect_info_raw
                    else:
                        label, xmin, ymin, xmax, ymax, comment_pose = self.img_win.rect_info_raw
                        level = None

                    if index < len(label):
                        label.pop(index)
                        xmin.pop(index)
                        ymin.pop(index)
                        xmax.pop(index)
                        ymax.pop(index)
                        comment_pose.pop(index)
                        if level is not None and index < len(level):
                            level.pop(index)

                        # 重新保存更新后的rectInfo
                        if level is not None:
                            self.img_win.rect_info_raw = [label, xmin, ymin, xmax, ymax, comment_pose, level]
                        else:
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

    def change_level(self):
        """修改方框的评级(level)"""
        # 用一个临时 QWidget 来确保对话框是应用级模态且不会被 scene 卡住
        temp_widget = QWidget()
        temp_widget.setWindowIcon(QIcon("./Sources/intecast.ico"))
        temp_widget.setWindowModality(Qt.ApplicationModal)
        temp_widget.hide()

        current_level = str(getattr(self, "level", "0"))
        level_text, ok = QInputDialog.getText(
            temp_widget,
            "评级",
            "请输入评级:",
            QtWidgets.QLineEdit.Normal,
            current_level,
        )
        if ok:
            self.level = str(level_text).strip() if level_text is not None else ""
            # 同步到 rect_info_raw，并刷新 UI
            if hasattr(self, "img_win") and self.img_win is not None:
                self.img_win.sync_rect_info_from_items()
                self.img_win.update_rect_items(True)
            if self.scene():
                self.scene().update()
        temp_widget.deleteLater()

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
        # save_xml/refresh 可能会导致 item 被移除；此时不要再触发 UI update
        if not graphics_item_is_valid(self):
            return
        self.img_win.update_rect_items(isUpdateLabel)
        try:
            self.update()
        except RuntimeError:
            pass

    def update_info_label(self, label, comment):
        self.label = label
        self.comment = comment

    def set_hovered(self, hovered: bool):
        if not graphics_item_is_valid(self):
            return
        self.is_hovered = hovered
        try:
            self.update()
        except RuntimeError:
            pass