# Instruksi testing DaVINCI Silicon

Panduan langkah demi langkah untuk mengetes DaVINCI di Mac lokal. Disusun dari level paling murah ke paling mahal: Level 1–5 gratis ($0, tanpa panggilan model), Level 6 memakai kredit Meta.

Dicek pada 2 Nov 2026 di `main` (hasilnya sesuai kolom "Hasil yang benar"): seluruh Level 1 dan 2; di Level 3 semua kecuali `make trace RUN=…`, `make gaps` dan `make layout-ref` (hasil yang ditulis untuk ketiganya berasal dari dokumentasi proyek); seluruh tabel Level 4; di Level 5 hanya pengalihan ke login, masuk dengan token, layar Evidence dan tombol Replay. Sisa checklist UI dan seluruh Level 6 belum dijalankan ulang untuk panduan ini. Angka seperti area dan timing tidak ditulis karena bisa berubah; cukup cek `status: ok`.

Jalankan semua perintah dari folder repo, dengan virtualenv aktif:

```bash
cd "/Users/adrianglazer/Future Tech Industries/Project DaVINCI/davinci-silicon"
```

```bash
export PATH=$PWD/.venv/bin:$PATH
```

## 0. Persiapan (sekali saja)

| Kebutuhan | Cara cek / pasang |
| --- | --- |
| Icarus Verilog | `iverilog -V` (pasang: `brew install icarus-verilog`) |
| Python venv + paket | `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` |
| Docker Desktop berjalan | `docker version` |
| Image sandbox | `make image` → `davinci-sim:latest` (wajib untuk RTL buatan model, replay, trace, coverage, area) |
| Image formal | `make formal-image` → `davinci-sim:formal` (untuk `make formal*`) |
| Image LibreLane + PDK SKY130 | hanya untuk `make sta*` / `make layout*`: `docker pull ghcr.io/librelane/librelane:3.0.17`, lalu `pip install ciel && ciel fetch --pdk sky130 8afc8346a57fe1ab7934ba5a6056ea8b43078e71` |
| Node.js | `node -v` (untuk UI di `web/`) |
| `.env.local` | hanya untuk Level 6: `META_API_KEY`, `PRICE_IN_META=1.25`, `PRICE_OUT_META=4.25` |

Setelah `tests/`, `verify/run_suite.py` atau `verify/mutants.json` berubah, image harus dibangun ulang (`make image`). Kalau tidak, run berhenti dengan pesan bahwa simulator menjalankan suite yang berbeda. Itu disengaja.

## Level 1 — Inti verifikasi ($0, ± 15 detik)

| Perintah | Hasil yang benar |
| --- | --- |
| `make sim RUN=t-sim` | `"passed": 10, "total": 10, "status": "pass"` (Icarus 13 di Mac) |
| `make sandbox RUN=t-sbx` | sama, 10/10, tetapi di dalam Docker (Icarus 12) |
| `make mutate` | `mutation score: 8/8`, setiap mutant `killed` |
| `make weak-demo` | suite lemah 6/8, `survivors ['M1', 'M8']`, lalu suite penuh membunuh keduanya (8/8) |

Catatan: `make mutate` dan `make weak-demo` menimpa `runs/mutation/` dan `runs/weak_demo/`, yang dibaca oleh API (`GET /mutation`). Untuk tes coba-coba tanpa menimpa, pakai:

```bash
python3 verify/mutate.py rtl/sync_fifo.v --out runs/t-mutation
```

## Level 2 — Loop AI tanpa biaya ($0, ± 10 detik)

Provider `fake` menjawab dengan RTL referensi; `replay` memutar ulang jawaban yang sudah direkam. Keduanya tidak memanggil model.

| Perintah | Hasil yang benar |
| --- | --- |
| `python -m agent.pipeline --run-id t-fake --provider fake` | `status=pass attempts=1 cost_usd=0.0` |
| `python -m agent.pipeline --run-id t-m1 --provider fake --seed-bug M1` | attempt 1 gagal 8/10, attempt 2 lulus 10/10, `attempts=2` |
| `python -m agent.pipeline --run-id t-replay --provider replay --replay-from live02-m1` | `status=pass attempts=2 cost_usd=0.0`; di `runs/t-replay/run.json`, `replay_check.reproduced: true` |
| `make plan RUN=t-m1` | menulis `runs/t-m1/verification_plan.{md,json,csv}` dan `testplan.hjson` |
| `python -m agent.extract spec/fixtures/sf16_datasheet.pdf --provider fake` | daftar `EX-01…` dengan label `AI interpretation · not verified` |

Yang perlu dicek di `runs/<id>/run.json`:

