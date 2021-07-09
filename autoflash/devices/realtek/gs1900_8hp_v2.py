from ...registry import Device
from ... import Serial, Network
from ...dnsmasq import Dnsmasq
from ...ssh import do_sysupgrade_ssh, wait_for_ssh

device = Device("realtek", "zyxel_gs1900-8hp-v2")


@device.register_step
def get_boot_console(serial: Serial):
    serial.setup(115200)

    serial.wait_for_partial(b"U-Boot Version:")
    serial.write(b" ")
    serial.wait_for_partial(b"RTL838x#")


@device.register_step
def boot(serial: Serial, network: Network, initramfs: str, failsafe: bool = False):
    serial.setup(115200)
    get_boot_console(serial)

    network.setup_ipv4("192.168.1.2")
    with Dnsmasq(tftp={"initramfs.bin": initramfs}):
        serial.write(
            b"rtk network on;"
            b"setsys bootpartition 0;"
            b"tftpboot 0x84f00000 192.168.1.2:initramfs.bin;"
            b"bootm\n"
        )
        serial.wait_for(b"done$")

    if failsafe:
        serial.wait_for(
            b"Press the \\[f\\] key and hit \\[enter\\] to enter failsafe mode"
        )
        serial.write(b"f\n")


@device.register_step
def sysupgrade(network: Network, sysupgrade: str, options: str = "-v"):
    network.setup_ipv4("192.168.1.2", vlan=100)
    wait_for_ssh("192.168.1.1")
    do_sysupgrade_ssh(
        "192.168.1.1",
        sysupgrade,
        options=options,
    )


@device.register_step
def miniterm(serial: Serial):
    serial.setup(115200)
    serial.miniterm(eol="lf")
