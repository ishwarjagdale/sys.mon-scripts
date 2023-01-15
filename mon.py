import asyncio
import datetime
import json
import os.path
import platform as plt
import signal
import sys
import threading
import time
from collections import defaultdict
from sys import exit
from notifypy import Notify
import pandas
import psutil
import requests
import websockets
from cpuinfo import get_cpu_info

from c_utils import API_URL, p_info, header

HOST = '0.0.0.0'
PORT = ''
rules = dict()

stats = {
    "cpu": 0,
    "mem": 0,
    "disk": 0
}

time_period = {
    "hour": 1,
    "week": 7,
    "month": 30
}

previous_report = None
reporting_time = None


def report(resource, rule, _stats):
    global previous_report, reporting_time

    if previous_report and reporting_time:
        if rule == previous_report['report']['activity']['rule'] and (
                datetime.datetime.now() - reporting_time).total_seconds() < 3600:
            # print(f'suppressing report for {3600 - (datetime.datetime.now() - reporting_time).total_seconds()} seconds')
            return
    p_info("Reporting server...")
    rep = {
        "sys_id": system_config['sys_id'],
        "v_token": system_config['v_token'],
        "report": {
            "activity": {
                "resource": resource,
                "rule": rule,
                "message": f"{resource} crossed {rule['max_limit']}%"
            },
            "stats": _stats
        }
    }
    res = send_request('post', API_URL + '/api/system/mon', pl=rep)
    if res.status_code != 200:
        p_info("Reporting failed!", res.status_code)
    previous_report = rep
    reporting_time = datetime.datetime.now()


def monitor():
    global rules
    secs = defaultdict(list)
    while True:
        _10_sec = gen_data(10)
        for r in _10_sec:
            secs[r].append(_10_sec[r])
            if r in rules:
                if _10_sec[r] >= rules[r]['max_limit']:
                    print("sys in trouble", _10_sec)
                    report(r, rules[r], _10_sec)
        if len(secs[list(secs.keys())[0]]) == 360:
            for i in secs:
                secs[i] = sum(secs[i]) / 360
            if not os.path.exists(os.path.join(os.path.expanduser("~"), ".sysmon")):
                os.mkdir(os.path.join(os.path.expanduser("~"), ".sysmon"))
            with open(os.path.join(os.path.expanduser("~"), ".sysmon", "hourly_logs.txt"), 'a+') as log:
                json.dump({f"{datetime.datetime.now()}": secs}, log)
                log.write("\n")
            secs.clear()


def send_request(method, url, pl):
    while True:
        try:
            if method == "get":
                return requests.get(url, json=pl)
            if method == "post":
                return requests.post(url, json=pl)
            if method == "patch":
                return requests.patch(url, json=pl)
        except Exception as e:
            print(e, 'waiting for connection...')
            time.sleep(10)


def gen_data(span=1):
    # RAM
    mem = psutil.virtual_memory()

    # DISKS
    used, total = 0, 0
    for i in psutil.disk_partitions():
        disk = psutil.disk_usage(i.mountpoint)
        total += disk.total
        used += disk.used

    # CPU
    cpu = psutil.cpu_percent(span)

    data = {
        "cpu": cpu,
        "mem": mem.percent,
        "disk": round(used * 100 / total, 2)
    }

    return data


def gen_spec():
    uname_result = plt.uname()
    cpu_info = get_cpu_info()
    cores, l_cores = psutil.cpu_count(False), psutil.cpu_count()
    spec = {
        "Node": uname_result.node,
        "Operating System Name": uname_result.system,
        "Operating System Version": uname_result.version,
        "Machine": uname_result.machine,
        "Processor": {
            "Processor Name": cpu_info['brand_raw'],
            "Base Frequency": cpu_info['hz_actual_friendly'],
            "Number of Cores (Logical Cores)": f"{cores} ({l_cores})",
            "Architecture": cpu_info['arch']
        },
        "Memory": {
            "Total Physical Memory": f"{round(psutil.virtual_memory().total / 2 ** 30, 2)} GB"
        }
    }
    return json.dumps({"spec": spec})


