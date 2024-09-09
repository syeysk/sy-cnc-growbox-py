from sygrowbox.base_adapter import BaseAdapter
from sygrowbox.gcode_parser import parse_gcode_line


class BaseEmulator(BaseAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.answer = ''

    def println(self, data):
        self.answer = f'{self.answer}{data}\r\n'

    def print(self, data):
        self.answer = f'{self.answer}{data}'

    def comment(self, letter: str, value: float):
        self.println(f'{letter}:{value:.2f}')

    def write(self, data: bytes):
        str_data = data.decode('utf-8')
        for gcode_line in str_data.split('\n'):
            if not gcode_line:
                continue

            g = parse_gcode_line(gcode_line)
            func = getattr(self, g.command.lower())
            if func:
                func(g)

        self.println('ok')

    def read(self, length):
        data_to_return = self.answer[:length]
        self.answer = self.answer[length:]
        return data_to_return.encode('utf-8')

    def close(self):
        pass