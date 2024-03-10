import json
import sys
from pathlib import Path

import serial
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QLineEdit, QGroupBox, QGridLayout,
    QCheckBox, QHBoxLayout, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QFileDialog, QTextEdit,
)
from serial.tools.list_ports import comports

from gcode_builder import GrowboxGCodeBuilder, AutoCycleHard, AutoCycleSoft, AutoClimateControl
from gcode_parser import parse_gcode_line
from thread_tools import SerialWorkersManager


def parse_and_bufferize_gcode_line(buff_json, gcode_line):
    gcode = parse_gcode_line(gcode_line)
    # from gcode_builder import commands
    # descr = commands.get(gcode.command)
    # if descr:
    #     function, kwargs_descr = descr
    #     buf_temp = buff_json.setdefault(function, {})
    #     for name_gcode, name_python in list(kwargs_descr.items())[:1]:
    #         buf_temp = buf_temp.setdefault(str(gcode.params[name_gcode]), {})
    #
    #     if kwargs_descr:
    #         name_gcode, name_python = list(kwargs_descr.items())[-1]
    #         buf_temp[name_python] = gcode.params[name_gcode]

    if gcode.command == 'E0':
        buff_json.setdefault('actuators', {}).setdefault(str(gcode['A']), {})['value'] = gcode['V']
    elif gcode.command == 'E100':
        buff_json.setdefault(str(AutoCycleHard.CODE), {}).setdefault(str(gcode['A']), {})['turn'] = gcode['B']
    elif gcode.command == 'E101':
        buff_json.setdefault(str(AutoCycleHard.CODE), {}).setdefault(str(gcode['A']), {}).setdefault(str(gcode['B']), {})['duration'] = str(gcode['D'])
    elif gcode.command == 'E103':
        buff_json.setdefault(str(AutoCycleHard.CODE), {}).setdefault(str(gcode['A']), {}).setdefault(str(gcode['B']), {})['value'] = str(gcode['V'])
    elif gcode.command == 'E150':
        buff_json.setdefault(str(AutoCycleSoft.CODE), {}).setdefault(str(gcode['A']), {})['turn'] = gcode.params['B']
    elif gcode.command == 'E151':
        buff_json.setdefault(str(AutoCycleSoft.CODE), {}).setdefault(str(gcode['A']), {}).setdefault(str(gcode['P']), {})['duration'] = str(gcode['D'])
    elif gcode.command == 'E153':
        buff_json.setdefault(str(AutoCycleSoft.CODE), {}).setdefault(str(gcode['A']), {}).setdefault(str(gcode['P']), {})['value'] = str(gcode['V'])
    elif gcode.command == 'E200':
        buff_json.setdefault(str(AutoClimateControl.CODE), {}).setdefault(str(gcode['A']), {})['turn'] = gcode['B']
    elif gcode.command == 'E201':
        buff_json.setdefault(str(AutoClimateControl.CODE), {}).setdefault(str(gcode['A']), {})['sensor'] = gcode['S']
    elif gcode.command == 'E202':
        buff_json.setdefault(str(AutoClimateControl.CODE), {}).setdefault(str(gcode['A']), {})['min'] = str(gcode['V'])
    elif gcode.command == 'E203':
        buff_json.setdefault(str(AutoClimateControl.CODE), {}).setdefault(str(gcode['A']), {})['max'] = str(gcode['V'])


