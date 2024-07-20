import json
import sys
from pathlib import Path

import requests
import serial
import yaml
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QLineEdit, QGroupBox, QGridLayout,
    QCheckBox, QHBoxLayout, QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QFileDialog, QTextEdit,
    QRadioButton, QButtonGroup
)
from serial.tools.list_ports import comports

from gcode_builder import GrowboxGCodeBuilder, AutoCycleHard, AutoCycleSoft, AutoClimateControl, AutoTimer
from gcode_parser import parse_gcode_line
from thread_tools import SerialWorkersManager
from set_value_windows import SetValueIntegerDialog, SetValueListDialog, SetValueTimeDialog

SHADE_AVOIDANCE = 1
SHADE_TOLERANCE = 2

LONG_DAY = 1
SHORT_DAY = 2
DAY_NEUTRAL = 3

VEGETATIVE_GROWING = 1
GENERATIVE_GROWING = 2

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
    elif gcode.command == 'E3' and 'R' in gcode and 'A' in gcode:
        buff_json.setdefault(str(gcode['R']), {}).setdefault(str(gcode['A']), {})['turn'] = gcode['B']
    elif gcode.command == 'E101':
        buff_json.setdefault(str(AutoCycleHard.CODE), {}).setdefault(str(gcode['A']), {}).setdefault(str(gcode['B']), {})['duration'] = str(gcode['D'])
    elif gcode.command == 'E103':
        buff_json.setdefault(str(AutoCycleHard.CODE), {}).setdefault(str(gcode['A']), {}).setdefault(str(gcode['B']), {})['value'] = str(gcode['V'])
    elif gcode.command == 'E151':
        buff_json.setdefault(str(AutoCycleSoft.CODE), {}).setdefault(str(gcode['A']), {}).setdefault(str(gcode['P']), {})['duration'] = str(gcode['D'])
    elif gcode.command == 'E153':
        buff_json.setdefault(str(AutoCycleSoft.CODE), {}).setdefault(str(gcode['A']), {}).setdefault(str(gcode['P']), {})['value'] = str(gcode['V'])
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


def generate_gcode(gcode: GrowboxGCodeBuilder, profile_data: dict, grow_mode: int):
    cycle_hard = gcode.cycle_hard
    cycle_soft = gcode.cycle_soft
    a_white_light = gcode.a_white_light
    a_fred_light = gcode.a_fred_light

    shade_reaction = profile_data['shade_reaction']
    photoperiodism = profile_data['photoperiodism']

    len_light_day = 12 * 60
    len_sunrise_day = 10
    # if shade_reaction == SHADE_AVOIDANCE:
    #     gcode.a_fred_light.set(0)  # чтобы растение не вытягивалось

    if photoperiodism == LONG_DAY:
        if grow_mode == GENERATIVE_GROWING:
            len_light_day = 14 * 60
        else:
            len_light_day = 12 * 60
    elif photoperiodism == SHORT_DAY:
        if grow_mode == GENERATIVE_GROWING:
            len_light_day = 11 * 60
        else:
            len_light_day = 14 * 60

    gcode.turn_off_all_autos()

    # Настройка белого света
    cycle_soft.set_value(a_white_light, cycle_soft.DAY, 255)
    cycle_soft.set_value(a_white_light, cycle_soft.NIGHT, 0)
    cycle_soft.set_duration(a_white_light, cycle_soft.SUNRISE, len_sunrise_day)
    cycle_soft.set_duration(a_white_light, cycle_soft.DAY, len_light_day - len_sunrise_day)
    cycle_soft.set_duration(a_white_light, cycle_soft.SUNSET, 10)
    cycle_soft.set_duration(a_white_light, cycle_soft.NIGHT, 590)
    cycle_soft.turn(a_white_light, True)

    # Настройка дальнего красного света


class HttpAdapter:
    def __init__(self, url):
        self.url = url
        self.mode = 'w'
        self.response_data = ''

    def write(self, row_string):
        params = {'action': 'send_to_serial', 'string_data': row_string, 'timeout_read': 2500}
        try:
            response = requests.post(f'{self.url}/api.c', params=params, timeout=4)
        except requests.ReadTimeout as error:
            print('read:', str(error), 'gcode:', row_string)
        except requests.ConnectTimeout as error:
            print('connect:', str(error), 'gcode:', row_string)
        else:
            if response.status_code == 200:
                string_response_data = response.json()['data']['string_response_data']
                self.response_data = f'{self.response_data}{string_response_data}'

    def read(self, length):
        data_to_return = self.response_data[:length]
        self.response_data = self.response_data[length:]
        return data_to_return.encode()


