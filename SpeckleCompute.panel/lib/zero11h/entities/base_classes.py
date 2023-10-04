#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module holds the base Component classes for working in Revit with 011h Components

"""

__author__ = 'Iván Pajares [Modelical]'

# from typing import List, Set, Dict  # From python3
# from enum import Enum

# from six import raise_from  # Deleted
# True Fixed six module import error see: https://github.com/eirannejad/pyRevit/issues/584
# But failed again after reorganizing modules. Deleted raise_from

import copy
import itertools

import pprint as pp
import traceback
from pprint import pformat

import logging, os

import zero11h.rt as rt
import zero11h.geometry as geo
import zero11h.revit_api.revit_utils as mru
from zero11h.revit_api import System, DB, UI, _REVIT_DOCUMENT_, _WORKING_PHASE_
import zero11h.wall_utils as mwu
import zero11h.revit_api.extensible_storage as mes

log_path_components = __file__.split('\\')[:-3]
# log_path_components.append("DYN")
log_filepath = "\\".join(log_path_components)
log_name = 'Component_Debug.log'
# log = mut.setup_logger(log_filename=log_name,
#                        log_base_path=log_filepath,
#                        log_filemode='w')
#
# log.debug('Execution started')
log = logging.getLogger('ComponentsLog')
log.setLevel(logging.DEBUG)
handler = logging.FileHandler(os.path.join(log_filepath, log_name),
                              mode='w')

fmt = logging.Formatter('%(asctime)s -  %(levelname)s - %(message)s')
handler.setFormatter(fmt)
log.addHandler(handler)
log.info('----')
log.info('Running Components on {}'.format(_REVIT_DOCUMENT_.Title))
log.info('----')

# CONFIGURATION DATA

EXECUTION_UNITS_WORKSET = 'ARC_EXECUTION UNITS'
COMPONENTS_WORKSET = 'ARC_COMPONENTS'
DETAILING_WORKSET = 'WIP_DETAILING'  # TODO: Remove, redundant

# Worksets to come from RT All this to go to config file

TEMPLATE_WORKSETS = ['ARC_COMPONENTS',
                     'ARC_EXECUTION UNITS',
                     'ARC_EXTERNAL ENVELOPE',
                     'ARC_FIRE PROTECTION',
                     'ARC_INTERNAL PARTITION',
                     'STW_VERTICAL STRUCTURE']


# END CONFIGURATION DATA


class EnumLike(object):
    @classmethod
    def __iter__(cls):
        keys = [key for key in cls.__dict__.keys() if not key.startswith("__")]
        return iter([getattr(cls, key) for key in keys])

    @classmethod
    def get_enum_from_value(cls, value):
        for key in cls.__dict__.keys():
            if key.startswith("__"):
                continue
            if cls.__dict__[key] == value:
                return ConstructionSiteType.__getattribute__(ConstructionSiteType, key)
        return None


class ConstructionSiteType(EnumLike):
    ONO = 'Onsite'
    OFM = 'OffsiteManufactured'
    OFO = 'OffsiteOutsourced'


class PanelAdjacency(EnumLike):
    Both = 'Both'
    ComponentReferenceSide = 'ReferenceSide'  # Relative to component
    ComponentOtherSide = 'OtherSide'
    PanelInterior = 'PanelInterior'  # Relative to panel
    PanelExterior = 'PanelExterior'  # i.e. SATE points to exterior, interior would point to CLT. Same with TRS


class Zero11hTypes(EnumLike):
    Opening = 'Opening'
    Component = 'Component'
    Joint = 'Joint'
    LayerGroupInstance = 'LayerGroup'
    ExecutionUnitInstance = 'ExecutionUnit'


class EntityNomenclator:
    @staticmethod
    def set_execution_unit_id(panel, position, idx=0):
        """
        Nomenclatura EU

        2113-00.0001.01.00

        NUMINSTANCIA.SLOT.CORRELATIVO

        Nueva nomenclatura Emilie 21220117
        Cambiado sobre nomenclatura porque fallaba con componentes con EU divisbles en ambas caras.
        """
        return ('{}.{}.{}'.format(panel.parent_component.id_prefix, str(int(position + 1)).zfill(2),
                                  str(int(idx + 1)).zfill(2)))

    @staticmethod
    def set_layergroup_id(panel, position, idx=0):
        """
        IDEU.CORRELATIVO

        por ej: 2113-00.0001.03.01.01
        """
        return ('{}.{}'.format(panel.parent_id.split('_')[-1], str(int(position) + 1 + idx).zfill(2)))


class _BaseObject_(object):
    """
    Base property for all ipy classes to use in dynamo
    """

    def __init__(self):
        pass

    def ToString(self):
        return self.__repr__()


class JsonSerializer(object):
    """

    """

    def __init__(self, obj, self_guid=None):
        self.obj = obj
        if self_guid:
            self.self_guid = self_guid
        else:
            self.guid = ''

    def serialize(self):
        if isinstance(self.obj, _Base3DPanel_):
            return self._Base3dPanel_serializer()
        else:
            return self.HorizontalPanel_serializer()
        # else:
        #     raise TypeError('No serializer found for {}'.format(type(self.obj)))

    def _Base3dPanel_serializer(self):
        """
        Specialized serializer for __Base3dPanel__ classes
        It creates a JSON version of the serializable data to be stored elsewhere

        :return: json string
        """
        dikt = {}
        cls = self.obj
        # Serialize AttributeData
        ancestry = {'ParentComponentGuid': cls.parent_component.rvt_element.UniqueId,
                    'SelfGuid': self.self_guid}

        # Serialize GeometryData
        # for pname, pvalue in cls.__dict__.items():
        #     if pvalue is None:
        #         continue
        #     if isinstance(pvalue, geo.Point3) or isinstance(pvalue, geo.Vector3):
        #         dikt[pname] = [pvalue.x, pvalue.y, pvalue.z]
        dikt['u'] = cls.face_local_cs.basisx.to_triplet()
        dikt['v'] = cls.face_local_cs.basisy.to_triplet()
        dikt['uv_origin'] = cls.face_local_cs.origin.to_triplet()
        dikt['p2'] = (cls.length, cls.height, 0.0)
        dikt['local_z'] = [cls.reference_face_normal.X,
                           cls.reference_face_normal.Y,
                           cls.reference_face_normal.Z]

        dikt['interior_center'] = [cls.interior_center.x,
                                   cls.interior_center.y,
                                   cls.interior_center.z]

        dikt['exterior_center'] = [cls.exterior_center.x,
                                   cls.exterior_center.y,
                                   cls.exterior_center.z]
        dikt['is_mirrored'] = cls.is_mirrored
        return {'ParentComponentGuid': cls.parent_component.rvt_element.UniqueId,
                'LayerGroupMetadata': {'IsPanelizable': False,
                                       'IsFrameable': False,
                                       'GeometryData': dikt,
                                       'LayerTypeData': False,
                                       'JoinData': {},
                                       'RegisterData': {'start_register': False,
                                                        'end_register': False},
                                       'PerforatorData': {}}
                }
        # return json.dumps({'LayerGroupMetadata': {'AncestryData': ancestry,
        #                                           'GeometryData': dikt,
        #                                           'LayerTypeData': False,
        #                                           'JoinData': False,
        #                                           'RegisterData': False,
        #                                           'PerforatorData': False}})

    def HorizontalPanel_serializer(self):
        dikt = {}
        cls = self.obj
        return {'ParentComponentGuid': cls.parent_component.rvt_element.UniqueId}


class _BaseWall_(_BaseObject_):
    """
    https://jeremytammik.github.io/tbc/a/0038_wall_layers.htm

    """

    def __init__(self, rvt_element):
        """

        Args:
            rvt_element:
        """
        self.rvt_element = rvt_element
        self.eid = self.rvt_element.Id.IntegerValue
        self.rvt_type = mru.get_rvt_element_type(self.rvt_element)
        self.instance_parameters = mru.PyParameterSet(self.rvt_element)
        self.type_parameters = mru.PyParameterSet(self.rvt_type)
        # local basis X es el vector startpoint a endpoint. Es la direcciï¿½n del muro
        self.local_vx = geo.Vector3(self.end_point_m.x - self.start_point_m.x,
                                    self.end_point_m.y - self.start_point_m.y,
                                    self.end_point_m.z - self.start_point_m.z)
        self.local_vy = geo.Vector3(0, 0, 1)
        self.local_vz = self.local_vx.cross(self.local_vy)
        self.local_cs = geo.CoordinateSystem3(self.start_point_m,
                                              self.local_vx,
                                              self.local_vy,
                                              self.local_vz)
        self.width = mru.UnitConversion.feet_to_m(self.rvt_element.WallType.Width)
        self.front_faces = None
        self.back_faces = None
        self.exterior_faces = None
        self.interior_faces = None
        self.top_faces = None
        self.bottom_faces = None
        self.compute_faces()

    @property
    def has_edited_profile(self):
        elem_filter = DB.ElementIsElementTypeFilter(True)
        dependent_elements = [_REVIT_DOCUMENT_.GetElement(eid)
                              for eid in self.rvt_element.GetDependentElements(elem_filter)]
        return len([element
                    for element in dependent_elements
                    if isinstance(element, DB.SketchPlane)]) > 0

    @property
    def has_walljoins_enabled(self):
        return (DB.WallUtils.IsWallJoinAllowedAtEnd(self.rvt_element, 0) is True or
                DB.WallUtils.IsWallJoinAllowedAtEnd(self.rvt_element, 1) is True)

    @property
    def length(self):
        return mru.UnitConversion.feet_to_m(self.rvt_element.Location.Curve.Length)

    @property
    def unconnected_height(self):
        return mru.UnitConversion.feet_to_m(self.instance_parameters.builtins['WALL_USER_HEIGHT_PARAM'].value)

    @property
    def height(self):
        """
        Nos devuelve la altura mï¿½xima del muro aunque tenga ediciones, etc.

        """
        try:
            # This will fail if no top horizontal face is found. Resort to unconnected height
            # TODO: calculate max height from vertices
            topmost_point_z = max([mru.UnitConversion.feet_to_m(face.Evaluate(DB.UV(0.5, 0.5)).Z)
                                   for face in self.top_faces])
            bottommost_point_z = min([mru.UnitConversion.feet_to_m(face.Evaluate(DB.UV(0.5, 0.5)).Z)
                                      for face in self.bottom_faces])
        except Exception as ex:
            # raise RuntimeError('Cannot get height for wall {}'.format(self.rvt_element.Id.ToString()))
            print('Wall {} has bottom or top face not horizontal. Returning unconnected height')
            return self.unconnected_height
        # topmost_point_zz = max([self.local_transform.from_world_XYZ_to_local(face.Evaluate(DB.UV(0.5, 0.5))).y
        #                         for face in self.top_faces])
        #
        # bottommost_point_zz = min([self.local_transform.from_world_XYZ_to_local(face.Evaluate(DB.UV(0.5, 0.5))).y
        #                            for face in self.bottom_faces])
        return topmost_point_z - bottommost_point_z  # , abs(topmost_point_zz) + abs(bottommost_point_zz)

    @property
    def location_line(self):
        return System.Enum.GetName(DB.WallLocationLine,
                                   self.instance_parameters.builtins['WALL_KEY_REF_PARAM'].value)

    @property
    def location_line_offset(self):
        """
        Only for walls as panels in curtain walls
        """
        return self.instance_parameters.builtins['WALL_LOCATION_LINE_OFFSET_PARAM'].value

    @property
    def base_offset(self):
        return mru.UnitConversion.feet_to_m(
            self.rvt_element.get_Parameter(mru.BuiltInParameter.WALL_BASE_OFFSET).AsDouble())

    @property
    def top_offset(self):
        return mru.UnitConversion.feet_to_m(
            self.rvt_element.get_Parameter(mru.BuiltInParameter.WALL_TOP_OFFSET).AsDouble())

    @property
    def local_transform(self):
        """
        The local transform's origin accounts for base offset

        :return:
        """
        tf = mru.Transform.Identity
        tf.BasisX = mru.UnitConversion.Point3_to_XYZ(self.local_vx.normalized()).Normalize()
        tf.BasisY = mru.UnitConversion.Point3_to_XYZ(self.local_vy.normalized()).Normalize()
        tf.BasisZ = mru.UnitConversion.Point3_to_XYZ(self.local_vz.normalized()).Normalize()
        tf.Origin = mru.UnitConversion.Point3_to_XYZ(self.start_point_m.translate(self.local_vy * self.base_offset))
        return mru.RvtTransform(tf)

    @property
    def start_point_m(self):
        # Siempre alineado al centro del muro y sobre la location line
        # no tiene en cuenta el base offset
        return mru.UnitConversion.XYZ_to_Point3(self.rvt_element.Location.Curve.GetEndPoint(0))

    @property
    def end_point_m(self):
        return mru.UnitConversion.XYZ_to_Point3(self.rvt_element.Location.Curve.GetEndPoint(1))

    def _get_wall_edge(self, exterior=True):
        flag = 1
        if self.rvt_element.Flipped:
            flag = -1
        if exterior:
            ext = -1
        else:
            ext = 1
        move_vector = self.local_vz * (self.width / 2.0) * flag * ext  # our local_vz points to interior
        x, y, z = geo.vect3_add(self.start_point_m, move_vector)
        p1 = geo.Point3(x, y, z)
        x, y, z = geo.vect3_add(self.end_point_m, move_vector)
        p2 = geo.Point3(x, y, z)
        return mru.LineBounded(p1.translate(self.local_vy * self.base_offset),
                               p2.translate(self.local_vy * self.base_offset))

    @property
    def exterior_edge(self):
        return self._get_wall_edge(exterior=True)

    @property
    def exterior_face_local_normal(self):
        if self.rvt_element.Flipped:
            return geo.Vector3(0.0, 0.0, 1.0)
        return geo.Vector3(0.0, 0.0, -1.0)

    @property
    def interior_edge(self):
        return self._get_wall_edge(exterior=False)

    def extend_start(self, length_m):
        move_vector = self.local_vx.normalized() * length_m * -1
        x, y, z = geo.vect3_add(self.start_point_m, move_vector)
        new_p = geo.Point3(x, y, z)
        self.rvt_element.Location.Curve = mru.Line.CreateBound(mru.UnitConversion.Point3_to_XYZ(new_p),
                                                               self.rvt_element.Location.Curve.GetEndPoint(1))
        self.compute_faces()

    def extend_end(self, length_m):
        move_vector = self.local_vx.normalized() * length_m
        x, y, z = geo.vect3_add(self.end_point_m, move_vector)
        new_p = geo.Point3(x, y, z)
        self.rvt_element.Location.Curve = mru.Line.CreateBound(self.rvt_element.Location.Curve.GetEndPoint(0),
                                                               mru.UnitConversion.Point3_to_XYZ(new_p))
        self.compute_faces()

    def compute_faces(self):
        wall_faces = mwu.RvtWallUtils.get_wall_faces(self.rvt_element)
        front, back, top, bottom = [], [], [], []
        for face in wall_faces:
            try:
                facenormal = face.FaceNormal
            except Exception as ex:
                continue
            if face.FaceNormal.AngleTo(mru.UnitConversion.Point3_to_XYZ(self.local_vx)) < 0.01:
                front.append(face)
            elif face.FaceNormal.AngleTo(mru.UnitConversion.Point3_to_XYZ(-self.local_vx)) < 0.01:
                back.append(face)
            elif face.FaceNormal.AngleTo(mru.UnitConversion.Point3_to_XYZ(self.local_vy)) < 0.01:
                top.append(face)
            elif face.FaceNormal.AngleTo(mru.UnitConversion.Point3_to_XYZ(-self.local_vy)) < 0.01:
                bottom.append(face)
        self.front_faces = front
        self.back_faces = back
        self.exterior_faces = mwu.RvtWallUtils.get_exterior_faces(self.rvt_element)
        self.interior_faces = mwu.RvtWallUtils.get_interior_faces(self.rvt_element)
        self.top_faces = top
        self.bottom_faces = bottom

    @property
    def bounding_box_solid(self):
        """
        Crear un Solid que sea la bounding box orientada del muro sin huecos para poder testear cosas contra el

        :return:
        """
        return mru.RvtSolidUtils.create_rectangular_prism_at_point(self.length,
                                                                   self.height,
                                                                   self.width,
                                                                   transform=self.local_transform,
                                                                   local_origin_p3=geo.Point3(self.length / 2.0,
                                                                                              self.height / 2.0,
                                                                                              0.0))

    def get_cutting_instances(self):
        # First a fast check
        all_cutting_instances = mru.RvtSubcomponents.get_openings_from_instance(self.rvt_element, filtered=False)
        origin_points = [el.Location.Point for el in all_cutting_instances]
        trf_to_local = [self.local_transform.from_world_XYZ_to_local(p) for p in origin_points]
        startpts = [p.translate(geo.Vector3(0, 0, -0.5)) for p in trf_to_local]
        endpts = [p.translate(geo.Vector3(0, 0, 0.5)) for p in trf_to_local]
        lines = [mru.Line.CreateBound(self.local_transform.from_local_to_world(stp),
                                      self.local_transform.from_local_to_world(enp)) for stp, enp in zip(startpts,
                                                                                                         endpts)]

        int_opts = mru.SolidCurveIntersectionOptions()

        cutting_instances = []
        not_cutting_instances = []
        for line, instance in zip(lines, all_cutting_instances):
            int_result = self.bounding_box_solid.IntersectWithCurve(line, int_opts)
            if int_result.SegmentCount > 0:
                cutting_instances.append(instance)
            else:
                not_cutting_instances.append(instance)

        # second check with solid intersection
        def get_subelements(elements=None):
            subelements = []
            for ele in elements:
                for eid in ele.GetSubComponentIds():
                    subelements.append(_REVIT_DOCUMENT_.GetElement(eid))
            return subelements

        def any_intersect(solids_list):
            for solid in solids_list:
                if mru.RvtSolidUtils.solid_solid_valid_intersection(solid, self.bounding_box_solid) > 0:
                    return True
            return False

        # get solids of instances and subelements and check if any intersect the wall bounding solid
        # TODO: add solid for openings with dimensions Width and Height driven to check instead of their geometry
        not_cutting_filtered = []
        for element in not_cutting_instances:
            subelements = [_REVIT_DOCUMENT_.GetElement(eid) for eid in element.GetSubComponentIds()]
            solids = mru.RvtSolidUtils.get_solids_from_instance(element, subcats_to_extract=[], filtered=False)
            if any_intersect(solids):
                cutting_instances.append(element)
                continue
            # now we check subelements
            for el in subelements:
                if any_intersect(mru.RvtSolidUtils.get_solids_from_instance(el, subcats_to_extract=[], filtered=False)):
                    cutting_instances.append(element)
                    continue

            not_cutting_filtered.append(element)

        return cutting_instances, not_cutting_filtered

    def uncut_not_cutting_instances(self):
        not_cutting = self.get_cutting_instances()[1]
        if not_cutting:
            [mru.InstanceVoidCutUtils.RemoveInstanceVoidCut(_REVIT_DOCUMENT_, self.rvt_element, el) for el in
             not_cutting]


class PanelFaceReferenceSystem(_BaseObject_):
    def __init__(self, reference_rvt_transform, local_origin):
        self.ref_tf = mru.RvtTransform(reference_rvt_transform)
        self.local_rvt_tf = self.ref_tf.rvt_transform.Identity
        self.local_rvt_tf.Origin = self.ref_tf.from_local_to_world(local_origin)
        self.local_rvt_tf.BasisX = self.ref_tf.rvt_transform.BasisX
        self.local_rvt_tf.BasisY = self.ref_tf.rvt_transform.BasisZ
        self.local_rvt_tf.BasisZ = self.ref_tf.rvt_transform.BasisY
        self.local_tf = mru.RvtTransform(self.local_rvt_tf)


class _Base3DPanel_(_BaseObject_):
    """
    Base 3d panel class for LayerGroups and ExecutionUnits

    All geometric properties transformed to its local coordinate system,
    which is parallel to the component's CS.

    """
    # pylint: disable=too-many-instance-attributes

    entity = 'Panel'

    def __init__(self, rvt_solid,
                 component,
                 id_=None,
                 parent=None,
                 orientation='Vertical'):

        self.id = id_
        self.orientation = orientation
        self.rvt_solid = rvt_solid
        assert self.rvt_solid, "Base3DPanel error for panel {}: No valid solid found".format(self.id)
        try:
            rvt_material = mru.RvtSolidUtils.get_material_from_solid(self.rvt_solid)
            self.material_name = rvt_material.Name
        except AttributeError as ex:
            # print(ex)
            # print(traceback.format_exc())
            self.material_name = 'NOT SET'

        self.parent_component = component
        self.parent = parent
        self.bounding_box3 = mru.get_bbox3_from_solid_and_cs(self.rvt_solid, self.parent_component.local_cs)
        self.entity_type = None
        self.slot = None
        # If is_mirrored, panel normal is facing other side, not reference side.
        self.is_mirrored = False  # This will be set when generating the component's structure
        self.on_reference_side = False  # Set when generating panel face
        self.has_subelements = False
        self.rvt_split_solids = []

        self.min_local_z = self.bounding_box3.p_min.z
        self.max_local_z = self.bounding_box3.p_max.z
        self.min_local_x = self.bounding_box3.p_min.x
        self.max_local_x = self.bounding_box3.p_max.x
        self.min_local_y = self.bounding_box3.p_min.y
        self.max_local_y = self.bounding_box3.p_max.y

        self.origin_relative_to_component = geo.Point3(self.bounding_box3.p_min.x,
                                                       self.bounding_box3.p_min.y,
                                                       self.bounding_box3.p_min.z)

        self.local_rvt_transform = self.get_local_rvt_transform(local_origin=self.origin_relative_to_component)
        self.compute_subdivisions()
        self.origin = mru.UnitConversion.XYZ_to_Point3(self.local_rvt_transform.Origin)
        self.local_vx = mru.UnitConversion.XYZ_to_Vector3(self.local_rvt_transform.BasisX)
        self.local_vy = mru.UnitConversion.XYZ_to_Vector3(self.local_rvt_transform.BasisZ)
        self.local_vz = mru.UnitConversion.XYZ_to_Vector3(self.local_rvt_transform.BasisY)
        self.local_cs = geo.CoordinateSystem3(self.origin, self.local_vx, self.local_vy, self.local_vz)
        self.face_local_tf = None
        self.face_local_cs = None
        self.back_face_local_tf = None
        self.back_face_local_cs = None
        self._generate_panel_face_cs()
        self.bounding_box3 = mru.get_bbox3_from_solid_and_cs(self.rvt_solid,
                                                             local_cs=self.face_local_cs)
        self.is_located = False
        self.localisation_data = PanelLocationData()

    @property
    def parent_id(self):
        return self.parent.id if self.parent else None

    def _generate_panel_face_cs(self):
        # TODO: cleanup and create helper class for face reference system
        # Determinamos si estamos en la cara de referencia del componente o en la otra cara
        # en el CS del componente Z positiva va en la dirección opuesta a cara de referencia
        bbox_min_point3 = geo.Point3(self.bounding_box3.p_min.x,
                                     self.bounding_box3.p_min.y,
                                     self.bounding_box3.p_min.z)
        bbox_max_point3 = geo.Point3(self.bounding_box3.p_max.x,
                                     self.bounding_box3.p_min.y,
                                     self.bounding_box3.p_max.z)
        if self.origin_relative_to_component.z <= 0.001:
            self.on_reference_side = True
            flip_vx = False
            origin_relative_to_component = bbox_min_point3
            backface_origin_relative_to_component = bbox_max_point3
        else:
            self.on_reference_side = False
            flip_vx = True
            origin_relative_to_component = bbox_max_point3
            backface_origin_relative_to_component = bbox_min_point3

        face_local_transform = self.get_local_rvt_transform(local_origin=origin_relative_to_component)
        back_face_local_transform = self.get_local_rvt_transform(local_origin=backface_origin_relative_to_component)
        origin = mru.UnitConversion.XYZ_to_Point3(face_local_transform.Origin)
        back_face_origin = mru.UnitConversion.XYZ_to_Point3(back_face_local_transform.Origin)
        if flip_vx:
            face_local_transform.BasisX = face_local_transform.BasisX.Negate()
            local_vx = mru.UnitConversion.XYZ_to_Vector3(face_local_transform.BasisX)
        else:
            local_vx = mru.UnitConversion.XYZ_to_Vector3(face_local_transform.BasisX)

        face_local_transform.BasisY = back_face_local_transform.BasisY = DB.XYZ(0, 0, 1)
        face_local_transform.BasisZ = face_local_transform.BasisX.CrossProduct(face_local_transform.BasisY).Negate()
        back_face_local_transform.BasisX = face_local_transform.BasisX.Negate()
        back_face_local_transform.BasisZ = face_local_transform.BasisZ.Negate()
        local_vy = mru.UnitConversion.XYZ_to_Vector3(DB.XYZ(0, 0, 1))
        local_vz = -local_vx.cross(local_vy)
        self.face_local_tf = mru.RvtTransform(face_local_transform)
        self.back_face_local_tf = mru.RvtTransform(back_face_local_transform)
        self.face_local_cs = geo.CoordinateSystem3(origin, local_vx, local_vy, local_vz)
        self.back_face_local_cs = geo.CoordinateSystem3(back_face_origin, -local_vx, local_vy, -local_vz)

    def is_point_on_panel_face(self):
        """
        Evaluates if a point is on the surface or outside
        Use Face.Project or Face.Evaluate etc.
        Use the actual face, not the layergroup panel (which is the bounding box)
        """
        pass

    def __repr__(self):
        try:
            type_id = self.entity_type.id
        except AttributeError as ex:
            type_id = 'NO TYPE'
        if self.is_mirrored:
            mirrored = 'is_mirrored'
        else:
            mirrored = ''

        return '{}:{} id:{} {}x{}x{} m {}'.format(self.entity,
                                                  type_id,
                                                  self.id,
                                                  self.length,
                                                  self.height,
                                                  self.thickness,
                                                  mirrored)

    def get_local_rvt_transform(self, local_origin=None):  # :  # -> mru.RvtTransform:
        """
        Creates a copy of parent component transform moved to Panel origin

        We keep parent component Y up coordinate system and Z to inside of component (pointing to other face)
        """
        tf = mru.RvtTransform(self.parent_component.local_rvt_transform)
        world_xyz_panel_origin = tf.from_local_to_world(local_origin)
        rvt_local_tf = tf.rvt_transform.Identity
        rvt_local_tf.Origin = world_xyz_panel_origin
        rvt_local_tf.BasisX = tf.rvt_transform.BasisX
        rvt_local_tf.BasisY = tf.rvt_transform.BasisY
        # rvt_local_tf.BasisZ = tf.rvt_transform.BasisX.CrossProduct(tf.rvt_transform.BasisY)
        rvt_local_tf.BasisZ = tf.rvt_transform.BasisZ

        return rvt_local_tf

    @property
    def length(self):  # -> float:
        return self.bounding_box3.size_x

    @property
    def height(self):  # -> float:
        return self.bounding_box3.size_y

    @property
    def thickness(self):  # -> float:
        return self.bounding_box3.size_z

    @property
    def net_area(self):  # -> float:
        return mru.UnitConversion.squarefeet_to_m2(
            mru.RvtSolidUtils.get_solid_face_area_from_normals(self.rvt_solid,
                                                               self.parent_component.local_cs.basisz))

    @property
    def gross_area(self):  # -> float:
        return self.length * self.height

    @property
    def volume(self):  # -> float:
        return mru.UnitConversion.cubicfeet_to_m3(self.rvt_solid.Volume)

    def compute_subdivisions(self):  # -> None:
        """Used to subdivide linings etc"""
        divided_solids = mru.RvtSolidUtils.split_solid_volumes(self.rvt_solid)
        if len(divided_solids) > 1:
            self.has_subelements = True
            self.rvt_split_solids = divided_solids

        return len(divided_solids)

    def duplicate(self):  # -> '_Base3DPanel_':
        return _Base3DPanel_(self.rvt_solid, self.parent_component, id_=None, parent=None)

    def local_point_to_model_xyz(self, point, metric=True):  # -> geo.Point3:
        """
        Returns a local point in world coordinates in metric Point3
        If we need to get a world cs xyz in api units we remove the unit conversion
        or add a UnitConversion.Point3_to_XYZ to the result

        :param point:
        :return:
        """
        xyz_from_local_point = mru.RvtTransform(self.local_rvt_transform).from_local_to_world(point)
        if metric:
            return mru.UnitConversion.XYZ_to_Point3(xyz_from_local_point)
        return xyz_from_local_point

    def model_xyz_to_local_point(self, revit_xyz):  # -> geo.Point3:
        return mru.RvtTransform(self.local_rvt_transform).from_world_XYZ_to_local(revit_xyz)

    @property
    def panel_center(self):  # -> revit XYZ
        return mru.UnitConversion.XYZ_to_Point3(self.face_local_tf.from_local_to_world(geo.Point3(self.length / 2.0,
                                                                                                  self.height / 2.0,
                                                                                                  self.thickness / 2.0)))

    @property
    def interior_center(self):  # -> revit XYZ, Point3
        # point on panel side pointing to component center or interior
        return mru.UnitConversion.XYZ_to_Point3(self.face_local_tf.from_local_to_world(geo.Point3(self.length / 2.0,
                                                                                                  self.height / 2.0,
                                                                                                  self.thickness)))

    @property
    def exterior_center(self):  # -> revit XYZ, Point3
        # point on panel side pointing out or away from component
        return mru.UnitConversion.XYZ_to_Point3(self.face_local_tf.from_local_to_world(geo.Point3(self.length / 2.0,
                                                                                                  self.height / 2.0,
                                                                                                  0.0)))

    @property
    def axis_points(self):
        """
        axis_points on panel ref face cs plane
        :return: [Point3]
        """
        origin = mru.UnitConversion.XYZ_to_Point3(self.face_local_tf.from_local_to_world(geo.Point3(0, 0, 0)))
        end = mru.UnitConversion.XYZ_to_Point3(self.face_local_tf.from_local_to_world(geo.Point3(self.length, 0, 0)))
        # origin = self.local_point_to_model_xyz(geo.Point3(0, 0, 0))
        # end = self.local_point_to_model_xyz(geo.Point3(self.length, 0, 0))
        return origin, end

    @property
    def center_axis_points(self):
        origin = mru.UnitConversion.XYZ_to_Point3(
            self.face_local_tf.from_local_to_world(geo.Point3(0, 0, self.thickness / 2.0)))
        end = mru.UnitConversion.XYZ_to_Point3(
            self.face_local_tf.from_local_to_world(geo.Point3(self.length, 0, self.thickness / 2.0)))
        return origin, end

    @property
    def reference_face_normal(self):
        """
        On a panel de reference face is the exterior one (normal pointing away from component)

        Returns Revit XYZ normal in model coordinates

        :return: XYZ()
        """
        # normal = self.local_rvt_transform.OfVector(DB.XYZ(0, 0, -1))
        # if self.is_mirrored:
        #     return normal.Negate()
        # return normal
        return self.face_local_tf.rvt_transform.BasisZ.Negate()

    @property
    def construction_site_type(self):
        return ConstructionSiteType.get_enum_from_value(self.entity_type.construction_site_type)

    @property
    def subcategory_name(self):
        """ Get the name of the subcategory.

        Returns:
            String : Name of the subcategory (ExecutionUnitsSubcategories or LayerGroupSubcategories enum).
        """
        gst_name = _REVIT_DOCUMENT_.GetElement(self.rvt_solid.GraphicsStyleId)
        if gst_name:
            return gst_name.Name
        return None

    @property
    def reference_face(self):
        """

        Returns: DB.Face

        """
        return mru.RvtSolidUtils.get_solid_face_from_normal(self.rvt_solid,
                                                            self.reference_face_normal)

    @property
    def back_face(self):
        return mru.RvtSolidUtils.get_solid_face_from_normal(self.rvt_solid,
                                                            self.reference_face_normal.Negate())


class LayerGroupInstance(_Base3DPanel_):
    entity = 'LayerGroup'

    @property
    def is_structural(self):
        return True if _REVIT_DOCUMENT_.GetElement(
            self.rvt_solid.GraphicsStyleId).Name == mru.LayerGroupSubcategories.VTS else False


class ExecutionUnitInstance(_Base3DPanel_):
    entity = 'ExecutionUnit'

    def __init__(self, rvt_solid,
                 component,
                 id_=None,
                 parent=None):
        self.mep_elements = []
        super(ExecutionUnitInstance, self).__init__(rvt_solid,
                                                    component,
                                                    id_=id_,
                                                    parent=parent)

    @property
    def attached_mep(self):
        """
        TODO: check orientation of MEP family
        Maybe create a ComponentAttachments class where we can store orientation an other relevant data?

        :return: List of MEP elements that intersect with EU solid
        """
        return []
        # return mru.RvtSolidUtils.get_intersecting_elements_with_solid(self.parent_component.attached_mep,
        #                                                               self.rvt_solid)

    @property
    def is_external_finish(self):
        return True if self.on_reference_side and _REVIT_DOCUMENT_.GetElement(
            self.rvt_solid.GraphicsStyleId).Name == mru.ExecutionUnitsSubcategories.VEI else False

    @property
    def is_structural(self):
        return True if _REVIT_DOCUMENT_.GetElement(
            self.rvt_solid.GraphicsStyleId).Name == mru.ExecutionUnitsSubcategories.VTS else False


class BaseComponent(_BaseObject_):
    """
    Base class for components. Only use it for inheritance. Do not instance it.
    """
    entity = 'BaseComponent'

    def __init__(self, rvt_element, all_data=False):  # all_data parameter after US5948
        self.rvt_element = rvt_element
        self.rvt_type = mru.get_rvt_element_type(self.rvt_element)
        self.instance_parameters = mru.PyParameterSet(self.rvt_element)
        self.type_parameters = mru.PyParameterSet(self.rvt_type)
        self.family_name = self.type_parameters.builtins['SYMBOL_FAMILY_NAME_PARAM'].value
        self.type_name = self.type_parameters.builtins['SYMBOL_NAME_PARAM'].value
        try:  # For two level based components
            base_level_id = self.rvt_element.get_Parameter(DB.BuiltInParameter.FAMILY_BASE_LEVEL_PARAM)
            self.rvt_level = _REVIT_DOCUMENT_.GetElement(base_level_id.AsElementId())
        except Exception as ex:
            self.rvt_level = _REVIT_DOCUMENT_.GetElement(self.rvt_element.LevelId)

        self.bldg_level = mru.BldgLevel(self.rvt_level)
        self.id = self.instance_parameters['EI_InstanceID'].value
        assert self.id, "Component ERROR: Empty EI_InstanceID {} for Revit ID:{}".format(self.id, self.rvt_element.Id)
        self.type_id = self.type_parameters['EI_TypeID'].value
        rt_ctype_data = rt.rt_request.get_component_types(ids=['{}'.format(self.type_id)],
                                                          model_type='full' if all_data else 'tree')
        # TODO: proper user understandable warnings for missing parameter data
        assert rt_ctype_data, "No ComponentType data from RT found for component EI_TypeID:{} with id:{}".format(
            self.type_id, self.rvt_type.Id)
        try:
            self.type_data = rt.ComponentType(rt_ctype_data[0])
        except IndexError:
            self.type_data = None
            raise IOError('No valid data for {}. Cannot instantiate component'.format(self.id))
        assert self.type_id == self.type_data.id, "Not valid ComponentType data:" \
                                                  "Cannot instantiate component {}".format(self.id)
        self.entity_type = self.type_data  # Por consistencia con LayerGroups y ExecutionUnits
        self.rvt_transform = self.rvt_element.GetTotalTransform()
        location = self.rvt_element.Location
        if isinstance(location, DB.LocationCurve):
            self.origin_feet = location.Curve.GetEndPoint(0)
        else:
            self.origin_feet = location.Point

        self.origin = mru.UnitConversion.XYZ_to_Point3(self.origin_feet)
        # If we want to cut or modify the solids we need to change this
        # We should get the solids the first time, and initalize the ComponentStructure
        # And if we modify any of the solids re-initialize it. May be dedicated method will do
        self.rvt_solids = mru.RvtSolidUtils.get_solids_from_instance(self.rvt_element)  # solids dict with subcat as key
        self.component_structure = None
        self._metadata = None

    def __repr__(self):  # -> str:
        return ('{} {}: '.format(self.entity, self.id) +
                '{}x'.format(self.bounding_box.length) +
                '{}x'.format(self.bounding_box.height) +
                '{} m'.format(self.bounding_box.thickness))

    def get_composition(self):
        """

        Returns: Ordered LayerGroup list of layergroup composition without subdivisions.
        Count == to LayerGroupTypes count

        """
        lg_type_ids = [lg_type.id for lg_type in self.type_data.layer_groups]
        res = []
        lg_type_idx = 0
        for lg in self.layer_groups:
            if lg.entity_type.id == lg_type_ids[lg_type_idx]:
                res.append(lg)
                if lg_type_idx < len(lg_type_ids) - 1:
                    lg_type_idx += 1
                else:
                    break
        return res

    @property
    def has_detailing(self):
        return len(self.metadata.detailing_guids) > 0

    def delete_subelements(self,
                           execution_units=False,
                           layer_groups=False,
                           detailing=False,
                           structural_connections=False):
        to_delete = []
        if execution_units:
            to_delete.extend(copy.copy(self.metadata.execution_unit_guids))
            self.metadata.execution_unit_guids = []
        if layer_groups:
            to_delete.extend(copy.copy(self.metadata.layer_group_guids))
            self.metadata.layer_group_guids = []
        if detailing:
            to_delete.extend(copy.copy(self.metadata.detailing_guids))
            self.metadata.detailing_guids = []
        if structural_connections:
            to_delete.extend(copy.copy(self.metadata.structural_connections_guids))
            self.metadata.structural_connections_guids = []
        if to_delete:
            mru.delete_elements_by_guidstr(to_delete)
            _REVIT_DOCUMENT_.Regenerate()

    @property
    def metadata(self):
        if self._metadata:
            return self._metadata
        # Create or update metadata. Requires transaction
        self._metadata = mes.ComponentMetadata(self.rvt_element)
        return self._metadata

    @property
    def bounding_box(self):  # -> _Base3DPanel_:
        """
        returns a _Base3DPanel_ with oriented solid bounding box of component

        NOTE: if SATE layer is overhanging the bounding box will be a bigger than the component
        """
        return _Base3DPanel_(mru.RvtSolidUtils.create_oriented_boundingbox_from_instance(self.rvt_element),
                             self, id_='ComponentBoundingBox')

    @property
    def bounding_box3(self):
        """
        returns a BoundingBox3 instance alignes to component's local_cs

        """
        return mru.get_bbox3_from_element(self.rvt_element,
                                          local_cs=self.local_cs,
                                          include_invisible=False)

    @property
    def local_rvt_transform(self):  # -> 'Transform':
        local_tf = self.rvt_transform.Identity
        local_tf.Origin = self.origin_feet
        local_tf.BasisX = self.rvt_transform.BasisX
        local_tf.BasisY = self.rvt_transform.BasisZ
        local_tf.BasisZ = self.rvt_transform.BasisY
        return local_tf

    @property
    def id_prefix(self):  # -> str:
        """
        Expected InstanceID structure: C_FAC-0001_2113-00.0001

        C _ Type _ Projcode-BldgNo . InstanceNo

        :return:
        """
        try:
            # return self.id.split('_')[1][0:].replace('.', '')
            # changed 220117 for new nomenclature from Emilie
            return self.id.split('_')[-1]
        except Exception as ex:
            raise Exception('Component Error: Invalid EI_InstanceID: "{}" for element with id {}. {}'.format(self.id,
                                                                                                             self.rvt_element.Id,
                                                                                                             ex))

    @property
    def ei_type(self):  # -> str:
        ei_type = self.type_parameters['EI_Type']
        return ei_type.value

    @property
    def local_cs(self):  # -> geo.CoordinateSystem3:
        return geo.CoordinateSystem3(self.origin, self.local_vx, self.local_vy, self.local_vz)

    @property
    def axis_points(self):
        """

        Returns startpoint and endpoint of component axis

        """
        plane = mru.get_plane_from_family_reference_by_name(self.rvt_element,
                                                            reference_name='Right')
        right = self.local_cs.transform_to_local(mru.UnitConversion.XYZ_to_Point3(plane.Origin))
        right.y, right.z = 0.0, 0.0
        local_startp = geo.Point3(0, 0, 0)
        local_endp = right
        return [mru.UnitConversion.XYZ_to_Point3(
            mru.RvtTransform(self.local_rvt_transform).from_local_to_world(point)
        ) for point in [local_startp, local_endp]]

    @property
    def center_axis_points(self):
        """
        Returns the VTS layer center axis points. We use the local CS and half thickness of VTS LayerGroup
        """
        location_center_lines = mru.get_lines_from_family_by_subcategory(self.rvt_element,
                                                                         subcat_name='Location Center Lines')
        if location_center_lines:
            location_center_line = location_center_lines[
                0]  # We get the first one. May be later we need better filtering
        else:
            raise Exception('Component.center_axis_points ERROR: no location center line found')
        assert isinstance(location_center_line.GetEndPoint(0), DB.XYZ), (
            'Component location center line not found. Check geometry.')
        local_location_center_line_start = mru.RvtTransform(self.local_rvt_transform).from_world_XYZ_to_local(
            location_center_line.GetEndPoint(0))
        reference_name = 'Right'
        plane = mru.get_plane_from_family_reference_by_name(self.rvt_element,
                                                            reference_name=reference_name)
        right = self.local_cs.transform_to_local(mru.UnitConversion.XYZ_to_Point3(plane.Origin))
        right.y, right.z = 0.0, local_location_center_line_start.z
        local_startp = geo.Point3(0, 0, local_location_center_line_start.z)
        local_endp = right
        return [mru.UnitConversion.XYZ_to_Point3(
            mru.RvtTransform(self.local_rvt_transform).from_local_to_world(point)
        ) for point in [local_startp, local_endp]]

    @property
    def reference_face_normal(self):
        return -self.local_vz

    @property
    def other_face_normal(self):
        return self.local_vz

    @property
    def execution_units(self):  # -> List[ExecutionUnitInstance]:
        if self.component_structure:
            return self.component_structure.execution_units
        return None

    @property
    def layer_groups(self):  # -> List[LayerGroupInstance]:
        if self.component_structure:
            return self.component_structure.layer_groups
        return None

    def _update_type_parameters(self):
        # Only update type if needed
        code = self.type_data.id
        description = self.type_data.description
        name = self.type_data.name
        try:
            ei_code_param = self.type_parameters['EI_TypeID']
            ei_descr_param = self.type_parameters['EI_Description']
            ei_name_param = self.type_parameters['EI_TypeName']
            ei_type_param = self.type_parameters['EI_Type']
            ei_short_id = self.type_parameters['EI_ShortID']  # US 3719
            ei_status = self.type_parameters['EI_Status']
            # if any([ei_type_param.value != self.entity,
            #         ei_code_param.value != code,
            #         ei_descr_param.value != description,
            #         ei_type_param.value != name]):
            ei_type_param.value = self.entity
            ei_code_param.value = code
            ei_descr_param.value = description
            ei_name_param.value = name
            ei_type_param.value = self.entity
            ei_short_id.value = self.type_data.short_id
            ei_status.value = self.type_data.status
        except Exception as ex:
            print('Component Type Parameters update ERROR')
            print(ex)

    def check_attached_openings(self):
        """
        This method checks that the openings attached to the component are actually cutting it.
        If not, it detaches them from it

        Returns: List[DB.FamilyInstance]  unattached openings
        """
        not_cutting_instances = set()
        openings = mru.RvtSubcomponents.get_openings_from_instance(self.rvt_element, filtered=False)
        if not openings:
            return []
        for opening in openings:
            # We need to check for opening alignment with component. If not, we are keeping openings perpendicular
            # to component in corner situations...
            opening_bb = mru.get_bbox3_from_element(opening, local_cs=self.local_cs, include_invisible=True)
            # Check that opening is correctly aligned to component, i.e. perpendicular to axis
            opening_is_aligned = mru.UnitConversion.XYZ_to_Vector3(opening.FacingOrientation).almost_parallel(
                self.reference_face_normal)
            if not self.bounding_box3.intersects(opening_bb) or not opening_is_aligned:
                not_cutting_instances.add(opening)

        return list(not_cutting_instances)

    def remove_unattached_openings(self):
        unattached_openings = self.check_attached_openings()
        if unattached_openings and not _REVIT_DOCUMENT_.IsModifiable:
            UI.TaskDialog.Show('Openings ERROR',
                               'Component {} has errors with the following openings:\n{}\nPlease review model'.format(
                                   self.id,
                                   '\n'.join(
                                       [str(op.Id.IntegerValue)
                                        for op in
                                        unattached_openings])))
            return
            raise RuntimeError('ERROR with component {} openings. Fix before instantiating'.format(self.id))

        uncut = []
        for unattached in unattached_openings:
            DB.InstanceVoidCutUtils.RemoveInstanceVoidCut(_REVIT_DOCUMENT_,
                                                          self.rvt_element,
                                                          unattached)
            uncut.append(unattached.Id.IntegerValue)
        if uncut:
            # Regenerate component solids
            _REVIT_DOCUMENT_.Regenerate()
            self.rvt_solids = mru.RvtSolidUtils.get_solids_from_instance(self.rvt_element)
            UI.TaskDialog.Show('Openings WARNING',
                               'Component {}. These openings where uncut from Component:\n{}\nPlease review model'.format(
                                   self.id,
                                   '\n'.join(
                                       [str(id) for id in uncut])))


class PanelLocator(_BaseObject_):
    """
    Creates an array of points around the panel with a configurable offset
    This points are then tested again model rooms to create a list of adjacent
    rooms to the panel.

    See: https://www.revitapidocs.com/2022/1fbe1cff-ed94-4815-564b-05fd9e8f61fe.htm
    """

    def __init__(self, panel,
                 probe_height=1.0,
                 probe_density=1.2,
                 offset_from_panel_face=0.05,
                 adjacency=PanelAdjacency.Both,
                 phase=_WORKING_PHASE_,
                 room_code_parameter='RI_RoomCode',
                 room_type_parameter='RI_RoomType',
                 area_code_parameter='RI_AreaCode',
                 probe_only_panel_center=False):
        self.panel = panel
        self.probe_only_panel_center = probe_only_panel_center
        c_offset = self.panel.parent_component.rvt_element.get_Parameter(
            DB.BuiltInParameter.INSTANCE_FREE_HOST_OFFSET_PARAM).AsDouble()
        self.component_has_offset = (c_offset < -0.01 or c_offset > 0.01)
        if probe_height < self.panel.height * 0.8:
            self.probe_height = probe_height
        else:
            self.probe_height = self.panel.height / 2
        self.offset = offset_from_panel_face
        self.probe_phase = phase
        self.subdivisions = int(round(self.panel.length / probe_density))
        self.adjacency = adjacency
        self.ends_offset = 0.1
        self.rooms = set()
        self.room_code_parameter = room_code_parameter
        self.area_code_parameter = area_code_parameter
        self.room_type_parameter = room_type_parameter

    def _subdivided_points(self, z_pos):
        # Working on panel exterior face CS (face_local_tf)
        # we need exterior and interior faces offset
        if self.probe_only_panel_center:
            return [geo.Point3(self.panel.length / 2.0,
                               self.probe_height,
                               z_pos)]
        midpoints = [geo.Point3(x, self.probe_height, z_pos)
                     for x in [(1 + n) * self.panel.length / self.subdivisions
                               for n in range(self.subdivisions - 1)]
                     ]
        start = geo.Point3(0.0 + self.ends_offset,
                           self.probe_height,
                           z_pos)
        end = geo.Point3(self.panel.length - self.ends_offset,
                         self.probe_height,
                         z_pos)

        return [start] + midpoints + [end]

    @property
    def interior_points(self):  # -> geo.Point3:  This are other side probe points
        if self.adjacency == PanelAdjacency.PanelExterior:
            return []
        z_pos = self.panel.thickness + self.offset
        return self._subdivided_points(z_pos)

    @property
    def exterior_points(self):  # Reference side points
        if self.adjacency == PanelAdjacency.PanelInterior:
            return []
        z_pos = 0.0 - self.offset
        return self._subdivided_points(z_pos)

    def _get_probe_points(self):
        """
        When component has offset we add top and bottom points to find rooms above or below also in contact with it
        """
        analysis_points = self.exterior_points + self.interior_points
        if self.component_has_offset:
            old_probe_height = self.probe_height
            self.probe_height = 0.1
            analysis_points = self.exterior_points + self.interior_points
            self.probe_height = self.panel.height - 0.1
            analysis_points.extend(self.exterior_points + self.interior_points)
            self.probe_height = old_probe_height
        return [self.panel.face_local_tf.from_local_to_world(point)
                for point in analysis_points]

    @property
    def probe_xyz_world_cs(self):
        """
        Used in Dynamo for debugging probe positions
        """
        return [mru.UnitConversion.XYZ_to_Point3(xyz)
                for xyz in self._get_probe_points()]

    @property
    def adjacent_rooms(self):
        if self.rooms:
            return self.rooms
        room_ids = set()
        for p in self._get_probe_points():
            room = _REVIT_DOCUMENT_.GetRoomAtPoint(p, self.probe_phase)
            if room:
                rid = room.Id.ToString()
                if rid not in room_ids:
                    self.rooms.add(room)
                    room_ids.add(rid)
        return self.rooms

    def get_fac_room_code(self):
        """ For SATE location"""
        self.fac_probes_xyz = []
        probe_location_point = geo.Point3(self.panel.length / 2.0, self.probe_height, -1)
        left_v = geo.Vector3(1, 0, -1).normalize()
        right_v = geo.Vector3(-1, 0, -1).normalize()
        probe_left = probe_location_point.translate(left_v)
        probe_right = probe_location_point.translate(right_v)
        max_probe_length = 70
        probe_points = [probe_left, probe_location_point, probe_right]
        while abs(probe_location_point.z) < max_probe_length:
            for p in probe_points:
                room = _REVIT_DOCUMENT_.GetRoomAtPoint(
                    self.panel.face_local_tf.from_local_to_world(p),
                    self.probe_phase)
                self.fac_probes_xyz.append(self.panel.face_local_tf.from_local_to_world(p))
                if room:
                    if room.LookupParameter(self.room_type_parameter).AsString() == 'FAC':
                        return room.LookupParameter(self.room_code_parameter).AsString()
            probe_left = probe_points[0].translate(left_v)
            probe_right = probe_points[2].translate(right_v)
            probe_location_point.z -= 1
            probe_points = [probe_left, probe_location_point, probe_right]

        return

    def get_room_codes(self, ordered=True):  # -> str
        room_numbers = [room.LookupParameter(self.room_code_parameter).AsString()
                        # changed from builtins['ROOM_NUMBER']
                        for room in self.adjacent_rooms
                        if room.LookupParameter(self.room_code_parameter).HasValue]
        if not room_numbers:
            return ''
        return '_'.join(sorted(room_numbers))

    def get_room_area_codes(self):
        # We increase offset to probe through any linings
        if not self.get_room_codes():
            return ''

        area_codes = '_'.join(sorted(
            {room.LookupParameter(self.area_code_parameter).AsString() for room in self.adjacent_rooms if
             room.LookupParameter(self.area_code_parameter).HasValue}))

        return area_codes

    def get_location_data(self):

        if self.panel.entity == 'LayerGroup':
            # As ExecutionUnits are processed first this should be OK
            return self.panel.parent.localisation_data

        if self.panel.entity == 'ExecutionUnit':
            if self.panel.is_external_finish:
                return PanelLocationData(room_codes=self.get_fac_room_code(),
                                         area_codes='')

            if self.panel.is_structural:
                return PanelLocationData(
                    room_codes=self.panel.parent_component.instance_parameters['EI_LocalisationCodeRoom'].value,
                    area_codes=self.panel.parent_component.instance_parameters['EI_LocalisationCodeArea'].value)

            self.adjacency = PanelAdjacency.PanelExterior
            return PanelLocationData(room_codes=self.get_room_codes(),
                                     area_codes=self.get_room_area_codes())

        return PanelLocationData(room_codes=self.get_room_codes(),
                                 area_codes=self.get_room_area_codes())

    def __repr__(self):
        return 'PanelLocator for panel {}'.format(self.panel)


class PanelLocationData(_BaseObject_):
    def __init__(self,
                 room_codes='',
                 area_codes='',
                 level=''):
        self._localisation_room_codes = room_codes
        self._localisation_area_codes = area_codes
        self._level_name = None

    @property
    def localisation_room_codes(self):
        return self._localisation_room_codes if self._localisation_room_codes else ''

    @property
    def localisation_area_codes(self):
        return self._localisation_area_codes if self._localisation_area_codes else ''

    @property
    def localisation_level_name(self):
        return self._level_name if self._level_name else ''

    @localisation_level_name.setter
    def localisation_level_name(self, level_name):
        self._level_name = level_name

    def __repr__(self):
        return 'Panel location data. Rooms:{} Areas:{} Level:{}'.format(self.localisation_room_codes,
                                                                        self.localisation_area_codes,
                                                                        self.localisation_level_name)


class BasePanelReference(object):
    def __init__(self, basepanel=None, basepanel_reference_point3=None):
        """
        basepanel: _BasePanel3d_
        basepanel_reference: Point3 in local panel coordinates
        """
        self.basepanel = basepanel
        self.reference_point3 = basepanel_reference_point3  # i.e.: wall.start_point_m

    @property
    def reference_name(self):
        """
        Asumimos la BasePanel face transform. Así la referencia es local a la cara y no al componente
        De esta forma podemos trabajar con LG por ambas caras del componente de manera consistente
        """
        startp = geo.Point3(0, 0, 0)
        endp = geo.Point3(self.basepanel.length, 0, 0)
        # project to ref cs
        self.reference_point3.y = 0
        self.reference_point3.z = 0
        dist_to_startp = geo.Vector3.from_two_points(self.reference_point3, startp).length
        dist_to_endp = geo.Vector3.from_two_points(self.reference_point3, endp).length
        if dist_to_startp < dist_to_endp:
            return "start point"
        return "end point"


class PanelFaceReference(_BaseObject_):
    def __init__(self, layergroup=None, revit_xyz=None):
        self.layergroup = layergroup
        self.revit_xyz = revit_xyz

    @property
    def point_on_reference_face(self):
        if not self.layergroup or not self.revit_xyz:
            return False
        project_result = self.layergroup.reference_face.Project(self.revit_xyz)
        if not project_result:
            return False
        if project_result.XYZPoint and project_result.Distance < 0.01:
            return True
        return False

    @property
    def point_on_back_face(self):
        if not self.layergroup or not self.revit_xyz:
            return False
        project_result = self.layergroup.back_face.Project(self.revit_xyz)
        if not project_result:
            return False
        if project_result.XYZPoint and project_result.Distance < 0.01:
            return True
        return False


class BaseJoint():
    ''' 
    Base class for all joint families (vertical & horizontal).

    Provides properties and methods shared by all joint objects.
      '''

    def __init__(self):
        self._rvt_element = None
        self._parent = None
        self._children = []
        self._joined_components = None
        self._is_parent = None
        self._joint_type = None
        self._id = None
        self._perforator = None

    @property
    def rvt_element(self):
        """ The revit family instance associated with this object.
        
            Returns:
                Revit FamilyInstance object. 
        """
        return self._rvt_element

    @rvt_element.setter
    def rvt_element(self, value):
        self._rvt_element = value

    @property
    def parent(self):
        """ Children joints will have one parent joint. 
        
            Returns:
                A joint object. 
        """
        return self._parent

    @parent.setter
    def parent(self, value):
        self._parent = value

    @property
    def children(self):
        """ Parent joints will have one or more children. 
        
            Returns:
                A list of joint objects. 
        """
        return self._children

    @children.setter
    def children(self, value):
        self._children = value

    @property
    def joined_components(self):
        """ A list of two or more components that form this joint. 
        
        Returns:
            A list of component objects.
        """
        return self._joined_components

    @joined_components.setter
    def joined_components(self, value):
        self._joined_components = value

    @property
    def is_parent(self):
        """A joint object can be a parent or a child.

        Returns:
            A boolean that describes this condition.
        """
        return self._is_parent

    @is_parent.setter
    def is_parent(self, value):
        self._is_parent = value

    @property
    def joint_type(self):
        """ Used to categorize the joint (L, T, END, etc.).

        Set this property with an EnumLike object.

        Returns:
            The joint type
        """
        return self._joint_type

    @joint_type.setter
    def joint_type(self, value):
        self._joint_type = value

    @property
    def id(self):
        """ Unique identifier for the joint. Format: <PJ.V-0000>

        Returns:
            str: The identifier
        """
        return self._id

    @id.setter
    def id(self, value):
        self._id = value

    @property
    def perforator(self):
        """ Optional perforator element

        Returns:
            str: The revit FamilyInstance
        """
        return self._perforator

    @perforator.setter
    def perforator(self, value):
        self._perforator = value

    def save_metadata(self):
        """Save all required data to extensible storage.
        
        Saves:
        - parent GUID (if it's a child)
        - children GUIDs (if it's a parent)
        - joined component GUIDs
        """
        element_meta = mes.JointMetadata(self.rvt_element)
        # Save parent or child ids
        if self.is_parent:
            guids = [child.rvt_element.UniqueId for child in self.children]
            element_meta.children_guids = guids

            # Save parent GUID to perforator
            if self.perforator:
                perforator_meta = mes.PerforatorMetadata(self.perforator)
                perforator_meta.joint_guid = self.rvt_element.UniqueId

        else:  # it's a child
            element_meta.parent_guid = self.parent.rvt_element.UniqueId
        # Save joined components
        component_guids = [comp.rvt_element.UniqueId for comp in self.joined_components]
        element_meta.component_guids = component_guids
