import logging
from dataclasses import dataclass
from queue import Queue, Empty
import re
import serial
import serial.threaded
from typing import Optional
from .registry import Context


@dataclass
class SerialData:
    data: bytes


@dataclass
class Line(SerialData):
    pass


@dataclass
class PartialLine(SerialData):
    pass


class SerialProtocol(serial.threaded.Protocol):
    def __init__(self, logger: logging.Logger, queue: Queue[SerialData], sep=b"\r\n"):
        super().__init__()
        self.logger = logger
        self.queue = queue
        self.sep = sep
        self.buffer = b""

    def connection_made(self, transport):
        super().connection_made(transport)
        self.logger.info("connection made")

    def data_received(self, data):
        super().data_received(data)

        self.buffer += data
        parts = self.buffer.split(self.sep)
        for part in parts[:-1]:
            self.queue.put(Line(part))
            self.logger.info(f"rx: {part!r}")

        if parts[-1]:
            self.queue.put(PartialLine(parts[-1]))
        self.buffer = parts[-1]

    def connection_lost(self, exc):
        if exc is not None:
            # traceback.print_exc(exc)
            self.logger.error(exc)
        self.logger.info("connection closed")


class Serial(Context):
    def __init__(self, serial_port: Optional[str] = None):
        assert serial_port is not None
        self.serial = serial.Serial(serial_port, 115200)
        assert hasattr(self.serial, "cancel_read")
        self.logger = logging.getLogger("serial")
        self.queue: Queue[SerialData] = Queue()

        def make_protocol():
            return SerialProtocol(self.logger, self.queue)

        self.protocol = serial.threaded.ReaderThread(self.serial, make_protocol)

    def __enter__(self):
        self.protocol.start()
        return self

    def __exit__(self, *exc):
        self.protocol.stop()

    def setup(self, baudrate: int):
        if self.serial.baudrate != baudrate:
            self.serial.baudrate = baudrate

    def clear(self):
        while True:
            try:
                self.queue.get_nowait()
            except Empty:
                break

    def wait_for(self, regex):
        while True:
            line = self.queue.get()
            if isinstance(line, Line):
                match = re.match(regex, line.data)
                if match is not None:
                    return match

    def wait_for_partial(self, regex):
        """match partial or full lines"""
        while True:
            line = self.queue.get()
            match = re.match(regex, line.data)
            if match is not None:
                return match

    def write(self, data):
        self.logger.info(f"tx: {data}")
        self.serial.write(data)

    def miniterm(self, **kwargs):
        from serial.tools.miniterm import Miniterm

        print("entering miniterm; press crtl-] to exit")
        self.protocol.stop()

        miniterm = Miniterm(self.serial, **kwargs)

        # miniterm.exit_character = unichr(args.exit_char)
        # miniterm.menu_character = unichr(args.menu_char)
        # miniterm.raw = args.raw
        miniterm.set_rx_encoding("UTF-8")
        miniterm.set_tx_encoding("UTF-8")

        miniterm.start()
        try:
            miniterm.join(True)
        except KeyboardInterrupt:
            pass
        miniterm.join()
        miniterm.close()
