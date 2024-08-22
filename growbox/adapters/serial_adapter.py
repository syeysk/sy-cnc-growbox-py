import serial

from growbox.sygrowbox.base_adapter import BaseAdapter


class SerialAdapter(BaseAdapter):
    def __init__(self, port: str, baudrate: int, timeout_read: int, timeout_write: int):
        self.serial = serial.Serial(
            port,
            baudrate=baudrate,
            timeout=timeout_read,
            write_timeout=timeout_write,
        )

    def write(self, data: bytes):
        self.serial.write(data)
    
    def read(self, length: int):
        return self.serial.read(length)

    def close(self):
        self.serial.close()
