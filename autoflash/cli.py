from typing import (
    List,
    Dict,
    Callable,
    Type,
    Any,
    Tuple,
    Union,
    Container,
    Optional,
)
import typing
import inspect
from dataclasses import dataclass
import argparse
from argparse import ArgumentParser, Namespace
from . import Context
from .exceptions import UserError
from .registry import DeviceRegistry, Device


@dataclass
class ParameterInfo:
    parameter: inspect.Parameter
    help: Optional[str] = None

    @property
    def name(self):
        return self.parameter.name


# - param has no default -> positional, default ignored
# - param has default -> optional, default used


class ArgumentBase:
    def __init__(self, param_info: ParameterInfo):
        self.param_info = param_info
        self.param = param_info.parameter

    def get_name(self) -> str:
        if self.param.default is inspect.Parameter.empty:
            return self.param.name
        else:
            return "--{name}".format(name=self.param.name.replace("_", "-"))

    def get_type(self) -> Callable:
        if is_optional(self.param.annotation):
            return typing.get_args(self.param.annotation)[0]
        else:
            return self.param.annotation

    def add_to_parser(self, parser: argparse._ActionsContainer, **kwargs):
        parser.add_argument(
            self.get_name(), type=self.get_type(), default=self.param.default, **kwargs
        )

    def get_argument(self, parsed_args) -> Any:
        return getattr(parsed_args, self.param.name)


class BoolArg(ArgumentBase):
    def add_to_parser(self, parser: argparse._ActionsContainer, **kwargs):
        assert self.param.default is not inspect.Parameter.empty
        assert isinstance(self.param.default, bool)

        name = self.param.name.replace("_", "-")
        if self.param.default:
            name = f"--no-{name}"
            action = "store_false"
        else:
            name = f"--{name}"
            action = "store_true"

        parser.add_argument(
            name,
            action=action,
            default=self.param.default,
            dest=self.param.name,
            **kwargs,
        )


def is_optional(t: Type[Any]) -> bool:
    return (
        typing.get_origin(t) == Union
        and len(typing.get_args(t)) == 2
        and typing.get_args(t)[1] is type(None)
    )


def is_optional_t(t: Type[Any], types: Container[Type[Any]]) -> bool:
    return is_optional(t) and typing.get_args(t)[0] in types


def handle_arg_base(param: ParameterInfo) -> ArgumentBase:
    base_types = (int, float, str)
    if param.parameter.annotation in base_types:
        return ArgumentBase(param)
    elif is_optional_t(param.parameter.annotation, base_types):
        return ArgumentBase(param)
    elif param.parameter.annotation is bool:
        return BoolArg(param)
    else:
        assert False


Kwargs = Dict[str, Any]


def add_args_to_parser(
    parser: argparse._ActionsContainer, args: List[ParameterInfo]
) -> Callable[[Namespace], Kwargs]:
    arg_handlers = {arg.name: handle_arg_base(arg) for arg in args}

    for handler in arg_handlers.values():
        handler.add_to_parser(parser)

    def get_args(parsed_args: Namespace) -> Dict[str, Any]:
        return {
            name: handler.get_argument(parsed_args)
            for name, handler in arg_handlers.items()
        }

    return get_args


@dataclass
class Step:
    name: str
    func: Callable
    context_args: List[inspect.Parameter]
    option_args: List[ParameterInfo]

    def __init__(self, name: str, func: Callable):
        self.name = name
        self.func = func  # type: ignore

        self.context_args = []
        self.option_args = []

        parameters = inspect.signature(func).parameters

        for param in parameters.values():
            if type(param.annotation) is type and issubclass(param.annotation, Context):
                self.context_args.append(param)
            else:
                self.option_args.append(ParameterInfo(param))

    def make_parser(self) -> Tuple[ArgumentParser, Callable[[Namespace], Kwargs]]:
        p = ArgumentParser(
            prog=self.name, description=getattr(self.func, "__help__", None)
        )

        get_args = add_args_to_parser(p, self.option_args)

        return p, get_args


