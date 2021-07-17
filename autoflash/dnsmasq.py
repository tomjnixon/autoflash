from typing import Optional
from tempfile import TemporaryDirectory
import shutil
from pathlib import Path
import subprocess
import logging
import time
import getpass
import threading
from queue import Queue
import os

responder_script = """#!/bin/bash
fifo="{fifo}"

(
    for arg in "$@"; do
        echo "arg $arg"
    done

    env | grep ^DNSMASQ | while read var; do
        echo "var $var"
    done

    echo end
) >> $fifo
"""


class ReaderThread(threading.Thread):
    def __init__(self, fifo_path, queue):
        self.fifo_path = fifo_path
        self.queue = queue

        super().__init__()

    def run(self):
        while True:
            with open(self.fifo_path, "r") as f:
                contents = f.read()
                args = []
                variables = {}
                for line in contents.splitlines(False):
                    cmd, sep, rest = line.partition(" ")

                    if cmd == "quit":
                        return
                    elif cmd == "arg":
                        args.append(rest)
                    elif cmd == "var":
                        name, value = rest.split("=", 1)
                        variables[name] = value
                    elif cmd == "end":
                        self.queue.put((args.copy(), variables.copy()))
                        args.clear()
                        variables.clear()

    def quit(self):
        with open(self.fifo_path, "w") as f:
            f.write("quit\n")
        self.join()


class Dnsmasq:
    def __init__(self, tftp: dict = {}, dhcp=None, dhcp_boot=None, bootp=False):
        self.tftp = tftp
        self.dhcp = dhcp
        self.dhcp_boot = dhcp_boot
        self.bootp = bootp
        self.tmpdir: Optional[TemporaryDirectory[str]] = None
        self.dnsmasq = None
        self.logger = logging.getLogger("dnsmasq")

        if self.dhcp_boot is not None:
            assert self.dhcp is not None

    def wait_for_tftp(self, filename=None):
        while True:
            args, env = self.queue.get()
            if args[0] == "tftp":
                size, address, path = args[1:]

                if filename is None or self.tftp_root / filename == Path(path):
                    return

    def __enter__(self):
        self.tmpdir = TemporaryDirectory("dnsmasq")
        pid_file = Path(self.tmpdir.name) / "dnsmasq.pid"

        self.fifo = Path(self.tmpdir.name) / "fifo"
        os.mkfifo(self.fifo)

        self.queue = Queue()
        self.reader_thread = ReaderThread(self.fifo, self.queue)
        self.reader_thread.start()

        script_f = Path(self.tmpdir.name) / "script"
        with open(script_f, "w") as f:
            f.write(responder_script.format(fifo=self.fifo))
        script_f.chmod(0o777)

        args = [
            "dnsmasq",
            "--port=0",
            f"--pid-file={pid_file}",
            "--keep-in-foreground",
            "--log-facility=-",
            "--user=" + getpass.getuser(),
            f"--dhcp-script={script_f}",
        ]

        if self.dhcp is not None:
            args.append(f"--dhcp-range={self.dhcp}")

        if self.tftp:
            self.tftp_root = Path(self.tmpdir.name) / "tftp"
            for name, src_path in self.tftp.items():
                dest_path = self.tftp_root / name
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src_path, dest_path)

            args.extend(["--enable-tftp", f"--tftp-root={self.tftp_root}"])

        if self.dhcp_boot:
            args.append(f"--dhcp-boot={self.dhcp_boot}")

        if self.bootp:
            args.append("--bootp-dynamic")

        self.logger.debug(f"running {' '.join(args)}")
        self.process = subprocess.Popen(args)

        for _i in range(30):
            if pid_file.exists():
                break
            self.logger.debug("waiting for dnsmasq to start")
            time.sleep(1)
        else:
            raise Exception("dnsmasq failed to start")

        return self

    def __exit__(self, *exc):
        self.reader_thread.quit()

        if self.process is not None:
            self.process.kill()
            self.process.wait()

        if self.tmpdir is not None:
            self.tmpdir.cleanup()