class BaseAutoWindow(QWidget):
    is_closed = False

    def closeEvent(self, *args, **kwargs):
        super().closeEvent(*args, **kwargs)
        self.is_closed = True

    def __init__(
            self,
            gcode_auto,
            actuator_code,
            actuator_name,
            gcode: GrowboxGCodeBuilder,
            buff_json: dict,
            checkboxes,
            open_type,
            worker_manager,
            parent=None,
    ):
        super().__init__(parent)
        self.code = gcode_auto.CODE
        self.actuator_code = actuator_code
        self.actuator_name = actuator_name
        self.gcode = gcode
        self.turn_checkboxes = checkboxes
        self.gcode_auto = gcode_auto
        self.open_type = open_type
        self.worker_manager = worker_manager
        self.setWindowTitle(f'Настройка автоматики')

        self.checkbox_turn = QCheckBox('Включена')
        self.checkbox_turn.clicked.connect(self.btn_toggle_auto_clicked)

        self.actuator_json = buff_json.get(str(gcode_auto.CODE), {}).get(str(self.actuator_code), {})
        self.checkbox_turn.setChecked(self.actuator_json.get('turn', False))

    def btn_toggle_auto_clicked(self, checked):
        self.gcode_auto.turn(actuator=self.actuator_code, status=checked)
        self.turn_checkboxes[f'{self.code}-{self.actuator_code}'].setChecked(checked)

    @staticmethod
    def format_duration(duration):
        hours = duration // 60
        minutes = duration % 60
        str_hours = f'{hours}ч' if hours else ''
        str_minutes = f'{minutes}м' if minutes else ''
        return f'{str_hours} {str_minutes}' if hours or minutes else '0'


class AutoCycleHardWindow(BaseAutoWindow):
    def set_duration(self, period_code, duration):
        str_duration = self.format_duration(duration)
        self.labels_by_period.setdefault(period_code, {})['duration'].setText(str_duration)
        self.period_data.setdefault(period_code, {})['duration'] = duration

    def get_duration(self, period):
        return self.period_data.get(period, {}).get('duration', 0)

    def set_value(self, period_code, value):
        self.labels_by_period.setdefault(period_code, {})['value'].setText(str(value))
        self.period_data.setdefault(period_code, {})['value'] = value

    def get_value(self, period):
        return self.period_data.get(period, {}).get('value', 0)

    def btn_set_value_clicked(self, checked, period_code, text, what_set):
        if what_set == 'value':
            dlg = SetValueIntegerDialog(self, text, getattr(self, f'get_{what_set}')(period_code))
        else:
            dlg = SetValueTimeDialog(self, text, getattr(self, f'get_{what_set}')(period_code))

        if dlg.exec():
            value = dlg.value
            getattr(self, f'set_{what_set}')(period_code, value)
            getattr(self.gcode_auto, f'set_{what_set}')(self.actuator_code, period_code, value)

    def build_btn_set_value(self, layout, period_code, text, y, value):
        label_value = QLabel(value)

        button = QPushButton('✎')
        what_set = 'value' if y else 'duration'
        self.labels_by_period.setdefault(period_code, {})[what_set] = label_value
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, period_code, text, what_set))

        layout.addWidget(QLabel(text), y, 0)
        layout.addWidget(label_value, y, 1)
        layout.addWidget(button, y, 2)

    def update(self, checked=None):
        def result_update(data):
            period_code, duration, value = data
            self.set_duration(period_code, duration)
            self.set_value(period_code, value)

        def task_update(period_code):
            return (
                period_code,
                self.gcode_auto.get_duration(self.actuator_code, period_code),
                self.gcode_auto.get_value(self.actuator_code, period_code),
            )

        def result_current(data):
            period_code, current_duration = data
            period_name = 'включённого' if period_code else 'выключенного'
            self.label_current.setText(self.label_current_mask.format(current_duration, period_name))

        def task_current():
            return self.gcode_auto.get_current(self.actuator_code)

        self.worker_manager.add_and_start_worker(result_current, task_current)
        for period_code in self.gcode_auto.PERIODS:
            self.worker_manager.add_and_start_worker(result_update, task_update, period_code)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'Автоматика с резкой сменой периода для устройства "{self.actuator_name}"'))
        layout.addWidget(self.checkbox_turn)
        self.setLayout(layout)
        self.labels_by_period = {}
        self.period_data = {}
        self.label_current = None
        self.label_current_mask = 'Прошло {} минуты {} состояния'

        for period_code, period_text in enumerate(('Выключенное состояние', 'Включённое состояние')):
            layout_grid = QGridLayout()
            groupbox = QGroupBox(period_text)

            period_json = self.actuator_json.get(str(period_code), {})
            self.build_btn_set_value(layout_grid, period_code, 'Длительность:', 0, period_json.get('duration', '0'))
            self.build_btn_set_value(layout_grid, period_code, 'Значение:', 1, period_json.get('value', '0'))

            groupbox.setLayout(layout_grid)
            layout.addWidget(groupbox)

        if self.open_type == 'connect':
            self.label_current = QLabel('')
            button_update = QPushButton('Обновить')
            button_update.clicked.connect(self.update)
            layout.addWidget(self.label_current)
            layout.addWidget(button_update)
            self.update()


