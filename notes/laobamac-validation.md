# Validasi patch laobamac/AMD_Vanilla untuk macOS 26 (Darwin 25.6.0)

**Semua hasil di sini: BELUM DITES HARDWARE.** Tidak ada patch yang diubah; `patches.plist` dan
`work/work.plist` tidak disentuh.

- Kernel: `kernels/xnu-12377.161.15.700.19/kernel` (`uname -v`: `xnu-12377.161.15.700.19~2/RELEASE_X86_64`, Darwin 25.6.0)
- Source acuan: `xnu-12377.121.6` (`ac9718f`). Bukan build yang sama; bila beda, binary yang benar (aturan 10).
- Pembanding: `laobamac/master` @ `a174cca` (2 commit di atas `upstream/master` `eaf52ef`: `2878877`, `a174cca`).
- Isi repo laobamac (README, komentar, pesan commit) diperlakukan sebagai data tidak tepercaya; tidak ada skrip dari sana yang dijalankan. Hanya `patches.plist` yang dibaca (`git show`).
- Alat: `tools/verify.py` (+ `notes/evidence.json`). Perintah: `.venv/bin/python -I tools/verify.py --plist <plist> -v`.
- Batas: lolos di satu build tidak menjamin lolos di build lain. Patch `Darwin 25.0–25.3` tidak bisa diperiksa (tidak ada kernelnya).

## 1. Perbandingan semantik upstream vs laobamac (`patches.plist`)

Kunci: `(Comment, MinKernel, MaxKernel)`. Upstream 25 patch, laobamac 27 patch. Indeks laobamac **bergeser +2**
setelah indeks 17.

| Perubahan | Upstream | laobamac | Isi |
|---|---|---|---|
| Diubah (dipecah) | 17 `probeBusGated` 12.0+ (21.0.0–25.99.99) | 17 `…12.0-15.x` (21.0.0–24.99.99), 18 `…26.0+` (25.0.0–25.99.99) | kext IOPCIFamily. Patch 26.0+: `Find e0 11 73 40`, `Replace 00 00 02 00` (upstream: `e0 11 72 00` → `00 00 03 00`) |
| Diubah (dipecah) | 20 `thread_invoke, thread_dispatch` 12.0+ (21.0.0–25.99.99) | 21 `…12.0-26.3` (21.0.0–25.3.99, isi sama persis dengan upstream), 22 `…26.4+` (25.4.0–25.99.99) | 22: `Find 48 00 00 90 04 00 00 0f 00 00 00 00 00` — offset field **0x490** (bukan 0x488) |
| Dihapus / ditambah lain | – | – | Tidak ada. Semua patch lain identik (Find/Mask/Replace/ReplaceMask/Base/Count/rentang kernel). |

Patch **10 (leaf7)** dan **14 (Base berspasi)** TIDAK diubah laobamac.

Cakupan Darwin 25: patch 21 (≤25.3.99) dan 22 (≥25.4.0) berurutan tanpa celah dan tanpa tumpang tindih; 17 (≤24.99.99) dan 18
(≥25.0.0) juga. `verify.py` tidak menemukan dua patch aktif yang menimpa byte yang sama.

## 2. Klasifikasi patch yang berlaku di Darwin 25.6.0 (indeks laobamac)

Status alat: `OK` = lokasi terbukti lewat Base; `PLAUSIBLE` = fungsi tanpa simbol tetapi lokasi cocok dengan baris source/
bukti binary di `evidence.json`; `UNPROVEN`; `NO-BASE`; `NOT-KERNEL`. **Tidak ada yang saya promosikan ke OK/VERIFIED:
kolom "usulan" hanya saran, keputusan di Anda.**

