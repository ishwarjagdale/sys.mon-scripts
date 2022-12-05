import asyncio
import json
import signal
import sys
import time
from sys import exit
import platform as plt
from cpuinfo import get_cpu_info
import psutil
import requests
import websockets
import threading
from c_utils import API_URL, p_info, header
from systems import Systems

HOST = '0.0.0.0'
PORT = ''
rules = dict()

stats = {
    "cpu": 0,
    "mem": 0,
    "disk": 0
}


def report(resource, rule, _stats):
    p_info("Reporting server...")
    res = send_request('post', API_URL + '/api/system/mon', pl={
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
    })
    if res.status_code != 200:
        p_info("Reporting failed!", res.status_code)


def monitor():
    global stats, rules
    while True:
        stats = gen_data()
        for r in stats:
            if r in rules:
                if stats[r] >= rules[r]['max_limit']:
                    print("sys in trouble", stats)
                    report(r, rules[r], stats)


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


def gen_data():
    # RAM
    mem = psutil.virtual_memory()

    # DISKS
    used, total = 0, 0
    for i in psutil.disk_partitions():
        disk = psutil.disk_usage(i.mountpoint)
        total += disk.total
        used += disk.used

    # CPU
    cpu = psutil.cpu_percent(1)

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


async def handler(ws):
    print(ws, 'got conn')
    try:
        async for message in ws:
            if message == "cpd":
                time.sleep(1)
                await ws.send(json.dumps({"stats": stats}))
            elif message == "spec":
                await ws.send(gen_spec())
            elif message == "update_mon":
                update_mon()
            else:
                await ws.send(json.dumps({"stats": stats}))
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
    p_info("Connecting server...", pre="INFO")
    res = send_request("get", API_URL + "/api/system/mon", {
        "sys_id": system_config['sys_id'],
        "v_token": system_config['v_token']
    })
    if res.status_code == 200:
        res = res.json()
        if not res['enable_mon']:
            p_info("MON DISABLED", pre="INFO")
            p_info("Exiting...", pre="INFO")
            exit(0)
        else:
            rules = res['rules']
    else:
        p_info(f"{res.status_code} Exiting...", pre="INFO")
        exit(0)


if __name__ == "__main__":

    system_config = Systems.load_config()
    if not system_config:
        exit(1)
    if len(sys.argv) == 2:
        PORT = sys.argv[1]

    update_mon()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    threading.Thread(target=monitor, ).start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt or Exception as e:
        p_info(f"Exiting...\n{e}", pre="ERROR")
