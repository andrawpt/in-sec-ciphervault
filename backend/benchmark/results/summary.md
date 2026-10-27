# Benchmark Results: AES vs DES vs RC4 — Safe Report

Machine: x86_64 (2 cores), Hardware AES acceleration: True, Python 3.13.17, pycryptodome 4.2.0, Linux-6.18.44-fc-v165-x86_64-with-glibc2.39. Timestamp: 2026-10-27T17:49:01.

Absolute numbers apply strictly to this test environment. The meaningful comparisons are the **ratios between ciphers** and **whether the performance delta affects end-user experience**.

## 1. Execution time per data type (identical scheme to application)

Per cipher: generate random key → chunk-wise 1 MiB encryption → tag/HMAC → wrap key. Decryption: unwrap key → verify tag/HMAC → decrypt. Median (quartiles 1–3 in parentheses). The *HMAC plaintext* row measures the end-to-end integrity check performed once per upload and once per download across all ciphers.

| Data | Size | Scheme | Encryption | Decryption | MB/s enc | MB/s dec | CV | Storage overhead |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| National ID (field) | 16 B | AES | 122.0 µs (118.4 µs–132.4 µs) | 121.3 µs | – | – | 18.1% | 88 B |
| National ID (field) | 16 B | DES | 93.8 µs (91.2 µs–101.7 µs) | 98.0 µs | – | – | 8.1% | 116 B |
| National ID (field) | 16 B | RC4 | 91.2 µs (88.6 µs–95.5 µs) | 90.4 µs | – | – | 7.0% | 108 B |
| National ID (field) | 16 B | HMAC plaintext (once) | 2.7 µs (2.7 µs–2.8 µs) | (same) | – | – | 9.8% | 32 B |
| Report chronology | 2 KB | AES | 123.6 µs (122.5 µs–127.3 µs) | 124.9 µs | – | – | 11.3% | 88 B |
| Report chronology | 2 KB | DES | 214.2 µs (195.0 µs–266.9 µs) | 197.4 µs | – | – | 18.7% | 116 B |
| Report chronology | 2 KB | RC4 | 103.6 µs (101.0 µs–107.3 µs) | 103.2 µs | – | – | 14.8% | 108 B |
| Report chronology | 2 KB | HMAC plaintext (once) | 8.0 µs (7.8 µs–8.2 µs) | (same) | – | – | 7.6% | 32 B |
| ID card scan | 600 KB | AES | 814.6 µs (800.3 µs–898.8 µs) | 886.0 µs | 719 | 661 | 7.9% | 88 B |
| ID card scan | 600 KB | DES | 32.59 ms (30.28 ms–46.32 ms) | 31.35 ms | 18 | 19 | 24.2% | 116 B |
| ID card scan | 600 KB | RC4 | 3.85 ms (3.71 ms–3.92 ms) | 3.77 ms | 152 | 155 | 3.9% | 108 B |
| ID card scan | 600 KB | HMAC plaintext (once) | 1.79 ms (1.67 ms–2.29 ms) | (same) | 328 | – | 18.6% | 32 B |
| Office document | 3 MB | AES | 3.82 ms (3.78 ms–4.17 ms) | 3.94 ms | 785 | 761 | 10.0% | 88 B |
| Office document | 3 MB | DES | 158.05 ms (152.03 ms–169.44 ms) | 146.48 ms | 19 | 20 | 6.9% | 116 B |
| Office document | 3 MB | RC4 | 17.58 ms (17.52 ms–17.86 ms) | 17.63 ms | 171 | 170 | 5.2% | 108 B |
| Office document | 3 MB | HMAC plaintext (once) | 8.52 ms (8.14 ms–9.39 ms) | (same) | 352 | – | 9.6% | 32 B |
| Evidence video | 64 MB | AES | 82.73 ms (78.44 ms–88.66 ms) | 87.71 ms | 774 | 730 | 9.6% | 88 B |
| Evidence video | 64 MB | DES | 3.37 s (3.31 s–3.48 s) | 3.26 s | 19 | 20 | 2.6% | 116 B |
| Evidence video | 64 MB | RC4 | 398.76 ms (381.59 ms–413.23 ms) | 378.56 ms | 160 | 169 | 3.9% | 108 B |
| Evidence video | 64 MB | HMAC plaintext (once) | 176.53 ms (173.38 ms–189.64 ms) | (same) | 363 | – | 4.4% | 32 B |

