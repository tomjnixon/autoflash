from ...registry import Device
from ... import Network
from ...dnsmasq import Dnsmasq
from ...ssh import do_sysupgrade_ssh, wait_for_ssh
from ... import ssh
import re

device = Device("generic", "routerboard_generic")


@device.register_step
def get_key(network: Network, fname: str):
    network.setup_ipv4("192.168.88.10")
    ssh.wait_for_ssh("192.168.88.1")

    ssh.run_command("admin@192.168.88.1", "/system license output".split())
    file_list_str = ssh.run_command("admin@192.168.88.1", "/file print".split())

    # parse key file from listing
    remote_fname = None
    for line in file_list_str.split(b"\n"):
        res = re.match(b" *\\d+ *(\\S+\\.key) *\\.key file", line)
        if res is not None:
            remote_fname = res.group(1).decode()

    assert remote_fname is not None

    ssh.scp_file("admin@192.168.88.1", remote_fname, fname)


@device.register_step
def boot(network: Network, initramfs: str):
    message = """
    To start the TFTP bootloader:
        - power-cycle or reset the device
        - immediately hold the reset button (before lights turn on)
        - wait for a light to:
            - turn on for 5 seconds
            - flash for 5 seconds
            - stay on for 5 seconds
            - turn off
        - release the reset button
    """
    print(message)
    network.setup_ipv4("192.168.1.2")
    with Dnsmasq(
        tftp={"initramfs.bin": initramfs},
        dhcp_boot="initramfs.bin",
        dhcp="192.168.1.100,192.168.1.200",
        bootp=True,
    ) as dnsmasq:
        dnsmasq.wait_for_tftp("initramfs.bin")

    print("for failsafe, press reset button once light starts to flash")


@device.register_step
def sysupgrade(network: Network, sysupgrade: str, options: str = "-v"):
    network.setup_ipv4("192.168.1.2")
    wait_for_ssh("192.168.1.1")
    do_sysupgrade_ssh(
        "192.168.1.1",
        sysupgrade,
        options=options,
    )
