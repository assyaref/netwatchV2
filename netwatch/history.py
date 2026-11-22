import sqlite3, time, os

DB = os.path.join(os.path.expanduser("~"), ".netwatch", "history.db")

def _conn():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS visits(
        ts REAL, ip TEXT, domain TEXT, bytes INTEGER)""")
    c.commit()
    return c

def record(ip, domain, nbytes=0):
    c = _conn()
    c.execute("INSERT INTO visits VALUES (?,?,?,?)", (time.time(), ip, domain, nbytes))
    c.commit(); c.close()

def for_ip(ip, limit=500):
    c = _conn()
    rows = c.execute("SELECT ts,domain,bytes FROM visits WHERE ip=? ORDER BY ts DESC LIMIT ?",
                     (ip, limit)).fetchall()
    c.close()
    return [{"ts": r[0], "domain": r[1], "bytes": r[2]} for r in rows]

def summary():
    c = _conn()
    rows = c.execute("SELECT ip,COUNT(*),MAX(ts) FROM visits GROUP BY ip").fetchall()
    c.close()
    return [{"ip": r[0], "visits": r[1], "last": r[2]} for r in rows]