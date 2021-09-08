from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QEvent, QRect, QRectF, QPointF, QSize, Qt, QPoint, QMargins, QLine
from PyQt5.QtGui import QPen, QPainter, QPainterPath, QFontMetrics, QColor, QVector2D
from PyQt5 import QtGui


class GraphicsScene(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.installEventFilter(self)

        self.guidelines = list()
        self.guidelines.append(QLine(QPoint(50, 50), QPoint(590, 50)))
        self.guidelines.append(QLine(QPoint(50, 75), QPoint(590, 75)))
        self.guidelines.append(QLine(QPoint(50, 100), QPoint(50, 420)))
        self.wiring_assistant = True
        self.closest_point = None

        self.selected_elements = list()
        self.moved = False
        self._hoveredElement = None
        self.grabbed_element = None
        self.grab_offset = None

        # In addElement function every new element is assigned zValue=(self.nextZValue + 0.001)
        # Note that 0.001 is used so that self.nextZValue will probably never overflow.
        self._nextZValue = 0.0

        self.elements = list()
        notElement = NotElement(self)
        notElement.setPosition(QPoint(290, 300))
        self.addElement(notElement)
        for i in range(4):
            element = SquareElement(self)
            element.setPosition(QPoint(i*85 + 150, 100))
            self.addElement(element)
        self.selectionElement = SelectionElement(self)

    def addElement(self, element):
        self._nextZValue = self._nextZValue + 0.001  # This will probably never overflow.
        element.setZValue(self._nextZValue)
        self.elements.append(element)
        # Sort elements in descending order so that _pick function can pick an element with highest zValue first.
        # This will help in the cases when there are elements on top of each other.
        self.elements.sort(key=lambda x: x.getZValue(), reverse=True)  # Descending Order based on zValue.

    def removeElement(self, element):
        if element in self.elements:
            self.elements.remove(element)
            self.update()

    def paintEvent(self, *args):
        print("paint")
        painter = QPainter(self)
        painter.setRenderHint(QPainter.HighQualityAntialiasing)

        r = self.rect()
        painter.fillRect(r, Qt.white)

        for element in reversed(self.elements):  # draw elements with lowest zValue first, hence, reversed.
            painter.translate(element.boundingBox.topLeft())
            # save the painter state so that any leftover brushes, pen, transformations effects by an element may not
            # affect other elements.
            painter.save()
            element.paint(painter)
            painter.restore()
            painter.translate(-element.boundingBox.topLeft())

        self.selectionElement.paint(painter)

        if self.wiring_assistant:
            painter.setPen(QPen(Qt.red, 1, Qt.PenStyle.DotLine))
            painter.setBrush(QColor(255, 128, 0))
            for line in self.guidelines:
                painter.drawLine(line)

            painter.setPen(QPen(Qt.red, 1, Qt.PenStyle.SolidLine))
            if self.closest_point is not None:
                p = self.closest_point
                painter.drawEllipse(p.x() - 4, p.y() - 4, 8, 8)

    def _closest_point(self, line, point):
        d = QVector2D(line.p2() - line.p1())
        d.normalize()
        v = QVector2D(point - line.p1())
        return line.p1() + (d * QVector2D.dotProduct(d, v)).toPoint()

    def _closest_guideline_point(self, point):
        currDistance = None
        closest = None
        for line in self.guidelines:
            p = self._closest_point(line, point)
            d = QVector2D(p - point).lengthSquared()
            if (currDistance is None or d < currDistance) and d < 200:
                # Discard if point p is outside line bounding rectangle.
                # If we don't discard then the point is drawn on the infinitely extended virtual line outside of the
                # bounding rectangle of line. This logic can be improved further.
                rect = QRect(line.p1(), line.p2())
                if rect.contains(p):
                    currDistance = d
                    closest = p
        return closest

    def eventFilter(self, widget, event):
        # The following logic solves problems of TWO Scenarios:
        # Scenario 1:
        # If an element is at the edge of the GraphicsScene or overlapping the GraphicsScene bounding box, now if mouse
        # pointer is moved over the element then the logic for hovering of an element in mouseMoveEvent generates
        # onEnter call for that element but now if the mouse pointer is moved outside of the GraphicsScene then as the
        # mouseMoveEvent is not generated anymore so onLeave call would not be generated for that element. But in this
        # case as you can imagine that the mouse pointer would not be over that element so onLeave call must be called
        # for that element.
        # Scenario 2:
        # While mouse pointer is over an element, now if you switch applications using ALT+TAB then onLeave call should
        # be generated for the previously hovered element.
        # While mouse pointer is over the position of an element but the application is in background, now if you switch
        # applications using ALT+TAB and bring the application utilizing GraphicsScene to front then we should generate
        # onEnter call for the element over which there is mouse pointer.
        # Solution:
        # In both scenarios, QEvent.Leave and QEvent.Enter are generated so the corresponding scenarios are handled in
        # the following logic.
        if event.type() == QEvent.Leave:
            if self._hoveredElement is not None:
                self._hoveredElement.onLeave()
                self._hoveredElement = None
                self.repaint()
        elif event.type() == QEvent.Enter:
            cursorPos = self.mapFromGlobal(QtGui.QCursor().pos())
            if self.rect().contains(cursorPos):
                if self.hoverElements(cursorPos):
                    self.repaint()
            elif self._hoveredElement is not None:
                self._hoveredElement.onLeave()
                self._hoveredElement = None
                self.repaint()

        return super(GraphicsScene, self).eventFilter(widget, event)

    def _pick(self, p):
        for element in self.elements:
            if element.boundingBox.contains(p):
                return element
        return None

    def hoverElements(self, pos):
        update = False
        element = self._pick(pos)
        if element is not None:
            if self._hoveredElement is None:
                self._hoveredElement = element
                self._hoveredElement.onEnter()
                update = True
            elif element is not self._hoveredElement:
                self._hoveredElement.onLeave()
                self._hoveredElement = element
                self._hoveredElement.onEnter()
                update = True
        elif self._hoveredElement is not None:
            self._hoveredElement.onLeave()
            self._hoveredElement = None
            update = True
        return update

    def mousePressEvent(self, e):
        self.grabbed_element = self._pick(e.pos())
        if self.grabbed_element is not None:
            self.grab_offset = self.grabbed_element.boundingBox.topLeft() - e.pos()

    def mouseReleaseEvent(self, e):
        moved = self.moved

        if self.grabbed_element is not None:
            self.grabbed_element = None
            self.moved = False

        if not moved:
            self.selected_elements = list()
            for element in self.elements:  # select an element with highest zValue.
                bb = element.boundingBox
                if bb.contains(e.pos()):
                    self.selected_elements.append(element)
                    break
            self.update()

    def mouseMoveEvent(self, e):
        update = False
        # onEnter would already have been called for the grabbed element, so we don't check again if there is already
        # a grabbed element.
        # This also avoid unnecessary onLeave and onEnter calls when the mouse is quickly moved while an element is
        # being grabbed. Those calls are generated because when mouse is quickly moved then the mouse pointer location
        # gets beyond the element's bounding rectangle(used in _pick function) momentarily.
        if self.grabbed_element is None:
            if self.hoverElements(e.pos()):
                update = True
        else:  # move the grabbed element with the mouse.
            self.grabbed_element.boundingBox.moveTopLeft(e.pos() + self.grab_offset)
            self.moved = True
            update = True

        if self.wiring_assistant:
            self.closest_point = self._closest_guideline_point(e.pos())
            if self.closest_point is not None:
                update = True

        if update:
            self.update()

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_W:
            self.wiring_assistant ^= True
            self.update()

class Element:
    def __init__(self, parent):
        self.parent = parent
        self.size = QSize(75, 75)
        self._zValue = float(0.0)
        self.boundingBox = QRect()

    def paint(self, painter):
        raise NotImplementedError

    def update(self):
        self.parent.update()

    # Accepts QPoint is pos parameter.
    def setPosition(self, pos):
        self.boundingBox.moveTopLeft(pos)
        self.update()

    def setZValue(self, value):
        self._zValue = value
        self.update()

    def getZValue(self):
        return self._zValue;

    def getPosition(self):
        self.boundingBox.topLeft()

    def onEnter(self):
        pass

    def onLeave(self):
        pass


class NotElement(Element):
    def __init__(self, parent):
        super().__init__(parent)
        self.boundingBox = QRect(QPoint(), self.size)
        self.color = Qt.white

    def paint(self, painter):
        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(self.color)

        path = QPainterPath()
        path.moveTo(QPoint())
        path.lineTo(QPoint(self.size.width() - 5, self.size.height() / 2))
        path.lineTo(QPoint(0, self.size.height()))
        path.closeSubpath()
        painter.drawPath(path)

        painter.drawEllipse(QPoint(self.size.width() - 2, self.size.height() / 2), 3, 3)

    def onEnter(self):
        self.color = Qt.green

    def onLeave(self):
        self.color = Qt.white


class SquareElement(Element):
    def __init__(self, parent):
        super().__init__(parent)
        self.boundingBox = QRect(QPoint(), self.size)
        self.color = Qt.white

    def paint(self, painter):
        painter.setPen(QPen(Qt.black, 2))
        painter.setBrush(self.color)

        path = QPainterPath()
        path.moveTo(QPoint())
        path.lineTo(QPoint(self.size.width(), 0))
        path.lineTo(QPoint(self.size.width(), self.size.height()))
        path.lineTo(QPoint(0, self.size.height()))
        path.closeSubpath()
        painter.drawPath(path)

        text = "HELLO"
        fontMetrics = painter.fontMetrics()
        textRect = fontMetrics.tightBoundingRect(text)
        painter.drawText((self.size.width()-textRect.width())/2, (self.size.height()+textRect.height())/2, text)

    def onEnter(self):
        self.color = Qt.green

    def onLeave(self):
        self.color = Qt.white


class SelectionElement(Element):
    def __init__(self, parent):
        super().__init__(parent)

    def paint(self, painter):
        painter.setPen(QPen(Qt.red, 1, Qt.DashLine))
        painter.setBrush(Qt.transparent)
        for element in self.parent.selected_elements:
            self.boundingBox = element.boundingBox
            self.boundingBox = self.boundingBox.marginsAdded(QMargins(2, 2, 1, 1))
            painter.drawRect(self.boundingBox)

