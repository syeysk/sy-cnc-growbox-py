from dataclasses import dataclass, field


@dataclass()
class GCodeLine:
    command: str = None
    cletter: str = None
    cvalue: int = None
    params: dict = field(default_factory=dict)

    def __getitem__(self, key):
        return self.params[key.upper()]

    def __contains__(self, key):
        return key.upper() in self.params


def parse_gcode_line(gcode_line):
    gcode_parts = gcode_line.split()
    if not gcode_parts:
        return GCodeLine(command='', cletter='', cvalue=0)

    gcode_parts[0] = gcode_parts[0].upper()
    gcode_line = GCodeLine(command=gcode_parts[0], cletter=gcode_parts[0][0], cvalue=int(gcode_parts[0][1:]))
    for part in gcode_parts[1:]:
        gcode_line.params[part[0].upper()] = int(part[1:])

    return gcode_line


class MachineBase:
    def __init__(self):
        self.answer = ''

    def println(self, data):
        self.answer = f'{self.answer}{data}\r\n'

    def print(self, data):
        self.answer = f'{self.answer}{data}'

    def comment(self, letter: str, value: float):
        self.println(f'{letter}:{value:.2f}')

    def write(self, gcode: str):
        for gcode_line in gcode.split('\n'):
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
        return data_to_return.encode()


def parse_answer(answer):
    answer_lines = answer.decode().strip().split('\r\n')[:-1]
    values = []
    for line in answer_lines:
        value = line[2:].strip()
        value = None if value.upper() == 'NAN' else float(value)
        values.append((line[1], value))

    return values