def gen_report(t):
    global time_period
    data = {}
    if not os.path.exists(os.path.join(os.path.expanduser("~"), ".sysmon", "hourly_logs.txt")):
        with open(os.path.join(os.path.expanduser("~"), ".sysmon", "hourly_logs.txt"), 'w') as log:
            pass
    with open(os.path.join(os.path.expanduser("~"), ".sysmon", "hourly_logs.txt"), 'r') as log:
        while log:
            chunk = log.readline().strip()
            if chunk:
                line = list((json.loads(chunk)).items())[0]
                if (datetime.datetime.now() - datetime.datetime.fromisoformat(line[0])).days <= time_period[t]:
                    data[datetime.datetime.fromisoformat(line[0])] = line[1]
                else:
                    continue
            else:
                break
    df = pandas.DataFrame.from_dict(data=data, orient="index")
    return df.to_json(date_format="iso")


async def handler(ws):
    p_info("New connection:", ws.request_headers["Origin"], pre="INFO")
    try:
        async for message in ws:
            if message == "cpd":
                await ws.send(json.dumps({"stats": gen_data()}))
            elif message == "spec":
                await ws.send(gen_spec())
            elif message == "update_mon":
                update_mon()
            elif message.startswith("report"):
                await ws.send('{"report": ' + gen_report(message.split("-")[1]) + '}')
            else:
                await ws.send(json.dumps({"stats": gen_data()}))
    except websockets.WebSocketException as err:
        print("\nConnection CLOSED: ", err)


async def main():
    async with websockets.serve(handler, HOST, PORT) as websocket:
        addr = websocket.server._sockets[0].getsockname()
        p_info(addr, pre="INFO")

        payload = {
            "port": addr[1],
            "sys_id": system_config['sys_id'],
            "v_token": system_config['v_token']
        }

        p_info("Sending patch request...", pre="INFO", end=' ')
        if send_request("patch", API_URL + "/api/system/mon", payload).status_code == 200:
            print("PATCHED")
            p_info("Listening for connections...", pre="INFO")
            await asyncio.Future()

        exit(1)


def shutdown(sig, frame):
    header("SHUT DOWN")
    p_info("SHUTDOWN SIGNAL RECEIVED - Notifying server...", pre="INFO")
    try:
        p_info("RESPONSE:", requests.post(API_URL + "/api/system/activity", json={
            "sys_id": system_config['sys_id'],
            "v_token": system_config['v_token'],
            "activity": ["SHUTDOWN", f"desc: {str(sig)}", "mon shutting down!"]
        }).status_code, pre="INFO")
    except ConnectionError or TimeoutError or Exception as err:
        p_info(err, pre="ERROR")
    p_info("Exiting...", pre="INFO")
    exit(0)


def update_mon():
    global rules
    p_info("Connecting server...", pre="INFO", end=' ')
    res = send_request("get", API_URL + "/api/system/mon", {
        "sys_id": system_config['sys_id'],
        "v_token": system_config['v_token']
    })
    if res.status_code == 200:
        print("ok")
        res = res.json()
        if not res['enable_mon']:
            p_info("MON DISABLED", pre="INFO")
            p_info("Exiting...", pre="INFO")
            exit(0)
        else:
            rules = res['rules']
    else:
        print()
        p_info(f"{res.status_code} - {res.json()['message']} Exiting...", pre="ERROR")
        exit(0)


if __name__ == "__main__":

    try:
        notif = Notify()
        notif.title = "Mon"
        notif.message = "Mon started!"
        notif.application_name = "SysMon"
        notif.icon = os.path.join(os.path.dirname(__file__), "favicon.png")
        notif.send()
    except Exception as e:
        notif = Notify()
        notif.title = "Mon"
        notif.message = "Mon started!"
        notif.application_name = "SysMon"
        notif.send()

    with open(os.path.join(os.path.expanduser('~'), ".sysmon", "sysmon_agent.config"), 'r') as conf:
        system_config = json.load(conf)
        if not ("sys_id" in system_config and "v_token" in system_config):
            p_info("Wrong configuration file, re-install mon", pre="ERROR")
            exit(1)
    if not system_config:
        exit(1)
    if len(sys.argv) == 2:
        PORT = sys.argv[1]

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    threading.Thread(target=monitor, daemon=True).start()

    update_mon()

    try:
        asyncio.run(main())
    except KeyboardInterrupt or Exception as e:
        p_info(f"Exiting...\n{e}", pre="ERROR")