class AutoCycleSoftWindow(BaseAutoWindow):
    def set_duration(self, period_code, duration):
        str_duration = self.format_duration(duration)
        self.labels_by_period.setdefault(period_code, {})['duration'].setText(str_duration)
        self.period_data.setdefault(period_code, {})['duration'] = duration

    def get_duration(self, period):
        return self.period_data.get(period, {}).get('duration', 0)

    def set_value(self, period_code, value):
        self.labels_by_period.setdefault(period_code, {})['value'].setText(str(value))
        self.period_data.setdefault(period_code, {})['value'] = value

    def get_value(self, period):
        return self.period_data.get(period, {}).get('value', 0)

    def btn_set_value_clicked(self, checked, period_code, text, label_value, what_set):
        if what_set == 'value':
            dlg = SetValueIntegerDialog(self, text, int(label_value.text()), maximum=255)
        else:
            dlg = SetValueTimeDialog(self, text, getattr(self, f'get_{what_set}')(period_code))

        if dlg.exec():
            value = dlg.value
            getattr(self, f'set_{what_set}')(period_code, value)
            getattr(self.gcode_auto, f'set_{what_set}')(self.actuator_code, period_code, value)

    def build_btn_set_value(self, layout, period_code, text, y, value):
        label_value = QLabel(value)

        button = QPushButton('✎')
        what_set = 'value' if y else 'duration'
        self.labels_by_period.setdefault(period_code, {})[what_set] = label_value
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, period_code, text, label_value, what_set))

        layout.addWidget(QLabel(text), y, 0)
        layout.addWidget(label_value, y, 1)
        layout.addWidget(button, y, 2)

    def update(self, checked=None):
        def result_update(data):
            period_code, duration, value = data
            self.set_duration(period_code, duration)
            if period_code % 2 != 0:
                self.set_value(period_code, value)

        def task_update(period_code):
            return (
                period_code,
                self.gcode_auto.get_duration(self.actuator_code, period_code),
                self.gcode_auto.get_value(self.actuator_code, period_code) if period_code % 2 != 0 else None,
            )

        def result_current(data):
            period_names = ['рассвета', 'дня', 'заката', 'ночи']
            period_code, current_duration = data
            period_name = period_names[period_code]
            self.label_current.setText(self.label_current_mask.format(current_duration, period_name))

        def task_current():
            return self.gcode_auto.get_current(self.actuator_code)

        self.worker_manager.add_and_start_worker(result_current, task_current)
        for period_code in self.gcode_auto.PERIODS:
            self.worker_manager.add_and_start_worker(result_update, task_update, period_code)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'Автоматика с плавной сменой периода для устройства "{self.actuator_name}"'))
        layout.addWidget(self.checkbox_turn)
        self.setLayout(layout)
        self.labels_by_period = {}
        self.label_current = None
        self.label_current_mask = 'Прошло {} минуты {}'
        self.period_data = {}

        for period_code, period_text in enumerate(('Рассвет', 'День', 'Закат', 'Ночь')):
            layout_grid = QGridLayout()
            groupbox = QGroupBox(period_text)

            period_json = self.actuator_json.get(str(period_code), {})
            self.build_btn_set_value(layout_grid, period_code, 'Длительность:', 0, period_json.get('duration', '0'))
            if period_code % 2 != 0:
                self.build_btn_set_value(layout_grid, period_code, 'Значение:', 1, period_json.get('value', '0'))

            groupbox.setLayout(layout_grid)
            layout.addWidget(groupbox)

        if self.open_type == 'connect':
            self.label_current = QLabel('')
            button_update = QPushButton('Обновить')
            button_update.clicked.connect(self.update)
            layout.addWidget(self.label_current)
            layout.addWidget(button_update)
            self.update()


