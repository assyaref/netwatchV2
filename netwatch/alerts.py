import json, os, smtplib, urllib.request, time

RULES_FILE = os.path.join(os.path.expanduser("~"), ".netwatch", "alerts.json")
STATE = {"rules": [], "last": {}}

def _load():
    os.makedirs(os.path.dirname(RULES_FILE), exist_ok=True)
    if os.path.exists(RULES_FILE):
        with open(RULES_FILE) as f:
            STATE["rules"] = json.load(f)
    return STATE["rules"]

def _save():
    with open(RULES_FILE, "w") as f:
        json.dump(STATE["rules"], f, indent=2)

def add_rule(ip, domain, channel, target):
    r = {"ip": ip, "domain": domain, "channel": channel, "target": target, "created": time.time()}
    STATE["rules"].append(r)
    _save()
    return r

def remove_rule(i):
    if 0 <= i < len(STATE["rules"]):
        STATE["rules"].pop(i)
        _save()

def list_rules():
    _load()
    return STATE["rules"]

def check(ip, domain):
    _load()
    for r in STATE["rules"]:
        if r["ip"] == ip and (r["domain"] == "*" or r["domain"] in domain):
            key = (r["ip"], r["domain"], r["target"])
            if time.time() - STATE["last"].get(key, 0) > 60:
                STATE["last"][key] = time.time()
                notify(r, ip, domain)

def notify(r, ip, domain):
    msg = f"[NETWATCH] {ip} mengakses {domain}"
    if r["channel"] == "telegram":
        try:
            url = f"https://api.telegram.org/bot{r['target'].split(':')[0]}/sendMessage"
            data = json.dumps({"chat_id": r['target'].split(':')[1], "text": msg}).encode()
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass
    elif r["channel"] == "email":
        try:
            s = smtplib.SMTP("localhost")
            s.sendmail("netwatch@local", r["target"], msg)
            s.quit()
        except Exception:
            pass