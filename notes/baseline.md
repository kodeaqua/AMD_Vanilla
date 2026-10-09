# Baseline: set patch yang boot di hardware (macOS 26.6 / Darwin 25.6.0)

**BOOT-OK ≠ VERIFIED.** BOOT-OK hanya berarti sistem boot dengan set patch ini. Itu **bukan bukti tiap patch terpasang atau berfungsi**:
patch yang Base-nya tidak ketemu atau yang tidak berefek tidak akan membuat boot gagal. Bukti terpasang hanya dari log debug OpenCore.
VERIFIED = terverifikasi statis (lihat `laobamac-validation.md`). Dua penanda ini terpisah; `verify.py` menampilkan BOOT-OK sebagai kolom sendiri (dari `notes/boot-ok.json`).

- Sumber: `notes/live-kernel-patch.plist` (Kernel.Patch dari config.plist yang sedang berjalan, dilaporkan pengguna 2026-10-09). 27 patch, 15 berlaku & aktif di Darwin 25.6.0.
- Kernel: `xnu-12377.161.15.700.19` (`uname -v` saat ini sama dengan salinan di `kernels/`). Versi OpenCore: belum dicatat.
- Tidak ada perubahan pada `work/work.plist` di langkah ini.

## 1. Perbandingan semantik (kunci: Comment, MinKernel, MaxKernel; semua field dibandingkan)

### live vs laobamac/master (`a174cca`)
Daftar Comment/rentang/Find/Mask/Replace/ReplaceMask/Base/Count/Identifier identik untuk semua 27 patch, **kecuali**:

| Patch | live | laobamac |
|---|---|---|
| Core count (4 entri) | Replace byte core count = `06`, disesuaikan pengguna dengan Ryzen 5 4500 (`b8 06…`, `ba 06…`, `ba 06…90`, `ba 06 00 00 00`) | `00` = nilai bawaan/template "user-specified" (sama dengan upstream), bukan cacat |
| PAT `algrey | … | 10.13+` dan `Algrey / Zormeister | … | 15.0+` | Enabled=false | true (bawaan) |
| PAT `Shaneee | … | 10.13+` dan `Shaneee / Zormeister | … | 15.0+` | Enabled=true, **pilihan sengaja pengguna** | false (bawaan) |

Patch kext live = persis laobamac: `probeBusGated 12.0-15.x` (Darwin 21.0.0–24.99.99) dan `probeBusGated 26.0+` (25.0.0–25.99.99, `Find e0 11 73 40`, `Replace 00 00 02 00`), keduanya Enabled; `IOPCIIsHotplugPort` (AM5) Enabled=false.
Patch 10 (leaf7) dan 14 (Base `'_cpuid_set_info '` berspasi) ada dan aktif, tidak diubah.

### live vs work/work.plist
| Perbedaan | live | work.plist |
|---|---|---|
| probeBusGated | 2 entri laobamac (12.0-15.x, 26.0+), aktif | 1 entri upstream `12.0+` (21.0.0–25.99.99, `Find e0 11 72 00` → `00 00 03 00`), aktif |
| PAT (4 entri) | Shaneee aktif, algrey nonaktif | algrey aktif, Shaneee nonaktif |
| Jumlah patch | 27 | 26 (entri probeBusGated tunggal) |

Selain itu identik (termasuk core count `06`, patch 22/26.4+ monotonic-time, patch 10, 14).

## 2. `verify.py` pada patch aktif live terhadap kernel saat ini
`.venv/bin/python -I tools/verify.py --plist notes/live-kernel-patch.plist --enabled-only` (alat kini menerima array Patch polos dan `--enabled-only`):

N/A=9, VERIFIED=10, PLAUSIBLE=2, UNPROVEN=1, NO-BASE=1, NOT-KERNEL=1 (dari 24 patch aktif; 15 berlaku di Darwin 25.6.0).

