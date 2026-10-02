import unittest

from pixelforge import Constraint, Interval, Version

p = Version.parse


class TestInterval(unittest.TestCase):
    def test_unbounded(self):
        iv = Interval(None, None)
        self.assertFalse(iv.is_empty())
        self.assertTrue(iv.contains(p("0.0.1")))
        self.assertTrue(iv.contains(p("99.0.0-rc.1")))

    def test_left_closed_right_open(self):
        iv = Interval(p("1.0.0"), p("2.0.0"))
        self.assertTrue(iv.contains(p("1.0.0")))
        self.assertTrue(iv.contains(p("1.5.0-alpha.1")))
        self.assertFalse(iv.contains(p("1.0.0-alpha.1")))
        self.assertFalse(iv.contains(p("2.0.0")))
        self.assertFalse(iv.contains(p("0.9.9")))

    def test_exact_point(self):
        iv = Interval.exact(p("1.2.3"))
        self.assertFalse(iv.is_empty())
        self.assertTrue(iv.contains(p("1.2.3")))
        self.assertFalse(iv.contains(p("1.2.4")))
        self.assertFalse(iv.contains(p("1.2.3-alpha")))

    def test_empty_point(self):
        self.assertTrue(Interval(p("1.0.0"), p("1.0.0")).is_empty())
        self.assertTrue(Interval(p("2.0.0"), p("1.0.0")).is_empty())

    def test_intersect(self):
        a = Interval(p("1.0.0"), p("3.0.0"))
        b = Interval(p("2.0.0"), None)
        merged = a.intersect(b)
        self.assertTrue(merged.contains(p("2.5.0")))
        self.assertFalse(merged.contains(p("1.5.0")))
        self.assertFalse(merged.contains(p("3.0.0")))
        self.assertIsNone(a.intersect(Interval(None, p("0.5.0"))))
        exact = a.intersect(Interval.exact(p("2.0.0")))
        self.assertTrue(exact.contains(p("2.0.0")))
        self.assertIsNone(a.intersect(Interval.exact(p("3.0.0"))))


class TestConstraint(unittest.TestCase):
    def test_any_and_empty(self):
        self.assertTrue(Constraint.any().contains(p("1.0.0")))
        self.assertTrue(Constraint().is_empty())
        self.assertFalse(Constraint().contains(p("1.0.0")))

    def test_union(self):
        c = Constraint((Interval(p("1.0.0"), p("2.0.0")),
                        Interval(p("3.0.0"), p("4.0.0"))))
        self.assertTrue(c.contains(p("1.5.0")))
        self.assertTrue(c.contains(p("3.5.0")))
        self.assertFalse(c.contains(p("2.5.0")))

    def test_intersect_unions(self):
        a = Constraint((Interval(p("1.0.0"), p("2.0.0")),
                        Interval(p("3.0.0"), p("4.0.0"))))
        b = Constraint.range(p("1.5.0"), p("3.5.0"))
        merged = a.intersect(b)
        self.assertTrue(merged.contains(p("1.5.0")))
        self.assertTrue(merged.contains(p("3.4.0")))
        self.assertFalse(merged.contains(p("2.5.0")))
        self.assertFalse(merged.contains(p("3.9.0")))

    def test_prerelease_in_ranges_without_filtering(self):
        c = Constraint.range(p("1.0.0-alpha"), p("1.0.0"))
        self.assertTrue(c.contains(p("1.0.0-beta.2")))
        self.assertFalse(c.contains(p("1.0.0")))
        self.assertFalse(c.contains(p("1.0.0-alpha") .__class__.parse("0.9.9")))


if __name__ == "__main__":
    unittest.main()
