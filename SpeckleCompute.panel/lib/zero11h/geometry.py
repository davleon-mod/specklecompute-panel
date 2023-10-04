#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Geometry helpers. Pure python

Original Author: ROK, Rippmann Oesterle Knauss GmbH, Silvan Oesterle
Web: http://www.rok-office.com
Description: Pure python geometry library. Fast 3d Vector classes.
Based on ROK designlib.geometry. No binary dependencies allowed.
Extended by: Iván Pajares[Modelical]
BBox3 and Domain1D originally from Hypars Elements
https://github.com/hypar-io/Elements/blob/a86b19a0fc73d18475a753e0f7ba03870010ce4c/Elements/src/Geometry/BBox3.cs
"""


import math

try:
    from zero11h.dynamo import DynPoint3Mixin, DynVector3Mixin
except ImportError:
    print('Dynamo Mixins import error. Are we on test environment?')


    class DynPoint3Mixin:
        pass


    class DynVector3Mixin:
        pass

EPSILON = 1e-10
TOLERANCE = 0.0001
MAX_ALLOWED_VALUE = 100000


def almost_equal(value1, value2, tolerance=TOLERANCE):
    # return math.isclose(value1, value2, abs_tol=EPSILON) # only from python 3.5 onwards
    return abs(value1 - value2) <= tolerance


class __Object3Base__(object):
    __slots__ = ('x', 'y', 'z')
    __hash__ = None

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    @classmethod
    def origin(cls):
        return cls(0, 0, 0)

    def __copy__(self):
        return self.__class__(self.x, self.y, self.z)

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y and self.z == other.z

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        return self.x < other.x and self.y < other.y and self.z < other.z

    def __le__(self, other):
        return self.x <= other.x and self.y <= other.y and self.z <= other.z

    def __gt__(self, other):
        return self.x > other.x and self.y > other.y and self.z > other.z

    def __ge__(self, other):
        return self.x >= other.x and self.y >= other.y and self.z >= other.z

    def __len__(self):
        """Returns the number of elements."""
        return 3

    def __iter__(self):
        return iter((self.x, self.y, self.z))

    def __getitem__(self, i):
        if i == 0:
            return self.x
        elif i == 1:
            return self.y
        elif i == 2:
            return self.z
        else:
            raise IndexError('Index out of range')

    def __setitem__(self, i, val):
        if i == 0:
            self.x = val
        elif i == 1:
            self.y = val
        elif i == 2:
            self.z = val
        else:
            raise IndexError('Index out of range')

    def almost_equal(self, other):
        return abs(self.x - other.x) < TOLERANCE and abs(self.y - other.y) < TOLERANCE and abs(
            self.z - other.z) < TOLERANCE
        # from Python 3.5 onwards
        # return (math.isclose(self.x, other.x, abs_tol=EPSILON) and
        #         math.isclose(self.y, other.y, abs_tol=EPSILON) and
        #         math.isclose(self.z, other.z, abs_tol=EPSILON))

    def ToString(self):
        return self.__repr__()

    def to_triplet(self):
        return [self.x, self.y, self.z]

    def clamped_string_triplet(self, n_of_digits=3):
        """Returns a copy of the object with clamped coordinates for hashing"""
        return [round(self.x, n_of_digits),
                round(self.y, n_of_digits),
                round(self.z, n_of_digits)]


class Vector3(__Object3Base__, DynVector3Mixin):
    """
    x,y,z (float): Vector components
    """
    entity = 'Vector3'

    def __repr__(self):
        return u'Vector3: <{0}, {1}, {2}>'.format(
            self.x, self.y, self.z)

    def __nonzero__(self):
        """A zero vector will return None."""
        return self.x != 0 or self.y != 0 or self.z != 0

    def __add__(self, other):
        """Return new Vector3 added self + other."""
        return Vector3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __iadd__(self, other):
        """Adds other to self in place and returns self."""
        self.x += other.x
        self.y += other.y
        self.z += other.z
        return self

    def __sub__(self, other):
        """Return new Vector3 subtracted self - other."""
        return Vector3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __isub__(self, other):
        """Subtracts other from self in place and returns self."""
        self.x -= other.x
        self.y -= other.y
        self.z -= other.z
        return self

    def __mul__(self, scalar):
        """
        Returns new Vector3. Scales the vector by scalar.
        scalar (int, float)
        return (Vector3)
        """
        return Vector3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __imul__(self, scalar):
        """Multiplies self in place with scalar and returns self."""
        self.x *= scalar
        self.y *= scalar
        self.z *= scalar
        return self

    def __neg__(self):
        """Unary -. Returns reversed version of self."""
        return Vector3(-self.x, -self.y, -self.z)

    @classmethod
    def from_two_points(cls, point1, point2):
        return cls(point2.x - point1.x,
                   point2.y - point1.y,
                   point2.z - point1.z)

    @property
    def length_sqrd(self):
        """Squared length of the vector (faster than length)."""
        return self.x ** 2 + self.y ** 2 + self.z ** 2

    @property
    def length(self):
        """Length of the vector."""
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)

    def dot(self, other):
        """
        Dot prodct of the vector with other vector.
        other (Vector3)
        return (int, float)
        """
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other):
        """
        Cross product of the vector with other vector.
        other (Vector3)
        return (Vector3)
        """
        return Vector3(self.y * other.z - self.z * other.y,
                       -self.x * other.z + self.z * other.x,
                       self.x * other.y - self.y * other.x)

    def scale(self, scalar):
        """In place scaling of the vector."""
        self.x *= scalar
        self.y *= scalar
        self.z *= scalar
        return self

    def normalize(self):
        """In place normalization of the vector (unit vector)."""
        d = self.length
        if d:
            self.x /= d
            self.y /= d
            self.z /= d
            return self
        raise RuntimeError('Zero vector, can not be normalized')

    def normalized(self):
        """Returns a normalized (unit vector) copy of self"""
        d = self.length
        if d:
            return Vector3(self.x / d,
                           self.y / d,
                           self.z / d)
        raise RuntimeError('Zero vector, can not be normalized')

    def angle_rad(self, other):
        """
        Angle between two vectors in radians (0-180).
        other (Vector3)
        return (float)
        """
        d = self.dot(other.normalized())
        # Fixes floating point arithmetic errors that could lead to the dot being
        # out of bounds -1, 1. This clamps to the bounds
        if d < -1:
            d = -1
        elif d > 1:
            d = 1
        return math.acos(d)

    def angle_deg(self, other):
        """
        Angle between two vectors in degress (0-180).
        other (Vector3)
        return (float)
        """
        return self.angle_rad(other) * (180 / math.pi)

    def rotate(self, angle, axis):
        """
        Rotation via Rodriguez formula.
        angle (double): The rotation angle in radians.
        axis (Vector3): Has to be normalized (unitized).
        """
        c = math.cos(angle)
        s = math.sin(angle)
        return c * self + s * axis.cross(self) + self.dot(axis) * (1 - c) * axis

    def almost_aligned(self, other, max_angular_deviation=0.01):
        """
        Aligned vectors are parallel and point in the same direction
        """
        d = self.dot(other.normalized())
        if d < 0:
            return False
        deviation = abs(math.cos(math.radians(max_angular_deviation)))
        if d < -1:
            d = -1
        elif d > 1:
            d = 1
        return abs(d) > deviation

    def almost_parallel(self, other, max_angular_deviation=0.01):
        """
        TODO: change signature to almost aligned because parallel can have opposite orientation
        """
        deviation = abs(math.cos(math.radians(max_angular_deviation)))
        d = self.dot(other.normalized())
        if d < -1:
            d = -1
        elif d > 1:
            d = 1
        return abs(d) > deviation

    def almost_perpendicular(self, other, max_angular_deviation=0.01):
        return 90 - max_angular_deviation < abs(self.angle_deg(other)) < 90 + max_angular_deviation


class Point3(__Object3Base__, DynPoint3Mixin):  # Mix in Dynamo conversion
    entity = 'Point3'

    @classmethod
    def from_triplet(cls, triplet):
        return cls(triplet[0], triplet[1], triplet[2])

    def distance_to(self, other):
        return Vector3.from_two_points(self, other).length

    def __repr__(self):
        return u'Point3: <{0}, {1}, {2}>'.format(
            self.x, self.y, self.z)

    def translate(self, vector):
        """Returns a copy of the point translated according to vector"""
        x, y, z = vect3_add(self, vector)
        return Point3(x, y, z)

    def to_vector(self):
        return Vector3.from_two_points(Point3(0, 0, 0),
                                       self)


def get_p_min_and_p_max_from_points(point_list):
    x_coords, y_coords, z_coords = [], [], []
    for p in point_list:
        x_coords.append(p.x)
        y_coords.append(p.y)
        z_coords.append(p.z)
    p_min = Point3(min(x_coords), min(y_coords), min(z_coords))
    p_max = Point3(max(x_coords), max(y_coords), max(z_coords))
    return p_min, p_max


class CoordinateSystem3(object):
    worldX = Vector3(1, 0, 0)
    worldY = Vector3(0, 1, 0)
    worldZ = Vector3(0, 0, 1)

    def __init__(self, origin, basisx, basisy, basisz):
        self.origin = origin
        self.basisx = basisx.normalize()
        self.basisy = basisy.normalize()
        self.basisz = basisz.normalize()

    @property
    def identity(self):
        return CoordinateSystem3(Point3(0, 0, 0),
                                 CoordinateSystem3.worldX,
                                 CoordinateSystem3.worldY,
                                 CoordinateSystem3.worldZ)

    def transform_to_local(self, geom):
        if self == self.identity:
            return geom
        elif isinstance(geom, Point3):
            v = Vector3(*vect3_subtract(geom, self.origin))
            return Point3(v.dot(self.basisx), v.dot(self.basisy), v.dot(self.basisz))
        elif isinstance(geom, Vector3):
            return Vector3(geom.dot(self.basisx), geom.dot(self.basisy), geom.dot(self.basisz))
        raise ValueError('Could not parse {} of type {}'.format(geom, type(geom)))

    def transform_from_local(self, geom):
        """
        transform from local requires matrix multiplication. Not implemented
        """
        if self == self.identity:
            return geom
        elif geom.entity == 'Point3':  # isinstance(geom, Point3):
            vo = self.origin.to_vector()
            rv = vo + self.transform_from_local(geom.to_vector())
            return Point3(rv.x, rv.y, rv.z)

        elif geom.entity == 'Vector3':  # isinstance(geom, Vector3):
            return (self.basisx * geom.x +
                    self.basisy * geom.y +
                    self.basisz * geom.z)
        # https://stackoverflow.com/questions/46708659/isinstance-fails-for-a-type-imported-via-package-and-from-the-same-module-direct
        # https: // stackoverflow.com / questions / 21498211 / using - isinstance - in -modules
        return 'Could not parse: {} of type: {}'.format(geom, type(geom))

    def __repr__(self):
        return 'CoordinateSystem with origin: {},{},{}'.format(round(self.origin.x, 3),
                                                               round(self.origin.y, 3),
                                                               round(self.origin.z, 3))

    def ToString(self):
        return self.__repr__()


WORLD_CS = CoordinateSystem3(Point3(0, 0, 0),
                             CoordinateSystem3.worldX,
                             CoordinateSystem3.worldY,
                             CoordinateSystem3.worldZ)


class Domain1d(object):
    """
    Python fork from:
    https://github.com/hypar-io/Elements/blob/a86b19a0fc73d18475a753e0f7ba03870010ce4c/Elements/src/Math/Domain1d.cs
    """

    def __init__(self, d_min=0.0, d_max=1.0):
        self.d_min = d_min
        self.d_max = d_max

    @property
    def is_increasing(self):
        return self.d_min < self.d_max

    @property
    def length(self):
        """
        Can be negative for non increasing domains
        """
        return self.d_max - self.d_min

    def includes(self, value, tolerance=0.0):
        """
        True if the value is within the domain exclusive of its ends + optional tolerance
        """
        if self.is_increasing:
            return self.d_min + tolerance < value < self.d_max - tolerance

        return self.d_min - tolerance > value > self.d_max + tolerance

    def is_value_close_to_boundary(self, value):
        """
        Test if value is within tolerance of the domain Min or Max
        """
        return almost_equal(self.d_min, value) or almost_equal(self.d_max, value)

    def overlaps(self, other_domain, tolerance=0.001):
        first_domain = Domain1d(d_min=self.d_min if self.is_increasing else self.d_max,
                                d_max=self.d_max if self.is_increasing else self.d_min)

        second_domain = Domain1d(d_min=other_domain.d_min if other_domain.is_increasing else other_domain.d_max,
                                 d_max=other_domain.d_max if other_domain.is_increasing else other_domain.d_min)

        # same or almost same
        if (first_domain.is_value_close_to_boundary(second_domain.d_min) and
                first_domain.is_value_close_to_boundary(second_domain.d_max)):
            return True
        # overlap
        if (first_domain.includes(second_domain.d_min,
                                  tolerance=tolerance) or
                first_domain.includes(second_domain.d_max,
                                      tolerance=tolerance) or
                second_domain.includes(first_domain.d_min,
                                       tolerance=tolerance) or
                second_domain.includes(first_domain.d_max,
                                       tolerance=tolerance)):
            return True
        # # no overlap
        # if second_domain.d_min > first_domain.d_max or second_domain.d_max < first_domain.d_min:
        #     return False
        return False

    def split_at(self, position):
        """

        Args:
            position: the position value at which to split the domain

        Returns: An array of 2 1d domains split at the designated position

        """
        if self.is_value_close_to_boundary(position):
            raise ValueError('Position {} too close to domain boundary'.format(position))
        if not self.includes(position):
            raise ValueError('Position {} out of domain bounds'.format(position))

        return [Domain1d(self.d_min, position),
                Domain1d(position, self.d_max)]

    def __repr__(self):
        return "From {} to {}".format(self.d_min, self.d_max)

    def ToString(self):
        return self.__repr__()


class BoundingBox3(object):
    """
    Simple BoundingBox Class
    p1, p2 = tuple of coordinates
    """

    def __init__(self, p1, p2):
        self.p_min = Point3(min(p1.x, p2.x), min(p1.y, p2.y), min(p1.z, p2.z))
        self.p_max = Point3(max(p1.x, p2.x), max(p1.y, p2.y), max(p1.z, p2.z))
        assert not self.p_min.almost_equal(
            self.p_max), "The bounding box will have zero volume. Ensure Min and Max points are not identical"
        self.type = 'Bounding Box'

    @classmethod
    def from_points(cls, point_list):
        """
        Creates bbox from a list of points
        """
        if len(point_list) < 2:
            raise ValueError('BoundingBox3.from_points error: point_list has to have more than 1 points')
        elif len(point_list) == 2:
            return cls(point_list[0], point_list[1])
        pmin, pmax = get_p_min_and_p_max_from_points(point_list)
        return cls(*get_p_min_and_p_max_from_points(point_list))

    def extend(self, point_list):
        point_list.extend([self.p_min, self.p_max])
        self.p_min, self.p_max = get_p_min_and_p_max_from_points(point_list)

    def expand(self, distance=None):
        """
        Expands the bounding box in all axis by distance
        """
        self.p_min = Point3(self.p_min.x - distance,
                            self.p_min.y - distance,
                            self.p_min.z - distance)
        self.p_max = Point3(self.p_max.x + distance,
                            self.p_max.y + distance,
                            self.p_max.z + distance)

    @property
    def size_x(self):
        return math.fabs(self.p_min.x - self.p_max.x)

    @property
    def size_y(self):
        return math.fabs(self.p_min.y - self.p_max.y)

    @property
    def size_z(self):
        return math.fabs(self.p_min.z - self.p_max.z)

    @property
    def size(self):
        return self.size_x, self.size_y, self.size_z

    @property
    def domain_x(self):
        return Domain1d(self.p_min.x, self.p_max.x)

    @property
    def domain_y(self):
        return Domain1d(self.p_min.y, self.p_max.y)

    @property
    def domain_z(self):
        return Domain1d(self.p_min.z, self.p_max.z)

    @property
    def center(self):
        return vect3_add(self.p_min,
                         Point3(self.size_x / 2.0, self.size_y / 2.0, self.size_z / 2.0))

    @property
    def volume(self):
        return self.size_x * self.size_y * self.size_z

    @property
    def corners(self):
        """
        Get all 8 corners of this bounding box.
        Ordering is CW bottom, then CW top, each starting from minimum (X,Y).
        For a unit cube this would be:
        (0,0,0),(0,1,0),(1,1,0),(1,0,0),(0,0,1),(0,1,1),(1,1,1),(1,0,1)
        """
        self.v11 = self.p_min
        self.v12 = Point3(self.p_min.x, self.p_max.y, self.p_min.z)
        self.v13 = Point3(self.p_max.x, self.p_max.y, self.p_min.z)
        self.v14 = Point3(self.p_max.x, self.p_min.y, self.p_min.z)
        self.v21 = Point3(self.p_min.x, self.p_min.y, self.p_max.z)
        self.v22 = Point3(self.p_min.x, self.p_max.y, self.p_max.z)
        self.v23 = self.p_max
        self.v24 = Point3(self.p_max.x, self.p_min.y, self.p_max.z)

        return [self.v11, self.v12, self.v13, self.v14, self.v21, self.v22, self.v23, self.v24]

    @property
    def faces(self):
        """WIP"""
        top = [self.v21, self.v22, self.v23, self.v24]
        bottom = [self.v11, self.v12, self.v13, self.v14]
        left = []
        right = []
        front = []
        back = []

    def intersects(self, other):
        """
        Valid only for bounding boxes aligned to the same CS
        """
        return not (other.p_min.x > self.p_max.x or
                    other.p_max.x < self.p_min.x or
                    other.p_min.y > self.p_max.y or
                    other.p_max.y < self.p_min.y or
                    other.p_min.z > self.p_max.z or
                    other.p_max.z < self.p_min.z)

    def contains(self, point):  # Point3
        # for p in self.corners:
        #     if p == point:
        #         print('point is a vertex of bounding box')
        # return all([self.p_min.x < point.x < self.p_max.x,
        #             self.p_min.y < point.y < self.p_max.y,
        #             self.p_min.z < point.z < self.p_max.z])
        return self.p_min <= point <= self.p_max

    def is_valid(self):
        return (self.p_min.x != MAX_ALLOWED_VALUE and
                self.p_min.y != MAX_ALLOWED_VALUE and
                self.p_min.z != MAX_ALLOWED_VALUE and
                self.p_max.x != EPSILON and
                self.p_max.y != EPSILON and
                self.p_max.z != EPSILON)

    def is_degenerate(self):
        return (almost_equal(self.p_min.x, self.p_max.x) or
                almost_equal(self.p_min.y, self.p_max.y) or
                almost_equal(self.p_min.z, self.p_max.z))

    def __eq__(self, other):
        if not isinstance(other, BoundingBox3):
            return False

        return almost_equal(self.p_min, other.p_min) and almost_equal(self.p_max, other.p_max)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "BoundingBox3 of size {} -- Min:{} Max:{}".format(self.size, self.p_min, self.p_max)

    def ToString(self):
        return self.__repr__()


# ------------------------------------------------------------------------------
# 3d Vector functions
def vect3_divide(v1, f):
    """
    Divides vector v1 by scalar f.
    v1 (3-tuple): 3d vector
    f (float): Scalar
    return (3-tuple): 3d vector
    """
    return (v1[0] / f, v1[1] / f, v1[2] / f)


def vect3_add(v1, v2):
    """
    Adds two 3d vectors.
    v1, v2 (3-tuple): 3d vectors
    return (3-tuple): 3d vector
    """
    return (v1[0] + v2[0], v1[1] + v2[1], v1[2] + v2[2])


def vect3_subtract(v1, v2):
    """
    Subtracts one 3d vector from another.
    v1, v2 (3-tuple): 3d vectors
    return (3-tuple): 3d vector
    """
    return (v1[0] - v2[0], v1[1] - v2[1], v1[2] - v2[2])


def vect3_pow(v):
    """
    Vector power.
    v (3-tuple): 3d vector
    return (float): the dot product of v.v
    """
    return vect3_dot(v, v)


def vect3_cross(u, v):
    """
    Cross product.
    u, v (3-tuple): 3d vectors
    return (3-tuple): 3d vector
    """
    return (u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0])


def vect3_dot(u, v):
    """
    u.v, dot (scalar) product.
    u, v (3-tuple): 3d vectors
    return (float): dot product
    """
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def vect3_length(v):
    """
    True length of a 3d vector.
    v (3-tuple): 3d vector
    return (float): length
    """
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def vect3_length_sqrd(v):
    """
    Squared length of a 3d vector.
    v (3-tuple): 3d vector
    return (float): squared length
    """
    return v[0] ** 2 + v[1] ** 2 + v[2] ** 2


def vect3_scale(v, f):
    """
    Scales a vector by factor f.
    v (3-tuple): 3d vector
    f (float): scale factor
    return (3-tuple): 3d vector
    """
    return (v[0] * f, v[1] * f, v[2] * f)


def vect3_normalized(v):
    """
    Normalize a vector.
    v (3-tuple): 3d vector
    return (3-tuple): 3d vector
    """
    d = float(vect3_length(v))
    return (v[0] / d, v[1] / d, v[2] / d)


def vect3_angle_rad(u, v):
    """
    Angle between two vectors in radians (0-180).
    v1, v2 (3-tuple): 3d vectors
    return (float): angle
    """
    d = vect3_dot(vect3_normalized(u), vect3_normalized(v))
    # Fixes floating point arithmetic errors that could lead to the dot being
    # out of bounds -1, 1. This clamps to the bounds
    if d < -1:
        d = -1
    elif d > 1:
        d = 1
    return math.acos(d)


def vect3_angle_deg(u, v):
    """
    Angle between two vectors in degress (0-180).
    v1, v2 (3-tuple): 3d vectors
    return (float): angle
    """
    return vect3_angle_rad(u, v) * (180 / math.pi)


def vect3_reverse(v):
    """
    Reverses a 3d vector.
    v (3-tuple): 3d vector
    return (3-tuple): 3d vector
    """
    return (v[0] * -1, v[1] * -1, v[2] * -1)


def vect3_bisector(v1, v2):
    """
    Gives the bisector vector of v1, v2
    v1, v2 (3-tuple): 3d vectors
    return (3-tuple): 3d vector
    """
    return vect3_add(vect3_normalized(v1), vect3_normalized(v2))


def vect3_rotate(v, angle, axis):
    """
    Rotation via Rodriguez formula.
    v (3-tuple): The vector to rotate
    angle (double): The rotation angle in radians.
    axis (3-tuple): Has to be normalized (unitized).
    """
    v = Vector3(*v)
    v.rotate(angle, Vector3(*axis))
    return (v.x, v.y, v.z)


if __name__ == "__main__":
    cs = CoordinateSystem3(Point3(3, -4, 0), CoordinateSystem3.worldX, CoordinateSystem3.worldZ,
                           CoordinateSystem3.worldY)
    p1 = Point3(3, -4, 1)
    p2 = cs.transform_to_local(p1)
    print(p2)
    v1 = Vector3(0, 1, 0)
    v2 = cs.transform_to_local(v1)
    print(v2)
    p1 = Point3(4, 4, 0)
    p2 = Point3(8, 5, 3)
    bb = BoundingBox3(p1, p2)
    p1 = Point3.origin()
    p4 = Point3(5, 5, 5)
    p3 = Point3(2, 2, 2)
    p2 = Point3(3, 3, 3)
    b0 = BoundingBox3.from_points([p1, p2, p3])