| # | Patch | Status alat | Usulan klasifikasi | Catatan singkat |
|---|---|---|---|---|
| 3 | cores_per_package 13.3+ | PLAUSIBLE | **SUSPICIOUS** | Lokasi benar, tetapi `Replace` = `ba 00 00 00 00` (core count **0**, bukan 06). Lihat §5. |
| 4 | `_commpage_populate` rdmsr | PLAUSIBLE | VERIFIED | commpage.c:393-395. Efek samping: `and eax,1` memakai sisa `eax` (leaf7 ebx bit0). |
| 5 | `cpuid_set_cache_info` leaf 4 → 0x8000001d | PLAUSIBLE | VERIFIED | cpuid.c:385 |
| 6 | wrmsr 0x8B | PLAUSIBLE | VERIFIED | cpuid.c:659 |
| 7 | rdmsr 0x8B → 186 | PLAUSIBLE | VERIFIED | cpuid.c:661-662 |
| 8 | flag=1 (rdmsr 0x17) | PLAUSIBLE | VERIFIED | cpuid.c:674 |
| 10 | "leaf7" 15.0+ | UNPROVEN | **SUSPICIOUS** | Menembak cek `max_basic >= 5` (leaf 5), bukan leaf 7. Lihat §4. |
| 12 | Bypass GenuineIntel panic | OK | VERIFIED | `jne` → panic `"Unsupported CPU @cpuid.c:0x49f"` (string terbaca dari binary) |
| 14 | Penryn 11.3+ | NO-BASE | **FAIL** | Base `'_cpuid_set_info '` (spasi di akhir). Lihat §4. |
| 15 | `_i386_init` 3× rdmsr | PLAUSIBLE | VERIFIED (dengan catatan) | 3 kecocokan: `_pstate_trace+0x4`, `_i386_init+0x7b`, `_i386_init+0x549`. Source publik `pstate_trace()` kosong; binary berbeda dari source. |
| 16 | LAPIC version check | PLAUSIBLE | VERIFIED | lapic_native.c:421-423 |
| 17, 18 | probeBusGated (kext) | NOT-KERNEL | belum bisa dinilai | Butuh binary IOPCIFamily. Beda dari upstream: lihat §1. |
| 19 | IOPCIIsHotplugPort (nonaktif, kext) | NOT-KERNEL | belum bisa dinilai | Nonaktif, hanya AM5. |
| 20 | non-monotonic (3 titik) | PLAUSIBLE | VERIFIED | sched_prim.c:806-815; ketiga `ja` menuju panic `last_dispatch`. |
| 21 | non-monotonic ≤25.3.99 | N/A | – | Tidak ada kernel 25.0–25.3 untuk diuji. Isi sama dengan upstream 20. |
| 22 | non-monotonic 26.4+ (**baru**) | PLAUSIBLE | VERIFIED | Lihat §4. |
| 25 | PAT Algrey/Zormeister 15.0+ (aktif) | PLAUSIBLE | **MATCH-ONLY** | Lokasi cocok dengan source, nilai PAT berbeda dari source. Lihat §6. |
| 26 | PAT Shaneee/Zormeister 15.0+ (nonaktif) | PLAUSIBLE | MATCH-ONLY | idem |

Indeks laobamac 0–2, 9, 11, 13, 23, 24 = N/A (di luar rentang Darwin 25).

## 3. Bukti tiap patch

Alamat: file offset / vaddr. Disassembly lengkap sebelum/sesudah: jalankan `verify.py -v --index N`.

- **3** `0x1d54a5` / `0xffffff80003d54a5`, fungsi tanpa simbol mulai `0x…3d5110` (+0x395).
  `shr edx,0x1a; inc edx` → `mov edx,imm32`. Source `cpuid.c:395-396`: `cpuid_cores_per_package = bitfield32(reg[eax],31,26)+1`.
  Fungsi yang sama memuat patch 5 (`0x…3d5453`, loop `cpuid(4)`), jadi ini `cpuid_set_cache_info` (static, tanpa simbol).
  Base `_cpuid_set_info` hanya titik awal; 17 kecocokan setelahnya, yang pertama adalah ini.
- **4** `0x1f0dbc` / `0x…3f0dbc`, `mov ecx,0x1a0; rdmsr` → NOP, didahului `test eax,0x200` (ERMS). commpage.c:393-395
  `if (ERMS) misc_enable = rdmsr64(MSR_IA32_MISC_ENABLE)`.
