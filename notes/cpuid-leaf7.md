# Patch 10 — "Disable check to allow leaf7" (algrey, 15.0+, Darwin 24–25)

**BELUM DITES HARDWARE.** Keputusan pengguna (2026-10-09): patch dibiarkan apa adanya (tetap aktif di `work/work.plist`), tidak dinonaktifkan,
tidak diubah. Status alat: `UNPROVEN`. Klasifikasi: SUSPICIOUS (target tidak sesuai Comment).

Build: `xnu-12377.161.15.700.19`. Source acuan: `xnu-12377.121.6`.

## Yang dilakukan patch sekarang
- `Find 00 05 0f 82` → `00 00 0f 82`, 2 kecocokan; dipakai yang pertama (`Count=1`): file `0x1d3d34`, `vaddr 0x…3d3d34`, `_cpuid_set_info+0x874`.
- Instruksi: `cmp dword ptr [rip+0xae3562],5 ; jb 0x…46cd` → imm 5 menjadi 0. Itu cek `cpuid_max_basic >= 5` (source `cpuid.c:723`, blok MONITOR/MWAIT),
  bukan leaf 7. Kecocokan ke-2 (`0x4943ed`, `_tcp_timers`) tidak dipakai.

## Padanan "leaf7" di Tahoe
- Gerbang leaf 7 di source: `cpuid.c:849` `if (info_p->cpuid_max_basic >= 7) { cpuid_fn(0x7, reg); … }`.
- Di binary: `0x…3d4540  mov eax,[rip+0xae2d52]` ; `0x…3d4546  cmp eax,7` ; `0x…3d4549  jb 0x…4623` ; `0x…3d454f  mov eax,7 … cpuid` (bentuk register, bukan memori-imm,
  maka Find lama tak akan cocok). Kompilasi menempatkan gerbang `>=5`, `>=6`, `>=7` sebagai cabang terpisah.
- Maksud asli (patch indeks 9, `00 3a 0f 82`, MaxKernel 23.99.99): imm `0x3a` = `CPUID_MODEL_IVYBRIDGE` (`cpuid.h:255`) — HIPOTESIS: gerbang model di kernel lama yang membuat leaf 7 terlewat
  di CPU non-Intel/model rendah. Hipotesis ini tidak bisa dibuktikan dari source 12377 (tidak ada gerbang model untuk leaf 7). `verify.py --all-versions --index 9` di kernel ini: **NO-MATCH**.
- Kesimpulan statis: di Darwin 25 satu-satunya gerbang leaf 7 adalah `max_basic >= 7`. Mesin ini `sysctl machdep.cpu.max_basic` = 16, jadi gerbang itu terlewati tanpa patch.
  Maksud asli patch 10 **tidak punya padanan** di Tahoe, dan patch yang ada kemungkinan inert di Ryzen 5 4500 (bukan bukti: kernel yang sedang berjalan mungkin sudah dipatch).
  `sysctl machdep.cpu.leaf7_features` terisi (`RDWRFSGS BMI1 AVX2 …`), konsisten dengan leaf 7 terbaca, tetapi tidak membuktikan patch 10 tidak diperlukan.

## Daftar riset (tugas 4)
- [ ] Uji hardware: boot dengan patch 10 aktif vs nonaktif, bandingkan `sysctl machdep.cpu.leaf7_features` dan `max_basic`.
- [ ] Cari tahu apakah ada gerbang lain yang memblokir leaf 7 di AMD pada Darwin 25 (mis. pemakai `cpuid_leaf7_features()` di commpage/`cpuid_set_cpufamily`).
- [ ] Bila tidak perlu: usulkan penonaktifan (keputusan pengguna).
