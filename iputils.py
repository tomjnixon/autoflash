import subprocess
import json


def run(cmd):
    output = subprocess.check_output(["ip", "-j"] + cmd)
    if output:
        return json.loads(output)


def get_if_info(ifname, info):
    [if_info] = [info_i for info_i in info if info_i["ifname"] == ifname]
    return if_info


def setup_ipv4(ifname, ip, prefixlen=24):
    ensure_ipv4(ifname, ip, prefixlen)
    ensure_up(ifname)


def ensure_ipv4(ifname, ip, prefixlen):
    info = get_if_info(ifname, run(["addr", "show", ifname]))

    addrs = [
        (addr["local"], addr["prefixlen"])
        for addr in info["addr_info"]
        if addr["family"] == "inet"
    ]

    found = False
    for current_ip, current_prefixlen in addrs:
        if current_ip == ip and current_prefixlen == prefixlen:
            found = True
        else:
            run(["addr", "del", f"{current_ip}/{current_prefixlen}", "dev", ifname])

    if not found:
        run(["addr", "add", f"{ip}/{prefixlen}", "dev", ifname])


def ensure_up(ifname):
    info = get_if_info(ifname, run(["link", "show", ifname]))
    if "UP" not in info["flags"]:
        run(["link", "set", "up", "dev", ifname])


if __name__ == "__main__":
    # print(run(["link", "set"]))
    setup_ipv4("enp0s25", "192.168.1.1")
