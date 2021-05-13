import logging
import serial
import serial.threaded
from serial.tools.miniterm import Miniterm
import queue
import traceback
import re
from dataclasses import dataclass
import iputils
from dnsmasq import Dnsmasq


@dataclass
class Line:
    data: bytes


@dataclass
class PartialLine:
    data: bytes


class SerialProtocol(serial.threaded.Protocol):
    def __init__(self, logger: logging.Logger, queue: queue.Queue, sep=b"\r\n"):
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
            self.logger.info(f"rx: {part}")

        if parts[-1]:
            self.queue.put(PartialLine(parts[-1]))
        self.buffer = parts[-1]

    def connection_lost(self, exc):
        if exc is not None:
            # traceback.print_exc(exc)
            self.logger.error(exc)
        self.logger.info("connection closed")


class Serial:
    def __init__(self, port, baud):
        self.serial = serial.Serial(port, baud)
        assert hasattr(self.serial, "cancel_read")
        self.logger = logging.getLogger("serial")
        self.logger.info("here")
        self.queue = queue.Queue()

        def make_protocol():
            return SerialProtocol(self.logger, self.queue)

        self.protocol = serial.threaded.ReaderThread(self.serial, make_protocol)

    def __enter__(self):
        self.protocol.start()
        return self

    def __exit__(self, *exc):
        self.protocol.stop()

    def clear(self):
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
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


class Network:
    def __init__(self, ifname):
        self.ifname = ifname

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def setup_ipv4(self, ip, prefixlen=24):
        iputils.setup_ipv4(self.ifname, ip, prefixlen)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    with Serial("/dev/ttyUSB0", 115200) as serial:
        serial.wait_for_partial(b"Hit any key to stop autoboot:")
        serial.write(b"a")
        serial.wait_for_partial(b"VR9 #")

        iputils.setup_ipv4("enp0s25", "192.168.1.2")

        initramfs = "/tmp/openwrt-lantiq-xrx200-bt_homehub-v5a-initramfs-kernel.bin"
        with Dnsmasq(tftp={"initramfs.bin": initramfs}) as dnsmasq:
            serial.write(
                b"setenv ipaddr 192.168.1.1;"
                b"setenv serverip 192.168.1.2;"
                b"tftpboot 0x81000000 initramfs.bin;"
                b"bootm 0x81000000\n"
            )
            serial.wait_for(b"done$")
        serial.miniterm(eol="lf")
