from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import random
import json
from pathlib import Path

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"

rooms = {}  # room_id -> {sockets: [ws,...], state: {deck, hands, board, turn}}


def build_deck():
    d = []
    for i in range(7):
        for j in range(i, 7):
            d.append([i, j])
    random.shuffle(d)
    return d


@app.get("/")
async def get(request: Request):
    content = TEMPLATE_PATH.read_text(encoding='utf-8')
    return HTMLResponse(content)


async def send(ws, obj):
    await ws.send_text(json.dumps(obj))


async def broadcast(room_id, obj):
    for ws in rooms[room_id]["sockets"]:
        try:
            await send(ws, obj)
        except:
            pass


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await websocket.accept()
    if room_id not in rooms:
        rooms[room_id] = {"sockets": [], "state": None}
    rooms[room_id]["sockets"].append(websocket)

    # If two players connected, start game
    if len(rooms[room_id]["sockets"]) == 2 and rooms[room_id]["state"] is None:
        deck = build_deck()
        hands = [[deck.pop() for _ in range(7)] for _ in range(2)]
        state = {"deck": deck, "hands": hands, "board": [], "turn": 0}
        rooms[room_id]["state"] = state
        # send init to both
        for i, ws in enumerate(rooms[room_id]["sockets"]):
            await send(
                ws,
                {
                    "type": "init",
                    "hand": state["hands"][i],
                    "board": state["board"],
                    "your_turn": i == state["turn"],
                },
            )

    try:
        while True:
            text = await websocket.receive_text()
            msg = json.loads(text)
            state = rooms[room_id]["state"]
            # find player index
            try:
                player = rooms[room_id]["sockets"].index(websocket)
            except ValueError:
                player = None
            if msg.get("action") == "play" and state and player is not None:
                if player != state["turn"]:
                    await send(websocket, {"type": "msg", "text": "Not your turn"})
                    continue
                idx = msg.get("index")
                if idx is None or idx < 0 or idx >= len(state["hands"][player]):
                    await send(websocket, {"type": "msg", "text": "Invalid tile index"})
                    continue
                # Play with rules: must match left or right end, or draw
                tile = state["hands"][player][idx]
                left = state["board"][0][0] if state["board"] else None
                right = state["board"][-1][1] if state["board"] else None
                placed = False
                # if board empty, place
                if not state["board"]:
                    state["hands"][player].pop(idx)
                    state["board"].append(tile)
                    placed = True
                else:
                    a, b = tile
                    # try match left: tile's right must equal left
                    if b == left or a == left:
                        # orient so tile[1] == left
                        if a == left:
                            tile = [b, a]
                        state["hands"][player].pop(idx)
                        state["board"].insert(0, tile)
                        placed = True
                    # try match right: tile's left must equal right
                    elif a == right or b == right:
                        # orient so tile[0] == right
                        if b == right:
                            tile = [b, a]
                        state["hands"][player].pop(idx)
                        state["board"].append(tile)
                        placed = True
                if not placed:
                    # cannot place: try draw
                    if state["deck"]:
                        drawn = state["deck"].pop()
                        state["hands"][player].append(drawn)
                        await send(websocket, {"type": "msg", "text": f'Did not fit, drew tile {drawn}'})
                        # check if drawable tile now fits; if so, auto-play once
                        a, b = drawn
                        left = state["board"][0][0] if state["board"] else None
                        right = state["board"][-1][1] if state["board"] else None
                        can_play = False
                        if not state["board"]:
                            can_play = True
                        elif a == left or b == left or a == right or b == right:
                            can_play = True
                        if can_play:
                            # auto-play drawn tile
                            idx2 = len(state["hands"][player]) - 1
                            tile2 = state["hands"][player].pop(idx2)
                            if not state["board"]:
                                state["board"].append(tile2)
                            else:
                                a, b = tile2
                                left = state["board"][0][0]
                                right = state["board"][-1][1]
                                # match left: tile2.right == left
                                if b == left or a == left:
                                    if a == left:
                                        tile2 = [b, a]
                                    state["board"].insert(0, tile2)
                                else:
                                    # match right: tile2.left == right
                                    if b == right:
                                        tile2 = [b, a]
                                    state["board"].append(tile2)
                            placed = True
                        else:
                            # pass turn
                            state["turn"] = 1 - state["turn"]
                    else:
                        # no deck: pass
                        await send(websocket, {"type": "msg", "text": "Cannot play and deck empty. Passing turn."})
                        state["turn"] = 1 - state["turn"]
                else:
                    # successful placement: change turn
                    state["turn"] = 1 - state["turn"]
                # check win
                for i in range(2):
                    if len(state["hands"][i]) == 0:
                        # i wins
                        for ws in rooms[room_id]["sockets"]:
                            await send(ws, {"type": "msg", "text": f'Player {i+1} wins!'})
                        rooms[room_id]["state"] = None
                        break
                # broadcast update
                for i, ws in enumerate(rooms[room_id]["sockets"]):
                    await send(
                        ws,
                        {
                            "type": "update",
                            "hand": state["hands"][i],
                            "board": state["board"],
                            "your_turn": i == state["turn"],
                        },
                    )
            else:
                await broadcast(room_id, {"type": "msg", "text": str(msg)})
    except WebSocketDisconnect:
        rooms[room_id]["sockets"] = [
            s for s in rooms[room_id]["sockets"] if s != websocket
        ]
        # cleanup
        if not rooms[room_id]["sockets"]:
            del rooms[room_id]
        else:
            await broadcast(room_id, {"type": "msg", "text": "Opponent disconnected"})
