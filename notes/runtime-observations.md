# Pengamatan runtime (sysctl, hanya-baca) pada sistem yang sedang berjalan

Diambil 2026-10-09 di mesin target (macOS 26.6, Darwin 25.6.0, Ryzen 5 4500) dengan `sysctl` (tanpa sudo, hanya membaca).
**Ini bukan log OpenCore** dan bukan tes per-patch; tetapi nilai tertentu hanya bisa berasal dari patch tertentu, jadi cukup kuat sebagai petunjuk bahwa patch itu *terpasang*.
BOOT-OK tetap tidak membuktikan apa pun; pengamatan di bawah memang membuktikan *efek* untuk patch yang disebut.

| sysctl | Nilai | Dikaitkan dengan | Kekuatan bukti |
|---|---|---|---|
| `machdep.cpu.microcode_version` | **186** (0xba) | Patch 7 (`rdmsr 0x8B` → `mov edx,0xba`) | Kuat: AMD asli akan melaporkan revisi microcode nyata, bukan konstanta 186 |
| `machdep.cpu.processor_flag` | **1** | Patch 8 (`mov dl,1`) | Kuat (nilai konstanta patch) |
| `machdep.cpu.core_count` / `cores_per_package` | **6** | Patch 3 (Replace `06`) | Kuat; thread_count 12 / logical_per_package 12 dari leaf 1 |
| `hw.cpufamily` | **2028621756 = 0x78ea4fbc** (`CPUFAMILY_INTEL_PENRYN`) | Patch 14 **atau** mekanisme setara | Efek terbukti (cpufamily terpaksa Penryn); **sumbernya tidak bisa dibedakan** antara patch 14 (NO-BASE di plist), `ProvideCurrentCpuInfo`, atau OpenCore yang menormalisasi Base. Log OpenCore masih diperlukan untuk menyebut patch 14 "terpasang" |
| `machdep.cpu.vendor` | `AuthenticAMD`; sistem tidak panic "Unsupported CPU" | Patch 12 (dan cpufamily non-UNKNOWN) | Kuat (tanpa patch 12 vendor ≠ Intel ⇒ panic) |
| `machdep.cpu.cache.size` | 512 (KB) | Patch 5 (leaf 4 → 0x8000001d) | Sedang (konsisten dengan L2 512 KB/core Zen 2) |
| `machdep.cpu.leaf7_features` | terisi (`RDWRFSGS BMI1 AVX2 SMEP BMI2 … SHA UMIP RDPID`) | Leaf 7 terbaca (gerbang `max_basic>=7`, `max_basic`=16) | Tidak menyangkut patch 10 (lihat `cpuid-leaf7.md`) |
| `machdep.cpu.features` | tanpa VMX, PCID, TSCTMR; ada x2APIC, AVX1.0, RDRAND | Gating VMX/PCID/TSC-deadline | Mendukung analisis di `amd-candidates.md` |
| `machdep.cpu.max_basic` | 16 | – | – |

Yang **tidak** teramati lewat sysctl: patch 4, 6, 15, 16, 20, 22, PAT (efeknya internal), `probeBusGated` (kext), patch 10 (kemungkinan tak berefek), dan patch 14 secara spesifik.
Karena itu log debug OpenCore tetap diperlukan untuk sisa patch dan untuk patch 14.
