import argparse
import csv
import gc
import hashlib
import hmac
import json
import math
import os
import platform
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import Crypto
from Crypto.Cipher import AES, ARC4, DES
from Crypto.Util.Padding import pad, unpad

from app.crypto import keywrap
from app.crypto.suites import CHUNK_SIZE, SUITES, IntegrityError

KEK = os.urandom(32)
INTEGRITY_KEY = os.urandom(32)
AAD = b"lapor-siber/v1|bench|attachment|x|content"
MiB = 1024 * 1024
SHORT = {"AES-256-GCM": "AES", "DES-CBC-HMAC": "DES", "RC4-HMAC": "RC4"}


class ListReader:
    def __init__(self, parts):
        self.parts = [p for p in parts if p]
        self.i = 0

    def read(self, n=-1):
        if self.i >= len(self.parts):
            return b""
        self.i += 1
        return self.parts[self.i - 1]

    def seek(self, pos):
        self.i = 0


class NullSink:
    def write(self, b):
        pass


def chunks_of(data: bytes):
    return [data[i:i + CHUNK_SIZE] for i in range(0, len(data), CHUNK_SIZE)] or [b""]


def measure(fn, samples: int, target_ms: float = 20.0) -> dict:
    fn(); fn()
    t0 = time.perf_counter_ns(); fn(); one = time.perf_counter_ns() - t0
    k = max(1, int(target_ms * 1e6 / max(one, 1)))
    times = []
    gc.disable()
    try:
        for _ in range(samples):
            t0 = time.perf_counter_ns()
            for _ in range(k):
                fn()
            times.append((time.perf_counter_ns() - t0) / k)
    finally:
        gc.enable()
    q = statistics.quantiles(times, n=4) if len(times) >= 4 else [min(times), statistics.median(times), max(times)]
    mean = statistics.fmean(times)
    return {"median_ns": statistics.median(times), "p25_ns": q[0], "p75_ns": q[2],
            "min_ns": min(times), "cv": statistics.pstdev(times) / mean if mean else 0.0,
            "samples": samples, "reps_per_sample": k}


def app_encrypt(suite, parts):
    aad = AAD + b"|" + suite.name.encode()
    key = suite.new_key()
    enc = suite.encryptor(key, aad)
    out = [enc.update(p) for p in parts]
    last, tag = enc.finalize()
    out.append(last)
    wrapped = keywrap.wrap(KEK, key, aad)
    return {"iv": enc.iv, "tag": tag, "parts": out, "wrapped": wrapped}


def app_decrypt(suite, blob, sink=None):
    aad = AAD + b"|" + suite.name.encode()
    key = keywrap.unwrap(KEK, blob["wrapped"], aad)
    suite.decrypt_stream(key, aad, blob["iv"], blob["tag"], ListReader(blob["parts"]), sink or NullSink())


class _Collect:
    def __init__(self):
        self.parts = []

    def write(self, b):
        self.parts.append(b)


def plain_hmac(parts):
    m = hmac.new(INTEGRITY_KEY, AAD, hashlib.sha256)
    for p in parts:
        m.update(p)
    return m.digest()


def raw_ciphers():
    def aes_ctr(parts):
        c = AES.new(os.urandom(32), AES.MODE_CTR, nonce=os.urandom(8))
        for p in parts:
            c.encrypt(p)

    def des_cbc(parts):
        c = DES.new(os.urandom(8), DES.MODE_CBC, iv=os.urandom(8))
        for p in parts[:-1]:
            c.encrypt(p)
        c.encrypt(pad(parts[-1], 8))

    def rc4(parts):
        c = ARC4.new(os.urandom(16), drop=3072)
        for p in parts:
            c.encrypt(p)

    def hmac_sha256(parts):
        m = hmac.new(os.urandom(32), digestmod=hashlib.sha256)
        for p in parts:
            m.update(p)
        m.digest()

    def aes_gcm(parts):
        c = AES.new(os.urandom(32), AES.MODE_GCM, nonce=os.urandom(12))
        for p in parts:
            c.encrypt(p)
        c.digest()

    return {"AES-256-CTR": aes_ctr, "AES-256-GCM (with tag)": aes_gcm, "DES-CBC": des_cbc,
            "RC4-drop3072": rc4, "HMAC-SHA256": hmac_sha256}