class AutoClimateControlWindow(BaseAutoWindow):
    def format_value(self, value):
        sensor = self.gcode.sensors.get(self.sensor_code, '')
        postfix = sensor.postfix if sensor else ''
        return f'{value} {postfix}'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sensors = {
            self.gcode.s_humid.code: 'Влажность',
            self.gcode.s_temperature.code: 'Температура',
        }
        self.sensor_code = int(self.actuator_json.get('sensor', -1))

        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'Автоматика с автоподстройкой значения для устройства "{self.actuator_name}"'))
        layout.addWidget(self.checkbox_turn)

        layout_grid = QGridLayout()
        layout.addLayout(layout_grid)

        text = 'Мин. допустимое значение:'
        self.label_value_min = QLabel(self.format_value(self.actuator_json.get('min', 0)))
        button = QPushButton('✎')
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, text, self.label_value_min, 'min'))
        layout_grid.addWidget(QLabel(text), 0, 0)
        layout_grid.addWidget(self.label_value_min, 0, 1)
        layout_grid.addWidget(button, 0, 2)

        text = 'Макс. допустимое значение:'
        self.label_value_max = QLabel(self.format_value(self.actuator_json.get('max', '0')))
        button = QPushButton('✎')
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, text, self.label_value_max, 'max'))
        layout_grid.addWidget(QLabel(text), 1, 0)
        layout_grid.addWidget(self.label_value_max, 1, 1)
        layout_grid.addWidget(button, 1, 2)

        text = 'Датчик:'
        sensor_code = self.sensor_code
        self.label_value_sensor = QLabel('Не выбран') if sensor_code == -1 else QLabel(self.sensors[sensor_code])
        button = QPushButton('✎')
        button.clicked.connect(lambda s: self.btn_set_value_clicked(s, text, self.label_value_sensor, 'sensor'))
        layout_grid.addWidget(QLabel(text), 2, 0)
        layout_grid.addWidget(self.label_value_sensor, 2, 1)
        layout_grid.addWidget(button, 2, 2)

        self.setLayout(layout)
        if self.open_type == 'connect':
            button_update = QPushButton('Обновить')
            button_update.clicked.connect(self.update)
            layout.addWidget(button_update)
            self.update()

    def btn_set_value_clicked(self, checked, text, label_value, what_set):
        if what_set == 'sensor':
            current_sensor_code = -1
            for sensor_code, sensor_name in self.sensors.items():
                if sensor_name == label_value.text():
                    current_sensor_code = sensor_code

            dlg = SetValueListDialog(self, text, current_sensor_code, self.sensors)
        else:
            dlg = SetValueIntegerDialog(self, text, int(label_value.text().split()[0]))

        if dlg.exec():
            if what_set == 'min':
                value = dlg.value
                label_value.setText(self.format_value(value))
                self.gcode_auto.set_min(self.actuator_code, value)
            elif what_set == 'max':
                value = dlg.value
                label_value.setText(self.format_value(value))
                self.gcode_auto.set_max(self.actuator_code, value)
            elif what_set == 'sensor':
                value = dlg.value
                label_value.setText(self.sensors[value])
                self.gcode_auto.set_sensor(self.actuator_code, value)
                self.sensor_code = value
                self.label_value_min.setText(self.format_value(self.label_value_min.text().split()[0]))
                self.label_value_max.setText(self.format_value(self.label_value_max.text().split()[0]))

    def update(self, checked=None):
        def result_update(data):
            vmin, vmax, sensor = data
            self.sensor_code = sensor
            self.label_value_min.setText(self.format_value(vmin))
            self.label_value_max.setText(self.format_value(vmax))
            self.label_value_sensor.setText(self.sensors[sensor])

        def task_update():
            return (
                self.gcode_auto.get_min(self.actuator_code),
                self.gcode_auto.get_max(self.actuator_code),
                self.gcode_auto.get_sensor(self.actuator_code),
            )

        self.worker_manager.add_and_start_worker(result_update, task_update)


class AutoTimerWindow(BaseAutoWindow):
    def update(self, checked=None):
        def result_update(data):
            pass

        def task_update():
            pass

        self.worker_manager.add_and_start_worker(result_update, task_update)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.addWidget(QLabel(f'Автоматика включения по таймеру для устройства "{self.actuator_name}"'))
        layout.addWidget(self.checkbox_turn)
        self.setLayout(layout)

        if self.open_type == 'connect':
            button_update = QPushButton('Обновить')
            button_update.clicked.connect(self.update)
            layout.addWidget(button_update)
            self.update()


