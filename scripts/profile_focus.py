"""Opt-in shortcut profiling; restore the user's Terminal settings afterward."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
import uuid

from configure import ACTIONS, parse_settings, settings_path


def write_settings(path, contents):
    staged = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        staged.write_bytes(contents)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def encode(data):
    return (json.dumps(data, ensure_ascii=False, indent=4) + "\n").encode("utf-8")


def action(data):
    return next(a for a in data["actions"] if a.get("id") == ACTIONS["herdr"])


@contextmanager
def trace_herdr(directory):
    path = settings_path()
    original = path.read_bytes()
    data = parse_settings(original.decode("utf-8-sig"))
    command = action(data)["command"]
    saved_command = command["commandline"]
    if "--focus-existing" not in saved_command or "--trace-dir" in saved_command:
        raise ValueError("Expected the installed Herdr return shortcut without active profiling")
    traced_command = saved_command + " --trace-dir " + subprocess.list2cmdline([str(directory)])
    command["commandline"] = traced_command
    changed = encode(data)
    write_settings(path, changed)
    try:
        time.sleep(.5)  # Terminal reloads its settings; outside the stopwatch.
        yield
    finally:
        current = path.read_bytes()
        if current == changed:
            write_settings(path, original)
        else:
            # Preserve other settings edited while the benchmark was running.
            current_data = parse_settings(current.decode("utf-8-sig"))
            current_command = action(current_data)["command"]
            if current_command.get("commandline") == traced_command:
                current_command["commandline"] = saved_command
                write_settings(path, encode(current_data))


STAGES = [
    ("Terminal and Python startup", "keypress", "python_entry"),
    ("Python imports and arguments", "python_entry", "arguments_parsed"),
    ("Select machine and resolve window context", "arguments_parsed", "machine_selected"),
    ("Settings and origin marker", "machine_selected", "settings_loaded"),
    ("Read live view records", "settings_loaded", "records_loaded"),
    ("Payload and helper cache", "records_loaded", "helper_ready"),
    ("Create handoff event", "helper_ready", "helper_spawn"),
    ("Helper process and CLR startup", "helper_spawn", "native_entry"),
    ("Native initialization and options", "native_entry", "options_decoded"),
    ("Enumerate Terminal tabs", "options_decoded", "tabs_enumerated"),
    ("Choose live MRU target", "tabs_enumerated", "target_chosen"),
    ("Signal and wait for launcher exit", "target_chosen", "launcher_exited"),
    ("Wait for tab closure", "launcher_exited", "launcher_tab_closed"),
    ("Resolve destination tab", "launcher_tab_closed", "target_resolved"),
    ("Select destination tab", "target_resolved", "tab_selected"),
    ("Apply window foreground", "tab_selected", "window_focused"),
    ("Focus terminal content", "window_focused", "content_focused"),
]


def collect(directory, measurements):
    traces = []
    for path in directory.glob("*.launcher.json"):
        native = Path(str(path).replace(".launcher.json", ".json"))
        events = json.loads(path.read_text()) + json.loads(native.read_text())
        traces.append({e["name"]: e["at"] for e in events})
    samples = []
    verification_tail = []
    for measurement in measurements:
        matches = [t for t in traces if measurement["started"] <= t["python_entry"] <= measurement["focused"]]
        if len(matches) != 1:
            raise ValueError("Expected exactly one complete launcher trace for each shortcut press")
        events = {**matches[0], "keypress": measurement["started"], "observed": measurement["focused"]}
        # The observer can see usable content focus while the helper is still
        # confirming it through UIA. Keep that tail out of user-visible latency.
        observed = measurement["focused"]
        durations = {label: (min(events[end], observed) - min(events[start], observed)) * 1000
                     for label, start, end in STAGES}
        samples.append(durations)
        verification_tail.append(max(0, (events["content_focused"] - observed) * 1000))
    stages = {label: {"mean": round(statistics.mean(s[label] for s in samples), 3),
                    "median": round(statistics.median(s[label] for s in samples), 3),
                    "min": round(min(s[label] for s in samples), 3),
                    "max": round(max(s[label] for s in samples), 3),
                    "samples": [round(s[label], 3) for s in samples]} for label, _, _ in STAGES}
    return stages, {"median": round(statistics.median(verification_tail), 3),
                    "samples": [round(s, 3) for s in verification_tail]}