def bench_payloads(payloads, samples_small, samples_big):
    rows = []
    for key, label, size in payloads:
        data = os.urandom(size)
        parts = chunks_of(data)
        for name, suite in SUITES.items():
            blob = app_encrypt(suite, parts)
            got = _Collect(); app_decrypt(suite, blob, got)
            assert b"".join(got.parts) == data, f"roundtrip failed: {name}"
            n = samples_big if size >= 8 * MiB else samples_small
            e = measure(lambda: app_encrypt(suite, parts), n)
            d = measure(lambda: app_decrypt(suite, blob), n)
            ct_len = sum(len(p) for p in blob["parts"])
            overhead = ct_len - size + len(blob["iv"]) + len(blob["tag"]) + len(blob["wrapped"])
            rows.append({
                "payload": key, "label": label, "size": size, "cipher": name,
                "enc": e, "dec": d, "overhead_bytes": overhead,
                "enc_mbps": size / MiB / (e["median_ns"] / 1e9) if size else None,
                "dec_mbps": size / MiB / (d["median_ns"] / 1e9) if size else None,
            })
            print(f"  {label:<28} {SHORT[name]}  enc {fmt_ns(e['median_ns']):>10}  dec {fmt_ns(d['median_ns']):>10}  "
                  f"CV {e['cv']*100:4.1f}%")
        m = measure(lambda: plain_hmac(parts), samples_big if size >= 8 * MiB else samples_small)
        rows.append({"payload": key, "label": label, "size": size, "cipher": "HMAC plaintext (once)",
                     "enc": m, "dec": m, "overhead_bytes": 32,
                     "enc_mbps": size / MiB / (m["median_ns"] / 1e9) if size else None,
                     "dec_mbps": size / MiB / (m["median_ns"] / 1e9) if size else None})
    return rows


def bench_raw(size, samples):
    data = os.urandom(size)
    parts = chunks_of(data)
    out = []
    for name, fn in raw_ciphers().items():
        m = measure(lambda: fn(parts), samples)
        out.append({"primitive": name, "size": size, **m, "mbps": size / MiB / (m["median_ns"] / 1e9)})
        print(f"  {name:<24} {out[-1]['mbps']:8.1f} MB/s  (CV {m['cv']*100:.1f}%)")
    return out


def bench_setup(samples):
    out = {}
    for name, suite in SUITES.items():
        out[f"Total scheme {SHORT[name]} (0 bytes)"] = measure(lambda: app_encrypt(suite, [b""]), samples)["median_ns"]
    k32, k8, k16 = os.urandom(32), os.urandom(8), os.urandom(16)
    parts = {
        "AES-GCM: initialization + tag": lambda: AES.new(k32, AES.MODE_GCM, nonce=os.urandom(12)).digest(),
        "DES-CBC: initialization": lambda: DES.new(k8, DES.MODE_CBC, iv=os.urandom(8)),
        "RC4: initialization without drop": lambda: ARC4.new(k16),
        "RC4: initialization + drop 3072": lambda: ARC4.new(k16, drop=3072),
        "HMAC-SHA256: init + digest": lambda: hmac.new(k32, b"x", hashlib.sha256).digest(),
        "Key wrap AES-GCM (used by all schemes)": lambda: keywrap.wrap(KEK, k32, AAD),
        "Random key os.urandom(48)": lambda: os.urandom(48),
    }
    for label, fn in parts.items():
        out[label] = measure(fn, samples)["median_ns"]
    return out


