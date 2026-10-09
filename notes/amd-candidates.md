# Pencarian kandidat patch AMD lain di kernel Tahoe

**BELUM DITES HARDWARE. Tidak ada patch yang ditambah/diubah; ini hanya laporan analisis statis.**
Kernel `xnu-12377.161.15.700.19` (Darwin 25.6.0); source acuan `xnu-12377.121.6` (bukan build yang sama). Klasifikasi kompatibilitas MSR terhadap AMD
berasal dari pengetahuan umum (AMD APM / Intel SDM), BUKAN dari binary; ditandai "hipotesis".

## Metode
Pindai seluruh `__TEXT,__text` per fungsi (LC_FUNCTION_STARTS, capstone): setiap `rdmsr`/`wrmsr` + nilai `ecx` (mov imm) sebelumnya + fungsi pemilik.
Hasil: **348 situs** `rdmsr/wrmsr` (data mentah tidak disimpan; ulang dengan skrip pindai bila perlu). Ditambah: referensi string `GenuineIntel`, dan pemanggil (rel32 call/jmp) fungsi terpilih.

## Temuan terverifikasi statis
1. **Hanya satu referensi `GenuineIntel`** (`_cpuid_set_info` `0x…3d46e9`) — sudah ditangani patch 12.
2. **Patch 14 tampaknya WAJIB agar tidak panic** (rantai, dari source `cpuid.c:958-964` + binary):
   `panic("Unsupported CPU")` terjadi bila vendor ≠ Intel **atau** `cpuid_set_cpufamily() == CPUFAMILY_UNKNOWN`. Patch 12 melewati cek vendor. Untuk family ≠ 6 (AMD family 0x17),
   `cmp byte [family],6; jne 0x…477f` menuju cabang default yang menyimpan `cpufamily = 0` lalu `test bl,bl; jne 0x…4a08` = panic "Unsupported CPU".
   Patch 14 (jika terpasang) mengganti dua instruksi itu menjadi `mov edx,0x78ea4fbc (PENRYN); xor ebx,ebx; jmp 0x…477f`.
   **Konsekuensi**: sistem Anda boot (BOOT-OK), jadi salah satu benar: (a) patch 14 sebenarnya terpasang walau `verify.py` menandai NO-BASE (mis. OpenCore menormalisasi spasi pada Base), atau
   (b) `ProvideCurrentCpuInfo` / mekanisme lain menetapkan cpufamily. Ini **inferensi, bukan bukti**; log debug OpenCore tetap satu-satunya penentu. Jangan perbaiki Base dulu.
3. **Penryn dipaksa memang diperlukan** karena `_cpuid_set_info` memilih sumber core count berdasarkan cpufamily: family Penryn (`0x78ea4fbc`) memanggil fungsi `cpuid_set_cache_info`
   (`0x…3d5110`, tempat patch 3/5), sedangkan family lain (kecuali Westmere `0x573b5eec`) menjalankan `rdmsr 0x35` (MSR_CORE_THREAD_COUNT, Intel-only, `0x…3d4903`).
   Ada boot-arg `-nomsr35h` yang melewati `rdmsr 0x35` (string di `0x…3d48bd`; cabang bergantung flag `rax`, belum dianalisis; source `cpuid.c:993` menyebut VMM yang tak mengemulasi MSR 0x35).
4. `_tsc_init` (dipanggil `_i386_init`) bercabang menurut cpufamily; cabang Penryn (`0x…3f04d9`) memakai `rdmsr 0x198` + string `"FSBFrequency"`; cabang lain `rdmsr 0x194/0xce`.
   Pada AMD MSR itu tidak ada. Kemungkinan besar ditangani quirk `ProvideCurrentCpuInfo` (patch internal OpenCore, tidak terlihat di plist ini); **tidak bisa dibuktikan dari kernel mentah**.

