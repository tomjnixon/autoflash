from typing import Optional
from tempfile import TemporaryDirectory
import shutil
from pathlib import Path
import subprocess
import logging
import time
import getpass


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

    def __enter__(self):
        self.tmpdir = TemporaryDirectory("dnsmasq")
        pid_file = Path(self.tmpdir.name) / "dnsmasq.pid"

        args = ["dnsmasq", "--port=0", f"--pid-file={pid_file}"]
        args += [
            "--keep-in-foreground",
            "--log-facility=-",
            "--user=" + getpass.getuser(),
        ]

        if self.dhcp is not None:
            args.append(f"--dhcp-range={self.dhcp}")

        if self.tftp:
            tftp_root = Path(self.tmpdir.name) / "tftp"
            for name, src_path in self.tftp.items():
                dest_path = tftp_root / name
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src_path, dest_path)

            args.extend(["--enable-tftp", f"--tftp-root={tftp_root}"])

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
        if self.tmpdir is not None:
            self.tmpdir.cleanup()

        if self.process is not None:
            self.process.kill()
            self.process.wait()
