import unittest

from pixelforge import Version


class TestVersionParse(unittest.TestCase):
    def test_roundtrip(self):
        for text in ["0.0.0", "1.2.3", "10.20.30", "1.0.0-alpha",
                     "1.0.0-alpha.1", "2.0.0-rc.1", "1.0.0-x-y-z.-"]:
            self.assertEqual(str(Version.parse(text)), text)

    def test_rejects_invalid(self):
        for bad in ["", "1.0", "1.0.0.0", "01.2.3", "1.0.0+build",
                    "1.0.0-01", "1.0.0-", "1.0.0-a..b", "v1.2.3"]:
            with self.assertRaises(ValueError, msg=bad):
                Version.parse(bad)


class TestVersionOrder(unittest.TestCase):
    def test_semver_spec_ordering(self):
        chain = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta",
                 "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
                 "1.0.0-rc.1", "1.0.0"]
        versions = [Version.parse(s) for s in chain]
        for lower, higher in zip(versions, versions[1:]):
            self.assertLess(lower, higher)
            self.assertGreater(higher, lower)
            self.assertNotEqual(lower, higher)

    def test_core_ordering(self):
        self.assertLess(Version.parse("1.9.9"), Version.parse("1.10.0"))
        self.assertLess(Version.parse("0.9.9"), Version.parse("1.0.0-alpha"))
        self.assertLess(Version.parse("2.0.0-rc.1"), Version.parse("2.0.0"))

    def test_equality_and_hash(self):
        self.assertEqual(Version.parse("1.2.3-alpha"), Version(1, 2, 3, ("alpha",)))
        self.assertEqual(hash(Version.parse("1.2.3")), hash(Version(1, 2, 3)))


if __name__ == "__main__":
    unittest.main()
