import sys

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QLineEdit, QToolBar, QGroupBox, QGridLayout,
    QCheckBox, QHBoxLayout, QDialog, QDialogButtonBox,
)

from gcode_builder import GrowboxGCodeBuilder


class SetValueDialog(QDialog):
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


class BaseAutoWindow(QWidget):
    gcode_auto = None
    code = None

    def __init__(self, actuator_code, actuator_name, gcode: GrowboxGCodeBuilder, parent=None):
        super().__init__(parent)
        self.actuator_code = actuator_code
        self.actuator_name = actuator_name
        self.gcode = gcode
        self.setWindowTitle(f'Настройка автоматики')

        self.checkbox_turn = QCheckBox('Включена')
        self.checkbox_turn.clicked.connect(self.btn_toggle_auto_clicked)

    def btn_toggle_auto_clicked(self, checked):
        self.gcode_auto.turn(self.actuator_code, checked)


class AutoCycleHardWindow(BaseAutoWindow):
    def btn_set_value_clicked(self, checked, period_code, text, label_value, what_set):
        dlg = SetValueDialog(self, text)
        if dlg.exec():
            value = dlg.input.text()
            label_value.setText(value)
            if what_set == 'duration':
                self.gcode.cycle_hard.set_duration(self.actuator_code, period_code, value)
            elif what_set == 'value':
                self.gcode.cycle_hard.set_value(self.actuator_code, period_code, value)

    def build_btn_set_value(self, layout, period_code, text, y):
        label_value = QLabel('0')

        button = QPushButton('✎')
        what_set = 'value' if y else 'duration'
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, period_code, text, label_value, what_set))

        layout.addWidget(QLabel(text), y, 0)
        layout.addWidget(label_value, y, 1)
        layout.addWidget(button, y, 2)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gcode_auto = self.gcode.cycle_hard
        self.code = self.gcode_auto.CODE

        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'Автоматика с резкой сменой периода для устройства "{self.actuator_name}"'))
        layout.addWidget(self.checkbox_turn)
        self.setLayout(layout)

        for period_code, period_text in enumerate(('Включённое состояние', 'Выключенное состояние')):
            layout_grid = QGridLayout()
            groupbox = QGroupBox(period_text)

            self.build_btn_set_value(layout_grid, period_code, 'Длительность:', 0)

            self.build_btn_set_value(layout_grid, period_code, 'Значение:', 1)

            groupbox.setLayout(layout_grid)
            layout.addWidget(groupbox)


class AutoCycleSoftWindow(BaseAutoWindow):
    def btn_set_value_clicked(self, checked, period_code, text, label_value, what_set):
        dlg = SetValueDialog(self, text)
        if dlg.exec():
            value = dlg.input.text()
            label_value.setText(value)
            if what_set == 'duration':
                self.gcode.cycle_soft.set_duration(self.actuator_code, period_code, value)
            elif what_set == 'value':
                self.gcode.cycle_soft.set_value(self.actuator_code, period_code, value)

    def build_btn_set_value(self, layout, period_code, text, y):
        label_value = QLabel('0')

        button = QPushButton('✎')
        what_set = 'value' if y else 'duration'
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, period_code, text, label_value, what_set))

        layout.addWidget(QLabel(text), y, 0)
        layout.addWidget(label_value, y, 1)
        layout.addWidget(button, y, 2)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gcode_auto = self.gcode.cycle_soft

        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'Автоматика с плавной сменой периода для устройства "{self.actuator_name}"'))
        layout.addWidget(self.checkbox_turn)
        self.setLayout(layout)

        for period_code, period_text in enumerate(('Рассвет', 'День', 'Закат', 'Ночь')):
            layout_grid = QGridLayout()
            groupbox = QGroupBox(period_text)

            self.build_btn_set_value(layout_grid, period_code, 'Длительность:', 0)

            if period_code % 2 != 0:
                self.build_btn_set_value(layout_grid, period_code, 'Значение:', 1)

            groupbox.setLayout(layout_grid)
            layout.addWidget(groupbox)