Highest coefficient of variation (CV): 24.2% (ID card scan, DES); for large payloads, highest CV is 9.6%. Variation is highest on small payloads sensitive to system interrupts. Differences on large data span orders of magnitude, far exceeding this noise, leaving comparative findings solid.

**Interpretation:**

- **Large data (evidence video, 64 MB):** AES is fastest. DES is 40.7× slower than AES, and RC4 is 4.8× slower than AES. AES dominates because of hardware instruction extensions (AES-NI/ARMv8), while DES and RC4 run entirely in software; DES is additionally inherently slow by design (16 rounds of bit-level permutations).
- **User wait time.** For a maximum 200 MB video: AES ≈ 0.3 s, DES ≈ 10.5 s, RC4 ≈ 1.2 s, plaintext HMAC ≈ 0.6 s. Because the system stores three copies, post-upload processing takes ≈ 12.6 s, with 84% of the duration consumed by DES. Storing only AES would reduce this processing overhead to ≈ 0.8 s.
- **Downloads** use a single cipher. A user downloading a 200 MB video waits ≈ AES 0.8 s, DES 10.7 s, RC4 1.7 s (including end-to-end integrity checks). Consequently, AES is designated as the primary default cipher.
- **Small data (National ID (field), 16 B):** all complete in at most 123 µs; RC4 is fastest and AES is slowest, a reversal of the large-file ranking. At small sizes, raw throughput is irrelevant; fixed setup overhead dominates. A variance of several microseconds is completely imperceptible to users.
- **Storage overhead** per item is small and constant: IV + tag + wrapped key, plus 1–8 byte PKCS#7 padding for DES. For a 16-byte National ID, the overhead appears large proportionally (AES 88 B, DES 116 B, RC4 108 B), but is negligible for multimedia files. The primary storage factor is storing **three copies**: disk consumption ≈ 3× raw evidence size.

## 2. Raw primitives vs HMAC

Payload size: 16 MB, without integrity, isolating cipher throughput from MAC computation.

| Primitive | MB/s | CV |
|---|---:|---:|
| AES-256-CTR | 1060 | 3.1% |
| AES-256-GCM (with tag) | 881 | 2.9% |
| DES-CBC | 20 | 4.0% |
| RC4-drop3072 | 325 | 4.1% |
| HMAC-SHA256 | 372 | 3.6% |

**Interpretation:**

- Raw DES achieves only 20 MB/s, acting as the primary bottleneck; HMAC (372 MB/s) adds only minimal overhead (estimated composite DES+HMAC ≈ 19 MB/s).
- Raw RC4 achieves 325 MB/s, but once paired with HMAC drops to ≈ 174 MB/s, while hardware-accelerated AES-GCM (which integrates AEAD integrity) reaches 881 MB/s. The historical justification that 'RC4 is chosen for speed' no longer holds when integrity is required on hardware-accelerated architectures.
- The throughput delta between AES-CTR (1060 MB/s) and AES-GCM (881 MB/s) reflects GHASH computation.

## 3. Fixed setup overhead per item

| Component | Latency |
|---|---:|
| Total scheme AES (0 bytes) | 119.2 µs |
| Total scheme DES (0 bytes) | 87.7 µs |
| Total scheme RC4 (0 bytes) | 88.0 µs |
| AES-GCM: initialization + tag | 44.3 µs |
| DES-CBC: initialization | 6.2 µs |
| RC4: initialization without drop | 3.2 µs |
| RC4: initialization + drop 3072 | 15.0 µs |
| HMAC-SHA256: init + digest | 2.4 µs |
| Key wrap AES-GCM (used by all schemes) | 62.0 µs |
| Random key os.urandom(48) | 617 ns |

**Interpretation:**

- Key wrapping (62.0 µs) constitutes the largest setup component and is identical across schemes due to envelope encryption.
- AES-GCM incurs a noticeable setup cost (44.3 µs) because pycryptodome constructs GHASH precomputation tables for every unique key. Because unique keys are enforced per item, this cost is incurred on every invocation.
- Discarding the initial 3072 bytes of keystream in RC4 increases initialization from 3.2 µs to 15.0 µs, a negligible trade-off given the security benefit.

