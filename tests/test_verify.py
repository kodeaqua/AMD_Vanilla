"""Tes unit untuk fungsi murni di tools/verify.py (tanpa kernel Apple).

Jalankan (dari root repo): .venv/bin/python -I tests/test_verify.py -v
"""
import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("verify", os.path.join(ROOT, "tools", "verify.py"))
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class FakeKernel:
    """Hanya antarmuka yang dipakai apply_evidence."""
    def off_to_vaddr(self, off):
        return 0xffffff8000000000 + off


class TestVersion(unittest.TestCase):
    def test_parse_ver_pads(self):
        self.assertEqual(v.parse_ver("25.6"), (25, 6, 0))
        self.assertEqual(v.parse_ver("22.3.99"), (22, 3, 99))

    def test_applies_range_inclusive(self):
        p = {"MinKernel": "25.4.0", "MaxKernel": "25.99.99"}
        self.assertTrue(v.applies(p, (25, 4, 0)))
        self.assertTrue(v.applies(p, (25, 6, 0)))
        self.assertFalse(v.applies(p, (25, 3, 99)))
        self.assertFalse(v.applies({"MinKernel": "21.0.0", "MaxKernel": "25.3.99"}, (25, 6, 0)))


class TestMatching(unittest.TestCase):
    def test_find_all_with_mask(self):
        data = bytes.fromhex("00 48 aa 90 04 00 00 0f 11 48 bb 90 04 00 00 0f 22 00".replace(" ", ""))
        find = bytes.fromhex("48 00 90 04 00 00 0f".replace(" ", ""))
        mask = bytes.fromhex("ff 00 ff ff ff ff ff".replace(" ", ""))
        hits = v.find_all(data, find, mask, [(0, len(data))])
        self.assertEqual(hits, [1, 9])

    def test_find_all_respects_range_start(self):
        data = b"\x90\x90\xcc\x90\x90"
        self.assertEqual(v.find_all(data, b"\x90\x90", b"\xff\xff", [(2, 5)]), [3])

    def test_apply_replace_mask(self):
        old = bytes([0x0f, 0x87, 0x15])
        rep = bytes([0x66, 0x90, 0x00])
        self.assertEqual(v.apply_replace(old, rep, b"\xff\xff\x00"), bytes([0x66, 0x90, 0x15]))


class TestExpected(unittest.TestCase):
    def test_base_and_comment_function(self):
        p = {"Base": "_cpuid_set_info", "Comment": "a | _cpuid_set_cache_info | do x | 10.13+"}
        self.assertEqual(v.expected_functions(p), {"cpuid_set_info", "cpuid_set_cache_info"})

    def test_description_is_not_function(self):
        p = {"Base": "", "Comment": "algrey | Force cpuid_cores_per_package to constant | 13.3+"}
        self.assertEqual(v.expected_functions(p), set())

    def test_multiple_functions(self):
        p = {"Base": "", "Comment": "Visual | thread_invoke, thread_dispatch | Remove panic | 12.0+"}
        self.assertEqual(v.expected_functions(p), {"thread_invoke", "thread_dispatch"})

    def test_trailing_space_base_is_stripped_for_expectation_only(self):
        p = {"Base": "_cpuid_set_info ", "Comment": "x | y | 11.3+"}
        self.assertEqual(v.expected_functions(p), {"cpuid_set_info"})


class TestHashAndEvidence(unittest.TestCase):
    def base_patch(self):
        return {"Arch": "x86_64", "Base": "", "Comment": "c", "Count": 1, "Enabled": True,
                "Find": b"\x01", "Identifier": "kernel", "Limit": 0, "Mask": b"",
                "MaxKernel": "25.99.99", "MinKernel": "25.0.0", "Replace": b"\x02",
                "ReplaceMask": b"", "Skip": 0}

    def test_hash_changes_with_replace(self):
        a, b = self.base_patch(), self.base_patch()
        b["Replace"] = b"\x03"
        self.assertNotEqual(v.patch_hash(a), v.patch_hash(b))
        self.assertEqual(v.patch_hash(a), v.patch_hash(self.base_patch()))

    def evidence(self, decision=None):
        e = {"build": "B", "comment": "c", "min_kernel": "25.0.0", "vaddrs": ["0xffffff8000000010"],
             "source": ["f.c:1"], "note": "n"}
        if decision:
            e["decision"] = decision
        return [e]

    def res(self, status):
        return {"status": status, "notes": [], "hits": [0x10]}

    def test_unproven_to_plausible_never_ok(self):
        r = self.res("UNPROVEN")
        v.apply_evidence(r, self.base_patch(), FakeKernel(), "B", self.evidence())
        self.assertEqual(r["status"], "PLAUSIBLE")

    def test_decision_gives_verified(self):
        r = self.res("UNPROVEN")
        v.apply_evidence(r, self.base_patch(), FakeKernel(), "B",
                         self.evidence({"status": "VERIFIED", "by": "u", "date": "d", "scope": "s"}))
        self.assertEqual(r["status"], "VERIFIED")

    def test_ok_without_decision_stays_ok(self):
        r = self.res("OK")
        v.apply_evidence(r, self.base_patch(), FakeKernel(), "B", self.evidence())
        self.assertEqual(r["status"], "OK")

    def test_vaddr_mismatch_does_not_promote(self):
        r = {"status": "UNPROVEN", "notes": [], "hits": [0x20]}
        v.apply_evidence(r, self.base_patch(), FakeKernel(), "B", self.evidence())
        self.assertEqual(r["status"], "UNPROVEN")

    def test_other_build_does_not_promote(self):
        r = self.res("UNPROVEN")
        v.apply_evidence(r, self.base_patch(), FakeKernel(), "OTHER", self.evidence())
        self.assertEqual(r["status"], "UNPROVEN")

    def test_failures_untouched(self):
        for st in ("NO-BASE", "NO-MATCH", "LENGTH"):
            r = self.res(st)
            v.apply_evidence(r, self.base_patch(), FakeKernel(), "B", self.evidence(
                {"status": "VERIFIED", "by": "u", "date": "d", "scope": "s"}))
            self.assertEqual(r["status"], st)


if __name__ == "__main__":
    unittest.main()