class TimeWindow(QWidget):
    is_closed = False

    def set_time(self, hours, minutes):
        self.extern_label_time.setText(f'{hours:02}:{minutes:02}')
        self.label_time.setText(f'{hours:02}:{minutes:02}')
        self.hours = hours
        self.minutes = minutes

    def closeEvent(self, *args, **kwargs):
        super().closeEvent(*args, **kwargs)
        self.is_closed = True

    def update(self, checked=None):

        def result_time(data):
            (hours, minutes), source_code = data
            self.set_time(hours, minutes)
            self.label_time_source.setText(self.source_times[source_code])

        def get_time():
            return self.gcode.get_time(), self.gcode.get_time_source()

        self.worker_manager.add_and_start_worker(result_time, get_time)

    def btn_select_source_time_clicked(self, _):
        current_source_code = -1
        for source_code, source_name in self.source_times.items():
            if source_name == self.label_time_source.text():
                current_source_code = source_code

        dlg = SetValueListDialog(self, 'Источник времени', current_source_code, self.source_times)
        if dlg.exec():
            value = dlg.value
            self.label_time_source.setText(self.source_times[value])
            self.gcode.set_time_source(value)

    def btn_set_time_clicked(self, _):
        dlg = SetValueTimeDialog(self, 'Время', self.hours * 60 + self.minutes)
        if dlg.exec():
            self.set_time(dlg.hours, dlg.minutes)
            self.gcode.set_time(dlg.hours, dlg.minutes)

    def __init__(
            self,
            gcode: GrowboxGCodeBuilder,
            buff_json: dict,
            label_time,
            open_type,
            worker_manager,
            parent=None,
    ):
        super().__init__(parent=parent)
        self.extern_label_time = label_time
        self.gcode = gcode
        self.open_type = open_type
        self.worker_manager = worker_manager
        self.buff_json = buff_json
        self.setWindowTitle(f'Настройка времени')
        self.source_times = {
            0: 'Процессор', 1: 'Встроенные часы',
        }
        self.current_time = 0

        self.label_time = QLabel('--:--')
        self.label_time_source = QLabel('-')

        layout = QVBoxLayout()

        layout_time = QHBoxLayout()
        layout_time.addWidget(self.label_time)
        button = QPushButton('✎')
        button.clicked.connect(self.btn_set_time_clicked)
        layout_time.addWidget(button)

        layout_time_source = QHBoxLayout()
        layout_time_source.addWidget(self.label_time_source)
        button = QPushButton('✎')
        button.clicked.connect(self.btn_select_source_time_clicked)
        layout_time_source.addWidget(button)

        layout.addLayout(layout_time)
        layout.addLayout(layout_time_source)
        self.setLayout(layout)

        if self.open_type == 'connect':
            button_update = QPushButton('Обновить')
            button_update.clicked.connect(self.update)
            layout.addWidget(button_update)
            self.update()


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


