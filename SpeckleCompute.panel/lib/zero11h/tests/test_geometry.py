import os
import sys
sys.path.insert(0, os.path.abspath('..'))

import unittest
from unittest import TestCase

from geometry import Vector3, Point3, Domain1d, BoundingBox3


class TestVector3(TestCase):
    def test_almost_perpendicular(self):
        # Almost perpendicular
        v1 = Vector3(1,0,0)
        v2 = Vector3(0.001,0.99, 0).normalize()
        print(v1.angle_deg(v2))
        self.assertTrue(v1.almost_perpendicular(v2, max_angular_deviation=0.1))
        # Not perpendicular
        v1 = Vector3(1,0,0)
        v2 = Vector3(0.5,0.5, 0).normalize()
        print(v1.angle_deg(v2))
        self.assertFalse(v1.almost_perpendicular(v2))
        v1 = Vector3(1,0,0)
        v2 = Vector3(0.1,1, 0).normalize()
        print(v1.angle_deg(v2))
        self.assertFalse(v1.almost_perpendicular(v2, max_angular_deviation=0.1))


class TestDomain1d(TestCase):
    def setUp(self) -> None:
        self.test_domain = Domain1d(d_min=0.0, d_max=2.0)
        self.test_domain_decreasing = Domain1d(d_min=2.0, d_max=0.0)
    def test_contains_value(self):
        value = 0.3
        self.assertTrue(self.test_domain.includes(value) is True)

    def test_does_not_contain_value(self):
        value = 2.0
        self.assertTrue(self.test_domain.includes(value) is False)

    def test_is_close_to_bounds(self):
        value = 1.999999999
        self.assertTrue(self.test_domain.is_value_close_to_boundary(value) is True)

    def test_contains_value_with_tolerance(self):
        value = 0.5
        tolerance = 0.1
        self.assertTrue(self.test_domain.includes(value, tolerance=tolerance) is True)
        self.assertTrue(self.test_domain_decreasing.includes(value, tolerance=tolerance) is True)

    def test_does_not_contain_value_with_tolerance(self):
        value = 0.5
        tolerance = 0.5
        self.assertTrue(self.test_domain.includes(value, tolerance=tolerance) is False)
        self.assertTrue(self.test_domain_decreasing.includes(value, tolerance=tolerance) is False)

    def test_domain_overlaps(self):
        other_domain_up = Domain1d(d_min=1.9, d_max=3.0)
        other_domain_down = Domain1d(d_min=-1.0, d_max=0.001)
        decreasing_other_domain_up = Domain1d(d_min=3.0, d_max=1.9)
        decreasing_other_domain_down = Domain1d(d_min=0.001, d_max=-1.0)
        tolerance = 0.0
        self.assertTrue(self.test_domain.overlaps(other_domain_up, tolerance=tolerance) is True)
        self.assertTrue(self.test_domain.overlaps(other_domain_down, tolerance=tolerance) is True)
        self.assertTrue(self.test_domain.overlaps(decreasing_other_domain_up, tolerance=tolerance) is True)
        self.assertTrue(self.test_domain.overlaps(decreasing_other_domain_down, tolerance=tolerance) is True)
        self.assertTrue(self.test_domain.overlaps(Domain1d(d_min=-0.01, d_max=2.01)) is True)
        self.assertTrue(self.test_domain.overlaps(self.test_domain) is True)
        self.assertTrue(self.test_domain.is_value_close_to_boundary(0.0) is True)
        self.assertTrue(self.test_domain.is_value_close_to_boundary(2.0) is True)

    def test_domain_does_not_overlap(self):
        other_domain_up = Domain1d(d_min=2.0, d_max=3.0)
        other_domain_down = Domain1d(d_min=-1.0, d_max=0.0)
        tolerance = 0.001
        self.assertTrue(self.test_domain.overlaps(other_domain_up, tolerance=tolerance) is False)
        self.assertTrue(self.test_domain.overlaps(other_domain_down, tolerance=tolerance) is False)

    def test_domain_does_not_overlap_no_tolerance(self):
        other_domain_up = Domain1d(d_min=2.0, d_max=3.0)
        other_domain_down = Domain1d(d_min=-1.0, d_max=0.0)
        tolerance = 0.0
        self.assertTrue(self.test_domain.overlaps(other_domain_up, tolerance=tolerance) is False)
        self.assertTrue(self.test_domain.overlaps(other_domain_down, tolerance=tolerance) is False)

    def test_domain_split(self):
        position = 0.5
        split1, split2 = self.test_domain.split_at(position)
        self.assertAlmostEqual(split1.length, 0.5, delta=0.0)
        self.assertAlmostEqual(split2.length, 1.5, delta=0.0)

