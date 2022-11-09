from colorama import Fore
from getpass import getpass
from sys import exit
from os import get_terminal_size

API_URL = "http://localhost:5000"


def header(text, fill="="):
    print(f"[ {text} ]".center(get_terminal_size().columns, fill))


def p_info(*args, n_line=False, pre="INFO", **kwargs):
    colors = {
        "INFO": Fore.YELLOW,
        "ERROR": Fore.RED
    }
    prefix = colors.get(pre) + f"[{pre}]"
    print(f"\n{prefix}" if n_line else f"{prefix}", end=' ')
    print(Fore.RESET, *args, **kwargs)


def get_input(prompt, echo=True, opt=False):
    try:
        data = input(prompt).strip() if echo else getpass(prompt).strip()
        if len(data) == 0:
            if opt:
                return data
            else:
                p_info("Need valid input, try again", pre="INFO")
                return get_input(prompt, echo, opt)
        return data
    except KeyboardInterrupt or Exception:
        p_info(f"Exiting...", pre="INFO", n_line=True)
        exit(0)