def buff2gcode(buff_json, gcode):
    # stop all autos
    if buff_json.get('turn_off_all_autos', True):
        gcode.turn_off_all_autos()

    # set values on actuators
    actuators_json = buff_json.setdefault('actuators', {})
    for actuator in gcode.actuators.values():
        actuator.set(actuators_json.setdefault(str(actuator.code), {}).get('value', actuator.DEFAULT_VALUE))

    # set autos
    for actuator in gcode.actuators.values():
        for auto in gcode.autos.values():
            actuator_json = buff_json.get(str(auto.CODE), {}).get(str(actuator), {})
            if auto.CODE in (0, 1):
                for period in auto.PERIODS:
                    period_json = actuator_json.get(str(period), {})
                    auto.set_value(actuator, period, period_json.get('value', auto.DEFAULT_VALUE))
                    auto.set_duration(actuator, period, period_json.get('duration', auto.DEFAULT_VALUE))
            elif auto.CODE == 2:
                auto.set_min(actuator, actuator_json.get('min', auto.DEFAULT_MIN))
                auto.set_max(actuator, actuator_json.get('max', auto.DEFAULT_MAX))
                sensor = actuator_json.get('sensor')
                if sensor is not None:
                    auto.set_sensor(actuator, sensor)

    # start autos if needs
    for actuator in gcode.actuators.values():
        for auto in gcode.autos.values():
            actuator_json = buff_json.get(str(auto.CODE), {}).get(str(actuator), {})
            value = actuator_json.get('turn')
            if value:
                auto.turn(actuator, value)


class SetValueDialog(QDialog):
    def __init__(self, parent=None, text='', initial_value='0', input_widget=None):
        super().__init__(parent)
        self.setWindowTitle(f'Новое значение для "{text}"')

        buttons = QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel
        button_box = QDialogButtonBox(buttons)
        button_box.clicked.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        self.input = input_widget
        if self.input is None:
            self.input = QLineEdit()
            self.input.setInputMask(r'999')
            self.input.setText(initial_value)

        layout.addWidget(self.input)
        layout.addWidget(button_box)
        self.setLayout(layout)


class BaseAutoWindow(QWidget):
    is_closed = False

    def closeEvent(self, *args, **kwargs):
        super().closeEvent(*args, **kwargs)
        self.is_closed = True

    def __init__(self, gcode_auto, actuator_code, actuator_name, gcode: GrowboxGCodeBuilder, buff_json: dict, checkboxes, parent=None):
        super().__init__(parent)
        self.code = gcode_auto.CODE
        self.actuator_code = actuator_code
        self.actuator_name = actuator_name
        self.gcode = gcode
        self.turn_checkboxes = checkboxes
        self.gcode_auto = gcode_auto
        self.setWindowTitle(f'Настройка автоматики')

        self.checkbox_turn = QCheckBox('Включена')
        self.checkbox_turn.clicked.connect(self.btn_toggle_auto_clicked)

        self.actuator_json = buff_json.get(str(gcode_auto.CODE), {}).get(str(self.actuator_code), {})
        self.checkbox_turn.setChecked(self.actuator_json.get('turn', False))

    def btn_toggle_auto_clicked(self, checked):
        self.gcode_auto.turn(actuator=self.actuator_code, status=checked)
        self.turn_checkboxes[f'{self.code}-{self.actuator_code}'].setChecked(checked)


class AutoCycleHardWindow(BaseAutoWindow):
    def btn_set_value_clicked(self, checked, period_code, text, label_value, what_set):
        dlg = SetValueDialog(self, text, label_value.text())
        if dlg.exec():
            value = dlg.input.text()
            label_value.setText(value)
            if what_set == 'duration':
                self.gcode_auto.set_duration(self.actuator_code, period_code, value)
            elif what_set == 'value':
                self.gcode_auto.set_value(self.actuator_code, period_code, value)

    def build_btn_set_value(self, layout, period_code, text, y, value):
        label_value = QLabel(value)

        button = QPushButton('✎')
        what_set = 'value' if y else 'duration'
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, period_code, text, label_value, what_set))

        layout.addWidget(QLabel(text), y, 0)
        layout.addWidget(label_value, y, 1)
        layout.addWidget(button, y, 2)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'Автоматика с резкой сменой периода для устройства "{self.actuator_name}"'))
        layout.addWidget(self.checkbox_turn)
        self.setLayout(layout)

        for period_code, period_text in enumerate(('Включённое состояние', 'Выключенное состояние')):
            layout_grid = QGridLayout()
            groupbox = QGroupBox(period_text)

            period_json = self.actuator_json.get(str(period_code), {})
            self.build_btn_set_value(layout_grid, period_code, 'Длительность:', 0, period_json.get('duration', '0'))
            self.build_btn_set_value(layout_grid, period_code, 'Значение:', 1, period_json.get('value', '0'))

            groupbox.setLayout(layout_grid)
            layout.addWidget(groupbox)