class AutoClimateControlWindow(BaseAutoWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gcode_auto = self.gcode.climate_control

        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'Автоматика с автоподстройкой значения для устройства "{self.actuator_name}"'))
        layout.addWidget(self.checkbox_turn)
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

    def btn_set_value_clicked(self, checked, actuator_code, text, label_value):
        dlg = SetValueDialog(self, text)
        if dlg.exec():
            value = dlg.input.text()
            label_value.setText(value)
            self.gcode.actuators[actuator_code].set(value)

    def btn_open_auto_clicked(self, checked, gcode_auto, actuator_code: int, actuator_name: str):
        auto_windows_classes = [AutoCycleHardWindow, AutoCycleSoftWindow, AutoClimateControlWindow]
        window_class = auto_windows_classes[gcode_auto.CODE]
        window_key = (gcode_auto.CODE, actuator_code)
        opened_window = self.auto_windows.get(window_key)
        if opened_window is None:
            opened_window = window_class(actuator_code, actuator_name, self.gcode)
            self.auto_windows[window_key] = opened_window
            opened_window.show()

    def btn_toggle_auto_clicked(self, checked, gcode_auto, actuator_code):
        gcode_auto.turn(actuator_code, checked)

    def btn_turn_off_all_autos_clicked(self, checked):
        for checkbox in self.turn_checkboxes:
            if checkbox.isChecked():
                checkbox.setChecked(False)

        self.gcode.turn_off_all_autos()

    def build_btn_set_value(self, layout, actuator_code, text, y):
        label_value = QLabel('0')

        button = QPushButton('✎')
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, actuator_code, text, label_value))

        layout.addWidget(QLabel(text), y, 0)
        layout.addWidget(label_value, y, 1)
        layout.addWidget(button, y, 2)

    def build_groupbox_actuators(self):
        layout = QGridLayout()
        self.build_btn_set_value(layout, self.gcode.A_WHITE_LIGHT, 'Белый свет:', 0)
        self.build_btn_set_value(layout, self.gcode.A_FRED_LIGHT, 'Дальний красный:', 1)
        self.build_btn_set_value(layout, self.gcode.A_EXTRACTOR, 'Вытяжка:', 2)
        self.build_btn_set_value(layout, self.gcode.A_HUMID, 'Увлажнитель:', 3)
        groupbox = QGroupBox('Исполнительные устройства')
        groupbox.setLayout(layout)
        return groupbox

    def build_autos_layout(self, gcode_auto, actuator_code, actuator_name):
        button = QPushButton('✎')
        button.clicked.connect(lambda s: self.btn_open_auto_clicked(s, gcode_auto, actuator_code, actuator_name))

        checkbox = QCheckBox()
        checkbox.clicked.connect(lambda s: self.btn_toggle_auto_clicked(s, gcode_auto, actuator_code))
        self.turn_checkboxes.append(checkbox)

        layout = QHBoxLayout()
        layout.addWidget(checkbox)
        layout.addWidget(button)
        return layout

    def build_groupbox_autos(self):
        layout = QVBoxLayout()

        button_turn_off_all_autos = QPushButton('Выключить всю автоматику')
        button_turn_off_all_autos.clicked.connect(self.btn_turn_off_all_autos_clicked)
        layout.addWidget(button_turn_off_all_autos)

        layout_table = QGridLayout()

        layout_table.addWidget(QLabel('Устройство'), 0, 0)
        layout_table.addWidget(QLabel('Резкий переход'), 0, 1)
        layout_table.addWidget(QLabel('Плавный переход'), 0, 2)
        layout_table.addWidget(QLabel('Климат-контроль'), 0, 3)

        actuators = [
            ('Белый свет', self.gcode.A_WHITE_LIGHT),
            ('Дальний красный', self.gcode.A_FRED_LIGHT),
            ('Вытяжка', self.gcode.A_EXTRACTOR),
            ('Увлажнитель', self.gcode.A_HUMID),
        ]
        for row_index, (actuator_name, actuator_code) in enumerate(actuators, 1):
            layout_table.addWidget(QLabel(actuator_name), row_index, 0)

            for column_index, (_, gcode_auto) in enumerate(self.gcode.autos.items(), 1):
                autos_layout_hard = self.build_autos_layout(gcode_auto, actuator_code, actuator_name)
                layout_table.addLayout(autos_layout_hard, row_index, column_index)

        layout.addLayout(layout_table)

        groupbox = QGroupBox('Автоматика')
        groupbox.setLayout(layout)
        return groupbox

    def __init__(self):
        super().__init__()
        self.auto_windows = {}
        self.turn_checkboxes = []
        self.gcode = GrowboxGCodeBuilder()

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


if __name__ == '__main__':
    run()
