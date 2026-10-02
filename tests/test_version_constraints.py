"""Unit tests for SemVer versions and constraint sets."""

import unittest

from pixelforge import Version, VersionSet


def v(text):
    return Version.parse(text)


class VersionParseTest(unittest.TestCase):
    def test_roundtrip(self):
        for text in ("0.0.0", "1.2.3", "10.20.30", "1.0.0-alpha",
                     "1.0.0-alpha.1", "1.0.0-0.3.7", "1.0.0-x-y-z.-"):
            self.assertEqual(str(v(text)), text)

    def test_rejects_invalid(self):
        for text in ("1.2", "1.2.3.4", "01.2.3", "1.2.3+build",
                     "1.2.3-alpha..1", "1.2.3-", "a.b.c", ""):
            with self.assertRaises(ValueError, msg=text):
                v(text)

    def test_rejects_leading_zero_numeric_prerelease(self):
        with self.assertRaises(ValueError):
            v("1.0.0-01")


class VersionOrderTest(unittest.TestCase):
    def test_semver_org_precedence_chain(self):
        chain = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta",
                 "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
                 "1.0.0-rc.1", "1.0.0"]
        versions = [v(t) for t in chain]
        for earlier, later in zip(versions, versions[1:]):
            self.assertLess(earlier, later)
            self.assertGreater(later, earlier)
            self.assertNotEqual(earlier, later)

    def test_core_ordering(self):
        self.assertLess(v("1.9.9"), v("1.10.0"))
        self.assertLess(v("2.0.0"), v("10.0.0"))

    def test_equality_and_hash(self):
        self.assertEqual(v("1.2.3"), v("1.2.3"))
        self.assertEqual(hash(v("1.2.3-alpha")), hash(v("1.2.3-alpha")))
        self.assertNotEqual(v("1.2.3"), v("1.2.3-0"))


class VersionSetTest(unittest.TestCase):
    def test_exact(self):
        s = VersionSet.exact(v("1.2.0"))
        self.assertTrue(s.contains(v("1.2.0")))
        self.assertFalse(s.contains(v("1.2.0-0")))
        self.assertFalse(s.contains(v("1.2.1")))
        self.assertFalse(s.contains(v("1.2.0-alpha")))

    def test_exact_prerelease(self):
        s = VersionSet.exact(v("1.2.0-alpha"))
        self.assertTrue(s.contains(v("1.2.0-alpha")))
        self.assertFalse(s.contains(v("1.2.0-alpha.0")))
        self.assertFalse(s.contains(v("1.2.0")))

    def test_range_half_open(self):
        s = VersionSet.range(v("1.0.0"), v("2.0.0"))
        self.assertTrue(s.contains(v("1.0.0")))
        self.assertTrue(s.contains(v("2.0.0-rc.1")))
        self.assertFalse(s.contains(v("2.0.0")))
        self.assertFalse(s.contains(v("1.0.0-alpha")))

    def test_unbounded(self):
        self.assertTrue(VersionSet.any().contains(v("0.0.0-0")))
        low = VersionSet.range(None, v("1.0.0"))
        self.assertTrue(low.contains(v("0.0.1")))
        self.assertFalse(low.contains(v("1.0.0")))
        high = VersionSet.range(v("1.0.0"), None)
        self.assertTrue(high.contains(v("99.0.0")))
        self.assertFalse(high.contains(v("1.0.0-alpha")))

    def test_intersect(self):
        a = VersionSet.range(v("1.0.0"), v("3.0.0"))
        b = VersionSet.range(v("2.0.0"), v("4.0.0"))
        c = a.intersect(b)
        self.assertTrue(c.contains(v("2.5.0")))
        self.assertFalse(c.contains(v("1.5.0")))
        self.assertFalse(c.contains(v("3.0.0")))
        self.assertTrue(a.intersect(
            VersionSet.range(v("5.0.0"), None)).is_empty())

    def test_union_normalizes(self):
        a = VersionSet.exact(v("1.0.0")).union(VersionSet.exact(v("2.0.0")))
        self.assertTrue(a.contains(v("1.0.0")))
        self.assertTrue(a.contains(v("2.0.0")))
        self.assertFalse(a.contains(v("1.5.0")))
        # Overlapping ranges merge.
        b = VersionSet.range(v("1.0.0"), v("2.0.0")).union(
            VersionSet.range(v("1.5.0"), v("3.0.0")))
        self.assertEqual(b, VersionSet.range(v("1.0.0"), v("3.0.0")))

    def test_empty(self):
        self.assertTrue(VersionSet().is_empty())
        self.assertFalse(VersionSet.any().is_empty())


if __name__ == "__main__":
    unittest.main()
