import sys

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QLineEdit, QToolBar, QGroupBox, QGridLayout,
    QCheckBox, QHBoxLayout, QDialog, QDialogButtonBox,
)

from gcode_builder import GrowboxGCodeBuilder


class ActuatorSetValueDialog(QDialog):
    def __init__(self, parent=None, text=''):
        super().__init__(parent)
        self.setWindowTitle(f'Новое значение для "{text}"')

        QBtn = QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        buttonBox = QDialogButtonBox(QBtn)
        buttonBox.clicked.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        layout = QVBoxLayout()
        self.input = QLineEdit()
        self.input.setInputMask(r'999')
        layout.addWidget(self.input)
        layout.addWidget(buttonBox)
        self.setLayout(layout)


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

    def btn_set_value_clicked(self, s, actuator_code, text):
        print('click', s)
        dlg = ActuatorSetValueDialog(self, text)
        if dlg.exec():
            print("Success!")
            print(actuator_code, dlg.input.text())
        else:
            print("Cancel!")

    def build_btn_set_value(self, layout, actuator_code, text, y):
        label = QLabel(text)
        layout.addWidget(label, y, 0)
        layout.addWidget(QLabel('0'), y, 1)
        button = QPushButton('✎')
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, actuator_code, text))
        layout.addWidget(button, y, 2)

    def build_groupbox_actuators(self):
        ACTUATOR_HUMID = 0
        ACTUATOR_EXTRACTOR = 1
        ACTUATOR_WHITE_LIGHT = 2

        layout = QGridLayout()
        self.build_btn_set_value(layout, ACTUATOR_WHITE_LIGHT, 'Белый свет:', 0)
        self.build_btn_set_value(layout, ACTUATOR_EXTRACTOR, 'Вытяжка:', 1)
        self.build_btn_set_value(layout, ACTUATOR_HUMID, 'Увлажнитель:', 2)
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
