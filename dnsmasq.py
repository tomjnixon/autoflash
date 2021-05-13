import tempfile
import shutil
from pathlib import Path
import subprocess
import logging
import time
import getpass


class Dnsmasq:
    def __init__(self, tftp: dict = {}):
        self.tftp = tftp
        self.tmpdir = None
        self.dnsmasq = None
        self.logger = logging.getLogger("dnsmasq")

    def __enter__(self):
        self.tmpdir = tempfile.TemporaryDirectory("dnsmasq")
        pid_file = Path(self.tmpdir.name) / "dnsmasq.pid"

        args = ["dnsmasq", "--port=0", f"--pid-file={pid_file}"]
        args += [
            "--keep-in-foreground",
            "--log-facility=-",
            "--user=" + getpass.getuser(),
        ]

        if self.tftp:
            tftp_root = Path(self.tmpdir.name) / "tftp"
            for name, src_path in self.tftp.items():
                dest_path = tftp_root / name
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(src_path, dest_path)

            args.extend(["--enable-tftp", f"--tftp-root={tftp_root}"])

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
