from typing import List, Callable
import importlib

class Device:
    def __init__(self, architecture: str, name: str):
        self.architecture = architecture
        self.name = name

        self.steps: List[Callable] = []

    def register_step(self, step):
        self.steps.append(step)
        return step

class DeviceRegistry:
    def __init__(self, base_package = None):
        self.base_package = base_package
        self.devices = []

    def add_from_module(self, module_name: str, attr_name: str = "device"):
        mod = importlib.import_module(module_name, self.base_package)
        self.devices.append(getattr(mod, attr_name))