class AutoCycleSoftWindow(BaseAutoWindow):
    def btn_set_value_clicked(self, checked, period_code, text, label_value, what_set):
        dlg = SetValueDialog(self, text, label_value.text())
        if dlg.exec():
            value = dlg.input.text()
            label_value.setText(value)
            if what_set == 'duration':
                self.gcode_auto.set_duration(self.actuator_code, period_code, value)
            elif what_set == 'value':
                self.gcode_auto.set_value(self.actuator_code, period_code, value)

    def build_btn_set_value(self, layout, period_code, text, y, value):
        label_value = QLabel(value)

        button = QPushButton('✎')
        what_set = 'value' if y else 'duration'
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, period_code, text, label_value, what_set))

        layout.addWidget(QLabel(text), y, 0)
        layout.addWidget(label_value, y, 1)
        layout.addWidget(button, y, 2)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'Автоматика с плавной сменой периода для устройства "{self.actuator_name}"'))
        layout.addWidget(self.checkbox_turn)
        self.setLayout(layout)

        for period_code, period_text in enumerate(('Рассвет', 'День', 'Закат', 'Ночь')):
            layout_grid = QGridLayout()
            groupbox = QGroupBox(period_text)

            period_json = self.actuator_json.get(str(period_code), {})
            self.build_btn_set_value(layout_grid, period_code, 'Длительность:', 0, period_json.get('duration', '0'))
            if period_code % 2 != 0:
                self.build_btn_set_value(layout_grid, period_code, 'Значение:', 1, period_json.get('value', '0'))

            groupbox.setLayout(layout_grid)
            layout.addWidget(groupbox)


class AutoClimateControlWindow(BaseAutoWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensors = {
            self.gcode.s_humid.code: 'Влажность',
            self.gcode.s_temperature.code: 'Температура',
        }

        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'Автоматика с автоподстройкой значения для устройства "{self.actuator_name}"'))
        layout.addWidget(self.checkbox_turn)

        layout_grid = QGridLayout()
        layout.addLayout(layout_grid)

        text = 'Мин. допустимое значение:'
        label_value_min = QLabel(self.actuator_json.get('min', '0'))
        button = QPushButton('✎')
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, text, label_value_min, 'min'))
        layout_grid.addWidget(QLabel(text), 0, 0)
        layout_grid.addWidget(label_value_min, 0, 1)
        layout_grid.addWidget(button, 0, 2)

        text = 'Макс. допустимое значение:'
        label_value_max = QLabel(self.actuator_json.get('max', '0'))
        button = QPushButton('✎')
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, text, label_value_max, 'max'))
        layout_grid.addWidget(QLabel(text), 1, 0)
        layout_grid.addWidget(label_value_max, 1, 1)
        layout_grid.addWidget(button, 1, 2)

        text = 'Датчик:'
        sensor_code = int(self.actuator_json.get('sensor', -1))
        label_value_sensor = QLabel('Не выбран') if sensor_code == -1 else QLabel(self.sensors[sensor_code])
        button = QPushButton('✎')
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, text, label_value_sensor, 'sensor'))
        layout_grid.addWidget(QLabel(text), 2, 0)
        layout_grid.addWidget(label_value_sensor, 2, 1)
        layout_grid.addWidget(button, 2, 2)

        self.setLayout(layout)

    def btn_set_value_clicked(self, checked, text, label_value, what_set):
        initial_value = label_value.text()
        input_widget = None
        if what_set == 'sensor':
            input_widget = QListWidget()
            for sensor_code, sensor_name in self.sensors.items():
                widget_item = QListWidgetItem(sensor_name, input_widget)
                widget_item.setData(Qt.ItemDataRole.UserRole, sensor_code)
                if initial_value == sensor_name:
                    widget_item.setSelected(True)

        dlg = SetValueDialog(self, text, initial_value, input_widget)
        if dlg.exec():
            if what_set == 'min':
                value = dlg.input.text()
                label_value.setText(value)
                self.gcode_auto.set_min(self.actuator_code, value)
            elif what_set == 'max':
                value = dlg.input.text()
                label_value.setText(value)
                self.gcode_auto.set_max(self.actuator_code, value)
            elif what_set == 'sensor':
                value = dlg.input.currentItem()
                label_value.setText(value.text())
                self.gcode_auto.set_sensor(self.actuator_code, value.data(Qt.ItemDataRole.UserRole))


