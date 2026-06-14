"""
Application entrypoint.

Run locally:
    pip install -r requirements.txt
    python app.py
Then open http://localhost:5000

Run in production (single worker is mandatory — in-memory rooms must not be
split across processes):
    gunicorn --worker-class eventlet -w 1 app:app
"""
# Eventlet must monkey-patch the standard library BEFORE anything else imports
# socket/threading, or blocking I/O will stall concurrent connections.
import eventlet
eventlet.monkey_patch()

import logging
import os

from flask import Flask, render_template, request
from flask_socketio import SocketIO

from config import Config
from game.manager import room_manager
from sockets import connection, lobby, drawing, gameplay

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
)
log = logging.getLogger("draw_hunt")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    return app


app = create_app()

socketio = SocketIO(
    app,
    async_mode="eventlet",
    cors_allowed_origins=app.config["CORS_ORIGINS"],
    logger=False,
    engineio_logger=False,
)

# Register socket handlers per concern.
connection.register(socketio)
lobby.register(socketio)
drawing.register(socketio)
gameplay.register(socketio)
# Start the periodic room-cleanup sweeper.
lobby.start_sweeper(socketio)


# ---------------- HTTP routes ----------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/create-room", methods=["POST"])
def create_room():
    data = request.get_json(silent=True) or {}
    user_id = (data.get("user_id") or "").strip()
    if not user_id:
        return {"error": "missing user_id"}, 400
    room = room_manager.create_room(host_id=user_id)
    log.info("room created: %s (host %s)", room.code, user_id)
    return {"code": room.code}, 201


@app.route("/room/<code>")
def room_page(code):
    return render_template(
        "game.html",
        room_code=code.upper(),
        min_players=Config.MIN_PLAYERS,
        max_players=Config.MAX_PLAYERS,
        allowed_rounds=Config.ALLOWED_ROUNDS,
        allowed_durations=Config.ALLOWED_DURATIONS,
    )


@app.route("/healthz")
def healthz():
    return {"status": "ok", "rooms": len(room_manager.rooms)}, 200


if __name__ == "__main__":
    # Local development entrypoint. In production, gunicorn imports `app` and
    # this block does not run (see Procfile / README).
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    log.info("starting draw_hunt server on http://localhost:%d", port)
    socketio.run(app, host="0.0.0.0", port=port, debug=debug)