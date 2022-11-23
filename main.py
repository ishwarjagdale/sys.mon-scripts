"""CLI to interact with sys.mon

Version:
    {}

Usage:
    sysmon
    sysmon <command> [help]
    sysmon -h | --help
    sysmon -v | --version

Options:
    help        To see the documentation of command
    -h --help   show this screen
    --version   show CLI version

Commands:
    start       Guided steps for new users
    register    To sign up
    verify      To activate account
    login       To log in
    init        To register current system
    status      To see status and enable/disable mon agent

    # In progress
"""
from docopt import docopt
from sys import exit
from systems import Systems
from authentication import Authentication

VERSION = "1.0.0"

if __name__ == "__main__":
    args = docopt(__doc__.format(VERSION), version=VERSION)

    commands = {"register": Authentication.register,
                "verify": Authentication.verification,
                "login": Authentication.login,
                "logout": Authentication.logout,
                "init": Systems.register_system,
                "install": Systems.install_mon
                }

    if args['-v']:
        print(VERSION)
        exit(0)
    if args['<command>'] in commands:
        commands[args['<command>']]()
    else:
        print(__doc__.format(VERSION))