- Setiap attempt tercatat, termasuk yang gagal atau ditolak.
- Diagnosis model ada di `ai_interpretation` (berlabel), hasil simulator ada di `measured`. Keduanya tidak tercampur.
- `suite_sha256` sama dengan isi `verify/suite.sha256`.

## Level 3 — Pemeriksaan tambahan ($0, ± 30 detik; `make gaps` ± 40 detik)

| Perintah | Butuh | Hasil yang benar |
| --- | --- | --- |
| `make trace-ref` | — | `ok 10 tests` |
| `make trace RUN=live02-m1` | Docker | trace tiap attempt di `runs/live02-m1/attempt_<n>/trace/` |
| `make coverage-ref` | — | `"status": "ok"`, `"cycles": 3253`, tidak ada skenario bernilai 0 |
| `make area-ref` | — | `"status": "ok"` dengan jumlah `cells` dan `flops` |
| `make formal-ref` | image formal | `Bounded formal: 6 of 6 properties hold for 20 cycles` |
| `make gaps` | — | ringkasan di `runs/coverage_gap/gaps.json`; M1 dan M8 tercatat rapuh (hanya satu test directed yang membunuhnya) |
| `make block-sim BLOCK=sat_gain` | — | 8/8 pass |
| `make model-demo` | — | `bit-accurate model: disagrees on 0 of 1000` |
| `make sta-ref` | LibreLane + PDK | `"status": "ok"`, label pre-layout estimate |
| `make layout-ref` | LibreLane + PDK | job berat (± 70 detik); ringkasan di `runs/reference/layout/summary.json` |

## Level 4 — API ($0)

Jalankan API dengan token admin buatan sendiri (nilai bebas, hanya untuk tes lokal):

```bash
DAVINCI_API_TOKEN=tes-lokal-123 make api
```

Di terminal lain:

```bash
B=http://127.0.0.1:8000; T='Authorization: Bearer tes-lokal-123'; J='Content-Type: application/json'
```

| Cek | Perintah | Hasil yang benar |
| --- | --- | --- |
| Hidup | `curl -s $B/health` | `{"ok":true,...}` |
| Token admin | `curl -s $B/me -H "$T"` | `"owner":"admin"` |
| Run live tanpa token ditolak | `curl -s -o /dev/null -w '%{http_code}' -X POST $B/runs -H "$J" -d '{"provider":"meta"}'` | `401` (atau `403` jika API berjalan tanpa token sama sekali) |
| Field asing ditolak | `... -d '{"provider":"fake","sandbox":"local"}'` | `422` |
| Run fake | `curl -s -X POST $B/runs -H "$J" -d '{"provider":"fake","seed_bug":"M1"}'` | `run_id`; lalu `curl -s $B/runs/<run_id>` → `"status": "pass"`, 2 attempt |
| Progres langsung | `curl -sN $B/runs/<run_id>/events` | event `run_started` … `run_finished`, lalu `end` |
| Replay | `curl -s -X POST $B/runs/live02-m1/replay` | run baru; status `pass`, `replay_check.reproduced: true`, sandbox `docker` |
| Upload spec | `curl -s -X POST $B/extractions -F file=@spec/fixtures/sf16_datasheet.png -F provider=fake` | `extraction_id`; beberapa detik kemudian status `awaiting_approval` |
| Approve tanpa token ditolak | `curl -s -o /dev/null -w '%{http_code}' -X POST $B/extractions/<xid>/approve -H "$J" -d '{"approved_by":"Nama"}'` | `401` |
| Approve | sama, tambahkan `-H "$T"` | `200` |
| Run dari daftar yang disetujui | `curl -s -X POST $B/runs -H "$J" -d '{"provider":"fake","extraction_id":"<xid>"}'` | `pass` (sebelum approve: `409`) |
| Biaya | `curl -s $B/ledger` | `spent_usd`, `budget_usd` |
| Login salah | `curl -s -o /dev/null -w '%{http_code}' -X POST $B/auth/login -H "$J" -d '{"email":"x@example.com","password":"salahsalahsalah"}'` | `401` |

## Level 5 — UI ($0)

Jalankan API (Level 4), lalu di terminal lain:

```bash
cd web && NEXT_PUBLIC_DAVINCI_API=http://127.0.0.1:8000 npx next dev --port 3000
```

Buka http://localhost:3000.

**Masuk.** Halaman aplikasi (Evidence, Run Console, New run, Spec intake, Account) mengarahkan ke `/login/` kalau belum masuk. Panel Connection settings ada di dalam halaman yang terkunci itu, jadi untuk masuk pertama kali pilih salah satu:

- Akun: daftar di `/register/`, lalu beri akses live dengan `python -m api.users grant <email>`. Akun baru read-only. Belum ada perintah untuk menghapus akun, jadi pakai email tes yang memang boleh tertinggal di `runs/_api/`.
- Token admin (khusus tes lokal): di DevTools Console halaman localhost jalankan `sessionStorage.setItem("davinci.token", "tes-lokal-123")`, lalu buka `/evidence/`.

**Checklist layar:**

- [ ] `/evidence/` sebelum masuk → diarahkan ke `/login/?next=/evidence/`
- [ ] Evidence: headline "10 of 10 requirements verified · the tests catch 8 of 8 planted bugs", kartu "Can the tests be trusted?" (8/8 dan weak test 6/8), scenario coverage 11/11
- [ ] Tombol "Replay this run" → muncul "Replay live02-m1-replay-…: pass (measured), reproduced the recorded run"
- [ ] Run Console untuk live02-m1: ganti attempt #1 ↔ #2, test dan cycle tetap (`test_full_simultaneous_rw`, cycle 19)
- [ ] Waveform: garis biru = terukur, putus-putus ungu = golden model, merah = mismatch
- [ ] New run: dry run (fake) dengan seeded bug → progres langsung → terbuka di Console
- [ ] Spec intake: upload `spec/fixtures/sf16_datasheet.pdf` dengan provider fake → gambar halaman, daftar bisa diedit, approve dengan nama, lalu run dari daftar itu
- [ ] Teks AI selalu di kotak putus-putus berlabel "AI interpretation · not verified"; hasil terukur di kotak solid
- [ ] Status selalu memakai ✓ / ✕ / ○ plus kata, warna hijau/merah hanya untuk status
- [ ] Dark mode (System Settings → Appearance → Dark) di keempat layar: kotak AI dan warna status tetap terbaca
- [ ] Sign out → halaman aplikasi kembali terkunci

## Level 6 — Tes live (memakai kredit Meta)

Hanya untuk integrasi, benchmark dan demo. Cek saldo dulu: `curl -s $B/ledger` atau baris terakhir `runs/_ledger.jsonl`. Batas keras $120 (`DAVINCI_BUDGET_USD`).

| Tes | Perintah | Biaya terekam 31 Okt |
| --- | --- | --- |
| Run live | `python -m agent.pipeline --run-id live-tes1` | ± $0.03 |
| Bug ditanam + repair live | `python -m agent.pipeline --run-id live-tes2 --seed-bug M1` | ± $0.01 |
| Ekstraksi PDF live | `python -m agent.extract spec/fixtures/sf16_datasheet.pdf` | ± $0.07 |
| Approve (oleh manusia) | `python -m agent.extract --approve <xid> --by "Nama Anda"` | $0 |
| Run dari daftar yang disetujui | `python -m agent.pipeline --run-id live-tes3 --requirements runs/_extract/<xid>/approved.json --spec runs/_extract/<xid>/interface_spec.md` | ± $0.05 |

Run live dengan RTL buatan model otomatis memakai sandbox Docker. Setiap hasil dicatat apa adanya, termasuk attempt yang gagal, terpotong (`truncated`) atau ditolak. Jangan menjalankan ulang diam-diam supaya hasilnya terlihat bagus.

## Yang wajib benar di setiap tes

- `git status tests/` kosong: test beku tidak pernah berubah.
- `suite_sha256` di setiap `verdict.json` sama dengan `verify/suite.sha256`.
- Setiap attempt terlihat di `run.json` dan UI, termasuk yang gagal, ditolak atau dibatalkan.
- Teks model berlabel AI interpretation; hanya output simulator yang disebut measured.
- Tidak ada angka (area, timing, tingkat keberhasilan) yang tidak berasal dari run yang tersimpan.

## Masalah yang diketahui (ditemukan saat menyusun panduan ini, 2 Nov)

- Saat menonton run yang sedang berjalan, event SSE `end` kadang membawa `"status": null` walaupun run lulus. Status yang benar ada di `GET /runs/<id>` (dan muncul kalau stream dibuka ulang). Kemungkinan stream ditutup sebelum worker mencatat status. Belum diperbaiki.
- Connection settings hanya ada di halaman yang butuh login, jadi token tidak bisa dimasukkan sebelum masuk dengan akun (jalan pintas DevTools di atas).
- Replay run lama menunjukkan `request_matches: false` karena spec dan requirements berubah setelah run direkam (misalnya REQ-10). Replay tetap memakai jawaban yang direkam dan tetap memeriksa hasilnya.

## Bersih-bersih

Semua output tes masuk ke `runs/` (diabaikan git). Hapus run tes yang namanya diawali `t-` kalau mengganggu daftar run di UI. Jangan hapus `live*`, `runs/_ledger.jsonl` atau `runs/_api/`: itu catatan biaya dan bukti.
