import sys

from sygrowbox.base_adapter import BaseAdapter
from sygrowbox.gcode_parser import parse_answer

# commands = {}


# def dec(gcode_command, verbose_command, **kwargs):
#     def dec2(function):
#         commands[gcode_command] = (verbose_command, {k.upper(): v for k, v in kwargs.items()})
#         return function
#
#     return dec2


class WriterInterface:
    def __init__(self, output, need_wait_answer: bool = False, callback_answer=None, callback_write=None):
        self.output = output
        self.callback_answer = callback_answer
        self.callback_write = callback_write
        # if need_wait_answer is None:
        #     self.need_wait_answer = hasattr(output, 'read') #isinstance(output, serial.Serial)
        # else:
        self.need_wait_answer = need_wait_answer
        self.mocked_answer = None

    def mock_answer(self, answer):
        self.mocked_answer = answer

    def _read_until_end(self, count_lines=1, end_byte=b'\n', max_bytes=100):
        received_bytes = []
        for _ in range(max_bytes):
            received_byte = self.output.read(1)
            if not received_byte:
                break

            received_bytes.append(received_byte)
            if received_byte == end_byte:
                count_lines -= 1

            if count_lines == 0:
                break

        return b''.join(received_bytes)

    def write(self, data: str, count_lines_to_receive=1, timeout=None, max_bytes=100):
        if timeout and hasattr(self.output, 'timeout'):
            prev_timeout = self.output.timeout
            self.output.timeout = timeout

        answer = None
        data = f'{data}\n'

        if self.callback_write:
            self.callback_write(data)

        if self.mocked_answer:
            answer = self.mocked_answer
            self.mocked_answer = None
        else:
            self.output.write(data.encode('utf-8'))
            if self.need_wait_answer:
                answer = self._read_until_end(count_lines_to_receive, max_bytes=max_bytes)  # self.output.read(100)
                # answer = self.output.read(100)
                if self.callback_answer:
                    self.callback_answer(answer)

        if timeout and hasattr(self.output, 'timeout'):
            self.output.timeout = prev_timeout

        return answer

    def write_and_parse(self, *args, **kwargs):
        answer = self.write(*args, **kwargs)
        return parse_answer(answer)

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

    def get(self) -> int:
        answer_lines = self.output.write_and_parse(f'E1 A{self.code}', 2)
        return int(answer_lines[0][1]) if self.output.need_wait_answer else None

    def set(self, value: int):
        return self.output.write(f'E0 A{self.code} V{value}')


class Sensor:
    def __init__(self, code: int, output: WriterInterface, postfix):
        self.code = code
        self.output = output
        self.postfix = postfix

    def __str__(self):
        return str(self.code)

    def get(self) -> float:
        answer_lines = self.output.write_and_parse(f'E2 S{self.code}', 2, 2.2)
        return answer_lines[0][1] if self.output.need_wait_answer else None


class BaseAuto:
    CODE = None

    def __init__(self, output: WriterInterface):
        self.output = output

    def turn(self, actuator: Actuator | int | str, status: bool):
        return self.output.write(f'E3 R{self.CODE} A{actuator} B{int(status)}')

    def is_turn(self, actuator: Actuator | int | str) -> bool:
        answer_lines = self.output.write_and_parse(f'E4 R{self.CODE} A{actuator}', 2)
        return bool(answer_lines[0][1]) if self.output.need_wait_answer else None


class AutoCycleHard(BaseAuto):
    CODE = 0
    DEFAULT_TURN = False
    DEFAULT_VALUE = 0
    DEFAULT_DURATION = 0
    # Periods
    DAY = 1
    NIGHT = 0
    PERIODS = [DAY, NIGHT]

    def get_current(self, actuator: Actuator | int | str):
        answer_lines = self.output.write_and_parse(f'E102 A{actuator}', 3)
        return (int(answer_lines[0][1]), int(answer_lines[1][1])) if self.output.need_wait_answer else None

    def set_duration(self, actuator: Actuator | int | str, period: int, duration: int):  # TODO: duration - объект Time
        return self.output.write(f'E101 A{actuator} B{period} D{duration}')

    def get_duration(self, actuator: Actuator | int | str, period: int):  # TODO: duration - объект Time
        answer_lines = self.output.write_and_parse(f'E1011 A{actuator} B{period}', 2)
        return int(answer_lines[0][1]) if self.output.need_wait_answer else None

    def set_value(self, actuator: Actuator | int | str, period: int, value: int):
        return self.output.write(f'E103 A{actuator} B{period} V{value}')

    def get_value(self, actuator: Actuator | int | str, period: int):
        answer_lines = self.output.write_and_parse(f'E1031 A{actuator} B{period}', 2)
        return int(answer_lines[0][1]) if self.output.need_wait_answer else None