class YesNoDialog(QDialog):
    def __init__(self, parent=None, text_title='', text_info='', text_question=''):
        super().__init__(parent)
        self.setWindowTitle(text_title)

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        button_box = QDialogButtonBox(buttons)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel(text_info))
        layout.addWidget(QLabel(text_question))
        layout.addWidget(button_box)
        self.setLayout(layout)


class MainPanelWindow(QMainWindow):
    def closeEvent(self, *args, **kwargs):
        super().closeEvent(*args, **kwargs)
        if self.serial:
            self.serial.close()

    def btn_save_gcode(self, checked):
        default_file_name = self.file_path.stem if self.file_path else ''
        file_path, mask = QFileDialog.getSaveFileName(self, 'Сохранение G-кода', default_file_name, '*.gcode')
        # if os.path.exists(file_path):
        #     dlg = YesNoDialog(
        #         self,
        #         'Сохранение файла...',
        #         'Файл с таким именем уже существует.',
        #         'Вы уверены, что хотите перезаписать его?',
        #     )
        #     if not dlg.exec():
        #         return
        if file_path:
            with open(file_path, 'w') as output_file:
                buff2gcode(self.buff_json, GrowboxGCodeBuilder(output_file))

            if not self.file_path:
                self.file_path = Path(file_path)
                self.print_to_status_bar(str(file_path), 1)

    def btn_save_json(self, checked):
        default_file_name = self.file_path.stem if self.file_path else ''
        file_path, mask = QFileDialog.getSaveFileName(self, 'Сохранение JSON', default_file_name, '*.json')
        if file_path:
            with open(file_path, 'w') as output_file:
                json.dump(self.buff_json, output_file)

            if not self.file_path:
                self.file_path = Path(file_path)
                self.print_to_status_bar(str(file_path), 1)

    def start_menubar(self):
        menu = self.menuBar()
        menu_file = menu.addMenu('Файл')

        if self.open_type in ('open', 'create'):
            button_action_save = QAction('Сохранить как G-код', self)
            button_action_save.triggered.connect(self.btn_save_gcode)
            # button_action_save_json = QAction('Сохранить как JSON', self)
            # button_action_save_json.triggered.connect(self.btn_save_json)
            menu_file.addAction(button_action_save)
            # menu_file.addAction(button_action_save_json)
        if self.open_type == 'connect':
            # button_action_send_json = QAction('Открыть JSON и послать в гроубокс', self)
            button_action_send_gcode = QAction('Открыть G-код и послать в гроубокс', self)
            # menu_file.addAction(button_action_send_json)
            menu_file.addAction(button_action_send_gcode)

    def build_groupbox_sensors(self):
        layout = QGridLayout()

        layout.addWidget(QLabel('Влажность:'), 0, 0)
        label_humid = QLabel('-')
        self.sensor_widgets[1] = label_humid
        layout.addWidget(label_humid, 0, 1)
        layout.addWidget(QLabel('%'), 0, 2)

        layout.addWidget(QLabel('Температура:'), 1, 0)
        label_temperatue = QLabel('-')
        self.sensor_widgets[0] = label_temperatue
        layout.addWidget(label_temperatue, 1, 1)
        layout.addWidget(QLabel('℃'), 1, 2)

        groupbox = QGroupBox('Показания датчиков')
        groupbox.setLayout(layout)

        return groupbox

    def btn_set_value_clicked(self, checked, actuator_code, text, label_value):
        dlg = SetValueDialog(self, text, label_value.text())
        if dlg.exec():
            value = dlg.input.text()
            label_value.setText(value)
            self.gcode.actuators[actuator_code].set(value)

    def btn_open_auto_clicked(self, checked, gcode_auto, actuator_code: int, actuator_name: str):
        auto_windows_classes = {
            self.gcode.cycle_hard.CODE: AutoCycleHardWindow,
            self.gcode.cycle_soft.CODE: AutoCycleSoftWindow,
            self.gcode.climate_control.CODE: AutoClimateControlWindow,
        }
        window_class = auto_windows_classes[gcode_auto.CODE]
        window_key = (gcode_auto.CODE, actuator_code)
        opened_window = self.auto_windows.get(window_key)
        if opened_window is None or opened_window.is_closed:
            opened_window = window_class(gcode_auto, actuator_code, actuator_name, self.gcode, self.buff_json, self.turn_checkboxes)
            self.auto_windows[window_key] = opened_window
            opened_window.show()

    def btn_toggle_auto_clicked(self, checked, gcode_auto, actuator_code):
        gcode_auto.turn(actuator_code, checked)

    def btn_turn_off_all_autos_clicked(self, checked):
        for key, checkbox in self.turn_checkboxes.items():
            if checkbox.isChecked():
                checkbox.setChecked(False)
                auto_code, actuator_code = key.split('-')
                auto_data = self.buff_json.get(auto_code)
                if auto_data:
                    actuator_data = auto_data.get(actuator_code)
                    if actuator_data.get('turn'):
                        actuator_data['turn'] = False

        self.gcode.turn_off_all_autos()

    def build_btn_set_value(self, layout, actuator_code: int, text, y):
        default_value = self.gcode.actuators[actuator_code].DEFAULT_VALUE
        value = self.buff_json.get('actuators', {}).get(str(actuator_code), {}).get('value', default_value)
        label_value = QLabel(str(value))

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
        is_turned = False
        if self.open_type == 'open':
            is_turned = self.buff_json.get(str(gcode_auto.CODE), {}).get(str(actuator_code), {}).get('turn', False)

        button = QPushButton('✎')
        button.clicked.connect(lambda s: self.btn_open_auto_clicked(s, gcode_auto, actuator_code, actuator_name))

        checkbox = QCheckBox()
        checkbox.setChecked(is_turned)
        checkbox.clicked.connect(lambda s: self.btn_toggle_auto_clicked(s, gcode_auto, actuator_code))
        self.turn_checkboxes[f'{gcode_auto.CODE}-{actuator_code}'] = checkbox

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
                autos_layout = self.build_autos_layout(gcode_auto, actuator_code, actuator_name)
                layout_table.addLayout(autos_layout, row_index, column_index)

        layout.addLayout(layout_table)

        groupbox = QGroupBox('Автоматика')
        groupbox.setLayout(layout)
        return groupbox

    def print_to_log(self, data: str, extern=False):
        if extern and self.worker_manager.current_worker:
            self.worker_manager.current_worker.signals.print_to_log.emit(data)
        else:
            if self.widget_log:
                self.widget_log.insertPlainText(data.decode() if isinstance(data, bytes) else data)

    def print_to_status_bar(self, message, status=0):
        if status == 0:
            self.statusBar().showMessage(message)
        elif status == 1:
            cutted_message = message if len(message) < 40 else f'{message[:19]}...{message[-18:]}'
            if not self.progress_bar:
                self.progress_bar = QLabel()
                self.statusBar().addPermanentWidget(self.progress_bar)

            self.progress_bar.setText(cutted_message)

    def callback_write(self, gcode_line, extern=False):
        if extern and self.worker_manager.current_worker:
            self.worker_manager.current_worker.signals.callback_write.emit(gcode_line)
        else:
            self.print_to_log(gcode_line)
            parse_and_bufferize_gcode_line(self.buff_json, gcode_line)

    def worker_update_from_serial(self):
        def result_autos(data):
            auto_code, actuator_code, is_turned = data
            self.buff_json.setdefault(auto_code, {}).setdefault(actuator_code, {})['turn'] = is_turned
            self.turn_checkboxes[f'{auto_code}-{actuator_code}'].setChecked(is_turned)

        def get_autos(key):
            auto_code, actuator_code = key.split('-')
            return auto_code, actuator_code, self.gcode.autos[int(auto_code)].is_turn(actuator_code)

        def result_sensors(data):
            sensor_code, value = data
            if value is None:
                self.sensor_widgets[int(sensor_code)].setText('-')
            else:
                self.sensor_widgets[int(sensor_code)].setText(str(value))

        def get_sensors(sensor_code):
            return sensor_code, self.gcode.sensors[int(sensor_code)].get()

        for sensor_code, sensor in self.gcode.sensors.items():
            self.worker_manager.add_and_start_worker(result_sensors, get_sensors, sensor.code)

        for key, checkbox in self.turn_checkboxes.items():
            self.worker_manager.add_and_start_worker(result_autos, get_autos, key)

    def __init__(
            self,
            open_type: str,
            open_subtype: str | None,
            file_path: Path | None = None,
            data: dict | None = None,
    ):
        super().__init__()
        self.serial = None
        self.progress_bar = None
        self.auto_windows = {}
        self.turn_checkboxes = {}
        self.buff_json = {}
        self.sensor_widgets = {}
        self.worker_manager = SerialWorkersManager(
            print_to_log=self.print_to_log,
            callback_write=self.callback_write,
        )

        self.setWindowTitle('CNC Growbox')

        self.open_type = open_type
        self.file_path = file_path
        if open_type == 'open' and open_subtype == 'json':
            self.print_to_status_bar(str(file_path), 1)
            with file_path.open() as json_file:
                self.buff_json = json.load(json_file)
                self.gcode = GrowboxGCodeBuilder(callback_write=self.callback_write)
        if open_type == 'open' and open_subtype == 'gcode':
            self.print_to_status_bar(str(file_path), 1)
            self.gcode = GrowboxGCodeBuilder(callback_write=self.callback_write)
            with file_path.open() as gcode_file:
                for gcode_line in gcode_file:
                    parse_and_bufferize_gcode_line(self.buff_json, gcode_line)
        elif open_type == 'create':
            self.print_to_status_bar('Новый файл', 1)
            self.gcode = GrowboxGCodeBuilder(callback_write=self.callback_write)
        elif open_type == 'connect' and open_subtype == 'serial':
            self.print_to_status_bar(str(file_path), 1)
            self.serial = serial.Serial(
                str(file_path),
                baudrate=data['baudrate'],
                timeout=data['timeout_read'],
                write_timeout=data['timeout_write'],
            )
            self.gcode = GrowboxGCodeBuilder(
                self.serial,
                callback_answer=lambda s: self.print_to_log(s, True),
                callback_write=lambda s: self.callback_write(s, True),
            )

        layout = QVBoxLayout()
        self.start_menubar()

        if open_type == 'connect':
            layout.addWidget(self.build_groupbox_sensors())

        groupbox_actuators = self.build_groupbox_actuators()
        layout.addWidget(groupbox_actuators)

        groupbox_autos = self.build_groupbox_autos()
        layout.addWidget(groupbox_autos)

        widget = QWidget()
        widget.setLayout(layout)

        self.setCentralWidget(widget)

        self.widget_log = QTextEdit()
        self.widget_log.setReadOnly(True)
        layout.addWidget(self.widget_log)

        if open_type == 'connect':
            # layout.addWidget(QLabel('Секунд с момента включения:'))
            button_update = QPushButton('Обновить показания')
            button_update.clicked.connect(lambda s: self.worker_update_from_serial())
            layout.addWidget(button_update)
            self.worker_manager.add_and_start_worker(None, self.gcode.output.write, '')
            self.worker_update_from_serial()


class SelectSerialPortDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'Подключение к гроубоксу')

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        button_box = QDialogButtonBox(buttons)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()

        self.input_port = QListWidget()
        for index, (port, desc, hwid) in enumerate(comports()):
            widget_item_port = QListWidgetItem(port, self.input_port)
            widget_item_port.setData(Qt.ItemDataRole.UserRole, port)
            if not index:
                widget_item_port.setSelected(True)

        self.input_baudrate = QListWidget()
        for baudrate in [4800, 9600, 19200, 38400, 76800, 153600]:
            widget_item_baudrate = QListWidgetItem(str(baudrate), self.input_baudrate)
            widget_item_baudrate.setData(Qt.ItemDataRole.UserRole, baudrate)
            # if baudrate == 9600:
            #     widget_item_baudrate.setSelected(True)

        self.input_timeout_read = QLineEdit('2.2')
        self.input_timeout_write = QLineEdit('0.1')

        layout_grid = QGridLayout()
        layout_grid.addWidget(QLabel('Таймаут на чтение:'), 0, 0)
        layout_grid.addWidget(self.input_timeout_read, 0, 1)
        layout_grid.addWidget(QLabel('Таймаут на запись:'), 1, 0)
        layout_grid.addWidget(self.input_timeout_write, 1, 1)

        layout.addWidget(QLabel('Выберите последовательный порт:'))
        layout.addWidget(self.input_port)
        layout.addWidget(QLabel('Выберите скорость:'))
        layout.addWidget(self.input_baudrate)
        layout.addLayout(layout_grid)
        layout.addWidget(button_box)
        self.setLayout(layout)