@dataclass
class CLIDevice:
    device: Device
    steps: Dict[str, Step]


class ContextInfo:
    def __init__(self, name: str, type: Type[Context]):
        self.name = name
        self.type = type

        self.option_args = [
            ParameterInfo(p) for p in inspect.signature(type).parameters.values()
        ]


class Runner:
    def __init__(self, registry: DeviceRegistry):
        self.devices = {
            device.name: CLIDevice(
                device=device,
                steps={
                    step_fn.__name__: Step(step_fn.__name__, step_fn)
                    for step_fn in device.steps
                },
            )
            for device in registry.devices
        }

        context_types = set(
            arg.annotation
            for device in self.devices.values()
            for step in device.steps.values()
            for arg in step.context_args
        )

        self.context_types = [
            ContextInfo(context_type.__name__, context_type)
            for context_type in context_types
        ]

    def list_steps(self, device: CLIDevice):
        print(f"available steps for {device.device.name}:")
        for step in device.steps.values():
            print(f"  {step.name}")
        sys.exit(0)

    def list_devices(self):
        for device in self.devices.values():
            print(device.device.architecture, device.device.name)
        sys.exit(0)

    def parse_step_args(self, device: CLIDevice, step_args: List[str]):
        if step_args == []:
            return self.list_steps(device)

        steps_and_args = []

        while step_args:
            step_name = step_args.pop(0)

            if step_name == "list":
                return self.list_steps(device)

            if step_name not in device.steps:
                raise UserError(f"expected step name, got {step_name}")
            step = device.steps[step_name]

            step_parser, get_args = step.make_parser()
            step_parser.add_argument(
                "commands", metavar="command [arg ...] ...", nargs="..."
            )

            parsed_step_args = step_parser.parse_args(step_args)
            step_kwargs = get_args(parsed_step_args)
            steps_and_args.append((step, step_kwargs))

            step_args = parsed_step_args.commands

        return steps_and_args

    def add_context_args(self, parser: ArgumentParser):
        ctx_with_args = []
        for ctx_type in self.context_types:
            group = parser.add_argument_group(ctx_type.name)
            get_args = add_args_to_parser(group, ctx_type.option_args)
            ctx_with_args.append((ctx_type, get_args))
        return ctx_with_args

    def get_device(self, device_name):
        if device_name in self.devices:
            return self.devices[device_name]
        elif device_name == "list":
            self.list_devices()
        else:
            raise UserError(
                f"device {device_name} not known; use 'list' to show known devices"
            )

    def parse_and_run(self, args: List[str]):
        main_parser = ArgumentParser()

        context_args = self.add_context_args(main_parser)

        main_parser.add_argument(
            "device", help="device name; use 'list' to show known devices"
        )
        main_parser.add_argument(
            "commands", metavar="command [arg ...] ...", nargs="..."
        )

        main_args = main_parser.parse_args(args)

        context_args_parsed = {
            ctx.type: get_args(main_args) for ctx, get_args in context_args
        }

        device = self.get_device(main_args.device)

        steps_and_args = self.parse_step_args(device, main_args.commands)

        self.run(steps_and_args, context_args_parsed)

    def run(self, steps_and_args, context_args_parsed):
        required_contexts = set(
            arg.annotation
            for step, _kwargs in steps_and_args
            for arg in step.context_args
        )

        contexts = {ctx: ctx(**context_args_parsed[ctx]) for ctx in required_contexts}

        for step, kwargs in steps_and_args:
            for ctx_arg in step.context_args:
                kwargs[ctx_arg.name] = contexts[ctx_arg.annotation]

        for ctx in contexts.values():
            ctx.__enter__()

        for step, kwargs in steps_and_args:
            step.func(**kwargs)

        for ctx in contexts.values():
            ctx.__exit__()


if __name__ == "__main__":
    from .devices import registry
    import sys
    import logging

    logging.basicConfig(level=logging.DEBUG)

    r = Runner(registry)
    try:
        r.parse_and_run(sys.argv[1:])
    except UserError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
