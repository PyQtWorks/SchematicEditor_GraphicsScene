from PyQt5.QtWidgets import QApplication, QMainWindow
from GraphicsScene import *
import sys

if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWindow = QMainWindow()
    mainWindow.setMinimumSize(640, 480)

    graphicsScene = GraphicsScene()
    mainWindow.setCentralWidget(graphicsScene)

    for i in range(4):
        element = SquareElement(graphicsScene)
        element.setPosition(QPoint(i * 85 + 150, 200))
        graphicsScene.addElement(element)

    mainWindow.setWindowTitle("Custom Graphics Scene")
    mainWindow.show()
    app.exec_()