class MainWindow(QMainWindow):
    def btn_open_gcode_clicked(self, checked):
        file_path, mask = QFileDialog.getOpenFileName(self, 'Открытие G-кода', '~', '*.gcode')
        if file_path:
            window = MainPanelWindow('open', 'gcode', file_path=Path(file_path))
            self.main_panel_windows.append(window)
            window.show()

    def btn_open_json_clicked(self, checked):
        file_path, mask = QFileDialog.getOpenFileName(self, 'Открытие JSON', '~', '*.json')
        if file_path:
            window = MainPanelWindow('open', 'json', file_path=Path(file_path))
            self.main_panel_windows.append(window)
            window.show()

    def btn_create_gcode_clicked(self, checked):
        window = MainPanelWindow('create', None, file_path=None)
        self.main_panel_windows.append(window)
        window.show()

    def btn_connect_serial_clicked(self, checked):
        dlg = SelectSerialPortDialog()
        if dlg.exec():
            port, baudrate, timeout_read, timeout_write = None, None, None, None
            current_item_port = dlg.input_port.currentItem()
            if current_item_port:
                port = current_item_port.data(Qt.ItemDataRole.UserRole)

            current_item_baudrate = dlg.input_baudrate.currentItem()
            if current_item_baudrate:
                baudrate = current_item_baudrate.data(Qt.ItemDataRole.UserRole)

            timeout_read = float(dlg.input_timeout_read.text())
            timeout_write = float(dlg.input_timeout_write.text())
            if port and baudrate and timeout_read and timeout_write:
                data = {
                    'port': port,
                    'baudrate': baudrate,
                    'timeout_read': timeout_read,
                    'timeout_write': timeout_write,
                }
                window = MainPanelWindow('connect', 'serial', file_path=Path(port), data=data)
                self.main_panel_windows.append(window)
                window.show()

    def __init__(self):
        super().__init__()
        self.main_panel_windows = []
        self.setWindowTitle('CNC Growbox')
        layout = QVBoxLayout()

        button = QPushButton('Создать управляющую программу')
        button.clicked.connect(self.btn_create_gcode_clicked)
        layout.addWidget(button)

        button = QPushButton('Открыть G-код')
        button.clicked.connect(self.btn_open_gcode_clicked)
        layout.addWidget(button)

        # button = QPushButton('Открыть JSON')
        # button.clicked.connect(self.btn_open_json_clicked)
        # layout.addWidget(button)

        button = QPushButton('Подключиться по Serial')
        button.clicked.connect(self.btn_connect_serial_clicked)
        layout.addWidget(button)

        # button = QPushButton('Подключиться по HTTP')
        # button.clicked.connect(self.btn_connect_http_clicked)
        # layout.addWidget(button)

        widget = QWidget()
        widget.setLayout(layout)

        self.setCentralWidget(widget)


def run():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    app.exec()


if __name__ == '__main__':
    run()
