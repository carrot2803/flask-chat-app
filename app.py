from typing import Any, Optional, Union
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase as base
from werkzeug import Response


app = Flask(__name__)
app.config["SECRET_KEY"] = "fjjfjf"
socketio = SocketIO(app)


rooms = {}
homeParams = tuple[str | None, str | None, Union[bool, str], Union[bool, str]]


def getCode(len: int) -> str:
    return "".join(random.choice(base) for _ in range(len))


def generateUniqueCode(length: int) -> str:
    code = getCode(length)
    while code in rooms:
        code = getCode(length)
    return code


def handleError(error_msg: str, code: Optional[str], name: Optional[str]) -> str:
    return render_template("home.html", error=error_msg, code=code, name=name)


def fetchForm() -> homeParams:
    name = request.form.get("name")
    code = request.form.get("code")
    join: Union[bool, str] = request.form.get("join", False)
    create: Union[bool, str] = request.form.get("create", False)
    return name, code, join, create


def createRoom(limit: int) -> str:
    roomCode = generateUniqueCode(limit)
    rooms[roomCode] = {"members": 0, "messages": []}
    return roomCode


def homeRedirect(roomCode: str | None, name: str) -> Response:
    session["room"] = roomCode
    session["name"] = name
    return redirect(url_for("room"))


def handleHome(params: homeParams) -> Response | str:
    name, code, join, create = params
    if not name:
        return handleError("Please enter a name", code, name)
    if join != False and not code:
        return handleError("Please enter a room code.", code, name)

    room = code
    if create != False:
        room = generateUniqueCode(4)
        rooms[room] = {"members": 0, "messages": []}
    elif code not in rooms:
        return handleError("Room does not exist", code, name)
    return homeRedirect(room, name)


@app.route("/room")
def room() -> Response | str:
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))
    return render_template("room.html", code=room, messages=rooms[room]["messages"])


@app.route("/", methods=["POST", "GET"])
def home() -> Response | str:
    session.clear()
    if request.method == "POST":
        return handleHome(fetchForm())
    return render_template("home.html")


@socketio.on("message")
def message(data) -> None:
    room = session.get("room")
    if room not in rooms:
        return

    content: dict[str, Any] = {"name": session.get("name"), "message": data["data"]}
    send(content, to=room)  # type: ignore
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} said: {data['data']}")


def getRoomInfo() -> tuple[str, str]:
    return str(session.get("room")), str(session.get("name"))


def handleLeave(room: str) -> None:
    leave_room(room)
    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]


@socketio.on("connect")
def connect() -> None:
    room, name = getRoomInfo()
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name": name, "message": "has entered the room"}, to=room)  # type: ignore
    rooms[room]["members"] += 1
    print(f"{name} joined room {room}")


@socketio.on("disconnect")
def disconnect():
    room, name = getRoomInfo()
    handleLeave(room)
    send({"name": name, "message": "has left the room"}, to=room)  # type: ignore
    print(f"{name} has left the room {room}")


if __name__ == "__main__":
    socketio.run(app, debug=True)  # type: ignore
