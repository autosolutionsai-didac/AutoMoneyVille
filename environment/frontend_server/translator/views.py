"""
Original Author: Joon Sung Park (joonspk@stanford.edu)
Heavily modified for Claudeville (Claude CLI port)

File: views.py
"""

import datetime
import json
import os
import time

import requests
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

# Backend server URL (env-overridable; defaults to the local Flask backend).
BACKEND_URL = os.environ.get("CLAUDEVILLE_BACKEND_URL", "http://127.0.0.1:5000")
CLIENT_VERSION = "stream-v2"


def _is_current_client(request):
    return request.headers.get("X-Claudeville-Client") == CLIENT_VERSION


def _stale_client_response():
    return JsonResponse(
        {
            "status": "stale_client",
            "error": "This simulator tab is stale. Hard refresh the page.",
        },
        status=409,
    )


def _get_backend_health():
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=2)
        response.raise_for_status()
        backend = response.json()
    except requests.RequestException:
        return None
    if backend.get("ok", True):
        return backend
    return None


def _read_json_file(path, retries=3, delay=0.05):
    last_error = None
    for attempt in range(retries):
        try:
            with open(path, encoding="utf-8") as json_file:
                return json.load(json_file)
        except json.JSONDecodeError as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(delay)
    raise last_error


def _world_render_context(backend):
    """maze_name + map pixel size for the Phaser frontend, read from the backend
    health snapshot (the running backend knows its world). Defaults to the_ville so
    the frontend keeps working when the backend is down. No filesystem reads.
    """
    backend = backend or {}
    return {
        "maze_name": backend.get("maze_name", "the_ville"),
        "map_width_px": backend.get("map_width_px", 4480),
        "map_height_px": backend.get("map_height_px", 3200),
    }


# =============================================================================
# API Endpoints (New HTTP-based communication)
# =============================================================================


def api_movements(request):
    """
    Poll for pending movements from backend.
    Frontend calls this to get movement data to animate.
    Backend (CLI) drives simulation and queues movements.
    """
    after_step = request.GET.get("after_step")
    if after_step is None and not _is_current_client(request):
        return _stale_client_response()

    try:
        params = {}
        if after_step is not None:
            params["after_step"] = after_step
        response = requests.get(f"{BACKEND_URL}/movements", params=params, timeout=5)
        response.raise_for_status()
        return JsonResponse(response.json())
    except requests.Timeout:
        return JsonResponse({"error": "Backend timeout"}, status=504)
    except requests.ConnectionError:
        return JsonResponse({"error": "Backend not running"}, status=502)
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=502)


def api_status(request):
    """Get current simulation status from backend."""
    try:
        response = requests.get(f"{BACKEND_URL}/status", timeout=5)
        response.raise_for_status()
        return JsonResponse(response.json())
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=502)


def api_health(request):
    """Return Django health plus backend health if Flask is reachable."""
    health = {
        "django": {
            "ok": True,
            "service": "claudeville-frontend",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "backend": {"ok": False, "error": None},
    }
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=2)
        response.raise_for_status()
        backend_health = response.json()
        backend_health["ok"] = bool(backend_health.get("ok", True))
        health["backend"] = backend_health
    except requests.RequestException as e:
        health["backend"] = {"ok": False, "error": str(e)}
    return JsonResponse(health)


def api_save(request):
    """Save simulation state via backend."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        response = requests.post(f"{BACKEND_URL}/save", timeout=30)
        response.raise_for_status()
        return JsonResponse(response.json())
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=502)


def api_simulate(request):
    """Request simulation steps from backend."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    if not _is_current_client(request):
        return _stale_client_response()

    try:
        data = json.loads(request.body) if request.body else {}
        response = requests.post(
            f"{BACKEND_URL}/simulate",
            json=data,
            timeout=240,  # First LLM-backed steps can be slow with 10 personas.
        )
        response.raise_for_status()
        return JsonResponse(response.json())
    except requests.Timeout:
        return JsonResponse(
            {
                "status": "busy",
                "message": "Simulation is still running after proxy timeout",
            }
        )
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=502)


def api_saves(request):
    """List available saves from backend."""
    try:
        response = requests.get(f"{BACKEND_URL}/saves", timeout=5)
        response.raise_for_status()
        return JsonResponse(response.json())
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=502)


def api_town_center(request):
    """Return the active town-center scenario, request, tool, and reward snapshot."""
    try:
        response = requests.get(f"{BACKEND_URL}/town-center", timeout=5)
        response.raise_for_status()
        return JsonResponse(response.json())
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=502)


