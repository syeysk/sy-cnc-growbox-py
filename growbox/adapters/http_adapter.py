import requests

from growbox.sygrowbox.base_adapter import BaseAdapter


class HttpAdapter(BaseAdapter):
    def __init__(self, url, timeout_read: int, timeout_write):
        self.url = url
        self.response_data = ''
        self.timeout_read = int(timeout_read)
        self.timeout_write = timeout_write

    def write(self, data: bytes):
        str_data = data.decode('utf-8')
        params = {'action': 'send_to_serial', 'string_data': str_data, 'timeout_read': self.timeout_read}
        try:
            response = requests.post(f'{self.url}/api.c', params=params, timeout=self.timeout_write)
        except requests.ReadTimeout as error:
            print('read:', str(error), 'gcode:', str_data)
        except requests.ConnectTimeout as error:
            print('connect timeout:', str(error), 'gcode:', str_data)
        except requests.ConnectionError as error:
            print('connect error:', str(error), 'gcode:', str_data)
        else:
            if response.status_code == 200:
                string_response_data = response.json()['data']['string_response_data']
                self.response_data = f'{self.response_data}{string_response_data}'

    def read(self, length):
        data_to_return = self.response_data[:length]
        self.response_data = self.response_data[length:]
        return data_to_return.encode('utf-8')

    def close(self):
        pass