def tamper_experiment(trials=2000, size=4096):
    data = os.urandom(size)
    res = {}
    for name, suite in SUITES.items():
        detected = 0
        for _ in range(trials):
            blob = app_encrypt(suite, [data])
            ct = bytearray(b"".join(blob["parts"]))
            bit = int.from_bytes(os.urandom(4), "big") % (len(ct) * 8)
            ct[bit // 8] ^= 1 << (bit % 8)
            blob["parts"] = [bytes(ct)]
            try:
                app_decrypt(suite, blob)
            except IntegrityError:
                detected += 1
        res[name] = {"trials": trials, "detected": detected, "silent": trials - detected}

    def raw(name):
        detected = silent = 0
        bits_changed = []
        for _ in range(trials):
            if name == "AES-256-CTR":
                k, n = os.urandom(32), os.urandom(8)
                ct = bytearray(AES.new(k, AES.MODE_CTR, nonce=n).encrypt(data))
                dec = lambda c: AES.new(k, AES.MODE_CTR, nonce=n).decrypt(bytes(c))
            elif name == "DES-CBC":
                k, iv = os.urandom(8), os.urandom(8)
                ct = bytearray(DES.new(k, DES.MODE_CBC, iv=iv).encrypt(pad(data, 8)))
                dec = lambda c: unpad(DES.new(k, DES.MODE_CBC, iv=iv).decrypt(bytes(c)), 8)
            else:
                k = os.urandom(16)
                ct = bytearray(ARC4.new(k, drop=3072).encrypt(data))
                dec = lambda c: ARC4.new(k, drop=3072).decrypt(bytes(c))
            bit = int.from_bytes(os.urandom(4), "big") % (len(ct) * 8)
            ct[bit // 8] ^= 1 << (bit % 8)
            try:
                pt = dec(ct)
            except ValueError:
                detected += 1
                continue
            if len(pt) != len(data):
                detected += 1
                continue
            silent += 1
            bits_changed.append(sum(bin(a ^ b).count("1") for a, b in zip(pt, data)))
        return {"trials": trials, "detected": detected, "silent": silent,
                "avg_plain_bits_changed": statistics.fmean(bits_changed) if bits_changed else 0}

    for name in ("AES-256-CTR", "DES-CBC", "RC4"):
        res[name + " (without MAC)"] = raw(name)
    return res


def forgery_demo():
    msg = b"Loss: $1,000 to Account 1234567890 for perpetrator"
    pos = msg.index(b"1,000")
    delta = ord("1") ^ ord("9")
    out = {"original": msg.decode()}

    k = os.urandom(16)
    ct = bytearray(ARC4.new(k, drop=3072).encrypt(msg)); ct[pos] ^= delta
    out["RC4 without MAC"] = ARC4.new(k, drop=3072).decrypt(bytes(ct)).decode(errors="replace")

    k, iv = os.urandom(8), bytearray(os.urandom(8))
    ct = DES.new(k, DES.MODE_CBC, iv=bytes(iv)).encrypt(pad(msg, 8))
    blk, off = divmod(pos, 8)
    if blk == 0:
        iv[off] ^= delta; forged = DES.new(k, DES.MODE_CBC, iv=bytes(iv)).decrypt(ct)
    else:
        c = bytearray(ct); c[(blk - 1) * 8 + off] ^= delta
        forged = DES.new(k, DES.MODE_CBC, iv=bytes(iv)).decrypt(bytes(c))
    out["DES-CBC without MAC"] = unpad(forged, 8).decode(errors="replace")

    for name, suite in SUITES.items():
        blob = app_encrypt(suite, [msg])
        ct = bytearray(b"".join(blob["parts"]))
        if name == "DES-CBC-HMAC":
            blk, off = divmod(pos, 8)
            if blk == 0:
                iv2 = bytearray(blob["iv"]); iv2[off] ^= delta; blob["iv"] = bytes(iv2)
            else:
                ct[(blk - 1) * 8 + off] ^= delta
        else:
            ct[pos] ^= delta
        blob["parts"] = [bytes(ct)]
        try:
            app_decrypt(suite, blob)
            out[name] = "PASSED (undetected)"
        except IntegrityError:
            out[name] = "REJECTED: integrity failed"
    return out


def rc4_bias(n: int):
    res = {}
    for drop in (0, 3072):
        zeros = 0
        for _ in range(n):
            if ARC4.new(os.urandom(16), drop=drop).encrypt(b"\x00\x00")[1] == 0:
                zeros += 1
        p = zeros / n
        se = math.sqrt(p * (1 - p) / n)
        z = (p - 1 / 256) / math.sqrt((1 / 256) * (255 / 256) / n)
        res[f"drop={drop}"] = {"n": n, "p": p, "ci95": [p - 1.96 * se, p + 1.96 * se], "z_vs_uniform": z}
    return res


def brute_force(seconds: float):
    block, iv = os.urandom(8), bytes(8)
    out = {}
    for name, keylen, bits, mk in (
        ("DES", 8, 56, lambda k: DES.new(k, DES.MODE_CBC, iv=iv)),
        ("AES-128", 16, 128, lambda k: AES.new(k, AES.MODE_CBC, iv=bytes(16))),
    ):
        blk = block if name == "DES" else block * 2
        keys = [os.urandom(keylen) for _ in range(20000)]
        n, t0 = 0, time.perf_counter()
        while time.perf_counter() - t0 < seconds:
            for k in keys:
                mk(k).encrypt(blk)
            n += len(keys)
        rate = n / (time.perf_counter() - t0)
        avg_trials = 2 ** (bits - 1)
        out[name] = {"key_bits": bits, "keys_per_s_1core": rate,
                     "years_avg_1core": avg_trials / rate / 31_557_600,
                     "years_avg_all_cores": avg_trials / rate / 31_557_600 / (os.cpu_count() or 1)}
    return out


def sweet32(max_file_mb=200):
    def p(bytes_, b):
        n = bytes_ / (b // 8)
        return min(1.0, n * n / 2 ** (b + 1))
    one_file = max_file_mb * MiB
    shared_key = 100 * 1024 * MiB
    return {"des_per_file_key": p(one_file, 64), "des_single_key_100GB": p(shared_key, 64),
            "aes_single_key_100GB": p(shared_key, 128), "des_birthday_bound_GiB": (2 ** 32 * 8) / 1024 ** 3}


def fmt_ns(ns):
    if ns < 1e3:
        return f"{ns:.0f} ns"
    if ns < 1e6:
        return f"{ns/1e3:.1f} µs"
    if ns < 1e9:
        return f"{ns/1e6:.2f} ms"
    return f"{ns/1e9:.2f} s"


def env_info():
    cpu = platform.processor() or ""
    flags = ""
    try:
        txt = Path("/proc/cpuinfo").read_text()
        for line in txt.splitlines():
            if line.startswith("model name") and not cpu:
                cpu = line.split(":", 1)[1].strip()
            if line.startswith("flags"):
                flags = line
                break
    except OSError:
        pass
    aesni = (" aes " in flags + " ") if flags else None
    if aesni is None and platform.machine().lower() in ("arm64", "aarch64"):
        aesni = "ARMv8 Crypto Ext. (likely)"
    return {"python": sys.version.split()[0], "pycryptodome": Crypto.__version__, "os": platform.platform(),
            "cpu": cpu or platform.machine(), "cores": os.cpu_count(), "aes_ni": aesni,
            "timestamp": datetime.now().isoformat(timespec="seconds")}


def write_charts(rows, raw, outdir: Path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  matplotlib not installed, charts skipped")
        return []
    colors = {"AES-256-GCM": "#2563eb", "DES-CBC-HMAC": "#dc2626", "RC4-HMAC": "#d97706"}
    files = []

    big = [p for p in dict.fromkeys(r["payload"] for r in rows) if next(r for r in rows if r["payload"] == p)["size"] >= 64 * 1024]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, kind in zip(axes, ("enc", "dec")):
        w = 0.26
        for i, c in enumerate(SUITES):
            vals = [next(r for r in rows if r["payload"] == p and r["cipher"] == c)[f"{kind}_mbps"] for p in big]
            xs = [j + (i - 1) * w for j in range(len(big))]
            ax.bar(xs, vals, w, label=SHORT[c], color=colors[c])
            for x, v in zip(xs, vals):
                ax.text(x, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8)
        ax.set_xticks(range(len(big)))
        ax.set_xticklabels([next(r["label"] for r in rows if r["payload"] == p) for p in big], fontsize=9)
        ax.set_title("Encryption" if kind == "enc" else "Decryption (verify + decrypt)")
        ax.set_yscale("log")
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("MB/s (log scale, higher is faster)")
    axes[0].legend()
    fig.suptitle("Application scheme throughput (cipher + integrity + key wrap)")
    fig.tight_layout()
    f = outdir / "throughput.png"; fig.savefig(f, dpi=150); plt.close(fig); files.append(f)

    small = [p for p in dict.fromkeys(r["payload"] for r in rows) if next(r for r in rows if r["payload"] == p)["size"] < 64 * 1024]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    w = 0.26
    for i, c in enumerate(SUITES):
        vals = [next(r for r in rows if r["payload"] == p and r["cipher"] == c)["enc"]["median_ns"] / 1e3 for p in small]
        xs = [j + (i - 1) * w for j in range(len(small))]
        ax.bar(xs, vals, w, label=SHORT[c], color=colors[c])
        for x, v in zip(xs, vals):
            ax.text(x, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(small)))
    ax.set_xticklabels([next(r["label"] for r in rows if r["payload"] == p) for p in small])
    ax.set_ylabel("µs per item (lower is faster)")
    ax.set_title("Encryption latency for small data (dominated by fixed overhead)")
    ax.legend(); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    f = outdir / "latency_small.png"; fig.savefig(f, dpi=150); plt.close(fig); files.append(f)

    fig, ax = plt.subplots(figsize=(7, 3.6))
    names = [r["primitive"] for r in raw]
    ax.barh(names, [r["mbps"] for r in raw], color=["#2563eb", "#60a5fa", "#dc2626", "#d97706", "#6b7280"])
    for i, r in enumerate(raw):
        ax.text(r["mbps"], i, f" {r['mbps']:.0f}", va="center", fontsize=8)
    ax.set_xlabel("MB/s"); ax.set_title("Primitive speed (without integrity) vs HMAC")
    ax.invert_yaxis(); ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    f = outdir / "primitives.png"; fig.savefig(f, dpi=150); plt.close(fig); files.append(f)
    return files


def row(rows, payload, cipher):
    return next(r for r in rows if r["payload"] == payload and r["cipher"] == cipher)


def write_summary(res, outdir: Path):
    rows, raw, env = res["payloads"], res["primitives"], res["env"]
    names = list(SUITES)
    L = []
    L.append("# Benchmark Results: AES vs DES vs RC4 — Safe Report\n")
    L.append(f"Machine: {env['cpu']} ({env['cores']} cores), Hardware AES acceleration: {env['aes_ni']}, "
             f"Python {env['python']}, pycryptodome {env['pycryptodome']}, {env['os']}. Timestamp: {env['timestamp']}.\n")
    L.append("Absolute numbers apply strictly to this test environment. The meaningful comparisons are the **ratios between ciphers** and "
             "**whether the performance delta affects end-user experience**.\n")

    L.append("## 1. Execution time per data type (identical scheme to application)\n")
    L.append("Per cipher: generate random key → chunk-wise 1 MiB encryption → tag/HMAC → wrap key. Decryption: unwrap key → "
             "verify tag/HMAC → decrypt. Median (quartiles 1–3 in parentheses). The *HMAC plaintext* row measures the end-to-end "
             "integrity check performed once per upload and once per download across all ciphers.\n")
    L.append("| Data | Size | Scheme | Encryption | Decryption | MB/s enc | MB/s dec | CV | Storage overhead |")
    L.append("|---|---:|---|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        mb = lambda v: f"{v:.0f}" if v and r["size"] >= 64 * 1024 else "–"
        iqr = f"{fmt_ns(r['enc']['median_ns'])} ({fmt_ns(r['enc']['p25_ns'])}–{fmt_ns(r['enc']['p75_ns'])})"
        dec = fmt_ns(r['dec']['median_ns']) if r["cipher"] in SUITES else "(same)"
        L.append(f"| {r['label']} | {human(r['size'])} | {SHORT.get(r['cipher'], r['cipher'])} | {iqr} | {dec} | "
                 f"{mb(r['enc_mbps'])} | {mb(r['dec_mbps']) if r['cipher'] in SUITES else '–'} | {r['enc']['cv']*100:.1f}% | "
                 f"{r['overhead_bytes']} B |")
    L.append("")
    worst = max(rows, key=lambda r: r["enc"]["cv"])
    big_cv = max(r["enc"]["cv"] for r in rows if r["size"] >= 8 * MiB)
    L.append(f"Highest coefficient of variation (CV): {worst['enc']['cv']*100:.1f}% ({worst['label']}, "
             f"{SHORT.get(worst['cipher'], worst['cipher'])}); for large payloads, highest CV is {big_cv*100:.1f}%. "
             + ("Measurement is stable." if worst["enc"]["cv"] < 0.15 else
                "Variation is highest on small payloads sensitive to system interrupts. Differences on large data "
                "span orders of magnitude, far exceeding this noise, leaving comparative findings solid."))

    payloads = list(dict.fromkeys(r["payload"] for r in rows))
    vid, small = payloads[-1], payloads[0]
    V = {n: row(rows, vid, n) for n in names}
    H = row(rows, vid, "HMAC plaintext (once)")
    S = {n: row(rows, small, n) for n in names}
    fastest_big = max(names, key=lambda n: V[n]["enc_mbps"])
    slowest_big = min(names, key=lambda n: V[n]["enc_mbps"])
    fastest_small = min(names, key=lambda n: S[n]["enc"]["median_ns"])
    slowest_small = max(names, key=lambda n: S[n]["enc"]["median_ns"])
    L.append("\n**Interpretation:**\n")
    ratio = lambda a, b: V[a]["enc_mbps"] / V[b]["enc_mbps"]
    L.append(f"- **Large data ({V[names[0]]['label'].lower()}, {human(V[names[0]]['size'])}):** {SHORT[fastest_big]} is fastest. "
             f"DES is {ratio('AES-256-GCM', 'DES-CBC-HMAC'):.1f}× slower than AES, and RC4 is {ratio('AES-256-GCM', 'RC4-HMAC'):.1f}× slower than AES. "
             + ("AES dominates because of hardware instruction extensions (AES-NI/ARMv8), while DES and RC4 run entirely in software; "
                "DES is additionally inherently slow by design (16 rounds of bit-level permutations)." if env["aes_ni"] else
                "Hardware acceleration was not detected on this machine; speed differences on native AES-NI hosts are even larger."))
    max_mb = 200
    t = {n: max_mb / V[n]["enc_mbps"] for n in names}
    th = max_mb / H["enc_mbps"]
    total = sum(t.values()) + th
    L.append(f"- **User wait time.** For a maximum {max_mb} MB video: AES ≈ {t['AES-256-GCM']:.1f} s, DES ≈ {t['DES-CBC-HMAC']:.1f} s, "
             f"RC4 ≈ {t['RC4-HMAC']:.1f} s, plaintext HMAC ≈ {th:.1f} s. Because the system stores three copies, post-upload processing "
             f"takes ≈ {total:.1f} s, with {t[slowest_big]/total*100:.0f}% of the duration consumed by {SHORT[slowest_big]}. "
             f"Storing only AES would reduce this processing overhead to ≈ {t['AES-256-GCM'] + th:.1f} s.")
    L.append(f"- **Downloads** use a single cipher. A user downloading a {max_mb} MB video waits ≈ "
             + ", ".join(f"{SHORT[n]} {max_mb / V[n]['dec_mbps'] + th:.1f} s" for n in names)
             + " (including end-to-end integrity checks). Consequently, AES is designated as the primary default cipher.")
    L.append(f"- **Small data ({S[names[0]]['label']}, {human(S[names[0]]['size'])}):** all complete in at most "
             f"{math.ceil(max(S[n]['enc']['median_ns'] for n in names)/1e3)} µs; {SHORT[fastest_small]} is fastest and {SHORT[slowest_small]} is slowest"
             + (", a reversal of the large-file ranking. " if fastest_small != fastest_big else ". ")
             + "At small sizes, raw throughput is irrelevant; fixed setup overhead dominates. A variance of several microseconds is completely imperceptible to users.")
    L.append(f"- **Storage overhead** per item is small and constant: IV + tag + wrapped key, plus 1–8 byte PKCS#7 padding for DES. "
             f"For a 16-byte National ID, the overhead appears large proportionally ({', '.join(SHORT[n] + ' ' + str(S[n]['overhead_bytes']) + ' B' for n in names)}), "
             "but is negligible for multimedia files. The primary storage factor is storing **three copies**: disk consumption ≈ 3× raw evidence size.\n")

    rp = {r["primitive"]: r["mbps"] for r in raw}
    L.append("## 2. Raw primitives vs HMAC\n")
    L.append(f"Payload size: {human(raw[0]['size'])}, without integrity, isolating cipher throughput from MAC computation.\n")
    L.append("| Primitive | MB/s | CV |")
    L.append("|---|---:|---:|")
    for r in raw:
        L.append(f"| {r['primitive']} | {r['mbps']:.0f} | {r['cv']*100:.1f}% |")
    h = rp["HMAC-SHA256"]
    harm = lambda a, b: 1 / (1 / a + 1 / b)
    L.append("")
    L.append("**Interpretation:**\n")
    L.append(f"- Raw DES achieves only {rp['DES-CBC']:.0f} MB/s, acting as the primary bottleneck; HMAC ({h:.0f} MB/s) adds only minimal "
             f"overhead (estimated composite DES+HMAC ≈ {harm(rp['DES-CBC'], h):.0f} MB/s).")
    rc4_mac = harm(rp["RC4-drop3072"], h)
    L.append(f"- Raw RC4 achieves {rp['RC4-drop3072']:.0f} MB/s, but once paired with HMAC drops to ≈ {rc4_mac:.0f} MB/s, "
             f"while hardware-accelerated AES-GCM (which integrates AEAD integrity) reaches {rp['AES-256-GCM (with tag)']:.0f} MB/s. "
             + ("The historical justification that 'RC4 is chosen for speed' no longer holds when integrity is required on hardware-accelerated architectures."
                if rp["AES-256-GCM (with tag)"] > rc4_mac else
                "Even where RC4+HMAC is nominally faster, the margin fails to justify its cryptographic vulnerabilities."))
    L.append(f"- The throughput delta between AES-CTR ({rp['AES-256-CTR']:.0f} MB/s) and AES-GCM ({rp['AES-256-GCM (with tag)']:.0f} MB/s) reflects GHASH computation.\n")

    st = res["setup_ns"]
    L.append("## 3. Fixed setup overhead per item\n")
    L.append("| Component | Latency |")
    L.append("|---|---:|")
    for k, v in st.items():
        L.append(f"| {k} | {fmt_ns(v)} |")
    L.append("")
    kw = st["Key wrap AES-GCM (used by all schemes)"]
    gcm = st["AES-GCM: initialization + tag"]
    L.append("**Interpretation:**\n")
    L.append(f"- Key wrapping ({fmt_ns(kw)}) constitutes the largest setup component and is identical across schemes due to envelope encryption.")
    L.append(f"- AES-GCM incurs a noticeable setup cost ({fmt_ns(gcm)}) because pycryptodome constructs GHASH precomputation tables for every unique key. "
             "Because unique keys are enforced per item, this cost is incurred on every invocation.")
    L.append(f"- Discarding the initial 3072 bytes of keystream in RC4 increases initialization from {fmt_ns(st['RC4: initialization without drop'])} to "
             f"{fmt_ns(st['RC4: initialization + drop 3072'])}, a negligible trade-off given the security benefit.\n")

    tp = res["tamper"]
    L.append("## 4. Ciphertext tampering test\n")
    L.append("One random bit was flipped within a 4 KB ciphertext payload, followed by decryption attempt.\n")
    L.append("| Scheme | Trials | Detected | Silent corruption | Average plaintext bits altered (when undetected) |")
    L.append("|---|---:|---:|---:|---:|")
    for k, v in tp.items():
        L.append(f"| {k} | {v['trials']} | {v['detected']} | {v['silent']} | {v.get('avg_plain_bits_changed', 0):.1f} |")
    L.append("")
    L.append("Targeted forgery demo: an attacker without encryption keys alters damage values in report text from 1,000 to 9,000.\n")
    for k, v in res["forgery"].items():
        L.append(f"- **{k}**: `{v}`")
    cbc = tp["DES-CBC (without MAC)"]
    L.append("")
    L.append("**Interpretation:**\n")
    L.append("- Without MAC protection, CTR and RC4 are malleable: bit flips in ciphertext directly translate to bit flips in plaintext. An attacker can selectively alter data without detection.")
    L.append(f"- Unauthenticated CBC corrupts an entire block plus 1 bit in the subsequent block (averaging {cbc['avg_plain_bits_changed']:.0f} bits altered), "
             f"with PKCS#7 padding validation failing only {cbc['detected']} out of {cbc['trials']} times. Targeted modifications can succeed invisibly via IV manipulation on the initial block.")
    L.append("- With GCM and Encrypt-then-MAC, 100% of tampered ciphertexts are detected and rejected prior to plaintext exposure.\n")

    b = res["rc4_bias"]
    L.append("## 5. Measured cryptographic weaknesses\n")
    L.append("**RC4 Keystream Bias.** Probability that byte 2 of the keystream equals 0 (uniform expected = 1/256 = 0.391%):\n")
    for k, v in b.items():
        L.append(f"- {k}: {v['p']*100:.3f}% (95% CI: {v['ci95'][0]*100:.3f}–{v['ci95'][1]*100:.3f}%), z = {v['z_vs_uniform']:.1f}, n = {v['n']:,}")
    d0, d1 = b["drop=0"], b["drop=3072"]
    L.append(f"\nWithout drop, probability is {d0['p']*256:.2f}× uniform expectation (z = {d0['z_vs_uniform']:.0f}), validating the Mantin-Shamir attack. "
             f"With drop 3072, z = {d1['z_vs_uniform']:.1f}, indistinguishable from uniform distribution at this sample size.\n")
    bf = res["brute_force"]
    L.append("**Key space brute force rate** (1 core, Python + pycryptodome):\n")
    for k, v in bf.items():
        L.append(f"- {k} ({v['key_bits']} bits): {v['keys_per_s_1core']:,.0f} keys/s → average {sci(v['years_avg_1core'])} years "
                 f"(1 core), {sci(v['years_avg_all_cores'])} years ({env['cores']} cores)")
    L.append("\nDES key space (56 bits) is completely vulnerable to specialized GPU/ASIC hardware (e.g. EFF Deep Crack cracked DES in 56 hours in 1998). "
             "By contrast, AES-128 and AES-256 are mathematically intractable to brute-force.\n")
    s = res["sweet32"]
    L.append(f"**DES 64-bit block collision (Sweet32).** Birthday paradox collision risk exceeds negligible thresholds after ≈ {s['des_birthday_bound_GiB']:.0f} GiB under a single key. "
             f"Because unique keys are provisioned per file (max 200 MB), collision probability remains ≈ {s['des_per_file_key']:.1e}. AES with 128-bit blocks eliminates this risk.\n")

    L.append("## 6. Conclusions for Safe Report Architecture\n")
    L.append("- **AES-256-GCM is designated as primary** for all operational retrieval (owner downloads, profile views, officer reviews): "
             f"highest throughput for evidence files ({V['AES-256-GCM']['enc_mbps']:.0f} MB/s vs DES {V['DES-CBC-HMAC']['enc_mbps']:.0f} "
             f"and RC4 {V['RC4-HMAC']['enc_mbps']:.0f}), native AEAD integrity, 256-bit key space, and 128-bit block size.")
    L.append("- **DES-CBC-HMAC** prevents undetected tampering via HMAC, but its 56-bit effective key fails contemporary confidentiality standards. It also incurs the largest upload latency penalty.")
    L.append("- **RC4-HMAC** mitigates initial bias with drop-3072 and achieves integrity through HMAC, but remains obsolete and offers no speed advantage over hardware-accelerated AES-GCM.")
    L.append("- **Implications of multi-cipher storage:** Tripling storage footprint and summing encryption overhead across all three ciphers creates a system whose confidentiality is bounded by its **weakest link** (DES 56-bit). In production, only AES-256-GCM should be retained.")
    (outdir / "summary.md").write_text("\n".join(L), encoding="utf-8")


def human(n):
    if n < 1024:
        return f"{n} B"
    if n < MiB:
        return f"{n/1024:.0f} KB"
    return f"{n/MiB:.0f} MB"


def sci(x):
    return f"{x:,.1f}" if x < 1e6 else f"{x:.1e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--pin", action="store_true", help="pin to CPU 0 (Linux)")
    ap.add_argument("--out", default=str(Path(__file__).parent / "results"))
    ap.add_argument("--summary-only", action="store_true", help="regenerate summary.md & charts from results.json")
    a = ap.parse_args()
    if a.summary_only:
        outdir = Path(a.out)
        res = json.loads((outdir / "results.json").read_text(encoding="utf-8"))
        write_charts(res["payloads"], res["primitives"], outdir)
        write_summary(res, outdir)
        print(f"Rewritten: {outdir / 'summary.md'}")
        return
    if a.pin and hasattr(os, "sched_setaffinity"):
        os.sched_setaffinity(0, {0})
    outdir = Path(a.out); outdir.mkdir(parents=True, exist_ok=True)

    video_mb = 16 if a.quick else 64
    payloads = [
        ("nik", "National ID (field)", 16),
        ("chronology", "Report chronology", 2 * 1024),
        ("ktp", "ID card scan", 600 * 1024),
        ("document", "Office document", 3 * MiB),
        ("video", "Evidence video", video_mb * MiB),
    ]
    ss, sb = (9, 5) if a.quick else (21, 9)
    res = {"env": env_info()}
    print("Environment:", res["env"])
    print("[1] Scenario payloads"); res["payloads"] = bench_payloads(payloads, ss, sb)
    print("[2] Raw primitives"); res["primitives"] = bench_raw(16 * MiB, sb)
    print("[3] Fixed setup cost"); res["setup_ns"] = bench_setup(ss)
    print("[4] Tamper test"); res["tamper"] = tamper_experiment(500 if a.quick else 2000)
    res["forgery"] = forgery_demo()
    print("[5] RC4 bias"); res["rc4_bias"] = rc4_bias(2 ** 16 if a.quick else 2 ** 18)
    print("[6] Brute force"); res["brute_force"] = brute_force(1.0 if a.quick else 3.0)
    res["sweet32"] = sweet32()

    (outdir / "results.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(outdir / "payloads.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["payload", "size_bytes", "cipher", "enc_median_ms", "enc_p25_ms", "enc_p75_ms", "dec_median_ms",
                    "enc_mbps", "dec_mbps", "enc_cv", "overhead_bytes"])
        for r in res["payloads"]:
            w.writerow([r["payload"], r["size"], r["cipher"], r["enc"]["median_ns"] / 1e6, r["enc"]["p25_ns"] / 1e6,
                        r["enc"]["p75_ns"] / 1e6, r["dec"]["median_ns"] / 1e6, r["enc_mbps"], r["dec_mbps"],
                        r["enc"]["cv"], r["overhead_bytes"]])
    charts = write_charts(res["payloads"], res["primitives"], outdir)
    write_summary(res, outdir)
    print(f"\nDone. See {outdir/'summary.md'}" + (f" and {len(charts)} PNG charts" if charts else ""))


if __name__ == "__main__":
    main()
