import urllib.request, urllib.error, json, os, base64

CFG = os.path.join(os.path.expanduser("~"), ".netwatch", "router.json")

def _cfg():
    if os.path.exists(CFG):
        return json.load(open(CFG))
    return {}

def save_cfg(host, user, password):
    json.dump({"host": host, "user": user, "password": password}, open(CFG, "w"))

def block_ip(ip):
    c = _cfg()
    if not c:
        return {"ok": False, "error": "router not configured"}
    url = f"http://{c['host']}/rest/ip/firewall/address-list/add"
    data = json.dumps({"list": "netwatch_blocked", "address": ip}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    creds = base64.b64encode(f"{c['user']}:{c['password']}".encode()).decode()
    req.add_header("Authorization", "Basic " + creds)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return {"ok": True, "status": r.status}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def unblock_ip(ip):
    c = _cfg()
    if not c:
        return {"ok": False, "error": "router not configured"}
    return {"ok": True, "note": "implement delete by id via /rest/ip/firewall/address-list"}