class AutoCycleSoft(BaseAuto):
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

    def get_current(self, actuator: Actuator | int | str):
        answer_lines = self.output.write_and_parse(f'E152 A{actuator}', 3)
        return (int(answer_lines[0][1]), int(answer_lines[1][1])) if self.output.need_wait_answer else None

    def set_duration(self, actuator: Actuator | int | str, period: int, duration: int):  # TODO: duration - объект Time
        return self.output.write(f'E151 A{actuator} P{period} D{duration}')

    def get_duration(self, actuator: Actuator | int | str, period: int):  # TODO: duration - объект Time
        answer_lines = self.output.write_and_parse(f'E1511 A{actuator} P{period}', 2)
        return int(answer_lines[0][1]) if self.output.need_wait_answer else None

    def set_value(self, actuator: Actuator | int | str, period: int, value: int):
        return self.output.write(f'E153 A{actuator} P{period} V{value}')

    def get_value(self, actuator: Actuator | int | str, period: int):
        answer_lines = self.output.write_and_parse(f'E1531 A{actuator} P{period}', 2)
        return int(answer_lines[0][1]) if self.output.need_wait_answer else None


class AutoClimateControl(BaseAuto):
    CODE = 2
    DEFAULT_TURN = False
    DEFAULT_MIN = 0
    DEFAULT_MAX = 0

    def set_min(self, actuator: Actuator | int | str, value: int):
        return self.output.write(f'E202 A{actuator} V{value}')

    def get_min(self, actuator: Actuator | int | str):
        answer_lines = self.output.write_and_parse(f'E2021 A{actuator}', 2)
        return int(answer_lines[0][1]) if self.output.need_wait_answer else None

    def set_max(self, actuator: Actuator | int | str, value: int):
        return self.output.write(f'E203 A{actuator} V{value}')

    def get_max(self, actuator: Actuator | int | str):
        answer_lines = self.output.write_and_parse(f'E2031 A{actuator}', 2)
        return int(answer_lines[0][1]) if self.output.need_wait_answer else None

    def set_sensor(self, actuator: Actuator | int | str, sensor: Sensor | int | str):
        return self.output.write(f'E201 A{actuator} S{sensor}')

    def get_sensor(self, actuator: Actuator | int | str):
        answer_lines = self.output.write_and_parse(f'E2011 A{actuator}', 2)
        return int(answer_lines[0][1]) if self.output.need_wait_answer else None