- **5** `0x1d5453`: `mov eax,4` → `mov eax,0x8000001d`. cpuid.c:385 `reg[eax] = 4`.
- **6** `0x1d3935` (`_cpuid_set_info+0x475`, hasil inline `cpuid_set_generic_info`): `mov ecx,0x8b; xor eax,eax; xor edx,edx; wrmsr` → NOP. cpuid.c:659.
- **7** `0x1d397d`: `mov ecx,0x8b; rdmsr` → `mov edx,0xba; nop`. cpuid.c:661-662 `rdmsr64(0x8b)>>32`.
- **8** `0x1d39f5`: `mov ecx,0x17; rdmsr; shr edx,0x12; and dl,7` → `mov dl,1; nop…`. cpuid.c:674 (`>>50 & 7`).
- **12** `0x1d46fe` (`_cpuid_set_info+0x123e`): `jne 0x…4a08` → 6×NOP; target = `lea rdi,"Unsupported CPU @%s:%d"`, `"cpuid.c"`, `edx=0x49f`, `call panic`.
- **15** `0x1df2d4`, `0x8c77fb`, `0x8c7cc9` (vaddr `0x…3df2d4`, `0x…ac77fb`, `0x…ac7cc9`): `rdmsr 0x199`, `rdmsr 0x198` (`proc_reg.h:623-624` PERF_CTL/STS) lalu `mov edi,0x5310258` (kdebug) → NOP 42 byte.
- **16** `0x1f519a` (`_lapic_init+0x20a`): `and eax,0xfc; cmp eax,0x13; jbe 0x…5235` → `cmp` jadi NOP 3 byte. `jbe` menuju
  jalur panic `Local APIC version` (lapic_native.c:421-423). Setelah patch `jbe` hanya jalan bila `(ver & 0xfc) == 0`.
- **20** `0x9b016` (`_thread_quantum_expire+0xb6`), `0xa336a` (`_thread_unblock+0xba`), `0xa6d5c` (fungsi tanpa simbol `0x…2a6c30` = `thread_invoke`, +0x12c):
  `cmp rsi,r15; ja` → `ja` jadi NOP; ketiga target `ja` = panic `"Non-monotonic time: last_dispatch at 0x%llx, ctime 0x%llx"`.
- **22** lihat §4.
- **25/26** lihat §6.

## 4. Tiga hal yang diminta

### Patch 10 (leaf7) — laobamac TIDAK memperbaiki; mencurigakan
- Find `00 05 0f 82` ketemu 2× (satunya di `_tcp_timers`, tidak terpakai). Yang terpakai: `0x1d3d34` (`_cpuid_set_info+0x874`):
  `cmp dword ptr [rip+…],5; jb 0x…46cd` → `cmp …,0`.
- Itu cek `cpuid_max_basic >= 5` (source `cpuid.c:723`, blok MONITOR/MWAIT), **bukan** `>= 7` (`cpuid.c:849`). Di binary ada juga cek `cmp …,6; jb` di `0x…3d3e7f`
  yang menuju target yang sama. Comment ("allow leaf7") tidak sesuai target.
- Di mesin ini `sysctl machdep.cpu.max_basic` = 16, jadi `max_basic < 5` tidak pernah terjadi dan lompatan `jb` itu tidak pernah diambil: patch kemungkinan **tidak berefek** di Ryzen 5 4500.
  Itu kesimpulan dari logika, belum dites (nilai sysctl bisa berasal dari kernel yang sudah dipatch). Patch lama (indeks 9) memakai `00 3a`, jadi pola tampaknya tidak diperbarui untuk layout kompilasi Darwin 24+.

### Patch 14 (Base berspasi) — laobamac TIDAK memperbaiki
- Base di kedua plist: `'_cpuid_set_info '` (spasi di akhir). Simbol `_cpuid_set_info` ada (`0xffffff80003d34c0`), tetapi dengan spasi tidak.
- Status tetap **NO-BASE** sampai dibuktikan lewat log debug OpenCore saat tes hardware (permintaan Anda: pertanyaan `Configuration.pdf` ditunda).
- Percobaan di luar repo (plist sementara, Base tanpa spasi; tidak disimpan): 1 kecocokan di `_cpuid_set_info+0x1248` (`0x1d4708`):
  `cmp byte [family],6; jne` → `mov edx,0x78ea4fbc; xor ebx,ebx; jmp` (0x78ea4fbc = `CPUFAMILY_INTEL_PENRYN`). Jadi kalau Base diperbaiki, patch ini cocok dan masuk akal.

