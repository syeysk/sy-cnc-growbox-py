from sygrowbox.gcode_builder import AutoCycleHard, AutoCycleSoft, AutoClimateControl, AutoTimer
from sygrowbox.base_emulator import BaseEmulator


class BuffEmulator(BaseEmulator):
    def __init__(self):
        super().__init__()
        self.buff = {}
        self.a_cycle_hard = self.buff.setdefault(str(AutoCycleHard.CODE), {})
        self.a_cycle_soft = self.buff.setdefault(str(AutoCycleSoft.CODE), {})
        self.a_climate_control = self.buff.setdefault(str(AutoClimateControl.CODE), {})
        self.a_timer = self.buff.setdefault(str(AutoTimer.CODE), {})
        self.time = self.buff.setdefault('time', {})
        self.mode = 'w'

    def get_default_time_bytes(self):
        return [0] * 12

    def get_default_time_flags(self):
        return [[0] * 4] * 24

    ## Датчики и исполнительные устройства, общие команды

    def e0(self, g):
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
        self.time['time'] = (g['H'], g['M'])

    def e81(self, g):
        pass

    def e9(self, g):
        self.time['source'] = g['T']

    def e91(self, g):
        self.comment('T', self.time.get('source', 0))

    ## Циклическая автоматика с резким переключением периода

    def e101(self, g):
        self.a_cycle_hard.setdefault(str(g['A']), {}).setdefault(str(g['B']), {})['duration'] = str(g['D'])

    def e1011(self, g):
        period_json = self.a_cycle_hard.get(str(g['A']), {}).get(str(g['B']), {})
        self.comment('D', int(period_json.get('duration', '0')))

    def e102(self, g):
        pass

    def e103(self, g):
        self.a_cycle_hard.setdefault(str(g['A']), {}).setdefault(str(g['B']), {})['value'] = str(g['V'])

    def e1031(self, g):
        period_json = self.a_cycle_hard.get(str(g['A']), {}).get(str(g['B']), {})
        self.comment('V', int(period_json.get('value', '255' if g['B'] else '0')))

    ## Циклическая автоматика с плавной сменой периода

    def e151(self, g):
        self.a_cycle_soft.setdefault(str(g['A']), {}).setdefault(str(g['P']), {})['duration'] = str(g['D'])

    def e1511(self, g):
        period_json = self.a_cycle_soft.get(str(g['A']), {}).get(str(g['P']), {})
        self.comment('D', int(period_json.get('duration', '0')))

    def e152(self, g):
        pass

    def e153(self, g):
        self.a_cycle_soft.setdefault(str(g['A']), {}).setdefault(str(g['P']), {})['value'] = str(g['V'])

    def e1531(self, g):
        period_json = self.a_cycle_soft.get(str(g['A']), {}).get(str(g['P']), {})
        self.comment('V', int(period_json.get('value', '0')))

    ## Условная автоматика климат-контроля

    def e201(self, g):
        self.a_climate_control.setdefault(str(g['A']), {})['sensor'] = g['S']

    def e2011(self, g):
        self.comment('S', int(self.a_climate_control.get(str(g['A']), {}).get('sensor', '0')))

    def e202(self, g):
        self.a_climate_control.setdefault(str(g['A']), {})['min'] = str(g['V'])

    def e2021(self, g):
        self.comment('V', int(self.a_climate_control.get(str(g['A']), {}).get('min', '0')))

    def e203(self, g):
        self.a_climate_control.setdefault(str(g['A']), {})['max'] = str(g['V'])

    def e2031(self, g):
        self.comment('V', int(self.a_climate_control.get(str(g['A']), {}).get('max', '0')))

    ## Автоматика по таймеру

    def e251(self, g):
        actuator_data = self.a_timer.setdefault(str(g['A']), {})
        bytes_list = actuator_data.get('bytes')
        if not bytes_list:
            bytes_list = self.get_default_time_bytes()
            actuator_data['bytes'] = bytes_list

        bytes_list[g['B']] = g['V']

    def e2511(self, g):
        actuator_data = self.a_timer.setdefault(str(g['A']), {})
        bytes_list = actuator_data.get('bytes')
        if not bytes_list:
            bytes_list = self.get_default_time_bytes()
            actuator_data['bytes'] = bytes_list

        for byte_value in bytes_list:
            self.comment('V', byte_value)

    def e252(self, g):
        actuator_data = self.a_timer.setdefault(str(g['A']), {})
        flags_list = actuator_data.get('flags')
        if not flags_list:
            flags_list = self.get_default_time_flags()
            actuator_data['flags'] = flags_list

        if 'M' in g:
            flags_list[g['H']][g['M']] = g['B']
        else:
            flags_list[g['H']] = [g['B']] * 4

    def e2521(self, g):
        actuator_data = self.a_timer.setdefault(str(g['A']), {})
        flags_list = actuator_data.get('flags')
        if not flags_list:
            flags_list = self.get_default_time_flags()
            actuator_data['flags'] = flags_list

        self.comment('B', flags_list[g['H']][g['M']])

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
