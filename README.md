# Python interfaces for CNC Growbox

It's python and GUI interfaces for [CNC Growbox ](https://github.com/syeysk/sy-cnc-growbox).

## Install

To install this program use:

```shell
pip install git+https://github.com/syeysk/sy-cnc-growbox-py.git
```

## Use python-api interface

To use the python-api interface:

```python
from growbox.gcode_builder import GrowboxGCodeBuilder

gcode = GrowboxGCodeBuilder()
# G-code will be printed to console
gcode.a_white_light.set(255) 
gcode.s_temperature.get() 
```

or

```python
from growbox.gcode_builder import GrowboxGCodeBuilder
from serial.tools.list_ports import comports
import serial


port = None
for port, desc, hwid in comports():
    print(port)
    break

with serial.Serial(port, baudrate=9600, timeout=2, write_timeout=0.1) as opened_serial:
    gcode = GrowboxGCodeBuilder(opened_serial)
    print(opened_serial.read(100))
    # G-code will be sent to serial port
    print(gcode.a_white_light.set(255))
    print(gcode.s_temperature.get())
```

## Use GUI

To run GUI use:

```shell
growbox
```

or 

```shell
python -m growbox.gui
```
