import pyroute2.netns
from typing import Optional
from .registry import Context
from . import iputils


class Network(Context):
    # XXX: make non-optional?
    def __init__(self, ifname: Optional[str] = None, use_netns: bool = True):
        assert ifname is not None
        self.ifname: str = ifname
        self.use_netns = use_netns

    def __enter__(self):
        if self.use_netns:
            self.netns_name = "autoflash_tmp"
            iputils.make_netns(self.netns_name, [self.ifname])
            pyroute2.netns.pushns(self.netns_name)

        return self

    def __exit__(self, *exc):
        if self.use_netns:
            pyroute2.netns.popns()
            iputils.del_netns(self.netns_name)

    def setup_ipv4(self, ip, prefixlen=24, vlan=None):
        iputils.setup_ipv4(self.ifname, ip, prefixlen=prefixlen, vlan=vlan)