| Status | Patch (Comment) |
|---|---|
| VERIFIED | `_commpage_populate`, `_cpuid_set_cache_info`, wrmsr 0x8B, rdmsr 0x8B→186, flag=1, GenuineIntel panic, `_i386_init` rdmsr, LAPIC version, monotonic 3 titik, monotonic 26.4+ |
| PLAUSIBLE | core count `13.3+` (`06`), PAT `Shaneee / Zormeister | 15.0+` |
| UNPROVEN | leaf7 15.0+ (patch 10) |
| NO-BASE | `_cpuid_set_cpufamily` 11.3+ (patch 14) |
| NOT-KERNEL | probeBusGated 26.0+ (kext, tidak bisa diperiksa tanpa binary IOPCIFamily) |

PAT Shaneee (`Shaneee / Zormeister`): lokasi sama dengan algrey (`mtrr_update_action` `0x…3fc9fc` dan `_pat_init+0x6a`); menulis PAT = `0x0606060606060606` (semua WB), berbeda dari source yang hanya mengubah PA6 (`mtrr.c:347-360`).
`probeBusGated 12.0-15.x` N/A di Darwin 25.

## 3. BOOT-OK
Dicatat di `notes/boot-ok.json` (kunci: hash isi patch, build kernel). Dipakai semua 15 patch aktif yang berlaku di Darwin 25.6.0 pada set live. Untuk `work.plist` hanya patch yang isinya identik yang ber-tag BOOT-OK;
yang **tidak**: PAT algrey (aktif di work), probeBusGated upstream `12.0+`.
Akibat BOOT-OK pada patch bermasalah: patch 14 (NO-BASE) dan patch 10 (kemungkinan inert) juga ber-tag BOOT-OK, namun itu tidak menunjukkan mereka terpasang. Sistem boot tidak berarti patch 14 diterapkan.

## 4. Usulan perubahan `work.plist` (BELUM DITERAPKAN, menunggu keputusan)

1. **probeBusGated**: ganti entri upstream tunggal dengan dua entri laobamac (disalin manual, bukan merge), sama dengan live. Alasan: live boot dengan itu; entri upstream `12.0+` memakai `e0 11 72 00 → 00 00 03 00` untuk seluruh Darwin 21–25, sedangkan laobamac memisahkan 26.0+ ke `e0 11 73 40 → 00 00 02 00`.
   Keterbatasan: **tidak bisa diverifikasi statis** (kext IOPCIFamily bukan kernel; tak ada salinannya di `kernels/`; aturan 2 hanya mengizinkan membaca `/System/Library/Kernels/kernel`). Status akan NOT-KERNEL + BOOT-OK, bukan VERIFIED. Bila Anda mau diverifikasi, salin binary kext (atau KC) ke folder repo dan beri tahu saya.
2. **PAT**: pengguna memilih **Shaneee** dengan sengaja (default algrey), dan set itu sudah boot (BOOT-OK). `work.plist` masih algrey dari keputusan awal; selisih ini hanya tertinggal, bukan ketidaksengajaan di live. Usulan: samakan `work.plist` dengan live (Shaneee aktif, algrey nonaktif) bila Anda setuju. Keduanya PLAUSIBLE secara statis.
3. **IOPCIIsHotplugPort (AM5)**: nonaktif di live dan work; tidak diubah.
4. **Patch 14**: tidak diubah; NO-BASE tetap sampai ada log debug OpenCore. **Patch 10**: tidak diubah.
5. Setelah keputusan 1–2, `verify.py --plist work/work.plist` seharusnya menunjukkan set yang sama dengan live (kecuali pilihan PAT).

## 5. Langkah yang membutuhkan Anda
- Log debug OpenCore (build DEBUG/`Target` log ke file) untuk: patch 14 (apakah dilewati), patch 10, dan kedua patch probeBusGated.
- Versi OpenCore yang dipakai (belum tercatat).
- Keputusan usulan 1 dan 2 (untuk 2: cukup konfirmasi bahwa `work.plist` boleh disamakan dengan live).
