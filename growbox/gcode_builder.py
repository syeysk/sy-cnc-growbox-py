import io
import sys

import serial


class WriterInterface:
    def __init__(self, output, need_wait_answer: bool | None = None):
        self.output = output
        if need_wait_answer is None:
            self.need_wait_answer = isinstance(output, serial.Serial)
        else:
            self.need_wait_answer = need_wait_answer

    def write(self, data: str):
        data = f'{data}\n'
        mode = getattr(self.output, 'mode', 'wb')
        encoding = getattr(self.output, 'encoding', 'utf-8')

        if mode == 'wb':
            data = data.encode(encoding)

        self.output.write(data)
        if self.need_wait_answer:
            return self.output.read(100)

        return None


class Actuator:
    DEFAULT_VALUE = 0

    def __init__(self, code: int, output: WriterInterface, buff_json, buff_to_json):
        self.code = code
        self.output = output
        self.buff_json = buff_json.setdefault('actuators', {}).setdefault(str(code), {})
        self.buff_to_json = buff_to_json

    def __str__(self):
        return str(self.code)

    def get(self):
        return self.output.write(f'E1 A{self.code}')

    def set(self, value: int):
        if self.buff_to_json:
            self.buff_json['value'] = value

        return self.output.write(f'E0 A{self.code} V{value}')

    def buff2gcode(self):
        self.set(self.buff_json.get('value', self.DEFAULT_VALUE))


class Sensor:
    def __init__(self, code: int, output: WriterInterface):
        self.code = code
        self.output = output

    def __str__(self):
        return str(self.code)

    def get(self):
        return self.output.write(f'E2 S{self.code}')


class AutoCycleHard:
    CODE = 0
    DEFAULT_TURN = False
    DEFAULT_VALUE = 0
    DEFAULT_DURATION = 0
    # Periods
    DAY = 1
    NIGHT = 0
    PERIODS = [DAY, NIGHT]

    def __init__(self, output: WriterInterface, buff_json, buff_to_json):
        self.output = output
        self.buff_json = buff_json.setdefault(str(self.CODE), {})
        self.buff_to_json = buff_to_json

    def turn(self, actuator: Actuator | int | str, status: bool):
        if self.buff_to_json:
            self.buff_json.setdefault(str(actuator), {})['turn'] = status

        return self.output.write(f'E100 A{actuator} B{int(status)}')

    def set_duration(self, actuator: Actuator | int | str, period: int, duration: int):
        if self.buff_to_json:
            self.buff_json.setdefault(str(actuator), {}).setdefault(period, {})['duration'] = duration

        return self.output.write(f'E101 A{actuator} B{period} D{duration}')

    def set_value(self, actuator: Actuator | int | str, period: int, value: int):
        if self.buff_to_json:
            self.buff_json.setdefault(str(actuator), {}).setdefault(period, {})['value'] = value

        return self.output.write(f'E103 A{actuator} B{period} V{value}')

    def buff2gcode_set(self, actuator):
        actuator_json = self.buff_json.get(str(actuator), {})
        for period in self.PERIODS:
            period_json = actuator_json.get(period, {})
            self.set_value(actuator, period, period_json.get('value', self.DEFAULT_VALUE))
            self.set_duration(actuator, period, period_json.get('value', self.DEFAULT_VALUE))

    def buff2gcode_turn_on_if_need(self, actuator):
        actuator_json = self.buff_json.get(str(actuator), {})
        value = actuator_json.get('turn', self.DEFAULT_TURN)
        if value:
            self.turn(actuator, value)


class AutoCycleSoft:
    CODE = 1
    DEFAULT_TURN = False
    DEFAULT_VALUE = 0
    DEFAULT_DURATION = 0
    # Periods
    SUNRISE = 0
    DAY = 1
    SUNSET = 2
    NIGHT = 3
    PERIODS = [SUNRISE, DAY, SUNSET, NIGHT]

    def __init__(self, output: WriterInterface, buff_json, buff_to_json):
        self.output = output
        self.buff_json = buff_json.setdefault(str(self.CODE), {})
        self.buff_to_json = buff_to_json

    def turn(self, actuator: Actuator | int | str, status: bool):
        if self.buff_to_json:
            self.buff_json.setdefault(str(actuator), {})['turn'] = status

        return self.output.write(f'E150 A{actuator} B{int(status)}')

    def set_duration(self, actuator: Actuator | int | str, period: int, duration: int):
        if self.buff_to_json:
            self.buff_json.setdefault(str(actuator), {}).setdefault(period, {})['duration'] = duration

        return self.output.write(f'E151 A{actuator} P{period} D{duration}')

    def set_value(self, actuator: Actuator | int | str, period: int, value: int):
        if self.buff_to_json:
            self.buff_json.setdefault(str(actuator), {}).setdefault(period, {})['value'] = value

        return self.output.write(f'E153 A{actuator} P{period} V{value}')

    def buff2gcode_set(self, actuator):
        actuator_json = self.buff_json.get(str(actuator), {})
        for period in self.PERIODS:
            period_json = actuator_json.get(period, {})
            self.set_value(actuator, period, period_json.get('value', self.DEFAULT_VALUE))
            self.set_duration(actuator, period, period_json.get('value', self.DEFAULT_VALUE))

    def buff2gcode_turn_on_if_need(self, actuator):
        actuator_json = self.buff_json.get(str(actuator), {})
        value = actuator_json.get('turn', self.DEFAULT_TURN)
        if value:
            self.turn(actuator, value)