## Situs MSR yang bukan patch kita (hipotesis kompatibilitas AMD; gating BELUM diperiksa kecuali dicatat)
| Kelompok | MSR / fungsi | Dugaan |
|---|---|---|
| Sudah ditangani | 0x8b, 0x17, 0x1a0, 0x198/0x199 (`_i386_init`,`_pstate_trace`), 0x277 PAT, `_lapic_init` version | patch 4–8, 15, 16, PAT |
| Ada di AMD | MTRR 0x250–0x26f/0x2ff/0xfe, EFER/STAR/LSTAR 0xc000008x, FS/GS base 0xc000010x, SYSENTER 0x174–176, x2APIC 0x1b/0x802/0x830/0x832, MCA 0x179/0x17b/0x400–0x404, DEBUGCTL 0x1d9 | kompatibel (hipotesis) |
| Fitur tak ada di AMD, kemungkinan di-gate cpuid | VMX 0x3a/0x480–0x48e (`_vmx_cpu_init` dari `_cpu_start`, `_cpu_machine_init`); XCPM 0x1aa/0x770/0x774/0x620/0x1fc/0xe2 (`_xcpm_init` dari `_i386_init`, `_acpi_sleep_kernel`); TSC-deadline 0x6e0; ARCH_CAPABILITIES 0x10a/0x10f/0x122/0x123 (`_cpuid_wa_required`: dijaga `test … 0x20000000` = bit leaf7 edx 29, terlihat di binary) | gating VMX/XCPM/0x6e0 belum diperiksa; 0x10a terjaga fitur |
| Hanya saat dipakai (bukan jalur boot) | perf counter `_cpc_*/_kpc_*` 0x186–0x189, 0x38d–0x390, 0xc1–0xc4; LBR 0x1c8/0x1c9/0x345; `_ucode_interface` wrmsr 0x79 (AMD memakai 0xC0010020); `_kdp_machine_msr64_*` | berpotensi #GP bila kperf/Instruments/ucupdate dipakai; prioritas rendah |

Catatan: `_vmx_hv_support` dan `_kperf_lazy_wait_sample` pernah tersentuh patch upstream 20 yang salah sasaran; patch 22 sudah menghindarinya.

## Pemeriksaan gating (lanjutan, terverifikasi di binary kecuali dicatat)
- **VMX** (`_vmx_cpu_init` `0x…3ff460`, dipanggil `_cpu_start`/`_cpu_machine_init`): setelah `call cpuid_features` ada `bt rax,0x25; jae` (bit 37 = CPUID.1:ECX bit 5 VMX) sebelum `rdmsr 0x3a`, dan `test rax,0x2000000000` (bit yang sama) sebelum MSR 0x480+.
  `sysctl machdep.cpu.features` di mesin ini **tidak memuat VMX** ⇒ jalur `rdmsr 0x3a/0x480…` dilewati. Terjaga.
- **XCPM** (`_xcpm_init` `0x…40b320`): diawali `cmp dword [flag 0x…e4fa80],0; je return`. Flag itu ditulis `_xcpm_bootstrap` (`0x…40a830`, dipanggil `_i386_init`): `=0` di `0x…40aa10`, `=1` di `0x…40abf9`.
  Alur (terverifikasi di binary): `cpuid_features(); test rax,rax; js 0x…aa10` (bit 63 = hypervisor/VMM ⇒ nonaktif), lalu `r12 = byte [cpu_info+0x4d]` (= `cpuid_model`; tata letak
  `i386_cpu_info_t` konsisten dengan `cpuid.h:429-442`, stepping di `+0x50` terbaca di instruksi berikutnya), `r12 -= 0x3c; cmp r12,0x69; ja 0x…aa10`, lalu jump table (`0x…40ad5c`).
  Isi tabel: 92 dari 106 model menuju `0x…aa10` (flag=0); hanya model Intel `0x3c,0x3d,0x45,0x46,0x47,0x4e,0x55,0x5e,0x7d,0x7e,0x8e,0x9e,0x9f,0xa5` menuju cabang lain.
  Mesin ini `machdep.cpu.model` = 96 (0x60) ⇒ indeks 0x24 ⇒ `0x…aa10` ⇒ **XCPM nonaktif**; model > 0xa5 juga nonaktif. Catatan: CPU AMD yang nomor modelnya bertabrakan dengan daftar Intel di atas akan masuk cabang Intel (tidak berlaku untuk model 0x60).
  Source `xcpm_bootstrap` tidak publik; hanya binary. Pengambilan keputusan `+0x4d = cpuid_model` didasarkan pada tata letak struct, bukan simbol.
- **TSC-deadline** (`_lapic_config_tsc_deadline_timer` `0x…3f6600`, MSR 0x6e0): tidak dipanggil langsung; thunk `0x…3ebbc0` ditunjuk dari `__DATA,__data 0x…c77f28` (anggota `rtc_config` tabel `rtc_timer_tsc_deadline`).
  Pemilihan tabel di `_rtc_timer_init` (`0x…3ebca6`): `call cpuid_features; bt rax,0x38 (CPUID_FEATURE_TSCTMR); jae` ke jalur non-deadline — sama dengan source `rtclock_native.c:171`.
  `sysctl machdep.cpu.features` di mesin ini tidak memuat TSCTMR ⇒ jalur LAPIC-timer biasa; MSR 0x6e0 tidak ditulis. Terjaga.

