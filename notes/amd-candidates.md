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

## Kesimpulan
- Dari pindaian ini **tidak ada kandidat patch baru yang terbukti perlu di jalur boot**; set yang ada (4–8, 12, 14, 15, 16, 20, 22, PAT, core count) menutup situs Intel-only yang terlihat, dengan dua ketergantungan di luar plist
  (`ProvideCurrentCpuInfo` untuk `_tsc_init`; status patch 14).
- Aturan 1 tetap berlaku: tidak ada byte Find/Replace baru yang ditulis dari hasil ini.

## Langkah lanjut (menunggu keputusan)
1. Log debug OpenCore: apakah patch 14 terpasang? (menjelaskan temuan 2).
2. Periksa gating `_vmx_cpu_init`, `_xcpm_init`, `_lapic_config_tsc_deadline_timer` di binary bila ingin menutup hipotesis di atas.
3. Bila `-nomsr35h` dianggap alternatif patch 14/3, analisis cabangnya (flag `rax`) dan uji di hardware.
4. Analisis `_cpc_*/_kpc_*` bila memakai Instruments/powermetrics di mesin ini.
