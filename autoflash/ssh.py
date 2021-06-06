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
    logger = logging.getLogger("ssh")

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
        args = ["ssh", *ssh_args, f"root@{address}", command]
        proc = subprocess.Popen(
            args,
            stdin=f,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        # normally sysupgrade will close the ssh shell, causing ssh to fail;
        # detect this and don't raise an error even if ssh exits non-zeroly
        lines = []
        while line := proc.stdout.readline():
            lines.append(line)
            logger.info(line.strip())
        rc = proc.wait()

        commencing_str = b"Commencing upgrade. Closing all shell sessions"
        has_commencing = any(commencing_str in line for line in lines)

        if rc != 0 and not has_commencing:
            raise Exception("ssh failed")