## Efek samping patch 15 pada `_kernel_debug_early` (analisis binary)
`_kernel_debug_early` (`0x…77f370`): `cmp [flag],0; je lanjut` (jika sudah selesai: `ret`); bila belum, hanya merekam bila indeks < 0x100 (`cmp rax,0x100; setae; jae ret`) dan hanya di CPU boot (`cmp cpu_number,[boot_cpu]; jne ret`),
menulis debugid + 4 argumen ke buffer statis berisi 256 entri × 64 byte (`shl rax,6`). Jalur lain (`kdebug` aktif) menuju `_kernel_debug` biasa. Jadi register sisa (debugid/argumen sampah, karena `mov edi,0x5310258; xor ecx; xor r8d` ikut di-NOP)
hanya menghasilkan paling banyak 256 entri trace awal yang tidak bermakna; penulisan dibatasi. Tidak terlihat risiko crash dari analisis ini (belum dites). Pemanggil rel32 langsung `_pstate_trace`: tidak ada.

## Pemeriksaan lain (2026-10-09)
- Tag source XNU terbaru: `git ls-remote` menunjukkan tag tertinggi tetap `xnu-12377.121.6` (`ac9718f`), sama dengan `xnu/`. Tidak ada tag baru untuk `xnu-12377.161.15.700.19`.
- `ocvalidate` tidak ada di mesin ini (`which ocvalidate` kosong); langkah `ocvalidate` belum bisa dijalankan sampai paket OpenCore disalin ke repo (dilakukan pengguna).

## Pindaian kedua: leaf CPUID dan instruksi khusus (2026-10-09)
Pindai `cpuid` (leaf dari `mov eax,imm`) dan instruksi khusus di `__TEXT,__text`:
- Leaf yang dipakai: 0x0,0x1,0x2,0x4,0x5,0x6,0x7,0xa,0xd,0x15, 0x80000000–8/6/7/8, plus leaf VMM 0x40000000/1/10. **Leaf 0xB/0x1F (topologi) tidak dipakai** ⇒ tidak ada masalah topologi AMD di jalur ini.
- Leaf 0x15 (TSC/crystal Intel) hanya dibaca bila `max_basic >= 0x15`; mesin ini 16, jadi dilewati (gerbang `cpuid.c:865`). Leaf 0xa (arch perfmon) dipakai dan AMD mengembalikan nilai tak bermakna; dampak ke `_cpc_*` (rdpmc ×31) lihat butir perf counter di bawah (terjaga).
- `invpcid` ×13 (pmap): hanya bila `invpcid_enabled`, yang di-set hanya bila `cpuid_features() & PCID` **dan** leaf7 INVPCID (`pmap_pcid.c:111-126`). `machdep.cpu.features` di sini tidak memuat PCID ⇒ terjaga.
- `monitor/mwait` hanya di `_xcpm_*` (XCPM nonaktif). `vmcall` ×9 hanya untuk tamu hypervisor. `vmxon/vmread/invept` terjaga VMX. `rdrand/rdseed` ada di Zen 2. `xsetbv/xgetbv` standar.
- **Perf counter (`_cpc_*`, `rdpmc` ×31, `wrmsr` 0x186–0x189/0x38d–0x390):** `sysctl machdep.cpu.arch_perf.*` semuanya **0** (version 0, number 0, fixed_number 0) di mesin ini. Source: `cpc_x86_64.c:358` hanya menyiapkan CPMU bila `arch_perf_leaf.version >= 2`;
  `kpc_x86.c:77-120` menghitung jumlah counter dari field yang sama (=0). Jadi counter Intel tidak tersedia/tidak dipakai; kperf/Instruments tidak akan menyentuh MSR itu (pengamatan runtime + source; tidak diuji dengan menjalankan kperf).
Tidak ada kandidat baru. Pengamatan runtime: `notes/runtime-observations.md`.

## Kesimpulan
- Dari pindaian ini **tidak ada kandidat patch baru yang terbukti perlu di jalur boot**; set yang ada (4–8, 12, 14, 15, 16, 20, 22, PAT, core count) menutup situs Intel-only yang terlihat, dengan dua ketergantungan di luar plist
  (`ProvideCurrentCpuInfo` untuk `_tsc_init`; status patch 14).
- Aturan 1 tetap berlaku: tidak ada byte Find/Replace baru yang ditulis dari hasil ini.

## Langkah lanjut (menunggu keputusan)
1. Log debug OpenCore: apakah patch 14 terpasang? (menjelaskan temuan 2).
2. ~~Gating VMX/XCPM/TSC-deadline~~ — selesai (lihat "Pemeriksaan gating"); ketiganya terjaga di mesin ini.
3. Bila `-nomsr35h` dianggap alternatif patch 14/3, analisis cabangnya (flag `rax`) dan uji di hardware.
4. Analisis `_cpc_*/_kpc_*` bila memakai Instruments/powermetrics di mesin ini.