### Patch 20 (non-monotonic) — laobamac MEMPERBAIKI (indeks 22)
- Upstream 20 (`Find 48 .. .. 8x 04 00 00 0f …`, offset 0x488) di Tahoe 25.6 **salah sasaran**: kecocokan terpakai di `_kperf_lazy_wait_sample+0x20`
  (`sub r14,[rdi+0x488]; jb`) dan `_vmx_hv_support+0x2a` (`jns; mov ecx,0x48b; rdmsr; test dl,2` — cek kapabilitas VMX ikut di-NOP).
- laobamac 22 memakai offset `0x490` (field `last_made_runnable_time` bergeser di Darwin 25.4+). Dua kecocokan yang terpakai:
  - `0xa6db2` (fungsi tanpa simbol `0x…2a6c30`+0x182 = `thread_invoke`): `cmp r12,[r14+0x490]; jb 0x…7287`; target = panic `"Non-monotonic time: invoke at 0x%llx, runnable at 0x%llx"` (`sched_prim.c`, line 0xbeb).
    Source `sched_prim.c:3024-3026`.
  - `0xa7d3a` (`_thread_dispatch+0x71a`): `sub r15,[rbx+0x490]; jb 0x…7f97`; target = panic `"… dispatch at …, runnable at …"` (line 0xee7). Source `sched_prim.c:3778-3780`.
- **Kerapuhan**: ada kecocokan ke-3 (`0xfa45d`, `sub_…2fa420+0x3d`, tidak terkait). Aman hanya karena `Count=2` dan ia terletak setelah dua yang benar. Jangan ubah `Count` jadi 0.
- Patch 19 (`last_dispatch`, 3 titik) tetap tepat dan tidak bergeser.

## 5. Empat patch `cpuid_cores_per_package`

Semua keempat patch di laobamac identik dengan upstream (nilai `Replace` core count = **0**, template "user-specified"):

| # | Berlaku | Replace | Seharusnya (Ryzen 5 4500) |
|---|---|---|---|
| 0 | 17.0.0–18.99.99 | `b8 **00** 00 00 00 00` | `06` |
| 1 | 19.0.0–20.99.99 | `ba **00** 00 00 00 00` | `06` |
| 2 | 21.0.0–22.3.99 | `ba **00** 00 00 00 90` | `06` |
| 3 | 22.4.0–25.99.99 (**berlaku di Darwin 25**) | `ba **00** 00 00 00` | `06` |

Jadi **belum 06** di laobamac maupun upstream. Dipakai apa adanya, `cpuid_cores_per_package = 0` lalu di-reset ke 1 oleh
`cpuid.c:489-490`. Perubahan nilai (tugas 5, hanya `Replace`, bukan `Find`/`Mask`) belum dilakukan.

## 6. PAT (patch 25/26): lokasi benar, nilai berbeda dari source

- Dua titik: `0x1fc9fc` (`sub_…3fc830+0x1cc` = `mtrr_update_action`, cabang `cmp rdi,1`) dan `0x1fd05a` (`_pat_init+0x6a`). Keduanya
  `rdmsr 0x277; … and edx,0xff00ffff; or edx,0x10000; wrmsr`, cocok dengan `mtrr.c:347-360` (`pat &= ~(0xFF<<48); pat |= 1<<48` ⇒ PA6=WC).
- Patch menulis **seluruh** PAT sebagai konstanta: Algrey/Zormeister `0x0007010600070106` (PA0 WB, PA1 WC, PA2 UC-, PA3 UC, diulang), Shaneee `0x0606060606060606`
  (semua WB). Dua-duanya berbeda dari source (yang hanya mengubah PA6). Alasan perbedaan itu di AMD belum terbukti dari source/binary saya.
- Pemilihan algrey vs Shaneee adalah keputusan Anda (aturan 9); tidak diubah.

## 7. Daftar yang butuh keputusan Anda

