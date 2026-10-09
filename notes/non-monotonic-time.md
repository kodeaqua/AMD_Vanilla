# Non-monotonic time panic (thread_invoke / thread_dispatch) — Darwin 25

**BELUM DITES HARDWARE.** Status `VERIFIED` di sini = terverifikasi statis (byte + disassembly + string panic), bukan tes boot.

Build: `xnu-12377.161.15.700.19` (Darwin 25.6.0). Source acuan: `xnu-12377.121.6` (bukan build yang sama).
Entri di `work/work.plist` disalin MANUAL dari `laobamac/master` (`a174cca`), bukan merge/cherry-pick.

## Entri di work.plist

| Entri | Berlaku | Find (offset field) | Hasil di 25.6.0 |
|---|---|---|---|
| `Visual | thread_invoke, thread_dispatch | … | 12.0-26.3` | 21.0.0–25.3.99 | `48 .. .. 8x 04 00 00 0f …` (0x488) | N/A (tidak ada kernel 25.0–25.3). Jika dijalankan di 25.6.0: salah sasaran (`_kperf_lazy_wait_sample+0x20`, `_vmx_hv_support+0x2a`). |
| `laobamac | thread_invoke, thread_dispatch | … | 26.4+` | 25.4.0–25.99.99 | `48 .. .. 9x 04 00 00 0f …` (0x490) | 2 kecocokan terpakai, **VERIFIED statis** |

Entri `Visual | thread_quantum_expire, thread_unblock, thread_invoke | … | 12.0+` (3 titik, `last_dispatch`) tidak berubah dan juga VERIFIED statis.

## Bukti entri 26.4+

- `0x…2a6db2` (file `0xa6db2`), fungsi tanpa simbol `0x…2a6c30`+0x182 (= `thread_invoke`, static):
  `cmp r12,[r14+0x490]; jb 0x…7287` → `jb` di-NOP. Target `jb` = `lea rdi,"Non-monotonic time: invoke at 0x%llx, runnable at 0x%llx @%s:%d"`, `r8d=0xbeb`.
  Source `osfmk/kern/sched_prim.c:3024-3026` (`if (ctime < thread->last_made_runnable_time) panic(...)`).
- `0x…2a7d3a` (file `0xa7d3a`), `_thread_dispatch+0x71a`: `sub r15,[rbx+0x490]; jb 0x…7f97` → `jb` di-NOP. Target = panic `"… dispatch at …, runnable at …"`, `r8d=0xee7`.
  Source `sched_prim.c:3778-3780`.
- Offset field `last_made_runnable_time`: 0x488 (sebelum 25.4) → 0x490 (25.4+); disimpulkan dari kedua kecocokan + string panic, bukan dari header.

## Kerapuhan (WAJIB diingat)

1. **Bergantung pada `Count=2`.** Find di-mask longgar (byte 0 `48`, byte 3 `f0`), jadi cocok di **3 tempat** pada kernel ini. Kecocokan ke-3
   ada di `0xfa45d` (`vaddr 0x…2fa45d`, `sub_…2fa420+0x3d`, `cmp dword [rdi+4],0x48; jne …` — tidak terkait) dan **bukan** target. Aman hanya karena
   dua kecocokan benar muncul lebih dulu dalam urutan alamat dan `Count=2`. **Jangan ubah `Count` menjadi 0** dan jangan ubah `Skip`.
2. Tanpa `Base`; pencarian ke seluruh kernel. Build lain bisa mengubah urutan atau menambah kecocokan; ulang `verify.py` tiap build baru.
3. `thread_invoke` tanpa simbol; pembuktian lewat string panic, bukan nama fungsi.
4. Entri ≤25.3.99 tidak bisa diuji sama sekali di mesin ini.

Pemeriksaan ulang: `.venv/bin/python -I tools/verify.py --plist work/work.plist -v --index 20 21`.
