import asyncio
import base64
import json
import os

import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

from kb_functions import FUNCTION_MAP

load_dotenv()

app = FastAPI()


# -------- Deepgram Agent WS --------
def sts_connect():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise Exception("DEEPGRAM_API_KEY not found")

    return websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        subprotocols=["token", api_key],
    )


def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


async def handle_barge_in(decoded, twilio_ws, streamsid):
    if decoded.get("type") == "UserStartedSpeaking":
        clear_message = {"event": "clear", "streamSid": streamsid}
        await twilio_ws.send_text(json.dumps(clear_message))


def execute_function_call(func_name, arguments):
    if func_name in FUNCTION_MAP:
        result = FUNCTION_MAP[func_name](**arguments)
        print(f"Function call result: {result}")
        return result
    else:
        result = {"error": f"Unknown function: {func_name}"}
        print(result)
        return result


def create_function_call_response(func_id, func_name, result):
    return {
        "type": "FunctionCallResponse",
        "id": func_id,
        "name": func_name,
        "content": json.dumps(result, ensure_ascii=False),
    }


async def handle_function_call_request(decoded, sts_ws):
    try:
        for function_call in decoded["functions"]:
            func_name = function_call["name"]
            func_id = function_call["id"]
            arguments = json.loads(function_call["arguments"])

            print(f"Function call: {func_name} (ID: {func_id}), arguments: {arguments}")

            result = execute_function_call(func_name, arguments)

            function_result = create_function_call_response(func_id, func_name, result)
            await sts_ws.send(json.dumps(function_result))
            print(f"Sent function result: {function_result}")

    except Exception as e:
        print(f"Error calling function: {e}")
        error_result = create_function_call_response(
            locals().get("func_id", "unknown"),
            locals().get("func_name", "unknown"),
            {"error": f"Function call failed with: {str(e)}"},
        )
        await sts_ws.send(json.dumps(error_result))


async def handle_text_message(decoded, twilio_ws, sts_ws, streamsid):
    await handle_barge_in(decoded, twilio_ws, streamsid)

    if decoded.get("type") == "FunctionCallRequest":
        await handle_function_call_request(decoded, sts_ws)


async def sts_sender(sts_ws, audio_queue):
    print("sts_sender started")
    while True:
        chunk = await audio_queue.get()
        await sts_ws.send(chunk)


async def sts_receiver(sts_ws, twilio_ws, streamsid_queue):
    print("sts_receiver started")
    streamsid = await streamsid_queue.get()

    async for message in sts_ws:
        if isinstance(message, str):
            decoded = json.loads(message)
            await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)
            continue

        raw_mulaw = message
        media_message = {
            "event": "media",
            "streamSid": streamsid,
            "media": {"payload": base64.b64encode(raw_mulaw).decode("ascii")},
        }
        await twilio_ws.send_text(json.dumps(media_message))


async def twilio_receiver(twilio_ws, audio_queue, streamsid_queue):
    BUFFER_SIZE = 20 * 160
    inbuffer = bytearray(b"")

    while True:
        try:
            message = await twilio_ws.receive_text()
        except WebSocketDisconnect:
            break
        except Exception:
            break

        try:
            data = json.loads(message)
            event = data.get("event")

            if event == "start":
                start = data["start"]
                streamsid = start["streamSid"]
                streamsid_queue.put_nowait(streamsid)

            elif event == "media":
                media = data["media"]
                chunk = base64.b64decode(media["payload"])
                if media.get("track") == "inbound":
                    inbuffer.extend(chunk)

            elif event == "stop":
                break

            while len(inbuffer) >= BUFFER_SIZE:
                chunk = inbuffer[:BUFFER_SIZE]
                audio_queue.put_nowait(chunk)
                inbuffer = inbuffer[BUFFER_SIZE:]

        except Exception:
            break


async def twilio_handler(twilio_ws: WebSocket):
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()

    async with sts_connect() as sts_ws:
        config_message = load_config()
        await sts_ws.send(json.dumps(config_message))

        tasks = [
            asyncio.create_task(sts_sender(sts_ws, audio_queue)),
            asyncio.create_task(sts_receiver(sts_ws, twilio_ws, streamsid_queue)),
            asyncio.create_task(twilio_receiver(twilio_ws, audio_queue, streamsid_queue)),
        ]

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

        for t in pending:
            t.cancel()

    try:
        await twilio_ws.close()
    except Exception:
        pass


# -------- HTTP endpoints for Render / health checks --------
@app.get("/")
def root():
    return {"status": "ok", "service": "nora-voice-agent"}

@app.get("/health")
def health():
    return {"ok": True}


# -------- Twilio Media Stream WebSocket --------
@app.websocket("/stream")
async def stream(ws: WebSocket):
    await ws.accept()
    await twilio_handler(ws)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "10000"))
    print(f"Starting HTTP+WS server on {host}:{port} (ws path: /stream)")
    uvicorn.run(app, host=host, port=port)
