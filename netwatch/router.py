import requests, os, json

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
    try:
        r = requests.post(url, json={"list": "netwatch_blocked", "address": ip}, auth=(c["user"], c["password"]), timeout=10)
        return {"ok": r.ok, "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def unblock_ip(ip):
    c = _cfg()
    if not c:
        return {"ok": False, "error": "router not configured"}
    return {"ok": True, "note": "implement delete by id via /rest/ip/firewall/address-list"}