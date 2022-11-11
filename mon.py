import asyncio
import json
import signal
import time
from sys import exit

import psutil
import requests
import websockets

from c_utils import API_URL, p_info, header
from systems import Systems

HOST = '0.0.0.0'
PORT = ''


def send_request(method, url, pl):
    while True:
        try:
            if method == "get":
                return requests.get(url, json=pl)
            if method == "post":
                return requests.post(url, json=pl)
            if method == "patch":
                return requests.patch(url, json=pl)
        except ConnectionError or Exception:
            print('waiting for connection...')
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
        "cpu": f"{cpu}%",
        "mem": f"{mem.percent}%",
        "disk": f"{round(used * 100 / total, 2)}%"
    }

    print("SENDING: ", data)
    return json.dumps(data)


async def handler(ws):
    try:
        async for message in ws:
            print("RECEIVED: ", message)
            if message == "cpd":
                await ws.send(gen_data())
            else:
                await ws.send(gen_data())
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
        if send_request("patch", API_URL + "/api/system", payload).status_code == 200:
            print("PATCHED")
            p_info("Listening for connections...", pre="INFO")
            await asyncio.Future()

        exit(1)


if __name__ == "__main__":

    system_config = Systems.load_config()
    if not system_config:
        exit(1)

    # TODO: make this work
    # p_info("Connecting server...", pre="INFO")
    # res = send_request("get", API_URL + "/api/system", {
    #     "sys_id": system_config['sys_id'],
    #     "v_token": system_config['v_token']
    # })
    # print(res.__dict__)
    # if res.status_code == 200:
    #     if not res.json()['enable_mon']:
    #         p_info("MON DISABLED", pre="INFO")
    #         p_info("Exiting...", pre="INFO")
    #         exit(0)
    # else:
    #     p_info("Exiting...", pre="INFO")
    #     exit(0)

    def shutdown(sig, frame):
        header("SHUT DOWN")
        p_info("SHUTDOWN SIGNAL RECEIVED - Notifying server...", pre="INFO")
        try:
            p_info("RESPONSE:", requests.post(API_URL + "/api/system/activity", json={
                "sys_id": system_config['sys_id'],
                "v_token": system_config['v_token'],
                "signal": sig
            }).status_code, pre="INFO")
        except ConnectionError or TimeoutError or Exception as err:
            p_info(err, pre="ERROR")
        p_info("Exiting...", pre="INFO")
        exit(0)


    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        asyncio.run(main())
    except KeyboardInterrupt or Exception as e:
        p_info(f"Exiting...\n{e}", pre="ERROR")
