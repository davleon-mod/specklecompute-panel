#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
This module holds the base Wall utility and join classes for working in Revit with 011h Partial Segments

"""

__author__ = 'Iván Pajares [Modelical]'



import zero11h.geometry as geo
import zero11h.revit_api.revit_utils as mru
from zero11h.revit_api import DB
# import zero11h.entities


class WallReference(object):
    """
    WIP
    """
    def __init__(self, wall, wall_reference):
        """
        wall_reference always in local coordinates

        :param wall: _BaseWall_ instance
        :param wall_reference:
        """
        self.wall = wall
        self.reference = wall_reference  # i.e.: wall.start_point_m

    @property
    def reference_name(self):
        dist_to_startp = geo.Vector3.from_two_points(self.reference, self.wall.start_point_m).length
        dist_to_endp = geo.Vector3.from_two_points(self.reference, self.wall.end_point_m).length
        if dist_to_startp < dist_to_endp:
            return "start point"
        return "end point"


class WallENDJoinResult(object):
    def __init__(self,
                 joining_wall_reference=None,
                 other_wall_reference=None,
                 join_distance=None,
                 join_result=None,
                 is_intersection=False):
        self.joining_wall_reference = joining_wall_reference
        self.other_wall_reference = other_wall_reference
        self.join_distance = join_distance
        self.join_result = join_result
        self.is_intersection = is_intersection


class WallTJoinResult(object):
    """
    TOTALLY WIP
    """
    def __init__(self,
                 joining_wall_reference=None,
                 receiving_wall=None,
                 t_join_point=None,
                 t_join_vector=None,
                 join_distance=None,
                 join_result=None,
                 is_intersection=False):
        self.joining_wall_reference = joining_wall_reference
        self.receiving_wall = receiving_wall
        self.t_join_point = t_join_point
        self.t_join_vector = t_join_vector
        self.join_distance = join_distance
        self.join_result = join_result
        self.is_intersection = is_intersection


class WallJoinEvaluator(object):
    def __init__(self,
                 wall=None,
                 otherwall=None,
                 max_angular_deviation=0.5,
                 max_separation_allowed_m=0.01,
                 tolerance_m=0.005,
                 vertical_tolerance_m = 0.01):  # 10mm will be the minimum overlap required to consider join posibility):
        self.wall = wall
        self.otherwall = otherwall
        self.max_angular_deviation = max_angular_deviation
        self.max_separation_allowed_m = max_separation_allowed_m
        self.tolerance_m = tolerance_m
        self.vertical_tolerance_m = vertical_tolerance_m
        self.receiving_wall = None
        self.joining_wall = None
        self.join_type = None
        self.walls_intersect = False

    def evaluate_join(self):
        if not self.within_z_range:
            return WallTJoinResult(join_result=False)  # Walls not in z range. Add this as message in result.
        if self.almost_perpendicular and self.t_join_possible():
            return self._t_join_solve()
        elif self.almost_aligned and self.within_axis_offset_allowed:
            return self._endjoin_solve()

        return WallTJoinResult(join_result=False)

    def _t_join_solve(self):
        # In local coordinates
        _receiving_wall_local_sp = self.receiving_wall.local_transform.from_world_XYZ_to_local(
            mru.UnitConversion.Point3_to_XYZ(self.joining_wall.start_point_m))
        _receiving_wall_local_ep = self.receiving_wall.local_transform.from_world_XYZ_to_local(
            mru.UnitConversion.Point3_to_XYZ(self.joining_wall.end_point_m))
        # We  need to project to receiving wall axis plane
        receiving_wall_local_sp = geo.Point3(_receiving_wall_local_sp.x, 0.0, _receiving_wall_local_sp.z)
        receiving_wall_local_ep = geo.Point3(_receiving_wall_local_ep.x, 0.0, _receiving_wall_local_ep.z)
        axis_point_of_t_join = geo.Point3(receiving_wall_local_sp.x, 0, 0)
        vector_to_startp = geo.Vector3(receiving_wall_local_sp.x - axis_point_of_t_join.x,
                                       receiving_wall_local_sp.y - axis_point_of_t_join.y,
                                       receiving_wall_local_sp.z - axis_point_of_t_join.z)
        vector_to_endp = geo.Vector3(receiving_wall_local_ep.x - axis_point_of_t_join.x,
                                     receiving_wall_local_ep.y - axis_point_of_t_join.y,
                                     receiving_wall_local_ep.z - axis_point_of_t_join.z)
        # distance from wall end to receiving wall side
        join_distance = min(vector_to_startp.length, vector_to_endp.length) - self.receiving_wall.width / 2
        if vector_to_startp.length < vector_to_endp.length:
            joining_wall_reference = WallReference(self.joining_wall,
                                                   self.joining_wall.start_point_m)
        else:
            joining_wall_reference = WallReference(self.joining_wall,
                                                   self.joining_wall.end_point_m)

        if self.walls_intersect:
            return WallTJoinResult(joining_wall_reference=joining_wall_reference,
                                   receiving_wall=self.receiving_wall,
                                   t_join_point=axis_point_of_t_join,
                                   t_join_vector=None,
                                   join_distance=join_distance,
                                   join_result=False,
                                   is_intersection=True)

        if (-1.01
                < vector_to_startp.normalized().dot(self.receiving_wall.exterior_face_local_normal)
                < -0.99):
            join_side = 'OTHER'
        else:
            join_side = 'REFERENCE'

        if 0.0005 < join_distance <= self.max_separation_allowed_m + 0.0005:
            MSG = 'JOINED'
        elif -0.0005 < join_distance <= 0.0005:
            MSG = 'TOUCHES'
        else:
            return WallTJoinResult(join_result=False)

        receiving_wall_tag = self.receiving_wall.rvt_element.Id.ToString()
        joining_wall_tag = self.joining_wall.rvt_element.Id.ToString()

        print('Wall {} {} T {} to {}, on {} side, distance: {}'.format(joining_wall_tag, MSG,
                                                                       joining_wall_reference.reference_name,
                                                                       receiving_wall_tag, join_side, join_distance))

        self.join_type = 'T JOIN.{}'.format(MSG)
        return WallTJoinResult(joining_wall_reference=joining_wall_reference,
                               receiving_wall=self.receiving_wall,
                               t_join_point=axis_point_of_t_join,
                               t_join_vector=None,
                               join_distance=join_distance,
                               join_result=True)

    def _endjoin_solve(self):
        overlap = -1
        # First check OVERLAP
        if (self.tolerance_m
            < self.wall.local_transform.from_world_XYZ_to_local(
                    mru.UnitConversion.Point3_to_XYZ(self.otherwall.start_point_m)).x
            < self.wall.length) or \
                (self.tolerance_m
                 < self.wall.local_transform.from_world_XYZ_to_local(
                            mru.UnitConversion.Point3_to_XYZ(self.otherwall.end_point_m)).x
                 < self.wall.length):
            overlap = 1
            # Walls overlap
            return WallENDJoinResult(join_result=False,
                                     is_intersection=True)

        startp_to_startp_dist = self.wall.local_transform.from_world_XYZ_to_local(
                                mru.UnitConversion.Point3_to_XYZ(self.otherwall.start_point_m)).x
        startp_to_endp_dist = self.wall.local_transform.from_world_XYZ_to_local(
                              mru.UnitConversion.Point3_to_XYZ(self.otherwall.end_point_m)).x
        endp_to_startp_dist = self.wall.local_transform.from_world_XYZ_to_local(
                              mru.UnitConversion.Point3_to_XYZ(self.otherwall.start_point_m)).x - self.wall.length
        endp_to_endp_dist = self.wall.local_transform.from_world_XYZ_to_local(
                            mru.UnitConversion.Point3_to_XYZ(self.otherwall.end_point_m)).x - self.wall.length

        refs = {0: ['start p', 'start p'], 1: ['start p', 'end p'], 2: ['end p', 'start p'], 3: ['end p', 'end p']}
        calc_dist = None
        calc_item = None
        for i, ref in enumerate([startp_to_startp_dist,
                                 startp_to_endp_dist,
                                 endp_to_startp_dist,
                                 endp_to_endp_dist]):
            if calc_dist is None:
                calc_dist = abs(ref)
                calc_item = i
                continue

            if abs(ref) < abs(calc_dist):
                calc_dist = abs(ref)
                calc_item = i

        min_distance = calc_dist
        wall_tag = self.wall.rvt_element.Id.ToString()
        otherwall_tag = self.otherwall.rvt_element.Id.ToString()

        if min_distance > self.max_separation_allowed_m + self.tolerance_m:
            # NOT JOINED
            return WallENDJoinResult(join_result=False,
                                     join_distance=min_distance * (overlap * -1))

        joined = 'JOINED'
        self.join_type = 'END JOIN'
        print('Wall {} {} is {} to wall {} {}. Distance on axis: {}'.format(wall_tag, refs[calc_item][0], joined,
                                                                            otherwall_tag, refs[calc_item][1],
                                                                            min_distance * (overlap * -1)))
        wall_ref = self.wall.start_point_m
        otherwall_ref = self.otherwall.start_point_m
        if 'end' in refs[calc_item][0]:
            wall_ref = self.wall.end_point_m
        if 'end' in refs[calc_item][1]:
            otherwall_ref = self.otherwall.end_point_m

        return WallENDJoinResult(joining_wall_reference=WallReference(self.wall, wall_ref),
                                 other_wall_reference=WallReference(self.otherwall, otherwall_ref),
                                 join_distance=min_distance * (overlap * -1),
                                 join_result=True)

    @property
    def almost_perpendicular(self):
        return (90 - self.max_angular_deviation
                < abs(self.wall.local_vx.angle_deg(self.otherwall.local_vx))
                < 90 + self.max_angular_deviation)

    @property
    def almost_aligned(self):
        return any([-self.max_angular_deviation
                    < self.wall.local_vx.angle_deg(self.otherwall.local_vx)
                    < self.max_angular_deviation,
                    180.00 - self.max_angular_deviation
                    < self.wall.local_vx.angle_deg(self.otherwall.local_vx)
                    < 180.00 + self.max_angular_deviation])

    @property
    def within_axis_offset_allowed(self):
        max_offset_allowed = self.wall.width / 2.0 + self.otherwall.width / 2.0 - self.tolerance_m
        offset = min(abs(self.wall.local_transform.from_world_XYZ_to_local(
                         mru.UnitConversion.Point3_to_XYZ(self.otherwall.end_point_m)).z),
                     abs(self.wall.local_transform.from_world_XYZ_to_local(
                         mru.UnitConversion.Point3_to_XYZ(self.otherwall.start_point_m)).z)
                     )

        return offset < max_offset_allowed

    @property
    def within_z_range(self):
        def get_wall_points(wall):
            return (mru.UnitConversion.XYZ_to_Point3(
                wall.local_transform.from_local_to_world(
                    geo.Point3(0, 0, 0))),
                    mru.UnitConversion.XYZ_to_Point3(
                        wall.local_transform.from_local_to_world(
                            geo.Point3(0, wall.height, 0))))

        wall_base, wall_top = get_wall_points(self.wall)
        other_base, other_top = get_wall_points(self.otherwall)

        # We project the points to the vertical line formed by the first two
        otherwall_base = geo.Point3(wall_base.x,
                                    wall_base.y,
                                    other_base.z)

        otherwall_top = geo.Point3(wall_top.x,
                                   wall_top.y,
                                   other_top.z)

        # Solve trivial cases that impede join
        # 1 wall is above other wall
        if round(wall_base.z, 3) >= round(other_top.z, 3):
            # print('Wall base {} above otherwall top z {}'.format(wall_base.z, other_top.z))
            return False
        # 2 wall is below other wall
        if round(other_base.z, 3) >= round(wall_top.z, 3):
            # print('Otherwall base {} above wall top z {}'.format(wall_top.z, other_base.z))
            return False

        cases = []
        # 3, 4 walls overlap vertically more than tolerance
        cases.append(wall_base.z + self.vertical_tolerance_m <=
                     otherwall_base.z <=
                     wall_top.z - self.vertical_tolerance_m)

        cases.append(wall_base.z + self.vertical_tolerance_m <=
                     otherwall_top.z <=
                     wall_top.z - self.vertical_tolerance_m)
        # 5 walls are levelled
        bases = geo.Vector3.from_two_points(wall_base, otherwall_base)
        tops = geo.Vector3.from_two_points(wall_top, otherwall_top)
        logic1 = 0.0 <= bases.length <= self.tolerance_m
        logic2 = 0.0 <= tops.length <= self.tolerance_m
        cases.append(logic1 or logic2)
        # 6 wall is completely within range
        logic1 = otherwall_base.z < wall_base.z + self.tolerance_m < wall_top.z - self.tolerance_m < otherwall_top.z
        logic2 = wall_base.z < otherwall_base.z + self.tolerance_m < otherwall_top.z - self.tolerance_m < wall_top.z
        cases.append(logic1 or logic2)

        return any(cases)

    def t_join_possible(self):
        def within_t_join_range(wall1, wall2):
            MIN_OVERLAP = 0.0005
            point_on_axis_x = wall2.local_transform.from_world_XYZ_to_local(
                mru.UnitConversion.Point3_to_XYZ(wall1.start_point_m)).x
            start_overlap = None
            end_overlap = None
            if point_on_axis_x < 0:
                start_overlap = abs(point_on_axis_x + wall1.width / 2.0)
                MSG = 'T point on axis is {}. T Overlap at start is {}'.format(point_on_axis_x,
                                                                      start_overlap)
            elif point_on_axis_x > 0:
                end_overlap = abs(point_on_axis_x - wall2.length - (wall1.width / 2.0))
                MSG = 'T point on axis is {}. T Overlap at end is {}'.format(point_on_axis_x,
                                                                      end_overlap)
            # print(MSG)
            return (MIN_OVERLAP - wall1.width / 2.0
                    < point_on_axis_x
                    < wall2.length + (wall1.width / 2.0) - MIN_OVERLAP)

        # Comprobamos que estamos dentro del rango de unión
        wall1, wall2 = self.wall, self.otherwall
        wall_to_otherwall = within_t_join_range(wall1, wall2)
        otherwall_to_wall = within_t_join_range(wall2, wall1)

        # Reverse joint possible?
        if not wall_to_otherwall:
            wall2, wall1 = self.wall, self.otherwall
            otherwall_to_wall = within_t_join_range(wall1, wall2)

        # Walls do not meet. OUTSIDE RANGE
        if not wall_to_otherwall and not otherwall_to_wall:
            # T Join out of range
            return False

        # Walls OVERLAP
        if wall_to_otherwall and otherwall_to_wall:
            intersection_result = mru.RvtSolidUtils.solid_solid_valid_intersection(self.wall.bounding_box_solid,
                                                                                   self.otherwall.bounding_box_solid)
            if intersection_result == 2:
                # Walls Touch
                pass
            else:
                print('Walls {} {} intersect. {}'.format(self.wall.rvt_element.Id.ToString(),
                                                         self.otherwall.rvt_element.Id.ToString(),
                                                         intersection_result))
                self.walls_intersect = True

        # Join is possible
        # REVERSED
        if self.wall.rvt_element.Id.IntegerValue != wall1.rvt_element.Id.IntegerValue:
            self.receiving_wall = self.wall
            self.joining_wall = self.otherwall
        else:  # STRAIGHT
            self.receiving_wall = self.otherwall
            self.joining_wall = self.wall

        return self.receiving_wall


class RvtWallUtils(object):
    @staticmethod
    def get_wall_faces(rvt_wall, detail_level=DB.ViewDetailLevel.Coarse):
        opt = DB.Options()
        opt.DetailLevel = detail_level
        for g in rvt_wall.get_Geometry(opt):
            if isinstance(g, DB.Solid):
                return [face for face in g.Faces]

    @staticmethod
    def get_exterior_faces(rvt_wall):
        references = DB.HostObjectUtils.GetSideFaces(rvt_wall, DB.ShellLayerType.Exterior)
        return [rvt_wall.GetGeometryObjectFromReference(ref) for ref in references]

    @staticmethod
    def get_interior_faces(rvt_wall):
        references = DB.HostObjectUtils.GetSideFaces(rvt_wall, DB.ShellLayerType.Interior)
        return [rvt_wall.GetGeometryObjectFromReference(ref) for ref in references]
