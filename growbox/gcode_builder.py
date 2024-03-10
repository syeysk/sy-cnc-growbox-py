import io
import sys

import serial

# commands = {}


# def dec(gcode_command, verbose_command, **kwargs):
#     def dec2(function):
#         commands[gcode_command] = (verbose_command, {k.upper(): v for k, v in kwargs.items()})
#         return function
#
#     return dec2


class WriterInterface:
    def __init__(self, output, need_wait_answer: bool | None = None, callback_answer=None, callback_write=None):
        self.output = output
        self.callback_answer = callback_answer
        self.callback_write = callback_write
        if need_wait_answer is None:
            self.need_wait_answer = isinstance(output, serial.Serial)
        else:
            self.need_wait_answer = need_wait_answer

    def write(self, data: str):
        answer = None
        data = f'{data}\n'
        mode = getattr(self.output, 'mode', 'wb')
        encoding = getattr(self.output, 'encoding', 'utf-8')

        if self.callback_write:
            self.callback_write(data)

        if mode == 'wb':
            data = data.encode(encoding)

        self.output.write(data)
        if self.need_wait_answer:
            answer = self.output.read(100)
            if self.callback_answer:
                self.callback_answer(answer)

        return answer

    # def write2(self, command: str, **kwargs):
    #     args = ' '.join([f'{k.upper()}{v}' for k, v in kwargs.items])
    #     self.write(f'{command} {args}')


class Actuator:
    DEFAULT_VALUE = 0

    def __init__(self, code: int, output: WriterInterface):
        self.code = code
        self.output = output

    def __str__(self):
        return str(self.code)

    def get(self):
        return self.output.write(f'E1 A{self.code}')

    def set(self, value: int):
        return self.output.write(f'E0 A{self.code} V{value}')


class Sensor:
    def __init__(self, code: int, output: WriterInterface):
        self.code = code
        self.output = output

    def __str__(self):
        return str(self.code)

    def get(self):
        answer = self.output.write(f'E2 S{self.code}')
        answer_lines = answer.decode().split('\r\n')
        value = answer_lines[0][2:].strip()
        return None if value == 'NAN' else float(value)


class AutoCycleHard:
    CODE = 0
    DEFAULT_TURN = False
    DEFAULT_VALUE = 0
    DEFAULT_DURATION = 0
    # Periods
    DAY = 1
    NIGHT = 0
    PERIODS = [DAY, NIGHT]

    def __init__(self, output: WriterInterface):
        self.output = output

    # @dec('E100', 'cycle_hard_turn', a='actuator', b='status')
    def turn(self, actuator: Actuator | int | str, status: bool):
        return self.output.write(f'E100 A{actuator} B{int(status)}')

    def is_turn(self, actuator: Actuator | int | str) -> bool:
        answer = self.output.write(f'E1001 A{actuator}')
        answer_lines = answer.decode().split('\r\n')
        return bool(float(answer_lines[0][2:]))

    def set_duration(self, actuator: Actuator | int | str, period: int, duration: int):
        return self.output.write(f'E101 A{actuator} B{period} D{duration}')

    def get_duration(self, actuator: Actuator | int | str, period: int):
        answer = self.output.write(f'E1011 A{actuator} B{period}')
        answer_lines = answer.decode().split('\r\n')
        return int(float(answer_lines[0][2:]))

    def set_value(self, actuator: Actuator | int | str, period: int, value: int):
        return self.output.write(f'E103 A{actuator} B{period} V{value}')

    def get_value(self, actuator: Actuator | int | str, period: int):
        answer = self.output.write(f'E1031 A{actuator} B{period}')
        answer_lines = answer.decode().split('\r\n')
        return int(float(answer_lines[0][2:]))


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

    def __init__(self, output: WriterInterface):
        self.output = output

    # @dec('E150', 'cycle_soft_turn', a='actuator', b='status')
    def turn(self, actuator: Actuator | int | str, status: bool):
        return self.output.write(f'E150 A{actuator} B{int(status)}')

    def is_turn(self, actuator: Actuator | int | str) -> bool:
        answer = self.output.write(f'E1501 A{actuator}')
        answer_lines = answer.decode().split('\r\n')
        return bool(float(answer_lines[0][2:]))

    def set_duration(self, actuator: Actuator | int | str, period: int, duration: int):
        return self.output.write(f'E151 A{actuator} P{period} D{duration}')

    def get_duration(self, actuator: Actuator | int | str, period: int):
        answer = self.output.write(f'E1511 A{actuator} P{period}')
        answer_lines = answer.decode().split('\r\n')
        return int(float(answer_lines[0][2:]))

    def set_value(self, actuator: Actuator | int | str, period: int, value: int):
        return self.output.write(f'E153 A{actuator} P{period} V{value}')

    def get_value(self, actuator: Actuator | int | str, period: int):
        answer = self.output.write(f'E1531 A{actuator} P{period}')
        answer_lines = answer.decode().split('\r\n')
        return int(float(answer_lines[0][2:]))


