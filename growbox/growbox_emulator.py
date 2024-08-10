from gcode_builder import AutoCycleHard, AutoCycleSoft, AutoClimateControl, AutoTimer
from gcode_parser import MachineBase


class GrowboxEmulator(MachineBase):
    def __init__(self, buff_json):
        super().__init__()
        self.buff = buff_json
        self.a_cycle_hard = self.buff.setdefault(str(AutoCycleHard.CODE), {})
        self.a_cycle_soft = self.buff.setdefault(str(AutoCycleSoft.CODE), {})
        self.a_climate_control = self.buff.setdefault(str(AutoClimateControl.CODE), {})
        self.a_timer = self.buff.setdefault(str(AutoTimer.CODE), {})
        self.time = self.buff.setdefault('time', {})

    ## Датчики и исполнительные устройства, общие команды

    def e0(self, g):
        self.buff['set_actuator_value'] = {'actuator': g['A'], 'value': g['V']}
        self.buff.setdefault('actuators', {}).setdefault(str(g['A']), {})['value'] = g['V']

    def e1(self, g):
        pass

    def e2(self, g):
        pass

    def e3(self, g):
        if 'R' in g and 'A' in g:
            self.buff.setdefault(str(g['R']), {}).setdefault(str(g['A']), {})['turn'] = g['B']

    def e4(self, g):
        pass

    ## Время

    def e8(self, g):
        self.buff['set_time'] = {'hours': g['H'], 'minutes': g['M']}
        self.time['time'] = (g['H'], g['M'])

    def e81(self, g):
        pass

    def e9(self, g):
        self.buff['set_time_source'] = {'source': g['T']}
        self.time['source'] = g['T']

    def e91(self, g):
        pass

    ## Циклическая автоматика с резким переключением периода

    def e101(self, g):
        self.buff['cycle_hard.set_duration'] = {'actuator': g['A'], 'period': g['B'], 'duration': g['D']}
        self.a_cycle_hard.setdefault(str(g['A']), {}).setdefault(str(g['B']), {})['duration'] = str(g['D'])

    def e1011(self, g):
        pass

    def e102(self, g):
        pass

    def e103(self, g):
        self.buff['cycle_hard.set_value'] = {'actuator': g['A'], 'period': g['B'], 'value': g['V']}
        self.a_cycle_hard.setdefault(str(g['A']), {}).setdefault(str(g['B']), {})['value'] = str(g['V'])

    def e1031(self, g):
        pass

    ## Циклическая автоматика с плавной сменой периода

    def e151(self, g):
        self.buff['cycle_soft.set_duration'] = {'actuator': g['A'], 'period': g['P'], 'duration': g['D']}
        self.a_cycle_soft.setdefault(str(g['A']), {}).setdefault(str(g['P']), {})['duration'] = str(g['D'])

    def e1511(self, g):
        pass

    def e152(self, g):
        pass

    def e153(self, g):
        self.buff['cycle_soft.set_value'] = {'actuator': g['A'], 'period': g['P'], 'value': g['V']}
        self.a_cycle_soft.setdefault(str(g['A']), {}).setdefault(str(g['P']), {})['value'] = str(g['V'])

    def e1531(self, g):
        pass

    ## Условная автоматика климат-контроля

    def e201(self, g):
        self.buff['climate_control.set_sensor'] = {'actuator': g['A'], 'sensor': g['S']}
        self.a_climate_control.setdefault(str(g['A']), {})['sensor'] = g['S']

    def e2011(self, g):
        pass

    def e202(self, g):
        self.buff['climate_control.set_min'] = {'actuator': g['A'], 'value': g['V']}
        self.a_climate_control.setdefault(str(g['A']), {})['min'] = str(g['V'])

    def e2021(self, g):
        pass

    def e203(self, g):
        self.buff['climate_control.set_max'] = {'actuator': g['A'], 'value': g['V']}
        self.a_climate_control.setdefault(str(g['A']), {})['max'] = str(g['V'])

    def e2031(self, g):
        pass

    ## Автоматика по таймеру

    def e251(self, g):
        self.buff['timer.set_minute_bits'] = {'actuator': g['A'], 'minute_byte': g['B'], 'byte_value': g['V']}
        self.a_timer.setdefault(str(g['A']), {})[str(g['B'])] = str(g['V'])

    def e2511(self, g):
        pass

#     gcode = parse_gcode_line(gcode_line)
#     # from gcode_builder import commands
#     # descr = commands.get(gcode.command)
#     # if descr:
#     #     function, kwargs_descr = descr
#     #     buf_temp = buff_json.setdefault(function, {})
#     #     for name_gcode, name_python in list(kwargs_descr.items())[:1]:
#     #         buf_temp = buf_temp.setdefault(str(gcode.params[name_gcode]), {})
#     #
#     #     if kwargs_descr:
#     #         name_gcode, name_python = list(kwargs_descr.items())[-1]
#     #         buf_temp[name_python] = gcode.params[name_gcode]
#