## 4. Ciphertext tampering test

One random bit was flipped within a 4 KB ciphertext payload, followed by decryption attempt.

| Scheme | Trials | Detected | Silent corruption | Average plaintext bits altered (when undetected) |
|---|---:|---:|---:|---:|
| AES-256-GCM | 2000 | 2000 | 0 | 0.0 |
| DES-CBC-HMAC | 2000 | 2000 | 0 | 0.0 |
| RC4-HMAC | 2000 | 2000 | 0 | 0.0 |
| AES-256-CTR (without MAC) | 2000 | 0 | 2000 | 1.0 |
| DES-CBC (without MAC) | 2000 | 5 | 1995 | 33.1 |
| RC4 (without MAC) | 2000 | 0 | 2000 | 1.0 |

Targeted forgery demo: an attacker without encryption keys alters damage values in report text from 1,000 to 9,000.

- **original**: `Loss: $1,000 to Account 1234567890 for perpetrator`
- **RC4 without MAC**: `Loss: $9,000 to Account 1234567890 for perpetrator`
- **DES-CBC without MAC**: `#@"2k: $9,000 to Account 1234567890 for perpetrator`
- **AES-256-GCM**: `REJECTED: integrity failed`
- **DES-CBC-HMAC**: `REJECTED: integrity failed`
- **RC4-HMAC**: `REJECTED: integrity failed`

**Interpretation:**

- Without MAC protection, CTR and RC4 are malleable: bit flips in ciphertext directly translate to bit flips in plaintext. An attacker can selectively alter data without detection.
- Unauthenticated CBC corrupts an entire block plus 1 bit in the subsequent block (averaging 33 bits altered), with PKCS#7 padding validation failing only 5 out of 2000 trials. Targeted modifications can succeed invisibly via IV manipulation on the initial block.
- With GCM and Encrypt-then-MAC, 100% of tampered ciphertexts are detected and rejected prior to plaintext exposure.

## 5. Measured cryptographic weaknesses

**RC4 Keystream Bias.** Probability that byte 2 of the keystream equals 0 (uniform expected = 1/256 = 0.391%):

- drop=0: 0.739% (95% CI: 0.706–0.772%), z = 28.6, n = 262,144
- drop=3072: 0.373% (95% CI: 0.350–0.397%), z = -1.4, n = 262,144

Without drop, probability is 1.89× uniform expectation (z = 29), validating the Mantin-Shamir attack. With drop 3072, z = -1.4, indistinguishable from uniform distribution at this sample size. Drop eliminates initial bias, though long-term biases in RC4 persist.

**Key space brute force rate** (1 core, Python + pycryptodome):

- DES (56 bits): 109,767 keys/s → average 10,400.9 years (1 core), 5,200.5 years (2 cores)
- AES-128 (128 bits): 112,784 keys/s → average 4.8e+25 years (1 core), 2.4e+25 years (2 cores)

DES key space (56 bits) is completely vulnerable to specialized GPU/ASIC hardware (e.g. EFF Deep Crack cracked DES in 56 hours in 1998). By contrast, AES-128 and AES-256 are mathematically intractable to brute-force.

**DES 64-bit block collision (Sweet32).** Birthday paradox collision risk exceeds negligible thresholds after ≈ 32 GiB under a single key. Because unique keys are provisioned per file (max 200 MB), collision probability remains ≈ 1.9e-05. AES with 128-bit blocks eliminates this risk.

## 6. Conclusions for Safe Report Architecture

- **AES-256-GCM is designated as primary** for all operational retrieval (owner downloads, profile views, officer reviews): highest throughput for evidence files (774 MB/s vs DES 19 and RC4 160), native AEAD integrity, 256-bit key space, and 128-bit block size.
- **DES-CBC-HMAC** prevents undetected tampering via HMAC, but its 56-bit effective key fails contemporary confidentiality standards. It also incurs the largest upload latency penalty.
- **RC4-HMAC** mitigates initial bias with drop-3072 and achieves integrity through HMAC, but remains obsolete and offers no speed advantage over hardware-accelerated AES-GCM.
- **Implications of multi-cipher storage:** Tripling storage footprint and summing encryption overhead across all three ciphers creates a system whose confidentiality is bounded by its **weakest link** (DES 56-bit). In production, only AES-256-GCM should be retained.
