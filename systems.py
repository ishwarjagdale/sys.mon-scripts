import json
import os.path
from platform import system as system_name
from platform import uname
from socket import gethostbyname, gethostname

import requests

from authentication import Authentication
from c_utils import header, get_input, API_URL, p_info


class Systems:

    @staticmethod
    def load_config():
        if not os.path.exists(os.path.join(os.path.expanduser("~"), ".sysmon", 'sysmon_agent.config')):
            return False
        try:
            with open(os.path.join(os.path.expanduser("~"), ".sysmon", 'sysmon_agent.config'), 'r') as config:
                system = json.load(config)
                if "sys_id" in system and "v_token" in system:
                    return system
                return False
        except OSError or Exception as e:
            p_info(e, pre="ERROR")
        return False

    @staticmethod
    def save_config(configurations):
        try:
            with open(os.path.join(os.path.expanduser("~"), ".sysmon", "sysmon_agent.config"), 'w') as config:
                json.dump(configurations, config)
            return True
        except OSError or Exception as e:
            p_info(e, pre="ERROR")
            return False

    @staticmethod
    def generate_system_name():
        name = uname()
        return f"{name.node} - {name.system} {name.release}"

    @staticmethod
    def get_ipv4():
        return gethostbyname(gethostname())

    @staticmethod
    def install_mon():
        pass

    @staticmethod
    def register_system():
        header('installation')

        p_info("Identifying system...", pre="INFO", end=' ')
        system = Systems.load_config()
        if system:
            print("system already registered!")
            return True
        else:
            print("is new")

        if Authentication.login(sub=True):
            credentials = Authentication.load_credentials()

            system = {
                "sys_name": get_input("Enter system's name [skip to autogenerate]: ", opt=True
                                      ) or Systems.generate_system_name(),
                "ipv4": Systems.get_ipv4(),
                "os": system_name()
            }

            res = requests.post(API_URL + "/api/system", json=system, cookies={
                'session': credentials['session_token']
            })

            if res.status_code == 200:
                p_info("System registered successfully!", pre="INFO")
                Systems.save_config(res.json())
                return True

            elif res.status_code == 401:
                p_info("Needs re-authentication", pre="ERROR")
            else:
                p_info("Something went wrong", pre="ERROR")
        p_info("Log in first to proceed for installation", pre="INFO")
        return False