class AutoClimateControl:
    CODE = 2
    DEFAULT_TURN = False
    DEFAULT_MIN = 0
    DEFAULT_MAX = 0

    def __init__(self, output: WriterInterface, buff_json, buff_to_json):
        self.output = output
        self.buff_json = buff_json.setdefault(str(self.CODE), {})
        self.buff_to_json = buff_to_json

    def turn(self, actuator: Actuator | int | str, status: bool):
        if self.buff_to_json:
            self.buff_json.setdefault(str(actuator), {})['turn'] = status

        return self.output.write(f'E200 A{actuator} B{int(status)}')

    def set_min(self, actuator: Actuator | int | str, value: int):
        if self.buff_to_json:
            self.buff_json.setdefault(str(actuator), {})['min'] = value

        return self.output.write(f'E202 A{actuator} V{value}')

    def set_max(self, actuator: Actuator | int | str, value: int):
        if self.buff_to_json:
            self.buff_json.setdefault(str(actuator), {})['max'] = value

        return self.output.write(f'E203 A{actuator} V{value}')

    def set_sensor(self, actuator: Actuator | int | str, sensor: Sensor | int | str):
        if self.buff_to_json:
            self.buff_json.setdefault(str(actuator), {})['sensor'] = str(sensor)

        return self.output.write(f'E201 A{actuator} S{sensor}')

    def buff2gcode_set(self, actuator):
        actuator_json = self.buff_json.get(str(actuator), {})
        self.set_min(actuator, actuator_json.get('min', self.DEFAULT_MIN))
        self.set_max(actuator, actuator_json.get('max', self.DEFAULT_MAX))
        sensor = actuator_json.get('sensor')
        if sensor is not None:
            self.set_sensor(actuator, sensor)

    def buff2gcode_turn_on_if_need(self, actuator):
        actuator_json = self.buff_json.get(str(actuator), {})
        value = actuator_json.get('turn', self.DEFAULT_TURN)
        if value:
            self.turn(actuator, value)


class GrowboxGCodeBuilder:
    A_HUMID = 0
    A_EXTRACTOR = 1
    A_WHITE_LIGHT = 2
    A_FRED_LIGHT = 3

    def __init__(self, output: io.TextIOWrapper | serial.Serial = sys.stdout, buff_to_json=False, buff_json=None):
        self.buff_json = {} if buff_json is None else buff_json
        self.buff_to_json = buff_to_json

        self.output = WriterInterface(output)

        self.a_humid = Actuator(self.A_HUMID, self.output, self.buff_json, self.buff_to_json)
        self.a_extractor = Actuator(self.A_EXTRACTOR, self.output, self.buff_json, self.buff_to_json)
        self.a_white_light = Actuator(self.A_WHITE_LIGHT, self.output, self.buff_json, self.buff_to_json)
        self.a_fred_light = Actuator(self.A_FRED_LIGHT, self.output, self.buff_json, self.buff_to_json)
        self.actuators = {
            self.a_humid.code: self.a_humid,
            self.a_extractor.code: self.a_extractor,
            self.a_white_light.code: self.a_white_light,
            self.a_fred_light.code: self.a_fred_light,
        }

        self.s_temperature = Sensor(0, self.output)
        self.s_humid = Sensor(1, self.output)
        self.sensors = {
            self.s_temperature.code: self.s_temperature,
            self.s_humid.code: self.s_humid,
        }

        self.cycle_hard = AutoCycleHard(self.output, self.buff_json, self.buff_to_json)
        self.cycle_soft = AutoCycleSoft(self.output, self.buff_json, self.buff_to_json)
        self.climate_control = AutoClimateControl(self.output, self.buff_json, self.buff_to_json)
        self.autos = {
            self.cycle_hard.CODE: self.cycle_hard,
            self.cycle_soft.CODE: self.cycle_soft,
            self.climate_control.CODE: self.climate_control,
        }

    def turn_off_all_autos(self):
        if self.buff_to_json:
            self.buff_json['turn_off_all_autos'] = True

        return self.output.write('E3')

    def buff2gcode(self):
        # stop all autos
        if self.buff_json.get('turn_off_all_autos', True):
            self.turn_off_all_autos()

        # set values on actuators
        for actuator in self.actuators.values():
            actuator.buff2gcode()

        # set autos
        for actuator in self.actuators.values():
            for auto in self.autos.values():
                auto.buff2gcode_set(actuator)

        # start autos if needs
        for actuator in self.actuators.values():
            for auto in self.autos.values():
                auto.buff2gcode_turn_on_if_need(actuator)

    # E4


if __name__ == '__main__':
    from serial.tools.list_ports import comports

    port = None
    for port, desc, hwid in comports():
        print(port)
        break

    with serial.Serial(port, baudrate=9600, timeout=2, write_timeout=0.1) as opened_serial:
        #opened_serial.write(gcode)
        #answer = opened_serial.read(100)
        gcode = GrowboxGCodeBuilder(opened_serial)
        print(opened_serial.read(100))
        print(gcode.a_white_light.set(255))
        print(gcode.a_humid.set(255))
        print(gcode.a_extractor.set(255))
        print(gcode.s_humid.get())
        print(gcode.s_temperature.get())
