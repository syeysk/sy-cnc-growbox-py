class BaseAdapter:
    def write(self, data: bytes):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def read(self, length: int) -> bytes:
        raise NotImplementedError()