class AutoTimer(BaseAuto):
    CODE = 3
    DEFAULT_TURN = False
    PARTS_PER_HOUR = 4

    def _get_bit(self, hour_index: int, minute_index: int, minutes_bits):
        index_bit = self.PARTS_PER_HOUR * hour_index + minute_index
        index_byte = index_bit // 8
        index_bit_inside_byte = index_bit % 8
        return minutes_bits[index_byte] >> (7 - index_bit_inside_byte) & 1

    def get_minute_bits(self, actuator: Actuator | int | str):
        answer_lines = self.output.write_and_parse(f'E2511 A{actuator}', 13, max_bytes=123)
        return [int(line[1]) for line in answer_lines] if self.output.need_wait_answer else None

    def set_minute_bits(self, actuator: Actuator | int | str, byte_index: int, byte_value: int):
        return self.output.write(f'E251 A{actuator} B{byte_index} V{byte_value}')

    def get_minute_flags(self, actuator: Actuator | int | str):
        minutes_bits = self.get_minute_bits(actuator)
        if not minutes_bits:
            return

        minute_flags = []
        for hour_index in range(0, 24):
            minute_flags.append([0] * self.PARTS_PER_HOUR)
            for minute_index in range(0, self.PARTS_PER_HOUR):
                minute_flags[hour_index][minute_index] = self._get_bit(hour_index, minute_index, minutes_bits)

        return minute_flags

    def set_minute_flag(self, actuator: Actuator | int | str, hour_index: int, minute_index: None | int, value: bool):
        if minute_index is None:
            return self.output.write(f'E252 A{actuator} H{hour_index} B{int(value)}')
        else:
            return self.output.write(f'E252 A{actuator} H{hour_index} M{minute_index} B{int(value)}')

    def get_minute_flag(self, actuator: Actuator | int | str, hour_index: int, minute_index: int):
        answer_lines = self.output.write_and_parse(f'E2521 A{actuator} H{hour_index} M{minute_index}', 2)
        return int(answer_lines[0][1]) if self.output.need_wait_answer else None


class GrowboxGCodeBuilder:
    """Генерирует G-код и отправляет в гроубокс"""
    A_HUMID = 0
    A_EXTRACTOR = 1
    A_WHITE_LIGHT = 2
    A_FRED_LIGHT = 3

    def __init__(
            self,
            output: BaseAdapter = sys.stdout,
            callback_answer=None,
            callback_write=None,
            need_wait_answer=False,
    ):
        self.output = WriterInterface(
            output,
            callback_answer=callback_answer,
            callback_write=callback_write,
            need_wait_answer=need_wait_answer,
        )

        self.a_humid = Actuator(self.A_HUMID, self.output)
        self.a_extractor = Actuator(self.A_EXTRACTOR, self.output)
        self.a_white_light = Actuator(self.A_WHITE_LIGHT, self.output)
        #self.a_fred_light = Actuator(self.A_FRED_LIGHT, self.output)
        self.actuators = {
            self.a_humid.code: self.a_humid,
            self.a_extractor.code: self.a_extractor,
            self.a_white_light.code: self.a_white_light,
            #self.a_fred_light.code: self.a_fred_light,
        }

        self.s_temperature = Sensor(0, self.output, '°C')
        self.s_humid = Sensor(1, self.output, '%')
        self.sensors = {
            self.s_temperature.code: self.s_temperature,
            self.s_humid.code: self.s_humid,
        }

        self.cycle_hard = AutoCycleHard(self.output)
        self.cycle_soft = AutoCycleSoft(self.output)
        self.climate_control = AutoClimateControl(self.output)
        self.timer = AutoTimer(self.output)
        self.autos = {
            self.cycle_hard.CODE: self.cycle_hard,
            self.cycle_soft.CODE: self.cycle_soft,
            self.climate_control.CODE: self.climate_control,
            self.timer.CODE: self.timer,
        }

    def execute(self, methods_chain_str: str, args: dict, answer=None):
        method = self
        for method_str in methods_chain_str.split('.'):
            method = method[int(method_str)] if method_str.isdigit() else getattr(method, method_str)

        if answer:
            self.output.mock_answer(answer)

        return method(**args)

    def set_actuator_value(self, actuator, value: int):
        return self.actuators[actuator].set(value)

    def write(self, gcode_line: str, count_lines=1):
        return self.output.write(gcode_line, count_lines)

    def turn_off_all_autos(self):
        return self.output.write('E3')

    def get_time(self): # TODO: отдавать объект Time
        answer_lines = self.output.write_and_parse('E81', 3)
        return (int(answer_lines[0][1]), int(answer_lines[1][1])) if self.output.need_wait_answer else None

    def set_time(self, hours, minutes): # TODO: передавать объект Time
        return self.output.write(f'E8 H{hours} M{minutes}')

    def get_time_source(self):
        answer_lines = self.output.write_and_parse('E91', 2)
        return int(answer_lines[0][1]) if self.output.need_wait_answer else None

    def set_time_source(self, source_code):
        return self.output.write(f'E9 T{source_code}')


if __name__ == '__main__':
    import serial
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
