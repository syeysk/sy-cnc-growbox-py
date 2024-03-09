from dataclasses import dataclass, field


@dataclass()
class GCodeLine:
    command: str = None
    cletter: str = None
    cvalue: int = None
    params: dict = field(default_factory=dict)

    def __getitem__(self, key):
        return self.params[key.upper()]


def parse_gcode_line(gcode_line):
    gcode_parts = gcode_line.split()
    gcode_parts[0] = gcode_parts[0].upper()
    gcode_line = GCodeLine(command=gcode_parts[0], cletter=gcode_parts[0][0], cvalue=int(gcode_parts[0][1:]))
    for part in gcode_parts[1:]:
        gcode_line.params[part[0].upper()] = int(part[1:])

    return gcode_line