class GCodeSendWindow(QWidget):
    def start_sending(self, checked):
        def result_send(line_index):
            self.label_progress.setText(self.progress_mask.format(line_index, self.count_lines))

        def task_send(gcode_line, line_index):
            self.gcode.write(gcode_line)
            return line_index

        with self.file_path.open() as file_gcode:
            line_index = 1
            for gcode_line in file_gcode:
                self.worker_manager.add_and_start_worker(result_send, task_send, gcode_line, line_index)
                line_index += 1

    def __init__(self, parent, gcode, file_path, worker_manager):
        super().__init__()
        self.setWindowTitle(f'Отправка G-кода в гроубокс')
        self.gcode = gcode
        self.file_path = file_path
        self.worker_manager = worker_manager

        self.progress_mask = 'Отправлено {} строк из {}'
        self.label_progress = QLabel()
        button_start = QPushButton('Начать')
        button_start.clicked.connect(self.start_sending)

        layout = QVBoxLayout()
        layout.addWidget(self.label_progress)
        layout.addWidget(button_start)
        self.setLayout(layout)

        with file_path.open() as file_gcode:
            self.count_lines = 0
            for _ in file_gcode:
                self.count_lines += 1

        self.label_progress.setText(self.progress_mask.format(0, self.count_lines))


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

    def btn_send_gcode(self, checked):
        file_path, mask = QFileDialog.getOpenFileName(self, 'Открытие G-кода', '~', '*.gcode')
        if file_path:
            window = GCodeSendWindow(self, self.gcode, Path(file_path), self.worker_manager)
            self.gcode_send_window = window
            window.show()

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
            button_action_send_gcode.triggered.connect(self.btn_send_gcode)
            # menu_file.addAction(button_action_send_json)
            menu_file.addAction(button_action_send_gcode)

    def apply_gcode_to_gui(self, gcode_line):
        parse_and_bufferize_gcode_line(self.buff_json, gcode_line)

    def open_time_window_clicked(self, checked):
        if self.window_time is None or self.window_time.is_closed:
            opened_window = TimeWindow(
                self.gcode,
                self.buff_json,
                self.label_time,
                self.open_type,
                self.worker_manager,
            )
            self.window_time = opened_window
            opened_window.show()

    def build_groupbox_time(self):
        layout = QHBoxLayout()
        self.label_time = QLabel('--:--')
        button_open_time_window = QPushButton('✎')
        button_open_time_window.clicked.connect(self.open_time_window_clicked)
        layout.addWidget(self.label_time)
        layout.addWidget(button_open_time_window)

        groupbox = QGroupBox('Время')
        # groupbox.setStyleSheet("""
        #     QGroupBox QLabel {color: #999999;}
        # """)
        groupbox.setLayout(layout)

        return groupbox

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
        dlg = SetValueIntegerDialog(self, text, int(label_value.text()))
        if dlg.exec():
            value = dlg.value
            label_value.setText(str(value))
            self.gcode.actuators[actuator_code].set(value)

    def btn_open_auto_clicked(self, checked, gcode_auto, actuator_code: int, actuator_name: str):
        auto_windows_classes = {
            self.gcode.cycle_hard.CODE: AutoCycleHardWindow,
            self.gcode.cycle_soft.CODE: AutoCycleSoftWindow,
            self.gcode.climate_control.CODE: AutoClimateControlWindow,
            self.gcode.timer.CODE: AutoTimerWindow,
        }
        window_class = auto_windows_classes[gcode_auto.CODE]
        window_key = (gcode_auto.CODE, actuator_code)
        opened_window = self.auto_windows.get(window_key)
        if opened_window is None or opened_window.is_closed:
            opened_window = window_class(
                gcode_auto,
                actuator_code,
                actuator_name,
                self.gcode,
                self.buff_json,
                self.turn_checkboxes,
                self.open_type,
                self.worker_manager,
            )
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
        layout_table.addWidget(QLabel('Таймер'), 0, 4)

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
            self.apply_gcode_to_gui(gcode_line)

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
                self.sensor_widgets[int(sensor_code)].setText('Не удалось получить')
            else:
                self.sensor_widgets[int(sensor_code)].setText(str(value))

        def get_sensors(sensor_code):
            return sensor_code, self.gcode.sensors[int(sensor_code)].get()

        def result_time(data):
            self.label_time.setText(f'{data[0]:02}:{data[1]:02}')

        def get_time():
            return self.gcode.get_time()

        self.worker_manager.add_and_start_worker(result_time, get_time)

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
        self.label_time = None
        self.window_time = None

        self.setWindowTitle('Управляющая программа')

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
                    self.apply_gcode_to_gui(gcode_line)
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
        elif open_type == 'connect' and open_subtype == 'http':
            self.print_to_status_bar(data['url'], 1)
            http_adapter = HttpAdapter(data['url'])
            self.gcode = GrowboxGCodeBuilder(
                http_adapter,
                callback_answer=lambda s: self.print_to_log(s, True),
                callback_write=lambda s: self.callback_write(s, True),
            )

        layout = QVBoxLayout()
        self.start_menubar()

        if open_type == 'connect':
            layout.addWidget(self.build_groupbox_time())
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
                self.input_port.setCurrentItem(widget_item_port)

        self.input_baudrate = QListWidget()
        for baudrate in [4800, 9600, 19200, 38400, 76800, 153600]:
            widget_item_baudrate = QListWidgetItem(str(baudrate), self.input_baudrate)
            widget_item_baudrate.setData(Qt.ItemDataRole.UserRole, baudrate)
            if baudrate == 38400:
                self.input_baudrate.setCurrentItem(widget_item_baudrate)

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


class SelectHttpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'Подключение к гроубоксу')

        buttons = QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        button_box = QDialogButtonBox(buttons)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QVBoxLayout()

        self.input_url = QLineEdit('http://192.168.0.0')

        layout_grid = QGridLayout()
        layout_grid.addWidget(QLabel('URL подключения:'), 0, 0)
        layout_grid.addWidget(self.input_url, 0, 1)

        layout.addLayout(layout_grid)
        layout.addWidget(button_box)
        self.setLayout(layout)


