# Ringkasan patch kernel — macOS 26.6 (Darwin 25.6.0), Ryzen 5 4500

Dibuat 2026-10-09 dari `work/work.plist` (27 patch, **sama dengan set live yang boot**). Kernel: `xnu-12377.161.15.700.19`; source acuan `xnu-12377.121.6` (bukan build yang sama; binary yang benar).
Indeks = urutan di `work/work.plist`. 17 dari 27 patch berlaku di Darwin 25.6.0; 10 lainnya di luar rentang (N/A).

**Arti status**
- **VERIFIED** = terverifikasi statis (byte cocok, disassembly, baris source/string panic di binary), disetujui pengguna. Bukan tes hardware.
- **PLAUSIBLE** = lokasi cocok dengan source/binary, belum diputuskan VERIFIED.
- **BOOT-OK** = sistem boot dengan set patch ini. **Bukan** bukti tiap patch terpasang; itu hanya bisa dibuktikan lewat log debug OpenCore.
- Semua patch: tes per-patch di hardware (satu per satu, `-v debug=0x100 keepsyms=1`) **belum dilakukan**.

| # | Patch | Status | BOOT-OK | Catatan |
|---|---|---|---|---|
| 3 | cores_per_package 13.3+ | PLAUSIBLE | ya | `Replace` core count `06` (disesuaikan pengguna; bawaan `00`). Fungsi static tanpa simbol (`cpuid_set_cache_info`). `cpuid.c:395` |
| 4 | `_commpage_populate` rdmsr 0x1a0 | VERIFIED | ya | `commpage.c:393-395`; `and eax,1` memakai sisa eax |
| 5 | `cpuid_set_cache_info` leaf 4 → 0x8000001d | VERIFIED | ya | `cpuid.c:385` |
| 6 | wrmsr 0x8B | VERIFIED | ya | `cpuid.c:659` |
| 7 | rdmsr 0x8B → 186 | VERIFIED | ya | `cpuid.c:661-662` |
| 8 | flag=1 (rdmsr 0x17) | VERIFIED | ya | `cpuid.c:674` |
| 10 | "leaf7" 15.0+ | UNPROVEN (SUSPICIOUS) | ya | Mengenai cek `max_basic >= 5`, bukan leaf 7; kemungkinan inert (`max_basic` = 16). Maksud asli tak punya padanan di Tahoe. `notes/cpuid-leaf7.md` |
| 12 | Bypass GenuineIntel panic | VERIFIED | ya | `jne` → panic "Unsupported CPU" (`_cpuid_set_info+0x123e`) |
| 14 | `cpuid_set_cpufamily` Penryn 11.3+ | **NO-BASE** | ya | Base `'_cpuid_set_info '` berspasi → simbol tidak ketemu. Tidak diperbaiki sampai ada log OpenCore; bila terbukti dilewati, perbaiki di commit terpisah. BOOT-OK tidak membuktikan patch ini diterapkan |
| 15 | `_i386_init` 3× rdmsr | VERIFIED | ya | Efek samping: ikut menghapus setup argumen `kernel_debug_early` (di `_pstate_trace` dan dua titik `_i386_init`); perilakunya belum dianalisis |
| 16 | LAPIC version check | VERIFIED | ya | `lapic_native.c:421-423` |
| 18 | probeBusGated 26.0+ (kext) | NOT-KERNEL | ya | Disalin manual dari laobamac. Tak bisa diperiksa statis tanpa binary IOPCIFamily |
| 19 | IOPCIIsHotplugPort (AM5, kext) | NOT-KERNEL | – | Nonaktif |
| 20 | non-monotonic `last_dispatch` (3 titik) | VERIFIED | ya | `sched_prim.c:806-815` |
| 22 | non-monotonic 26.4+ (offset 0x490) | VERIFIED | ya | Dari laobamac. Rapuh: `Count=2`, kecocokan ke-3 di `0xfa45d`. `notes/non-monotonic-time.md` |
| 25 | PAT Algrey/Zormeister 15.0+ | PLAUSIBLE | – | Nonaktif (pilihan pengguna: Shaneee) |
| 26 | PAT Shaneee/Zormeister 15.0+ | PLAUSIBLE | ya | Aktif. Lokasi cocok `mtrr.c:347-360`; menulis PAT konstanta (semua WB), berbeda dari source (hanya PA6) |

Yang tidak berlaku di Darwin 25 (N/A): indeks 0–2, 9, 11, 13, 17, 21, 23, 24. Indeks 21 (non-monotonic ≤25.3.99) tidak bisa diuji; tak ada kernel 25.0–25.3.

## Perubahan dari upstream di `work.plist`
- Core count `00` → `06` pada 4 entri algrey (hanya `Replace`).
- Non-monotonic: entri upstream dipecah (≤25.3.99 dan 26.4+), disalin manual dari laobamac (upstream salah sasaran di 25.6).
- probeBusGated: dipecah (12.0-15.x dan 26.0+), disalin manual dari laobamac.
- PAT: Shaneee aktif, algrey nonaktif (pilihan pengguna).
- Patch 10 dan 14 tidak diubah.

## Belum selesai / butuh Anda
1. Log debug OpenCore (+ versi OpenCore): bukti patch 14 dan 10 benar-benar terpasang (probeBusGated ditunda).
2. ~~Binary IOPCIFamily untuk `probeBusGated`~~ — DITUNDA atas permintaan pengguna (2026-10-09); tetap NOT-KERNEL + BOOT-OK, tidak dikerjakan sekarang.
3. Tes hardware per patch dan catat (normal/hang/panic) di `notes/`.
4. Riset patch 10: source tidak punya gerbang leaf 7 lain selain `max_basic >= 7` (lihat `cpuid-leaf7.md`); tinggal uji boot on/off + log OpenCore. Usulan: nonaktifkan bila terbukti tidak perlu (keputusan pengguna).
5. ~~Patch 15: analisis `_kernel_debug_early`~~ — selesai: paling banyak 256 entri trace awal sampah, tidak ada risiko crash terlihat (`amd-candidates.md`).
6. `ocvalidate` pada config yang memuat patch (langkah 5 alur kerja) belum dijalankan; butuh paket OpenCore.
7. Cek ulang tag source XNU baru (`git ls-remote … rel/xnu-12377`) dan ulang `verify.py` bila build kernel berubah.

Rincian: `laobamac-validation.md`, `baseline.md`, `evidence.json`, `boot-ok.json`.
