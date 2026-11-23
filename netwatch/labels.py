import json, os

F = os.path.join(os.path.expanduser("~"), ".netwatch", "labels.json")

def _load():
    if os.path.exists(F):
        return json.load(open(F))
    return {}

def _save(d):
    os.makedirs(os.path.dirname(F), exist_ok=True)
    json.dump(d, open(F, "w"), indent=2)

def set_label(ip, name):
    d = _load(); d[ip] = name; _save(d)

def get_label(ip):
    return _load().get(ip)

def all_labels():
    return _load()