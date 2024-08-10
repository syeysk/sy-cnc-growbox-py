from growbox.gcode_builder import AutoCycleHard, AutoCycleSoft, AutoClimateControl, AutoTimer
from growbox.gcode_parser import MachineBase


class BuffEmulator(MachineBase):
    def __init__(self):
        super().__init__()
        self.buff = {}
        self.a_cycle_hard = self.buff.setdefault(str(AutoCycleHard.CODE), {})
        self.a_cycle_soft = self.buff.setdefault(str(AutoCycleSoft.CODE), {})
        self.a_climate_control = self.buff.setdefault(str(AutoClimateControl.CODE), {})
        self.a_timer = self.buff.setdefault(str(AutoTimer.CODE), {})
        self.time = self.buff.setdefault('time', {})
        self.mode = 'w'

    ## Датчики и исполнительные устройства, общие команды

    def e0(self, g):
        self.buff['set_actuator_value'] = {'actuator': g['A'], 'value': g['V']}
        self.buff.setdefault('actuators', {}).setdefault(str(g['A']), {})['value'] = g['V']

    def e1(self, g):
        self.comment('V', self.buff.get('actuators', {}).get(str(g['A']), {}).get('value', 255))

    def e2(self, g):
        pass

    def e3(self, g):
        if 'R' in g and 'A' in g:
            self.buff.setdefault(str(g['R']), {}).setdefault(str(g['A']), {})['turn'] = g['B']
        else:
            for actuator_code in range(0, 3):
                for auto_code in range(0, 4):
                    self.buff.setdefault(str(auto_code), {}).setdefault(str(actuator_code), {})['turn'] = False

    def e4(self, g):
        actuator_json = self.buff.get(str(g['R']), {}).get(str(g['A']), {})
        self.comment('B', int(actuator_json.get('turn', False)))

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
        period_json = self.a_cycle_hard.get(str(g['A']), {}).get(str(g['B']), {})
        self.comment('D', int(period_json.get('duration', '0')))

    def e102(self, g):
        pass

    def e103(self, g):
        self.buff['cycle_hard.set_value'] = {'actuator': g['A'], 'period': g['B'], 'value': g['V']}
        self.a_cycle_hard.setdefault(str(g['A']), {}).setdefault(str(g['B']), {})['value'] = str(g['V'])

    def e1031(self, g):
        period_json = self.a_cycle_hard.get(str(g['A']), {}).get(str(g['B']), {})
        self.comment('V', int(period_json.get('value', '0')))

    ## Циклическая автоматика с плавной сменой периода

    def e151(self, g):
        self.buff['cycle_soft.set_duration'] = {'actuator': g['A'], 'period': g['P'], 'duration': g['D']}
        self.a_cycle_soft.setdefault(str(g['A']), {}).setdefault(str(g['P']), {})['duration'] = str(g['D'])

    def e1511(self, g):
        period_json = self.a_cycle_soft.get(str(g['A']), {}).get(str(g['P']), {})
        self.comment('D', int(period_json.get('duration', '0')))

    def e152(self, g):
        pass

    def e153(self, g):
        self.buff['cycle_soft.set_value'] = {'actuator': g['A'], 'period': g['P'], 'value': g['V']}
        self.a_cycle_soft.setdefault(str(g['A']), {}).setdefault(str(g['P']), {})['value'] = str(g['V'])

    def e1531(self, g):
        period_json = self.a_cycle_soft.get(str(g['A']), {}).get(str(g['P']), {})
        self.comment('V', int(period_json.get('value', '0')))

    ## Условная автоматика климат-контроля

    def e201(self, g):
        self.buff['climate_control.set_sensor'] = {'actuator': g['A'], 'sensor': g['S']}
        self.a_climate_control.setdefault(str(g['A']), {})['sensor'] = g['S']

    def e2011(self, g):
        self.comment('S', int(self.a_climate_control.get(str(g['A']), {}).get('sensor', '-1')))

    def e202(self, g):
        self.buff['climate_control.set_min'] = {'actuator': g['A'], 'value': g['V']}
        self.a_climate_control.setdefault(str(g['A']), {})['min'] = str(g['V'])

    def e2021(self, g):
        self.comment('V', int(self.a_climate_control.get(str(g['A']), {}).get('min', '0')))

    def e203(self, g):
        self.buff['climate_control.set_max'] = {'actuator': g['A'], 'value': g['V']}
        self.a_climate_control.setdefault(str(g['A']), {})['max'] = str(g['V'])

    def e2031(self, g):
        self.comment('V', int(self.a_climate_control.get(str(g['A']), {}).get('max', '0')))

    ## Автоматика по таймеру

    def e251(self, g):
        self.buff['timer.set_minute_bits'] = {'actuator': g['A'], 'minute_byte': g['B'], 'byte_value': g['V']}
        self.a_timer.setdefault(str(g['A']), {})[str(g['B'])] = str(g['V'])

    def e2511(self, g):
        bytes_dict = self.a_timer.get(str(g['A']), {})
        bytes_list = [0] * 12  # TODO: 12 replace by constanta
        for byte_index, byte_value in bytes_dict.items():
            if byte_index.isdigit():
                bytes_list[int(byte_index)] = int(byte_value)

        for byte_value in bytes_list:
            self.comment('V', byte_value)

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
