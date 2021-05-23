from ..registry import DeviceRegistry

registry = DeviceRegistry(__name__)

registry.add_from_module(".realtek.gs1900_8hp_v2")
