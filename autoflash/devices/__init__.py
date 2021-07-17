from ..registry import DeviceRegistry

registry = DeviceRegistry(__name__)

registry.add_from_module(".lantiq.bt_homehub_v5a")
registry.add_from_module(".lantiq.netgear_dm200")
registry.add_from_module(".realtek.gs1900_8hp_v2")
