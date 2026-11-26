"""Lightweight pure-Python internet speed test (Ping, Download, Upload) via Cloudflare."""

from __future__ import annotations

import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from .i18n import tr


@dataclass
class SpeedTestResult:
    ok: bool
    ping_ms: float = 0.0
    download_mbps: float = 0.0
    upload_mbps: float = 0.0
    error: str = ""


def _measure_ping(host: str = "1.1.1.1", port: int = 443, samples: int = 3) -> float:
    times = []
    for _ in range(samples):
        t0 = time.perf_counter()
        s = socket.create_connection((host, port), timeout=4.0)
        elapsed = (time.perf_counter() - t0) * 1000.0
        s.close()
        times.append(elapsed)
    return min(times) if times else 0.0


def _measure_download(num_bytes: int = 8_000_000) -> float:
    url = f"https://speed.cloudflare.com/__down?bytes={num_bytes}"
    req = urllib.request.Request(url, headers={"User-Agent": "MintSpot/1.0"})
    t0 = time.perf_counter()
    total = 0
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            total += len(chunk)
    elapsed = max(time.perf_counter() - t0, 0.01)
    return (total * 8.0) / (elapsed * 1_000_000.0)


def _measure_upload(num_bytes: int = 2_000_000) -> float:
    url = "https://speed.cloudflare.com/__up"
    payload = b"\x00" * num_bytes
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "User-Agent": "MintSpot/1.0",
            "Content-Type": "application/octet-stream",
        },
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=15.0) as resp:
        resp.read()
    elapsed = max(time.perf_counter() - t0, 0.01)
    return (num_bytes * 8.0) / (elapsed * 1_000_000.0)


def run_speedtest(on_stage: Optional[Callable[[str], None]] = None) -> SpeedTestResult:
    try:
        if on_stage:
            on_stage(tr("speedtest_stage_ping"))
        ping_ms = _measure_ping()

        if on_stage:
            on_stage(tr("speedtest_stage_download"))
        dl_mbps = _measure_download()

        if on_stage:
            on_stage(tr("speedtest_stage_upload"))
        ul_mbps = _measure_upload()

        return SpeedTestResult(
            ok=True,
            ping_ms=round(ping_ms, 1),
            download_mbps=round(dl_mbps, 1),
            upload_mbps=round(ul_mbps, 1),
        )
    except (OSError, urllib.error.URLError) as exc:
        return SpeedTestResult(ok=False, error=tr("speedtest_failed", error=exc))
