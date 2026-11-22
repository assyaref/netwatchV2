import os, time

def export_pdf(ip, visits, out_path=None):
    out_path = out_path or os.path.join(os.path.expanduser("~"), ".netwatch", f"report_{ip}.txt")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    lines = [f"NETWATCH Report - {ip}", f"Generated: {time.ctime()}", "", "Visited domains:"]
    for v in visits:
        lines.append(f"  {time.ctime(v['ts'])}  {v['domain']}  ({v['bytes']} bytes)")
    with open(out_path, "w") as f:
        f.write("\n".join(lines))
    return out_path