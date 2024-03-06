import sys

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QLineEdit, QToolBar, QGroupBox, QGridLayout,
    QCheckBox, QHBoxLayout,
)

from gcode_builder import GrowboxGCodeBuilder


class MainWindow(QMainWindow):
    def start_menubar(self):
        menu = self.menuBar()

        button_action_open = QAction('Открыть из файла', self)
        button_action_save = QAction('Сохранить в файл', self)
        button_action_connect_by_serial = QAction('Добавить по Serial', self)
        button_action_connect_by_web = QAction('Добавить по WEB', self)
        button_action_send_gcode = QAction('Открыть из файла и послать в гроубокс', self)

        menu_file = menu.addMenu('G-code')
        menu_connect = menu.addMenu('Гроубоксы')

        menu_file.addAction(button_action_open)
        menu_file.addAction(button_action_send_gcode)
        menu_file.addAction(button_action_save)
        menu_connect.addAction(button_action_connect_by_serial)
        menu_connect.addAction(button_action_connect_by_web)

    def build_groupbox_sensors(self):
        layout = QGridLayout()

        layout.addWidget(QLabel('Влажность:'), 0, 0)
        layout.addWidget(QLabel('75%'), 0, 1)

        layout.addWidget(QLabel('Температура:'), 1, 0)
        layout.addWidget(QLabel('25С'), 1, 1)

        groupbox = QGroupBox('Показания датчиков')
        groupbox.setLayout(layout)
        return groupbox

    def build_groupbox_actuators(self):
        layout = QGridLayout()

        layout.addWidget(QLabel('Белый свет:'), 0, 0)
        layout.addWidget(QLabel('0'), 0, 1)
        layout.addWidget(QPushButton('✎'), 0, 2)

        layout.addWidget(QLabel('Вытяжка:'), 1, 0)
        layout.addWidget(QLabel('0'), 1, 1)
        layout.addWidget(QPushButton('✎'), 1, 2)

        layout.addWidget(QLabel('Увлажнитель:'), 2, 0)
        layout.addWidget(QLabel('0'), 2, 1)
        layout.addWidget(QPushButton('✎'), 2, 2)

        groupbox = QGroupBox('Исполнительные устройства')
        groupbox.setLayout(layout)
        return groupbox

    def build_autos_layout(self):
        layout = QHBoxLayout()
        layout.addWidget(QCheckBox())
        layout.addWidget(QPushButton('✎'))
        return layout

    def build_groupbox_autos(self):
        layout = QVBoxLayout()
        layout.addWidget(QPushButton('Выключить всю автоматику'))

        layout_table = QGridLayout()

        layout_table.addWidget(QLabel('Устройство'), 0, 0)
        layout_table.addWidget(QLabel('Резкий переход'), 0, 1)
        layout_table.addWidget(QLabel('Плавный переход'), 0, 2)
        layout_table.addWidget(QLabel('Климат-контроль'), 0, 3)

        for actuator_index, actuator_name in enumerate(['Белый свет', 'Вытяжка', 'Увлажнитель']):
            layout_table.addWidget(QLabel(actuator_name), actuator_index + 1, 0)
            layout_table.addLayout(self.build_autos_layout(), actuator_index + 1, 1)
            layout_table.addLayout(self.build_autos_layout(), actuator_index + 1, 2)
            layout_table.addLayout(self.build_autos_layout(), actuator_index + 1, 3)

        layout.addLayout(layout_table)

        groupbox = QGroupBox('Автоматика')
        groupbox.setLayout(layout)
        return groupbox

    def __init__(self):
        super().__init__()

        self.setWindowTitle('CNC Growbox')
        layout = QVBoxLayout()

        groupbox_sensors = self.build_groupbox_sensors()
        layout.addWidget(groupbox_sensors)

        groupbox_actuators = self.build_groupbox_actuators()
        layout.addWidget(groupbox_actuators)

        groupbox_autos = self.build_groupbox_autos()
        layout.addWidget(groupbox_autos)

        layout.addWidget(QLabel('Секунд с момента включения:'))
        layout.addWidget(QPushButton('Обновить показания'))

        widget = QWidget()
        widget.setLayout(layout)

        self.setCentralWidget(widget)

        self.start_menubar()


def run():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()
    gcode = GrowboxGCodeBuilder()


if __name__ == '__main__':
    run()
