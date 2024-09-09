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


def parse_answer(answer):
    values = []
    if answer:
        if not isinstance(answer, str):
            answer = answer.decode('utf-8')

        answer_lines = answer.strip().split('\r\n')[:-1]
        for line in answer_lines:
            value = line[2:].strip()
            value = None if value.upper() == 'NAN' else float(value)
            values.append((line[1], value))

    return values
