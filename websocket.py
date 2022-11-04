import threading
import asyncio
import websockets
import json

import texttranslate
import imagetranslate
from windowcapture import WindowCapture
import settings
import VRC_OSCLib
import flanLanguageModel


WS_CLIENTS = set()


def websocketMessageHandler(msgObj):

    if msgObj["type"] == "setting_change":
        settings.SetOption(msgObj["name"], msgObj["value"])
        BroadcastMessage(json.dumps({"type": "translate_settings", "data": settings.TRANSLATE_SETTINGS}))  # broadcast updated settings to all clients

    if msgObj["type"] == "translate_req":
        translate_result = texttranslate.TranslateLanguage(msgObj["text"], msgObj["from_lang"], msgObj["to_lang"])
        BroadcastMessage(json.dumps({"type": "translate_result", "translate_result": translate_result}))

    if msgObj["type"] == "ocr_req":
        window_name = settings.GetOption("ocr_window_name")
        ocr_result = imagetranslate.run_image_processing(window_name, ['en', msgObj["ocr_lang"]])
        translate_result = (texttranslate.TranslateLanguage(" -- ".join(ocr_result), msgObj["from_lang"], msgObj["to_lang"]))
        BroadcastMessage(json.dumps({"type": "translate_result", "original_text": "\n".join(ocr_result), "translate_result": "\n".join(translate_result.split(" -- "))}))

    if msgObj["type"] == "flan_req":
        if flanLanguageModel.init():
            flan_result = flanLanguageModel.flan.encode(msgObj["text"])
            BroadcastMessage(json.dumps({"type": "flan_result", "flan_result": flan_result}))

    if msgObj["type"] == "get_windows_list":
        windows_list = WindowCapture.list_window_names()
        BroadcastMessage(json.dumps({"type": "windows_list", "data": windows_list}))

    if msgObj["type"] == "send_osc":
        osc_address = settings.GetOption("osc_address")
        osc_ip = settings.GetOption("osc_ip")
        osc_port = settings.GetOption("osc_port")
        if osc_ip != "0":
            VRC_OSCLib.Chat(msgObj["text"], True, osc_address, IP=osc_ip, PORT=osc_port)


async def handler(websocket):
    print('Websocket: Client connected.')

    # send all available text translation languages
    available_languages = texttranslate.GetInstalledLanguageNames()
    await send(websocket, json.dumps({"type": "installed_languages", "data": available_languages}))

    # send all available image recognition languages
    available_languages = imagetranslate.get_installed_language_names()
    await send(websocket, json.dumps({"type": "available_img_languages", "data": available_languages}))

    # send all current text translation settings
    await send(websocket, json.dumps({"type": "translate_settings", "data": settings.TRANSLATE_SETTINGS}))

    WS_CLIENTS.add(websocket)
    try:
        async for message in websocket:
            msgObj = json.loads(message)
            print(msgObj)
            websocketMessageHandler(msgObj)

        await websocket.wait_closed()
    except websockets.ConnectionClosedError as error:
        print('Websocket: Client connection failed.', error)
    finally:
        WS_CLIENTS.remove(websocket)
        print('Websocket: Client disconnected.')


async def send(websocket, message):
    try:
        await websocket.send(message)
    except websockets.ConnectionClosed:
        pass


async def broadcast(message):
    for websocket in WS_CLIENTS:
        asyncio.create_task(send(websocket, message))


def BroadcastMessage(message):
    # detect if a loop is running and run on existing loop or asyncio.run
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 'RuntimeError: There is no current event loop...'
        loop = None

    if loop and loop.is_running():
        loop.create_task(broadcast(message))
    else:
        asyncio.run(broadcast(message))


async def server_program(ip, port):
    async with websockets.serve(handler, ip, port):
        print('Websocket: Server started.')
        await asyncio.Future()  # run forever


def StartWebsocketServer(ip, port):
    SocketServerThread(ip, port)


class SocketServerThread(object):
    """ Threading example class
    The run() method will be started, and it will run in the background
    until the application exits.
    """

    def __init__(self, ip, port):
        thread = threading.Thread(target=self.run, args=(ip, port,))
        thread.daemon = True  # Daemonize thread
        thread.start()  # Start the execution

    @staticmethod
    def run(ip, port):
        while True:
            asyncio.run(server_program(ip, port))
