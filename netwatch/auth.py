import hashlib, secrets, json, os, time

USERS_FILE = os.path.join(os.path.expanduser("~"), ".netwatch", "users.json")

def _load():
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        data = {
            "admin": {"hash": _hash("admin123"), "role": "admin"},
            "viewer": {"hash": _hash("viewer123"), "role": "viewer"},
        }
        _save(data)
        return data
    with open(USERS_FILE) as f:
        return json.load(f)

def _save(data):
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

_TOKENS = {}

def authenticate(user, pw):
    data = _load()
    u = data.get(user)
    if not u or u["hash"] != _hash(pw):
        return None
    token = secrets.token_hex(32)
    _TOKENS[token] = {"user": user, "role": u["role"], "exp": time.time() + 3600*8}
    return token, u["role"]

def verify(token):
    t = _TOKENS.get(token)
    if not t or t["exp"] < time.time():
        return None
    return t

def require(token, role=None):
    t = verify(token)
    if not t:
        return False
    if role and t["role"] != role and t["role"] != "admin":
        return False
    return True