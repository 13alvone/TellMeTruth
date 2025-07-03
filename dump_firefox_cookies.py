#!/usr/bin/env python3
import browser_cookie3
import os

print("[i] Make sure you are LOGGED IN to YouTube in your Firefox browser before continuing!")

# Try to put cookies.txt in the current project directory
out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "cookies.txt"))
cj = browser_cookie3.firefox(domain_name="youtube.com")

with open(out_path, "w") as f:
    f.write("# Netscape HTTP Cookie File\n")
    for c in cj:
        line = "\t".join([
            c.domain,
            "TRUE" if c.domain_initial_dot else "FALSE",
            c.path,
            "TRUE" if c.secure else "FALSE",
            str(int(c.expires or 0)),
            c.name,
            c.value
        ])
        f.write(line + "\n")

print(f"[i] Dumped cookies to {out_path}")
print("[i] If you are running Docker on a different machine, move this cookies.txt to that machine's project directory before running docker-compose.")