def api_town_center_request(request):
    """Submit a town-center request through the backend."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        data = json.loads(request.body) if request.body else {}
        response = requests.post(
            f"{BACKEND_URL}/town-center/requests",
            json=data,
            timeout=10,
        )
        response.raise_for_status()
        return JsonResponse(response.json())
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=502)


def api_town_center_request_transition(request, request_id):
    """Transition a town-center request through the approval lifecycle."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        data = json.loads(request.body) if request.body else {}
        response = requests.post(
            f"{BACKEND_URL}/town-center/requests/{request_id}/transition",
            json=data,
            timeout=10,
        )
        response.raise_for_status()
        return JsonResponse(response.json())
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=502)


def api_town_center_reward(request):
    """Award points or revenue evidence through the backend."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        data = json.loads(request.body) if request.body else {}
        response = requests.post(
            f"{BACKEND_URL}/town-center/rewards",
            json=data,
            timeout=10,
        )
        response.raise_for_status()
        return JsonResponse(response.json())
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    except requests.RequestException as e:
        return JsonResponse({"error": str(e)}, status=502)


# =============================================================================
# Page Views
# =============================================================================


def landing(request):
    context = {}
    template = "landing/landing.html"
    return render(request, template, context)


def demo(request, sim_code, step, play_speed="2"):
    move_file = f"compressed_storage/{sim_code}/master_movement.json"
    meta_file = f"compressed_storage/{sim_code}/meta.json"
    step = int(step)
    play_speed_opt = {"1": 1, "2": 2, "3": 4, "4": 8, "5": 16, "6": 32}
    if play_speed not in play_speed_opt:
        play_speed = 2
    else:
        play_speed = play_speed_opt[play_speed]

    # Loading the basic meta information about the simulation.
    meta = dict()
    with open(meta_file) as json_file:
        meta = json.load(json_file)

    sec_per_step = meta["sec_per_step"]
    start_datetime = datetime.datetime.strptime(
        meta["start_date"] + " 00:00:00", "%B %d, %Y %H:%M:%S"
    )
    for i in range(step):
        start_datetime += datetime.timedelta(seconds=sec_per_step)
    start_datetime = start_datetime.strftime("%Y-%m-%dT%H:%M:%S")

    # Loading the movement file
    raw_all_movement = dict()
    with open(move_file) as json_file:
        raw_all_movement = json.load(json_file)

    # Loading all names of the personas
    persona_names = dict()
    persona_names = []
    persona_names_set = set()
    for p in list(raw_all_movement["0"].keys()):
        persona_names += [
            {
                "original": p,
                "underscore": p.replace(" ", "_"),
                "initial": p[0] + p.split(" ")[-1][0],
            }
        ]
        persona_names_set.add(p)

    # <all_movement> is the main movement variable that we are passing to the
    # frontend. Whereas we use ajax scheme to communicate steps to the frontend
    # during the simulation stage, for this demo, we send all movement
    # information in one step.
    all_movement = dict()

    # Preparing the initial step.
    # <init_prep> sets the locations and descriptions of all agents at the
    # beginning of the demo determined by <step>.
    init_prep = dict()
    for int_key in range(step + 1):
        key = str(int_key)
        val = raw_all_movement[key]
        for p in persona_names_set:
            if p in val:
                init_prep[p] = val[p]
    persona_init_pos = dict()
    for p in persona_names_set:
        persona_init_pos[p.replace(" ", "_")] = init_prep[p]["movement"]
    all_movement[step] = init_prep

    # Finish loading <all_movement>
    for int_key in range(step + 1, len(raw_all_movement.keys())):
        all_movement[int_key] = raw_all_movement[str(int_key)]

    context = {
        "sim_code": sim_code,
        "step": step,
        "persona_names": persona_names,
        "persona_init_pos": json.dumps(persona_init_pos),
        "all_movement": json.dumps(all_movement),
        "start_datetime": start_datetime,
        "sec_per_step": sec_per_step,
        "play_speed": play_speed,
        "mode": "demo",
    }
    template = "demo/demo.html"

    return render(request, template, context)


@ensure_csrf_cookie
def home(request):
    f_curr_sim_code = "temp_storage/curr_sim_code.json"
    f_curr_step = "temp_storage/curr_step.json"

    backend = _get_backend_health()
    initial_curr_time = None
    if backend and backend.get("sim_code"):
        sim_code = backend["sim_code"]
        step = backend.get("step", 0)
        initial_curr_time = backend.get("curr_time")
    else:
        if not os.path.exists(f_curr_sim_code) or not os.path.exists(f_curr_step):
            context = {}
            template = "home/error_start_backend.html"
            return render(request, template, context)
        try:
            sim_code = _read_json_file(f_curr_sim_code)["sim_code"]
            step = _read_json_file(f_curr_step)["step"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            context = {}
            template = "home/error_start_backend.html"
            return render(request, template, context)

    # NOTE: Removed os.remove(f_curr_step) - keep file so browser refresh works

    persona_names = []
    persona_names_set = set()
    personas_dir = f"storage/runs/{sim_code}/personas"
    for x in os.listdir(personas_dir):
        if not x.startswith("."):
            persona_names.append([x, x.replace(" ", "_")])
            persona_names_set.add(x)

    persona_init_pos = []
    if backend and backend.get("sim_code") == sim_code:
        step = backend.get("step", step)
        initial_curr_time = backend.get("curr_time")
        for persona in backend.get("personas", []):
            name = persona.get("name")
            tile = persona.get("tile")
            if name in persona_names_set and tile and len(tile) >= 2:
                persona_init_pos += [[name, tile[0], tile[1]]]

    if not persona_init_pos:
        env_dir = f"storage/runs/{sim_code}/environment"
        file_count = [
            int(f.split(".")[0])
            for f in os.listdir(env_dir)
            if f.endswith(".json") and not f.startswith(".")
        ]
        curr_json = f"{env_dir}/{max(file_count)}.json"
        with open(curr_json) as json_file:
            persona_init_pos_dict = json.load(json_file)
            for key, val in persona_init_pos_dict.items():
                if key in persona_names_set:
                    persona_init_pos += [[key, val["x"], val["y"]]]

    context = {
        "sim_code": sim_code,
        "step": step,
        "persona_names": persona_names,
        "persona_init_pos": persona_init_pos,
        "initial_curr_time": initial_curr_time,
        "mode": "simulate",
    }
    context.update(_world_render_context(backend))
    template = "home/home.html"
    return render(request, template, context)


@ensure_csrf_cookie
def replay(request, sim_code, step):
    sim_code = sim_code
    step = int(step)

    persona_names = []
    persona_names_set = set()
    personas_dir = f"storage/runs/{sim_code}/personas"
    for x in os.listdir(personas_dir):
        if not x.startswith("."):
            persona_names.append([x, x.replace(" ", "_")])
            persona_names_set.add(x)

    persona_init_pos = []
    env_dir = f"storage/runs/{sim_code}/environment"
    file_count = [
        int(f.split(".")[0])
        for f in os.listdir(env_dir)
        if f.endswith(".json") and not f.startswith(".")
    ]
    curr_json = f"{env_dir}/{max(file_count)}.json"
    with open(curr_json) as json_file:
        persona_init_pos_dict = json.load(json_file)
        for key, val in persona_init_pos_dict.items():
            if key in persona_names_set:
                persona_init_pos += [[key, val["x"], val["y"]]]

    context = {
        "sim_code": sim_code,
        "step": step,
        "persona_names": persona_names,
        "persona_init_pos": persona_init_pos,
        "mode": "replay",
    }
    template = "home/home.html"
    return render(request, template, context)


def replay_persona_state(request, sim_code, step, persona_name):
    sim_code = sim_code
    step = int(step)

    persona_name_underscore = persona_name
    persona_name = " ".join(persona_name.split("_"))
    memory = f"storage/runs/{sim_code}/personas/{persona_name}/bootstrap_memory"
    if not os.path.exists(memory):
        memory = (
            f"compressed_storage/{sim_code}/personas/{persona_name}/bootstrap_memory"
        )

    with open(memory + "/scratch.json") as json_file:
        scratch = json.load(json_file)

    with open(memory + "/spatial_memory.json") as json_file:
        spatial = json.load(json_file)

    with open(memory + "/associative_memory/nodes.json") as json_file:
        associative = json.load(json_file)

    a_mem_event = []
    a_mem_chat = []
    a_mem_thought = []

    for count in range(len(associative.keys()), 0, -1):
        node_id = f"node_{str(count)}"
        node_details = associative[node_id]

        if node_details["type"] == "event":
            a_mem_event += [node_details]

        elif node_details["type"] == "chat":
            a_mem_chat += [node_details]

        elif node_details["type"] == "thought":
            a_mem_thought += [node_details]

    context = {
        "sim_code": sim_code,
        "step": step,
        "persona_name": persona_name,
        "persona_name_underscore": persona_name_underscore,
        "scratch": scratch,
        "spatial": spatial,
        "a_mem_event": a_mem_event,
        "a_mem_chat": a_mem_chat,
        "a_mem_thought": a_mem_thought,
    }
    template = "persona_state/persona_state.html"
    return render(request, template, context)


@ensure_csrf_cookie
def path_tester(request):
    context = {}
    template = "path_tester/path_tester.html"
    return render(request, template, context)


def path_tester_update(request):
    """
    Processing the path and saving it to path_tester_env.json temp storage for
    conducting the path tester.

    ARGS:
      request: Django request
    RETURNS:
      HttpResponse: string confirmation message.
    """
    data = json.loads(request.body)
    camera = data["camera"]

    with open("temp_storage/path_tester_env.json", "w") as outfile:
        outfile.write(json.dumps(camera, indent=2))

    return HttpResponse("received")