class TestBoundingBox3(TestCase):
    def setUp(self):
        self.bbox = BoundingBox3(Point3(0,0,0), Point3(4, 2, 1))

    def test_size(self):
        self.assertTrue((4, 2, 1) == self.bbox.size)

    def test_bbox_calculates(self):
        diagonal = self.bbox.p_max.distance_to(self.bbox.p_min)
        print(diagonal)
        self.assertAlmostEqual(diagonal, 4.5825756, 6)

    def test_degenerate(self):
        bbox = BoundingBox3(Point3.origin(), Point3(1, 1, 1))
        self.assertFalse(bbox.is_degenerate(),
                         msg=f"Failed test: Bbox {bbox} is degenerate")

        degenerate_bbox = BoundingBox3(Point3.origin(), Point3(1, 1, 0))
        self.assertTrue(degenerate_bbox.is_degenerate(),
                        msg=f"Failed test: Bbox {degenerate_bbox} is not degenerate")

    def test_contains_point_at_bounds(self):
        bbox = BoundingBox3(Point3(1, 1, 1), Point3(3, 3, 3))
        p = Point3(1, 1, 1)
        self.assertTrue(bbox.contains(p),
                        msg=f"Failed test_contains_point_at_bounds: {p} is contained at bounds of {bbox}")

    def test_contains_point_inside_bounds(self):
        bbox = BoundingBox3(Point3(1, 1, 1), Point3(3, 3, 3))
        p = Point3(2, 2, 2)
        self.assertTrue(bbox.contains(p),
                        msg=f"Failed test_contains_point_inside_bounds: {p} is contained inside bounds of {bbox}")

    def test_does_not_contain_point_outside_bounds(self):
        bbox = BoundingBox3(Point3(1, 1, 1), Point3(3, 3, 3))
        p = Point3.origin()
        self.assertFalse(bbox.contains(p),
                         msg=f"Failed test_does_not_contain_point_outside_bounds: {p} is outside bounds of {bbox}")

    def test_bounding_box_intersections(self):
        # Contained
        b1 = BoundingBox3(Point3.origin(), Point3(5, 5, 5))
        b2 = BoundingBox3(Point3(1, 1, 1), Point3(6, 6, 6))
        self.assertTrue(b1.intersects(b2),
                        msg=f'Failed test_bounding_box_intersections: {b1} intersects {b2}')
        # Coincident at corner
        b2 = BoundingBox3(Point3(-1, -1, -1), Point3.origin())
        self.assertTrue(b1.intersects(b2),
                        msg=f'Failed test_bounding_box_intersections: {b1} coincident at corner with {b2}')
        # Not contained or touching
        b2 = BoundingBox3(Point3(6, 6, 6), Point3(10, 10, 10))
        self.assertFalse(b1.intersects(b2),
                        msg=f'Failed test_bounding_box_intersections: {b1} not contained or touching {b2}')
        # Full overlap
        b2 = b1
        self.assertTrue(b1.intersects(b2),
                        msg=f'Failed test_bounding_box_intersections: {b1} intersects {b2}')
        # Coincident at face
        b2 = BoundingBox3(Point3(0, -5, 0), Point3(5, 0, 5))
        self.assertTrue(b1.intersects(b2),
                        msg=f'Failed test_bounding_box_intersections: {b1} touches {b2}')


if __name__ == '__main__':
    unittest.main()