class PlantProfileWindow(QMainWindow):
    def btn_set_grow_mode_clicked(self, checked, radio_id):
        print(checked, radio_id)

    def collect_profile_from_gui(self) -> dict | None:
        species_lat = self.input_species_lat.text()
        if not species_lat:
            self.print_to_status_bar('Не указано видовое название растения')
            return

        current_item_shade_reaction = self.select_shade_reaction.currentItem()
        if not current_item_shade_reaction:
            self.print_to_status_bar('Не указана реакция растения на тень')
            return

        current_item_photoperiodism = self.select_photoperiodism.currentItem()
        if not current_item_photoperiodism:
            self.print_to_status_bar('Не указан фотопериодизм')
            return

        return {
            'species_lat': species_lat,
            'shade_reaction': current_item_shade_reaction.data(Qt.ItemDataRole.UserRole),
            'photoperiodism': current_item_photoperiodism.data(Qt.ItemDataRole.UserRole),
        }

    def btn_save_profile_clicked(self, checked):
        profile_data = self.collect_profile_from_gui()
        if not profile_data:
            return

        default_file_name = self.file_path.stem if self.file_path else profile_data['species_lat']
        file_path, mask = QFileDialog.getSaveFileName(self, 'Сохранение профиля', default_file_name, '*.yaml')
        if file_path:
            with open(file_path, 'w') as output_file:
                yaml.dump(profile_data, output_file)

            if not self.file_path:
                self.file_path = Path(file_path)
                self.print_to_status_bar(str(file_path), 1)
                self.setWindowTitle('Редактирование профиля растения')

        self.print_to_status_bar('Сохранено')

    def btn_generate_gcode_clicked(self, checked):
        profile_data = self.collect_profile_from_gui()
        if not profile_data:
            return

        default_file_name = self.file_path.stem if self.file_path else profile_data['species_lat']
        file_path, mask = QFileDialog.getSaveFileName(self, 'Сохранение G-код', default_file_name, '*.gcode')
        if file_path:
            with open(file_path, 'w') as output_file:
                generate_gcode(GrowboxGCodeBuilder(output=output_file), profile_data, self.grow_mode)

            if not self.file_path:
                self.file_path = Path(file_path)

        self.print_to_status_bar('Сгенерировано и Сохранено')

    def print_to_status_bar(self, message, status=0):
        if status == 0:
            self.statusBar().showMessage(message)
        elif status == 1:
            cutted_message = message if len(message) < 40 else f'{message[:19]}...{message[-18:]}'
            self.progress_bar.setText(cutted_message)

    def start_menubar(self):
        menu = self.menuBar()
        menu_file = menu.addMenu('Файл')

        button_action_save = QAction('Сохранить профиль', self)
        button_action_save.triggered.connect(self.btn_save_profile_clicked)
        menu_file.addAction(button_action_save)

    def __init__(self, file_path: Path | None = None):
        super().__init__()
        self.file_path = file_path
        self.grow_mode = VEGETATIVE_GROWING
        self.progress_bar = QLabel()
        self.statusBar().addPermanentWidget(self.progress_bar)

        if file_path:
            with file_path.open('r') as profile_file_object:
                profile_data = yaml.load(profile_file_object, Loader=yaml.Loader)

            self.print_to_status_bar(str(file_path), 1)
            self.setWindowTitle('Редактирование профиля растения')
        else:
            profile_data = {}
            self.print_to_status_bar('Новый', 1)
            self.setWindowTitle('Создание профиля растения')

        layout = QVBoxLayout()

        layout.addWidget(QLabel('Видовое название растение (на латыни):'))
        self.input_species_lat = QLineEdit(profile_data.get('species_lat', ''))
        layout.addWidget(self.input_species_lat)

        layout.addWidget(
            QLabel(
                text='Реакция растения на тень:',
                toolTip='реакция на дальний красный в тени',
                toolTipDuration=2000,
            ),
        )
        self.select_shade_reaction = QListWidget()
        items = (
            ('Теневые избегатели (вытягивают стебель)', SHADE_AVOIDANCE),
            ('Теневыносливые (увеличивают листья)', SHADE_TOLERANCE),
        )
        for item_name, item_id in items:
            item_widget = QListWidgetItem(item_name)
            item_widget.setData(Qt.ItemDataRole.UserRole, item_id)
            self.select_shade_reaction.addItem(item_widget)
            if profile_data.get('shade_reaction') == item_id:
                self.select_shade_reaction.setCurrentItem(item_widget)

        self.select_shade_reaction.setMaximumHeight(25*3)
        layout.addWidget(self.select_shade_reaction)

        layout.addWidget(
            QLabel(
                text='Фотопериодизм:',
                toolTip='реакция на изменение длин светового дня',
                toolTipDuration=2000,
            ),
        )
        self.select_photoperiodism = QListWidget()
        items = (
            ('Длиннодневные (зацветают при удлинении свет. дня)', LONG_DAY),
            ('Короткодневные (зацветают при укорочении свет. дня)', SHORT_DAY),
            ('Нейтральные (цветут при неизменной длине свет. дня)', DAY_NEUTRAL),
        )
        for item_name, item_id in items:
            item_widget = QListWidgetItem(item_name)
            item_widget.setData(Qt.ItemDataRole.UserRole, item_id)
            self.select_photoperiodism.addItem(item_widget)
            if profile_data.get('photoperiodism') == item_id:
                self.select_photoperiodism.setCurrentItem(item_widget)

        self.select_photoperiodism.setMaximumHeight(25*3)
        layout.addWidget(self.select_photoperiodism)

        group = QGroupBox('Генерация управляющей программы')

        layout_group = QVBoxLayout()
        layout_group.addWidget(QLabel('Желаемый тип развития растения:'))

        layout_mode = QHBoxLayout()
        radio_group = QButtonGroup()
        for radio_name, radio_id in (('Вегетативный', VEGETATIVE_GROWING), ('Генеративный', GENERATIVE_GROWING)):
            radio_item = QRadioButton(radio_name)
            layout_mode.addWidget(radio_item)
            radio_group.addButton(radio_item)
            radio_group.setId(radio_item, radio_id)
            if self.grow_mode == radio_id:
                radio_item.setChecked(True)

        radio_group.idClicked.connect(self.btn_set_grow_mode_clicked)
        layout_group.addLayout(layout_mode)

        button = QPushButton('Сгенерировать G-код')
        button.clicked.connect(self.btn_generate_gcode_clicked)
        layout_group.addWidget(button)
        group.setLayout(layout_group)

        layout.addWidget(group)

        widget = QWidget()
        widget.setLayout(layout)

        self.start_menubar()

        self.setCentralWidget(widget)


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

    def btn_create_plant_profile_clicked(self, checked):
        window = PlantProfileWindow()
        self.plant_profile_windows.append(window)
        window.show()

    def btn_open_plant_profile_clicked(self, checked):
        file_path, mask = QFileDialog.getOpenFileName(self, 'Открытие профиля растения', '~', '*.yaml')
        if file_path:
            window = PlantProfileWindow(file_path=Path(file_path))
            self.plant_profile_windows.append(window)
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

    def btn_connect_http_clicked(self, checked):
        dlg = SelectHttpDialog()
        if dlg.exec():
            input_url = dlg.input_url.text()
            if input_url:
                data = {
                    'url': input_url,
                }
                window = MainPanelWindow('connect', 'http', file_path=None, data=data)
                self.main_panel_windows.append(window)
                window.show()

    def __init__(self):
        super().__init__()
        self.main_panel_windows = []
        self.plant_profile_windows = []
        self.setWindowTitle('CNC Growbox')
        layout = QVBoxLayout()

        button = QPushButton('Создать управляющую программу')
        button.clicked.connect(self.btn_create_gcode_clicked)
        layout.addWidget(button)

        button = QPushButton('Открыть управляющую программу')
        button.clicked.connect(self.btn_open_gcode_clicked)
        layout.addWidget(button)

        # button = QPushButton('Открыть JSON')
        # button.clicked.connect(self.btn_open_json_clicked)
        # layout.addWidget(button)

        button = QPushButton('Подключиться по Serial')
        button.clicked.connect(self.btn_connect_serial_clicked)
        layout.addWidget(button)

        button = QPushButton('Подключиться по HTTP')
        button.clicked.connect(self.btn_connect_http_clicked)
        layout.addWidget(button)

        # button = QPushButton('Создать профиль растения')
        # button.clicked.connect(self.btn_create_plant_profile_clicked)
        # layout.addWidget(button)

        # button = QPushButton('Открыть профиль растения')
        # button.clicked.connect(self.btn_open_plant_profile_clicked)
        # layout.addWidget(button)

        widget = QWidget()
        widget.setLayout(layout)

        self.setCentralWidget(widget)


def run():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()


# handle fatal errors according to https://stackoverflow.com/questions/33736819/pyqt-no-error-msg-traceback-on-exit
def except_hook(cls, exception, traceback):
    sys.__excepthook__(cls, exception, traceback)


if __name__ == '__main__':
    sys.excepthook = except_hook
    run()