class AutoClimateControl:
    CODE = 2
    DEFAULT_TURN = False
    DEFAULT_MIN = 0
    DEFAULT_MAX = 0

    def __init__(self, output: WriterInterface):
        self.output = output

    # @dec('E200', 'climate_control_turn', a='actuator', b='status')
    def turn(self, actuator: Actuator | int | str, status: bool):
        return self.output.write(f'E200 A{actuator} B{int(status)}')

    def is_turn(self, actuator: Actuator | int | str) -> bool:
        answer = self.output.write(f'E2001 A{actuator}')
        answer_lines = answer.decode().split('\r\n')
        return bool(float(answer_lines[0][2:]))

    def set_min(self, actuator: Actuator | int | str, value: int):
        return self.output.write(f'E202 A{actuator} V{value}')

    def get_min(self, actuator: Actuator | int | str):
        answer = self.output.write(f'E2021 A{actuator}')
        answer_lines = answer.decode().split('\r\n')
        return int(float(answer_lines[0][2:]))

    def set_max(self, actuator: Actuator | int | str, value: int):
        return self.output.write(f'E203 A{actuator} V{value}')

    def get_max(self, actuator: Actuator | int | str):
        answer = self.output.write(f'E2031 A{actuator}')
        answer_lines = answer.decode().split('\r\n')
        return int(float(answer_lines[0][2:]))

    def set_sensor(self, actuator: Actuator | int | str, sensor: Sensor | int | str):
        return self.output.write(f'E201 A{actuator} S{sensor}')

    def get_sensor(self, actuator: Actuator | int | str):
        answer = self.output.write(f'E2011 A{actuator}')
        answer_lines = answer.decode().split('\r\n')
        return int(float(answer_lines[0][2:]))


class GrowboxGCodeBuilder:
    A_HUMID = 0
    A_EXTRACTOR = 1
    A_WHITE_LIGHT = 2
    A_FRED_LIGHT = 3

    def __init__(
            self, output: io.TextIOWrapper | serial.Serial = sys.stdout, callback_answer=None, callback_write=None,
    ):
        self.output = WriterInterface(output, callback_answer=callback_answer, callback_write=callback_write)

        self.a_humid = Actuator(self.A_HUMID, self.output)
        self.a_extractor = Actuator(self.A_EXTRACTOR, self.output)
        self.a_white_light = Actuator(self.A_WHITE_LIGHT, self.output)
        self.a_fred_light = Actuator(self.A_FRED_LIGHT, self.output)
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

        self.cycle_hard = AutoCycleHard(self.output)
        self.cycle_soft = AutoCycleSoft(self.output)
        self.climate_control = AutoClimateControl(self.output)
        self.autos = {
            self.cycle_hard.CODE: self.cycle_hard,
            self.cycle_soft.CODE: self.cycle_soft,
            self.climate_control.CODE: self.climate_control,
        }

    def turn_off_all_autos(self):
        return self.output.write('E3')


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
