import json
import os
import requests
from c_utils import get_input, API_URL, p_info, header


class Authentication:

    @staticmethod
    def save_credentials(credentials, res):
        print(res.cookies.values())
        try:
            with open(os.path.join(os.path.expanduser("~"), "sysmon_cli.config"), 'w') as config:
                json.dump({
                    "name": res.json()['name'],
                    "email": credentials['email'],
                    "session_token": res.cookies.get("session")
                }, config)
        except OSError or Exception as e:
            p_info(e, pre="ERROR")
            return False

    @staticmethod
    def load_credentials():
        try:
            with open(os.path.join(os.path.expanduser("~"), "sysmon_cli.config"), 'r') as config:
                credentials = json.load(config)
                if "email" in credentials and "session_token" in credentials:
                    return credentials
                return None
        except FileNotFoundError or Exception:
            return None

    @staticmethod
    def register():
        header("registration")

        credentials = {
            "name": get_input("Enter your name: "),
            "email": get_input("Enter email address: "),
            "password": get_input("Enter password: ", echo=False)
        }

        res = requests.post(API_URL + "/auth/get-started", json=credentials)

        if res.status_code == 200:
            p_info("Registered successfully!", pre="INFO")
            Authentication.verification()

    @staticmethod
    def verification():
        header("verification")

        p_info("Enter the verification code given in the email we sent you", pre="INFO")
        p_info("If you haven't received the code, enter your email address to resend", pre="INFO")

        token_or_email = get_input("Verification Code [or email address]: ")
        if "@" in token_or_email:

            res = requests.get(API_URL + "/auth/verification", json={"email": token_or_email})

            if res.status_code == 200:
                p_info("Email sent successfully!", pre="INFO")
                token_or_email = get_input("Verification Code: ")
            elif res.status_code == 400:
                p_info("This account has already been authenticated!")
                return True
            elif res.status_code == 404:
                p_info("Couldn't find the user, verify the credentials or sign up again.", pre="ERROR")
                return False
            else:
                p_info("Couldn't process your request.", pre="ERROR")

        res = requests.post(API_URL + "/auth/verification", json={"token": token_or_email})

        if res.status_code == 200:
            p_info("Email address verified, your account has been activated!", pre="INFO")
            return True
        elif res.status_code == 404:
            p_info("Couldn't find the user, verify the credentials or sign up again.", pre="ERROR")
            return False
        else:
            p_info("Couldn't process your request.", pre="ERROR")

    @staticmethod
    def handle_login_responses(res, credentials=None):
        if res.status_code == 200:
            p_info("Logged in successfully!", pre="INFO")
            if res and credentials:
                Authentication.save_credentials(credentials, res)
            return True
        elif res.status_code == 404:
            p_info("Couldn't find the user, verify the credentials or sign up again.", pre="ERROR")
            return False
        else:
            p_info("Needs re-verification.", pre="ERROR")
            try:
                os.remove(os.path.join(os.path.expanduser("~"), "sysmon_cli.config"))
            except OSError as e:
                p_info(e, pre="ERROR")

    @staticmethod
    def login(sub=False):
        if not sub:
            header("login")

        p_info("Checking for existing credentials...", pre="INFO", end=" ")
        credentials = Authentication.load_credentials()
        if credentials:
            print("found")
            cont_ = get_input(f"Continue as {credentials['email']}? (yes(y) | no(n)): ").strip().lower()
            if cont_.startswith('y'):
                res = requests.get(API_URL + "/auth/login", cookies={
                    'session': credentials['session_token']
                })
                ret = Authentication.handle_login_responses(res)
                if ret is not None:
                    return ret
        else:
            print("not found")

        credentials = {
            "email": get_input("Enter email address: "),
            "password": get_input("Enter password: ", echo=False)
        }

        res = requests.post(API_URL + "/auth/login", json=credentials)
        return Authentication.handle_login_responses(res, credentials)

    @staticmethod
    def logout():
        credentials = Authentication.load_credentials()
        if credentials:
            requests.get(API_URL + "/auth/logout", cookies={
                "session": credentials["session_token"]
            })
            p_info("Logged out!", pre="INFO")
        else:
            p_info("No log in session found", pre="INFO")
        try:
            os.remove(os.path.join(os.path.expanduser("~"), 'sysmon_cli.config'))
        except OSError or Exception:
            if credentials:
                p_info("Couldn't remove config file", pre="ERROR")
