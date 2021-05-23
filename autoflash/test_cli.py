from cli2 import Step, Runner, Context, ContextInfo
from typing import Optional


def ex_fn(
    pos1: str,
    pos2: int,
    opt1: str = "foo",
    opt2: int = 5,
    opt3: Optional[str] = None,
    opt4: Optional[float] = None,
):
    pass


def test_step():
    step = Step("ex_fn", ex_fn)
    parser, get_args = step.make_parser()

    # all args
    parsed = parser.parse_args(
        "bar 7 --opt1=baz --opt2=8 --opt3=quux --opt4=3.5".split()
    )
    args = get_args(parsed)
    assert args == dict(pos1="bar", pos2=7, opt1="baz", opt2=8, opt3="quux", opt4=3.5)

    # defaults
    parsed = parser.parse_args("bar 7".split())
    args = get_args(parsed)
    assert args == dict(pos1="bar", pos2=7, opt1="foo", opt2=5, opt3=None, opt4=None)


# we could use unittest.mock for this, but all the introspection makes it
# tricky. notably, we'd have to manually specify the signatures for the
# methods, as the types would need to match the mocked context type
call_record = []


def record_call(f, **args):
    call_record.append((f, args))


class Serial(Context):
    name = "serial"

    def __init__(self, serial_port: Optional[str] = None):
        record_call(Serial.__init__, self=self, serial_port=serial_port)
        self.serial_port = serial_port

    def __enter__(self):
        record_call(Serial.__enter__, self=self)

    def __exit__(self):
        record_call(Serial.__exit__, self=self)


def boot(serial: Serial, initrd: str):
    record_call(boot, serial=serial, initrd=initrd)


def flash(sysupgrade: str, sysupgrade_args: str = "-v"):
    record_call(flash, sysupgrade=sysupgrade, sysupgrade_args=sysupgrade_args)


def test_runner():
    steps = [Step("boot", boot), Step("flash", flash)]
    contexts = [ContextInfo("serial", Serial)]
    runner = Runner(contexts, steps)

    def check_calls(serial_path=None, sysupgrade_args="-v"):
        [serial_init, serial_enter, boot_call, flash_call, serial_exit] = call_record

        assert serial_init[0] is Serial.__init__
        serial = serial_init[1]["self"]
        assert serial_init[1]["serial_port"] == serial_path

        assert serial_enter == (Serial.__enter__, dict(self=serial))
        assert boot_call == (boot, dict(serial=serial, initrd="initrd.bin"))
        assert flash_call == (
            flash,
            dict(sysupgrade="sysupgrade.bin", sysupgrade_args=sysupgrade_args),
        )

        assert serial_exit == (Serial.__exit__, dict(self=serial))

    args = "boot initrd.bin flash sysupgrade.bin".split()

    call_record.clear()
    runner.parse_and_run(args)
    check_calls()

    args = "--serial-port=/foo boot initrd.bin flash --sysupgrade-args=-w sysupgrade.bin".split()

    call_record.clear()
    runner.parse_and_run(args)
    check_calls(serial_path="/foo", sysupgrade_args="-w")
