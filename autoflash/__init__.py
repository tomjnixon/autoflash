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
import subprocess
import time


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


class Network:
    def __init__(self, ifname):
        self.ifname = ifname

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    def setup_ipv4(self, ip, prefixlen=24):
        iputils.setup_ipv4(self.ifname, ip, prefixlen)


def sha256(fname):
    import hashlib

    h = hashlib.sha256()
    with open(fname, "rb") as f:
        while block := f.read(1000000):
            h.update(block)
    return h.hexdigest()


def wait_for_ssh(address):
    def can_connect():
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            try:
                s.connect((address, 22))
            except socket.timeout:
                logging.info(f"waiting for {address}:22")
                return False
            except OSError:
                logging.info(f"error connecting to {address}:22; waiting...")
                return False
        return True

    while not can_connect():
        time.sleep(1)


def do_sysupgrade_ssh(address, sysupgrade_fname, options="-v"):
    ssh_args = (
        "-Fnone -oUserKnownHostsFile=/dev/null -oStrictHostKeyChecking=no".split()
    )

    checksum = sha256(sysupgrade_fname)

    fname = "/tmp/sysupgrade.bin"
    commands = [
        f"cat > {fname}",
        f"echo '{checksum}  {fname}' | sha256sum -c > /dev/null",
        f"sysupgrade {options} {fname}",
    ]
    command = " && ".join(commands)
    with open(sysupgrade_fname, "rb") as f:
        subprocess.check_call(["ssh", *ssh_args, f"root@{address}", command], stdin=f)
