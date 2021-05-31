import logging
import time
import socket
from .misc import sha256
import subprocess


def wait_for_ssh(address):
    def can_connect():
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
