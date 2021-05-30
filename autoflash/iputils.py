import subprocess
import json


def run(cmd):
    output = subprocess.check_output(["ip", "-j"] + cmd)
    if output:
        return json.loads(output)


def get_if_info(ifname, info):
    [if_info] = [info_i for info_i in info if info_i["ifname"] == ifname]
    return if_info


def setup_vlans(ifname, vlans=[]):
    info = run(["link", "show", "type", "vlan"])

    current = [
        int(interface["ifname"].split(".")[1])
        for interface in info
        if interface["link"] == ifname
    ]

    for to_remove in set(current) - set(vlans):
        run(["link", "delete", f"{ifname}.{to_remove}"])
    for to_add in set(vlans) - set(current):
        run(
            [
                "link",
                "add",
                "link",
                ifname,
                "name",
                f"{ifname}.{to_add}",
                "type",
                "vlan",
                "id",
                str(to_add),
            ]
        )


def setup_ipv4(ifname, ip, prefixlen=24, vlan=None):
    setup_vlans(ifname, [vlan] if vlan is not None else [])
    ensure_ipv4(ifname, ip, prefixlen, vlan=vlan)
    ensure_up(ifname, vlan=vlan)


def format_ifname(ifname, vlan):
    return f"{ifname}.{vlan}" if vlan is not None else ifname


def ensure_ipv4(ifname, ip, prefixlen, vlan=None):
    info = run(["addr", "show"])

    current = []
    for if_info in info:
        if if_info["ifname"] == ifname or (
            "link" in if_info and if_info["link"] == ifname
        ):
            if "." in if_info["ifname"]:
                addr_name, addr_vlan = if_info["ifname"].split(".")
                addr_vlan = int(addr_vlan)
            else:
                addr_name, addr_vlan = if_info["ifname"], None

            for addr_info in if_info["addr_info"]:
                current.append(
                    (addr_name, addr_vlan, addr_info["local"], addr_info["prefixlen"])
                )
    target = [(ifname, vlan, ip, prefixlen)]

    for ifname, vlan, ip, prefixlen in set(current) - set(target):
        run(["addr", "del", f"{ip}/{prefixlen}", "dev", format_ifname(ifname, vlan)])

    for ifname, vlan, ip, prefixlen in set(target) - set(current):
        run(["addr", "add", f"{ip}/{prefixlen}", "dev", format_ifname(ifname, vlan)])


def ensure_up(ifname, vlan):
    ifname = format_ifname(ifname, vlan)

    info = get_if_info(ifname, run(["link", "show", ifname]))
    if "UP" not in info["flags"]:
        run(["link", "set", "up", "dev", ifname])


def make_netns(name, interfaces):
    run(["netns", "add", name])
    for interface in interfaces:
        run(["link", "set", interface, "netns", name])


def del_netns(name):
    run(["netns", "del", name])
