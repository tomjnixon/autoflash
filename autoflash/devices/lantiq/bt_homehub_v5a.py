from ...registry import Device
from ... import Serial, Network, do_sysupgrade_ssh, wait_for_ssh
from ...dnsmasq import Dnsmasq

device = Device("lantiq", "bt_homehub-v5a")


@device.register_step
def get_boot_console(serial: Serial):
    serial.setup(115200)

    serial.wait_for_partial(b"Hit any key to stop autoboot:")
    serial.write(b"a")
    serial.wait_for_partial(b"VR9 #")


@device.register_step
def boot(serial: Serial, network: Network, initramfs: str):
    serial.setup(115200)
    get_boot_console(serial)

    network.setup_ipv4("192.168.1.2")
    with Dnsmasq(tftp={"initramfs.bin": initramfs}):
        serial.write(
            b"setenv ipaddr 192.168.1.1;"
            b"setenv serverip 192.168.1.2;"
            b"tftpboot 0x81000000 initramfs.bin;"
            b"bootm 0x81000000\n"
        )
        serial.wait_for(b"done$")


@device.register_step
def miniterm(serial: Serial):
    serial.setup(115200)
    serial.miniterm(eol="lf")
