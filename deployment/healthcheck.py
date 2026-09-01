#!/usr/bin/env python3
from urllib.request import urlopen

with urlopen('http://127.0.0.1:8000/health/ready', timeout=3) as response:
    if response.status != 200:
        raise SystemExit(1)