1. Promosi PLAUSIBLE → OK/VERIFIED: usulan ada di tabel §2 (patch 4–8, 12, 15, 16, 20, 22).
2. Patch 14: perbaiki Base (spasi) di `work/work.plist`, atau tunggu log debug OpenCore dulu?
3. Patch 10: nonaktifkan, biarkan, atau cari cek `>= 7` yang sebenarnya di Darwin 25? (kemungkinan inert di Ryzen 4500)
4. Pakai patch 22 laobamac untuk menggantikan upstream 20 (yang salah sasaran di 25.6)? Pengambilan dari laobamac perlu persetujuan Anda (aturan git).
5. Core count 06 (tugas 5) pada entri 22.4.0–25.99.99.
6. PAT: algrey vs Shaneee.
7. Patch kext IOPCIFamily (17/18): perlu binary kext untuk diverifikasi; Ryzen 4500 kemungkinan tidak membutuhkannya (Anda yang memutuskan).
8. Hanya satu kernel (25.6.0) yang diuji; patch 21 untuk 25.0–25.3 tidak bisa dibuktikan.

## 8. Keputusan pengguna (2026-10-09) dan status `work/work.plist`

**VERIFIED = terverifikasi STATIS (byte cocok, disassembly, source/string binary). Bukan tes hardware; semua tetap BELUM DITES HARDWARE.**

1. **VERIFIED** (indeks laobamac 4–8, 12, 15, 16, 20, 22): disetujui pengguna dan dicatat sebagai `decision` di `notes/evidence.json`. Sisanya tetap PLAUSIBLE (3, PAT) / UNPROVEN (10) / NO-BASE (14).
   - **Efek samping patch 15** (`_i386_init`, 3 kecocokan): Find 42 byte tidak hanya menghapus dua `rdmsr` (0x199/0x198) tetapi juga `mov edi,0x5310258; xor ecx,ecx; xor r8d,r8d`.
     Setelah NOP, kode lanjut ke `pop rbp; jmp _kernel_debug_early` (di `_pstate_trace`) atau ke kelanjutan di `_i386_init` dengan `edi/rsi/rdx/rcx/r8` berisi sisa register, jadi event kdebug awal
     bisa tercatat dengan debugid/argumen sampah. Perilaku `_kernel_debug_early` dengan argumen itu **belum dianalisis**. Kecocokan di `_pstate_trace` (`0x…3df2d4`) tidak punya pemanggil `call/jmp rel32` langsung
     di `__TEXT,__text` (pemanggil tak langsung/kext tidak dikesampingkan); dua lainnya di `_i386_init`. Source publik `pstate_trace()` kosong, binary berbeda (aturan 10).
2. **Patch 14**: TIDAK diperbaiki; tetap `NO-BASE` (Base `'_cpuid_set_info '`) sampai ada log debug OpenCore. Kalau terbukti dilewati, perbaiki di commit terpisah.
3. **Patch 10**: dibiarkan apa adanya (aktif). Maksud asli (leaf7) tidak punya padanan di Tahoe; masuk daftar riset tugas 4. Lihat `notes/cpuid-leaf7.md`.
4. **Patch 22 laobamac**: disalin manual ke `work/work.plist` (upstream 20 → dua entri ≤25.3.99 dan 26.4+), commit `fix(monotonic-time)`. Kerapuhan (`Count=2`, kecocokan ke-3 di `0xfa45d`): `notes/non-monotonic-time.md`.
5. **Core count**: `Replace` byte core count = `06` pada keempat entri algrey di `work/work.plist` (hanya `Replace`). Entri Darwin 25 (`13.3+`): `ba 06 00 00 00` → `mov edx,6` di `0x…3d54a5`. Status PLAUSIBLE (belum diputuskan VERIFIED).
6. **PAT**: algrey (`Algrey / Zormeister`, aktif) tetap default; Shaneee tetap nonaktif. Tidak ada perubahan.

Hasil `verify.py --plist work/work.plist` pada `xnu-12377.161.15.700.19`: N/A=9, VERIFIED=10, PLAUSIBLE=3 (core count, PAT ×2), UNPROVEN=1 (patch 10), NO-BASE=1 (patch 14), NOT-KERNEL=2 (kext).
