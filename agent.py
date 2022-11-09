import asyncio
import json

import requests
import websockets
from systems import Systems
from sys import exit
from c_utils import API_URL, p_info
import psutil
import time

HOST = '0.0.0.0'
PORT = ''


def patch_system(url, pl):
    while True:
        try:
            return requests.patch(url, json=pl).status_code
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
    except websockets.WebSocketException as e:
        print("\nConnection CLOSED: ", e)


async def main():
    async with websockets.serve(handler, HOST, PORT) as websocket:
        addr = websocket.server._sockets[0].getsockname()
        p_info(addr, pre="INFO")
        system_config = Systems.load_config()
        if not system_config:
            exit(1)

        payload = {
            "port": addr[1],
            "sys_id": system_config['sys_id'],
            "v_token": system_config['v_token']
        }

        p_info("Sending patch request...", pre="INFO", end=' ')
        if patch_system(API_URL + "/api/system", payload) == 200:
            print("PATCHED")
            p_info("Listening for connections...", pre="INFO")
            await asyncio.Future()

        exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt or Exception as e:
        p_info(f"Exiting...\n{e}", pre="ERROR")
