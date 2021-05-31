# autoflash

Autoflash automates the process of flashing OpenWrt onto routers: given a serial port and a network interface to use, it knows how to talk to uBoot, set up a network interface, load and boot an initrd using tftp, copy a sysupgrade image over ssh, and run sysupgrade. It uses network namespaces to avoid conflicts with other network connections.

The project consists of:

- A set of python tools for talking to serial ports, configuring networks, running dnsmasq etc.
- Sets of tasks specific to each supported device, built using the generic tools.
- A command-line tool for running the tasks.

You might want to use this if:
- You're developing openwrt and want to speed up or automate your build/test cycle.
- You want to install openwrt on lots of devices.
- You find the manual install processes annoying and fiddly.

Currently, using this will almost certainly involve writing code; this is still a new project and very few devices are supported. For simple cases this will mostly be copy/paste, though. There are a few obvious deficiencies, primarily in the user interface, which are listed in the issue tracker.

## install

Requirements:

- linux (this uses linux networking features; docker/virtualisation may be used on other platforms)
- iproute2 (the `ip` command)
- Python 3.8+
- dnsmasq (optional, needed for tftp)

To install:

    python -m pip install git+https://github.com/tomjnixon/autoflash.git

## usage

Typical usage looks something like this:

```
# autoflash --ifname eth0 --serial-port /dev/ttyUSB0 bt_homehub-v5a boot initrd.bin miniterm
            \______________________________________/ \____________/ \_____________/ \______/
                                 |                     |               |                |
          global configuration --'        device name -'   first task -'   second task -'
```

Generally this will need to run as root to be able to change network configuration.

The parts are as follows:

### global configuration

Configuration that applies to all tasks; run `autoflash --help` for a list of options.

### device name

The name of the device, which affects the list available tasks; run `autoflash list` to show the available devices.

### tasks

The tasks to execute; run `autoflash bt_homehub-v5a list` (with your device name) to list the available tasks.

The task name is followed by optional and required arguments; run `autoflash bt_homehub-v5a boot --help` (with your device and task names) show the supported arguments.

Multiple tasks may be specified, by concatenating the arguments.

## development

For development, use poetry:

    git clone https://github.com/tomjnixon/autoflash.git
    cd autoflash
    # pip install --user poetry
    poetry install

Then, prefix commands with `poetry run`, like:

    poetry run autoflash --help

Various tools are configured:

    poetry run black autoflash # format code
    poetry run mypy # type check
    poetry run flake8 autoflash # style check
    poetry run pytest # run tests
