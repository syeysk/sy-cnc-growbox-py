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

            # def write2(self, command: str, **kwargs):
    #     args = ' '.join([f'{k.upper()}{v}' for k, v in kwargs.items])
    #     self.output.write(f'{command} {args}')

    def write(self, data: str):
        self.output.write(f'{data}\n'.encode())
        if self.need_wait_answer:
            return self.output.read(100)

        return None


class Actuator:
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
        return self.output.write(f'E2 S{self.code}')


class AutoCycle:
    # Periods
    DAY = 1
    NIGHT = 0

    def __init__(self, output: WriterInterface):
        self.output = output

    def turn(self, actuator: Actuator, status: bool):
        return self.output.write(f'E100 A{actuator} B{int(status)}')

    def set_duration(self, actuator: Actuator, period: int, duration: int):
        return self.output.write(f'E101 A{actuator} B{period} D{duration}')

    def set_value(self, actuator: Actuator, period: int, value: int):
        return self.output.write(f'E103 A{actuator} B{period} V{value}')


class AutoCycleSoft:
    # Periods
    SUNRISE = 0
    DAY = 1
    SUNSET = 2
    NIGHT = 3

    def __init__(self, output: WriterInterface):
        self.output = output

    def turn(self, actuator: Actuator, status: bool):
        return self.output.write(f'E150 A{actuator} B{int(status)}')

    def set_duration(self, actuator: Actuator, period: int, duration: int):
        return self.output.write(f'E151 A{actuator} P{period} D{duration}')

    def set_value(self, actuator: Actuator, period: int, value: int):
        return self.output.write(f'E153 A{actuator} P{period} V{value}')


class GrowboxGCodeBuilder:
    def __init__(self, output: io.TextIOWrapper | serial.Serial = sys.stdout):
        self.output = WriterInterface(output)

        self.a_humid = Actuator(0, self.output)
        self.a_extractor = Actuator(1, self.output)
        self.a_white_light = Actuator(2, self.output)
        self.a_fred_light = Actuator(3, self.output)

        self.s_temperature = Sensor(0, self.output)
        self.s_humid = Sensor(1, self.output)

        self.cycle_hard = AutoCycle(self.output)
        self.cycle_soft = AutoCycleSoft(self.output)

    def turn_off_all_auto(self):
        return self.output.write('E3')

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
