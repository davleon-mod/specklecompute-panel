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

from pprint import pformat

import zero11h.geometry as geo
import zero11h.revit_api.revit_utils as mru
from zero11h.revit_api import System, DB, UI, _REVIT_DOCUMENT_
from zero11h.revit_api.revit_utils import PROJECT_INFORMATION
import zero11h.revit_api.extensible_storage as mes

from .base_classes import (_BaseObject_, _Base3DPanel_, JsonSerializer, log,
                           BaseComponent, LayerGroupInstance, ExecutionUnitInstance, PanelLocator,
                           _WORKING_PHASE_, EntityNomenclator, PanelAdjacency, PanelLocationData,
                           Zero11hTypes, PanelFaceReference)

from .openings import OpeningInstance, MEPBoxInstance

MS_APP_BOOLEAN_PARAMNAMES_VALUES = {'MS_OverConcrete': 'OC',
                                    'MS_NoFloor': 'NF',
                                    'MS_NoRoof': 'NR',
                                    'MS_HoldDown': 'HD',
                                    'Lower_Acoustic_Band': 'LE',
                                    'Top_Acoustic_Band': 'TE'}
AUX_TRS_CUTTING_FAMILYNAME = 'AUX_TRS_Perforator'
MEP_BOX_LOD350_FAMILY_NAME = 'GMO_MEPBox_v3'
TRS_DISCRIMINATOR = 'TRS'

DEBUG = False


def filter_by_family_names(rvt_family_instance, family_name=None, invert=False):
    cond = rvt_family_instance.Symbol.FamilyName == family_name
    if invert:
        cond = rvt_family_instance.Symbol.FamilyName != family_name
    return True if cond else False


class ComponentGeometry(_BaseObject_):
    """
    This class allows us to access component geometry available without instancing it (ie. not calling RT)

    """

    def __init__(self, rvt_element):
        self.rvt_element = rvt_element
        self.rvt_level = _REVIT_DOCUMENT_.GetElement(self.rvt_element.LevelId)
        self.rvt_type = mru.get_rvt_element_type(self.rvt_element)
        self.id = self.rvt_element.LookupParameter('EI_InstanceID').AsString()
        self.rvt_transform = self.rvt_element.GetTotalTransform()
        location = self.rvt_element.Location
        if isinstance(location, DB.LocationCurve):
            self.origin_feet = location.Curve.GetEndPoint(0)
            self.origin = mru.UnitConversion.XYZ_to_Point3(self.origin_feet)
        else:
            self.origin_feet = location.Point
            self.origin = mru.UnitConversion.XYZ_to_Point3(self.origin_feet)
        self.local_vx = mru.UnitConversion.XYZ_to_Vector3(self.rvt_transform.BasisX)
        self.local_vy = mru.UnitConversion.XYZ_to_Vector3(self.rvt_transform.BasisZ)
        # local_vz is pointing inside, flip it and you get ext / reference face
        self.local_vz = mru.UnitConversion.XYZ_to_Vector3(self.rvt_transform.BasisY)
        self.thickness = self.rvt_element.LookupParameter('TotalWidth').AsDouble()
        self.length = self.rvt_element.LookupParameter('TotalLength').AsDouble()
        self.height = self.rvt_element.LookupParameter('TotalHeight').AsDouble()
        top_offset = self.rvt_element.LookupParameter('TopStructuralFloor_Height_m')
        if top_offset:
            self.height -= top_offset.AsDouble()
        self.bldg_level = mru.BldgLevel(self.rvt_level)

    @property
    def rvt_level_offset(self):
        """
        Instance offset from level. Applies to point based family instances.

        Returns: Float (feet)

        """
        return self.rvt_element.get_Parameter(DB.BuiltInParameter.INSTANCE_ELEVATION_PARAM).AsDouble()

    @property
    def base_rvt_level(self):
        """
        Returns Base Level for two level based family instances

        Returns: DB.Level

        """
        try:
            return _REVIT_DOCUMENT_.GetElement(
                self.rvt_element.get_Parameter(DB.BuiltInParameter.FAMILY_BASE_LEVEL_PARAM).AsElementId())
        except AttributeError:
            return None

    @property
    def base_rvt_level_offset(self):
        """
        Returns Base Level offset for two level based family instances

        Returns: Float (feet)

        """
        try:
            return self.rvt_element.get_Parameter(DB.BuiltInParameter.FAMILY_BASE_LEVEL_OFFSET_PARAM).AsDouble()
        except AttributeError:
            return None

    @property
    def top_rvt_level(self):
        """
        Returns Top Level for two level based family instances

        Returns: DB.Level

        """
        try:
            return _REVIT_DOCUMENT_.GetElement(
                self.rvt_element.get_Parameter(DB.BuiltInParameter.FAMILY_TOP_LEVEL_PARAM).AsElementId())
        except AttributeError:
            return None

    @property
    def top_rvt_level_offset(self):
        """

        Returns Top Level offset for two level based family instances

        Returns: Float (feet)

        """
        try:
            return self.rvt_element.get_Parameter(DB.BuiltInParameter.FAMILY_TOP_LEVEL_OFFSET_PARAM).AsDouble()
        except AttributeError:
            return None

    @property
    def local_rvt_transform(self):  # -> 'Transform':
        local_tf = self.rvt_transform.Identity
        local_tf.Origin = self.origin_feet
        local_tf.BasisX = self.rvt_transform.BasisX
        local_tf.BasisY = self.rvt_transform.BasisZ
        local_tf.BasisZ = self.rvt_transform.BasisY
        return local_tf

    @property
    def local_cs(self):  # -> geo.CoordinateSystem3:
        return geo.CoordinateSystem3(self.origin, self.local_vx, self.local_vy, self.local_vz)

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
    def component_hash(self):
        """

        Returns: int hash of component. It is sensible to geometrical changes around 0.5mm

        """
        def get_3_sig_digits(float_number, round_digits=3):
            number = round(abs(float_number), round_digits)
            int_part, dec_part = str(number).split('.')
            res = int_part + dec_part.ljust(round_digits, '0')
            return res

        def _hash_solid(solid, parent_component_geometry):
            vertices = [
                mru.UnitConversion.XYZ_to_Point3(parent_component_geometry.local_rvt_transform.Inverse.OfPoint(pt)) for
                pt in mru.RvtSolidUtils.get_solid_vertices(solid)]
            distances = round(sum([geo.vect3_length_sqrd(pt) for pt in vertices]), 3)
            centroid = geo.Point3(sum([p[0] for p in vertices]) / len(vertices),
                                  sum([p[1] for p in vertices]) / len(vertices),
                                  sum([p[2] for p in vertices]) / len(vertices))
            vtx_count = len(vertices)
            hs1 = int(get_3_sig_digits(centroid[0])) << vtx_count
            hs2 = int(get_3_sig_digits(centroid[1])) << vtx_count
            hs3 = int(get_3_sig_digits(centroid[2])) ^ vtx_count
            hs4 = int(get_3_sig_digits(distances, round_digits=1))
            hsh = (hs1) ^ (hs2) ^ (hs3) ^ (hs4)
            return hsh

        hashes = []
        for sl in mru.RvtSolidUtils.get_all_solids_from_instance(self.rvt_element):
            hashes.append(_hash_solid(sl, self))

        for idx, item in enumerate(hashes):
            if idx == 0:
                hsh = item
            else:
                hsh = hsh ^ item
        component_hash = hash('{}_{}'.format(self.rvt_type.LookupParameter('EI_TypeID').AsString(), hsh))
        return component_hash

    @property
    def openings(self):
        return sorted([element
                       for idx, element in
                       enumerate(mru.RvtSubcomponents.get_openings_from_instance(self.rvt_element))
                       ],
                      key=lambda opening: mru.RvtTransform(self.local_rvt_transform).from_world_XYZ_to_local(
                          opening.Location.Point).x,
                      reverse=False)

    @property
    def cuts(self):
        return [gm_cut for gm_cut in mru.RvtSubcomponents.get_openings_from_instance(self.rvt_element,
                                                                                     filtered=True,
                                                                                     builtin_cat_list=[
                                                                                         DB.BuiltInCategory.OST_GenericModel])
                if DB.InstanceVoidCutUtils.IsVoidInstanceCuttingElement(gm_cut)]


class ComponentReferences(_BaseObject_):
    pass


class ComponentMEP(_BaseObject_):
    """
    Helper class to operate with component's attached MEP
    """

    def __init__(self, rvt_element,
                 parent_component=None):
        self.rvt_element = rvt_element
        self.parent_component = parent_component
        self.geometry = ComponentGeometry(rvt_element=self.rvt_element)

    @property
    def attached_mep(self):
        """

        """
        mep_boxes_in_component = []
        for element in mru.RvtNearbyElements.get_nearby_elements(self.rvt_element,
                                                                 [DB.BuiltInCategory.OST_GenericModel]):
            try:
                if element.Symbol.FamilyName != MEP_BOX_LOD350_FAMILY_NAME:
                    continue
            except Exception as ex:
                continue

            mep_box_local_origin = self.geometry.local_cs.transform_to_local(
                mru.UnitConversion.XYZ_to_Point3(element.Location.Point))
            bb = self.geometry.bounding_box3
            bb.expand(distance=0.005)
            if bb.contains(mep_box_local_origin):
                mep_boxes_in_component.append(element)

        if not mep_boxes_in_component:
            return []

        mep_boxes = [MEPBoxInstance(rvt_element=element,
                                    parent=self.parent_component if self.parent_component else None,
                                    position=idx) for idx, element in enumerate(mep_boxes_in_component)]

        return sorted(mep_boxes,
                      key=lambda mepbox: mru.RvtTransform(
                          self.geometry.local_rvt_transform).from_world_XYZ_to_local(
                          mepbox.rvt_element.Location.Point).x,
                      reverse=False)


class Component(BaseComponent):
    """
    geometric_references: list of reference planes in component family relevant for us
    bounding_box: _base3dpanel_ instance of rvt_solid bounding box

    Instantiating a vertical component means:
    execute __init__ of super BaseComponent
    instantiate a ComponentStructure
        This creates ComponentSlots for solids in family per subcategory
        each slot is generated around a BasePanel from a solid, each solid has a known subcategory


    """
    entity = 'Component'

    # pylint: disable=too-many-instance-attributes
    def __init__(self, rvt_element, all_data=False):  # -> None:
        super(Component, self).__init__(rvt_element, all_data=all_data)
        self.component_geometry = ComponentGeometry(rvt_element)
        self.is_two_level_based = True if self.component_geometry.top_rvt_level else False
        # Check if component had previous detailing CLT and Structural Connections
        if self.has_detailing:
            existing_stc_cuts = ComponentMetadataUtils.get_existing_stc_cutting_elements_if_previous_clt(self)
            if existing_stc_cuts:
                self.metadata.structural_connections_guids = [element.UniqueId
                                                              for element in existing_stc_cuts]
        # Local CS definition
        self.local_vx = mru.UnitConversion.XYZ_to_Vector3(self.rvt_transform.BasisX)
        self.local_vy = mru.UnitConversion.XYZ_to_Vector3(self.rvt_transform.BasisZ)
        # local_vz is pointing inside, flip it and you get ext / reference face
        self.local_vz = mru.UnitConversion.XYZ_to_Vector3(self.rvt_transform.BasisY)
        assert not self.rvt_element.Mirrored, "Component ERROR: {} with Revit ID:{} is MIRRORED".format(self.id,
                                                                                                        self.rvt_element.Id)
        self.attached_mep = []
        self.get_attached_mep()
        self.remove_unattached_openings()
        self.component_structure = ComponentStructure(self)
        self.openings = [OpeningInstance(rvt_element=element,
                                         parent=self,
                                         position=idx)
                         for idx, element in enumerate(self.component_geometry.openings)
                         ]
        self.cuts = self.component_geometry.cuts
        self.is_located = False
        self._location_data = None
        self.is_structural = False if 'NO STRUCTURAL' in self.rvt_type.FamilyName else True
        self.thickness = self.instance_parameters['TotalWidth'].value  # confuso que estemos en unidades de la API
        self.length = self.instance_parameters['TotalLength'].value
        self.height = self.instance_parameters['TotalHeight'].value
        top_offset = self.instance_parameters.get_value('TopStructuralFloor_Height_m')
        if top_offset:
            self.height -= top_offset
        if _REVIT_DOCUMENT_.IsModifiable:
            self._update_dimension_parameters()
            self._update_type_parameters()
            self._update_ms_application_parameters()
            self.update_openings_parameters()
            self.update_mepboxes_parameters()

    @property
    def auxiliary_cuts(self):
        return [cut for cut in self.cuts if filter_by_family_names(cut, family_name=AUX_TRS_CUTTING_FAMILYNAME)]

    @property
    def perforators(self):
        return [cut for cut in self.cuts if filter_by_family_names(cut,
                                                                   family_name=AUX_TRS_CUTTING_FAMILYNAME,
                                                                   invert=True)]

    def _update_dimension_parameters(self):
        self.instance_parameters['QU_Length_m'] = self.length
        self.instance_parameters['QU_Height_m'] = self.height
        self.instance_parameters['QU_Thickness_m'] = self.thickness
        self.instance_parameters['QU_Volume_m3'] = mru.UnitConversion.m3_to_cubicfeet(self.bounding_box.volume)

    def _update_ms_application_parameters(self):  # US3927
        app_params = []
        for pname in MS_APP_BOOLEAN_PARAMNAMES_VALUES.keys():
            try:
                if self.instance_parameters[pname].value == 1 or self.instance_parameters[pname].value == True:
                    app_params.append(MS_APP_BOOLEAN_PARAMNAMES_VALUES[pname])
            except ValueError:
                pass

        ms_application_parameter_string = ','.join(sorted(app_params, reverse=True))
        if not ms_application_parameter_string:
            return
        self.instance_parameters['MS_ApplicationParameter'] = ms_application_parameter_string

    def update_openings_parameters(self):
        for opening in self.openings:
            opening.update_parameters()

    def update_mepboxes_parameters(self):
        for mepbox in self.attached_mep:
            mepbox.update_mepbox()
            mepbox.locate()
            mepbox.update_parameters()

    # def get_openings(self):
    #     return self.component_geometry.openings

    def get_attached_mep(self):
        """
        May be a more correct approach would be that Component only has the property attached_mep and a
        Component MEP handler has the responsibility to fill that in
        MEP components have normal, hand vector, etc. we have to check that against component reference face
        """
        comp_mep = ComponentMEP(self.rvt_element,
                                parent_component=self)
        self.attached_mep = comp_mep.attached_mep

    def locate_component(self, relocate=False):
        if not self._location_data or relocate:
            self._location_data = PanelLocator(self.bounding_box).get_location_data()
            if self._location_data.localisation_area_codes:
                # We locate the component in the lowest floor of its areas
                self._location_data.localisation_level_name = self._location_data.localisation_area_codes.split('.')[0]
            else:
                if '_' in self.rvt_level.Name:
                    self._location_data.localisation_level_name = self.rvt_level.Name.split('_')[-1]
                else:
                    self._location_data.localisation_level_name = self.rvt_level.Name
            building_code = PROJECT_INFORMATION['BI_BuildingCode'].value
            if building_code:
                self._location_data.localisation_level_name = '{}_{}'.format(building_code,
                                                                             self._location_data.localisation_level_name)
        # else:
        #     room_codes = self._location_data.localisation_room_codes
        #     area_codes = self._location_data.localisation_area_codes
        #     self._location_data.localisation_level_name = self._location_data.localisation_level_name

        self.instance_parameters['EI_LocalisationCodeRoom'] = self._location_data.localisation_room_codes
        self.instance_parameters['EI_LocalisationCodeArea'] = self._location_data.localisation_area_codes
        self.instance_parameters['EI_LocalisationCodeFloor'] = self._location_data.localisation_level_name
        self.is_located = True


class ComponentMetadataUtils(_BaseObject_):
    @staticmethod
    def get_existing_clt_detailing_element(component):
        # Asumimos un solo CLT, en caso de varios habrá que desarrollar más esto
        existing_in_model = [_REVIT_DOCUMENT_.GetElement(guid) for guid in component.metadata.detailing_guids
                             if _REVIT_DOCUMENT_.GetElement(guid) is not None]
        if not existing_in_model:
            return None
        str_framing_elements = [element for element in existing_in_model
                                if element.Category.Id == DB.Category.GetCategory(_REVIT_DOCUMENT_,
                                                                                  DB.BuiltInCategory.OST_StructuralFraming).Id]
        if str_framing_elements:
            return str_framing_elements[0]
        return None

    @staticmethod
    def get_existing_stc_cutting_elements_if_previous_clt(component):
        """
        We check if previous detailing element CLT existed and had STC cutting
        """
        clt = ComponentMetadataUtils.get_existing_clt_detailing_element(component)
        if not clt:
            return []
        return [_REVIT_DOCUMENT_.GetElement(eid) for eid in DB.InstanceVoidCutUtils.GetCuttingVoidInstances(clt)
                if _REVIT_DOCUMENT_.GetElement(eid).Category.Id == DB.Category.GetCategory(_REVIT_DOCUMENT_,
                                                                                           DB.BuiltInCategory.OST_StructConnections).Id]

    @staticmethod
    def get_lg_direct_shape_by_id(component=None, lg_id=None):
        direct_shapes = [_REVIT_DOCUMENT_.GetElement(guid_str) for guid_str in component.metadata.layer_group_guids if
                         guid_str]
        for ds in direct_shapes:
            ds_id = ds.LookupParameter('EI_InstanceID').AsString()
            if ds_id == lg_id:
                return ds
        return None


class ComponentSlot(_BaseObject_):
    """
    A ComponentSlot is a vertical poliedric volume that can host
    ExecutionUnits and LayerGroups
    """

    # pylint: disable=too-many-instance-attributes

    entity = 'ComponentSlot'

    def __init__(self, panel, position):  # -> None:
        self.panel = panel
        self._children = set()
        self.parent = None
        self.id = self.panel.id
        self.thickness = self.panel.thickness
        self.position = position
        self.start = self.panel.min_local_z
        self.middle = self.start + self.thickness / 2
        self.end = self.panel.max_local_z
        self.subelements = self.get_subelements()

    @property
    def children(self):  # -> 'List[ComponentSlot]':
        """
        Slot children refer to LayerGroups inside ExecutionUnits.
        For example:
        VTS EU with CLT + FPP will have two LG children
        The children are returned ordered by their relative position in the component layers
        The first being the outermost
        """
        return sorted(self._children, key=lambda x: x.position, reverse=False)

    def add_child(self, slot):  # -> None:
        self._children.add(slot)

    def get_subelements(self):  # -> List[ExecutionUnitInstance]:
        """
        Slot sublements are split volumes on the long axis of the slot
        For example, linings cut by perpendicular walls

        We process subelements only at ExecutionUnit level. LayerGroups are non divisible
        """
        if not self.panel.has_subelements or self.panel.entity == 'LayerGroup':
            return []
        xslot = {}
        for solid in self.panel.rvt_split_solids:
            subpanel = ExecutionUnitInstance(solid, self.panel.parent_component, id_=self.id)
            xslot[int(1000 * subpanel.min_local_x)] = subpanel
        subelements_list = []

        for key in sorted(xslot.keys()):
            subelements_list.append(xslot[key])
        return subelements_list

    def __repr__(self):  # -> str:
        if self.subelements:
            return ('Slot in position {} st/mid/end {}:{}:{} '.format(self.position,
                                                                      round(self.start, 4),
                                                                      round(self.middle, 4),
                                                                      round(self.end, 4)) +
                    ' {} '.format(self.panel.material_name) +
                    'Subcategory: {}'.format(self.id) +
                    ' has subelements {}'.format(self.subelements))
        return ('Slot in position {} st/mid/end {}:{}:{} '.format(self.position,
                                                                  round(self.start, 4),
                                                                  round(self.middle, 4),
                                                                  round(self.end, 4)) +
                ' {} '.format(self.panel.material_name) +
                'Subcategory: {}'.format(self.id))

    def duplicate_as_layergroup(self):  # -> 'ComponentSlot':
        """
        This method duplicates a slot and its panel changing its entity type to LayerGroup
        This is used to create non modelled LayerGroups from ExecutionUnits, for example
        the external insulation layer (SATE)
        """
        new_panel = self.panel.duplicate()
        new_panel.__class__ = LayerGroupInstance
        return ComponentSlot(new_panel, self.position)


class ComponentStructure(_BaseObject_):
    """
    Mapping class to work with the EU & LG hierarchy

    we input a Component class and creates the mapping and relationships between EU and LG

    """
    entity = 'ComponentStructure'

    def __init__(self, component):
        self.component = component
        # might need to be a property if we need to recalculate it
        self.execution_unit_slots = self._get_slots(mru.ExecutionUnitsSubcategories)
        self.layer_group_slots = self._get_slots(mru.LayerGroupSubcategories)
        self._log_debug_data()
        self._set_parents_and_children()
        self.execution_unit = []
        self.layer_groups = []
        # We populate EU and LG or raise exception if fail
        self._get_executionunits_layergroups()

    def _log_debug_data(self):
        log.debug('Component {} ExecutionUnit data'.format(self.component.id))
        log.debug('\n' + pformat(self.execution_unit_slots))
        log.debug('RT Data:')
        log.debug('\n' + pformat(self.component.type_data.execution_units))
        log.debug('Component {} LayerGroup data'.format(self.component.id))
        log.debug('\n' + pformat(self.layer_group_slots))
        log.debug('RT Data:')
        log.debug('\n' + pformat(self.component.type_data.layer_groups))

    @property
    def are_model_eu_correct(self):  # -> bool:
        """
        Checks if model materials are aligned with RT data
        """
        if DEBUG:
            for slot, eu in zip(self.execution_unit_slots, self.component.type_data.execution_units):
                try:
                    print('slot:##{}##\nRT  :##{}##'.format(slot.panel.material_name, eu.id))
                except Exception as ex:
                    print
                    ex
                    print
                    slot.panel, slot.panel.id
        return all([slot.panel.material_name == eu.id
                    for slot, eu in zip(self.execution_unit_slots,
                                        self.component.type_data.execution_units)])

    @property
    def are_model_lg_correct(self):  # -> bool:
        rt_layer_group_types = [lg.id for lg in self.component.type_data.layer_groups]
        if DEBUG:
            for slot in self.layer_group_slots:
                print
                rt_layer_group_types
                print(slot.panel.material_name, slot.panel.material_name in rt_layer_group_types)
        return all([slot.panel.material_name in rt_layer_group_types
                    for slot in self.layer_group_slots])

    def _create_panel_z_position_dict(self,
                                      solid_list,  # : List[DB.Solid]
                                      slots_dict,  # : Dict[int, _Base3DPanel_]
                                      subcat_name,
                                      entity_class):  # -> List[Dict[int, _Base3DPanel_]]:
        for solid in solid_list:
            solid_panel = _Base3DPanel_(solid, self.component, id_=subcat_name)
            solid_panel.__class__ = entity_class
            slots_dict[int(1000 * solid_panel.min_local_z)] = solid_panel
        return slots_dict

    def _get_slots(self, entity_enum):  # -> List[ComponentSlot]:
        """
        returns an ordered list of slots based on local z position
        Note that this method works with the actual solids modeled in the family

        usage: self._get_slots(mru.ExecutionUnitsSubcategories)
        """
        panels_dict = {}
        if entity_enum == mru.ExecutionUnitsSubcategories:
            entity_class = ExecutionUnitInstance
        else:
            entity_class = LayerGroupInstance

        for subcat, solid_list in self.component.rvt_solids.items():
            if subcat in [enum_item for enum_item in entity_enum.__iter__()]:
                panels_dict = self._create_panel_z_position_dict(solid_list,
                                                                 panels_dict,
                                                                 subcat,
                                                                 entity_class)

        ordered_slots = []
        position = 0  # Position 0 starts on external / reference side
        for _, value in sorted(panels_dict.items()):
            ordered_slots.append(ComponentSlot(value, position))
            position += 1

        return ordered_slots

    def _get_eu_slot_from_lg_slot(self, lg_slot):  # -> ComponentSlot:
        """
        If the supplied LayerGroup Slot is within an ExecutionUnit Slot it returns it
        Used to determine de parent relationship of LayerGroups towards ExecutionUnits

        :param lg_slot: ComponentSlot
        :return: ComponentSlot
        """
        for slot in self.execution_unit_slots:
            if slot.start < lg_slot.middle < slot.end:
                return slot
        return None

    def _set_parents_and_children(self):  # -> None:
        for layer_group_slot in self.layer_group_slots:
            parent_execution_unit_slot = self._get_eu_slot_from_lg_slot(layer_group_slot)
            if parent_execution_unit_slot:
                layer_group_slot.parent = parent_execution_unit_slot
                parent_execution_unit_slot.add_child(layer_group_slot)
        # Now we reset positions index start to 0 for layergroup children
        for eu_slot in self.execution_unit_slots:
            position = 0
            for lg_slot in eu_slot.children:
                lg_slot.position = position
                position += 1

    def _model_lg_panels(self):
        """
        Ojo porque estoy mutando items de una lista y esto es un code smell de libro
        """
        output = []

        for lg_slot in self.layer_group_slots:
            eu_slot = lg_slot.parent
            eu_type = self.component.type_data.execution_units[eu_slot.position]
            try:
                lg_type = eu_type.layer_group_types[lg_slot.position]
            except IndexError as ex:
                raise IndexError(
                    "ComponentStructure: wrong number of LayerGroups " +
                    "for ExecutionUnit {} in component {}.\n{}".format(eu_type.id, self.component.id, ex))

            assert lg_type, 'Failed LayerGroup type for {}'.format(lg_slot)
            lg_slot.panel.entity_type = lg_type
            lg_slot.panel.parent = eu_slot.panel
            lg_slot.panel.id = EntityNomenclator.set_layergroup_id(lg_slot.panel, lg_slot.position)
            lg_slot.panel.is_mirrored = lg_type.is_mirrored
            lg_slot.panel.slot = lg_slot
            output.append(lg_slot.panel)

        return output

    def _report_wrong_eu_lg(self):
        mask = [slot.panel.material_name == eu.id for slot, eu in
                zip(self.execution_unit_slots,
                    self.component.type_data.execution_units)]

        errors = []
        for slot, eu, m_bool in zip(self.execution_unit_slots,
                                    self.component.type_data.execution_units, mask):
            if not m_bool:
                errors.append(('Family: {}'.format(slot.panel.material_name), eu.id))

        log.error('Component Structure Error. Id: {}'.format(self.component.id))
        log.error(self.execution_unit_slots)
        log.error('RT Data:')
        log.error(self.component.type_data.execution_units)
        log.error('Error data')
        log.error(mask)
        log.error(errors)
        raise RuntimeError(
            'ComponentStructure Error. {} execution unit data is incorrect. '.format(self.component.id) +
            'Please review material names of EU and EU type data in RT {}'.format(errors))

    def _get_executionunits_layergroups(self):  # -> None:
        if self.are_model_eu_correct and self.are_model_lg_correct:
            eu_panels = []
            lg_panels = []
            log.debug('_get_executionunits_layergroups for component {}'.format(self.component.id))
            if len(self.execution_unit_slots) != len(self.component.type_data.execution_units):
                msg = 'Component {} execution unit count is incorrect. Please review RT data'.format(self.component.id)
                log.error(msg)
                raise RuntimeError(msg)

            for slot in self.execution_unit_slots:
                eu_type = self.component.type_data.execution_units[slot.position]
                log.debug('ExecutionUnit of Type {}'.format(eu_type))
                # Tomamos la primera LG de la EU pero la usaremos o no
                # según esté modelada la LG en el modelo o no
                # Si está modelada - ver más adelante - ignoramos esta lg_type
                lg_type = eu_type.layer_group_types[0]
                log.debug('LayerGroupType is {}'.format(lg_type))
                # TODO: crear ids internos para EU y LG y luego aplicarles nomenclatura
                # De esta forma desacoplamos los cambios de nomenclatura de los ids?
                if not slot.subelements:  # Execution Units that are not subdivided
                    slot.panel.parent = self.component
                    slot.panel.entity_type = eu_type
                    slot.panel.slot = slot
                    slot.panel.id = EntityNomenclator.set_execution_unit_id(slot.panel,
                                                                            slot.position)
                    eu_panels.append(slot.panel)

                    if slot.children:  # Esto significa que tiene LG modeladas
                        continue

                    new_panel = slot.panel.duplicate()
                    new_panel.parent = slot.panel
                    new_panel.entity_type = lg_type
                    new_panel.id = EntityNomenclator.set_layergroup_id(new_panel, 0)  # slot.position)
                    new_panel.__class__ = LayerGroupInstance
                    lg_panels.append(new_panel)

                else:  # Instantiation of subdivided EU's LayerGroups
                    for idx, panel in enumerate(slot.subelements):
                        msg = 'subelement on slot {} with entity type {}'.format(slot.id, lg_type)
                        log.debug(msg=msg)
                        panel.parent = self.component
                        panel.entity_type = eu_type
                        panel.slot = slot
                        panel.id = EntityNomenclator.set_execution_unit_id(panel, slot.position,
                                                                           idx=idx)  # slot.position, idx=idx)
                        eu_panels.append(panel)

                        new_panel = panel.duplicate()
                        new_panel.parent = panel
                        new_panel.entity_type = lg_type
                        new_panel.__class__ = LayerGroupInstance
                        new_panel.id = EntityNomenclator.set_layergroup_id(new_panel, 0)
                        lg_panels.append(new_panel)
                        msg = 'END--subelement--'
                        log.debug(msg=msg)

            # Final step: iterate over modeled LayerGroups and create their panels
            lg_panels.extend(self._model_lg_panels())

            self.execution_units = eu_panels
            self.layer_groups = sorted(lg_panels, key=lambda x: (round(x.origin_relative_to_component.z, 3),
                                                                 x.id))
            return

        self._report_wrong_eu_lg()

    def to_revit_elements(self):
        # -> DB.DirectShape:
        # TODO: refactor and clarify. Too many things happening
        # Store active workset
        wks_table = _REVIT_DOCUMENT_.GetWorksetTable()
        active_wks_id = wks_table.GetActiveWorksetId()
        # Delete all component subelements if present as they need to be regenerated
        self.component.delete_subelements(execution_units=True,
                                          layer_groups=True,
                                          detailing=True,
                                          structural_connections=False)

        # Update component parameters as we are in a Transaction at this point
        # This should move to a method
        self.component.instance_parameters['IfcName'] = '{}_{}'.format(
            self.component.type_parameters['EI_TypeID'].value,
            self.component.type_parameters['EI_TypeName'].value)
        self.component.type_parameters['EI_Type'] = 'Component'

        direct_shapes = []
        all_panels = self.execution_units + self.layer_groups

        execution_unit_guids = []
        layer_group_guids = []

        if not self.component.is_located:
            self.component.locate_component()

        # TODO: check for orphan DirectShapes and delete them
        for panel in all_panels:
            # Change to ExecutionUnits workset
            eu_wks = mru.WorksetUtils.get_workset_by_name(panel.entity_type.workset)  # US4720 & 4721
            if not eu_wks:
                raise RuntimeError(
                    'to_revit_elements ERROR: Workset {} not found for {}'.format(panel.entity_type.workset,
                                                                                  panel.entity_type.id))
            wks_table.SetActiveWorksetId(eu_wks.Id)
            ds_type = mru.RvtDirectShape.get_dstype_byname(panel.entity_type.id)
            ds = mru.RvtDirectShape.ds_from_solid_wdstype(panel.rvt_solid, panel.id, dstype=ds_type)
            self.update_parameters(ds, ds_type, panel)

            if panel.entity == 'ExecutionUnit':
                self.update_mep(panel)
                eu_metadata = mes.ElementMetadata(ds)
                eu_metadata.parent_component_guid = self.component.rvt_element.UniqueId
                execution_unit_guids.append(ds.UniqueId)

            # Metadata for LayerGroups
            if panel.entity == 'LayerGroup':
                # _REVIT_DOCUMENT_.Regenerate()
                data_dict = JsonSerializer(panel, self_guid=ds.UniqueId).serialize()
                lg_metadata = mes.LayerGroupMetadata(ds)
                lg_metadata._update_metadata_property('LayerGroupMetadata', data_dict['LayerGroupMetadata'])
                lg_metadata.parent_component_guid = self.component.rvt_element.UniqueId
                layer_group_guids.append(ds.UniqueId)

            direct_shapes.append(ds)

        # Write eu and lg guids to component metadata
        self.component.metadata.execution_unit_guids = execution_unit_guids
        self.component.metadata.layer_group_guids = layer_group_guids
        self.component.metadata.component_hash = self.component.component_geometry.component_hash
        self.component.instance_parameters['EI_Hash'] = self.component.component_geometry.component_hash
        # Reset active workset back
        wks_table.SetActiveWorksetId(active_wks_id)

        return direct_shapes

    def update_parameters(self, ds, ds_type, panel):
        # type parameters
        log.debug("updating parameters for panel {}".format(panel.id))

        # Instance and Type ParameterSets
        direct_shape_instance_parameters = mru.PyParameterSet(ds)
        direct_shape_type_parameters = mru.PyParameterSet(ds_type)
        parent_component_pset = mru.PyParameterSet(self.component.rvt_element)

        # TODO: extract all parameter names to an interface class for maintainability
        # Type Parameters
        direct_shape_type_parameters['EI_Type'] = panel.entity
        direct_shape_type_parameters['EI_TypeID'] = "{}_{}".format(panel.entity_type.id.split('_')[0],
                                                                   panel.entity_type.id.split('_')[1])
        direct_shape_type_parameters['EI_TypeName'] = panel.entity_type.name
        direct_shape_type_parameters['EI_Description'] = panel.entity_type.description
        direct_shape_type_parameters['EI_011hClassCode'] = panel.entity_type.class_code
        direct_shape_type_parameters['NameOverride'] = panel.entity_type.id
        direct_shape_type_parameters['IfcExportAs'] = 'IfcWall'
        direct_shape_type_parameters['EI_ShortID'] = panel.entity_type.short_id  # US 3719 & 5207

        # Instance Parameters
        direct_shape_instance_parameters['EI_InstanceID'] = panel.id
        direct_shape_instance_parameters['EI_HostComponentInstanceID'] = self.component.id
        direct_shape_instance_parameters['EI_HostComponentType'] = self.component.type_id
        # direct_shape_instance_parameters['EI_ParentID'] = panel.parent_id <- removed 10/3/2022
        direct_shape_instance_parameters['QU_GrossArea_m2'] = mru.UnitConversion.m2_to_squarefeet(panel.gross_area)
        direct_shape_instance_parameters['QU_Area_m2'] = mru.UnitConversion.m2_to_squarefeet(panel.net_area)
        direct_shape_instance_parameters['QU_Length_m'] = mru.UnitConversion.m_to_feet(panel.length)
        direct_shape_instance_parameters['QU_Height_m'] = mru.UnitConversion.m_to_feet(panel.height)
        direct_shape_instance_parameters['QU_Thickness_m'] = mru.UnitConversion.m_to_feet(panel.thickness)
        direct_shape_instance_parameters['QU_Volume_m3'] = mru.UnitConversion.m3_to_cubicfeet(panel.volume)
        # direct_shape_instance_parameters['QU_Weight_kg'] = 2000.0  # Removed as it will be handled by DATA
        direct_shape_instance_parameters['IfcExportAs'] = 'IfcWall'
        direct_shape_instance_parameters['IfcName'] = panel.entity_type.id

        # We locate first EU panels and then LG
        panel.localisation_data = PanelLocator(panel).get_location_data()
        direct_shape_instance_parameters['EI_LocalisationCodeRoom'] = panel.localisation_data.localisation_room_codes
        direct_shape_instance_parameters['EI_LocalisationCodeArea'] = panel.localisation_data.localisation_area_codes

        # Copy parent component instance parameters
        param_names = ['EI_LocalisationCodeFloor',
                       'MS_ApplicationParameter']
        #  'SC_PlanningZone'] <- removed 10/3/2022

        for pname in param_names:
            try:
                direct_shape_instance_parameters[pname] = parent_component_pset[pname].value
            except ValueError:
                pass

        if panel.entity == 'LayerGroup':
            parent_id = panel.parent_id
            if parent_id:
                direct_shape_instance_parameters['EI_HostEUType'] = panel.parent.entity_type.id
                direct_shape_instance_parameters['EI_HostEUInstanceID'] = parent_id
        # Parametric CLT thickness
        if panel.entity == 'LayerGroup' and 'CLT' in panel.entity_type.name.upper():
            material_id = parent_component_pset['StructuralLG_SKU'].value
            panel_layer_type = panel.entity_type.get_layer_type_from_material_id(material_id)
            if not panel_layer_type:
                raise RuntimeError('ComponentStructure.update_parameters ERROR: ' +
                                   '{} {} has no LayerType with material_id:{}'.format(panel.entity, panel.id,
                                                                                       material_id))
            direct_shape_instance_parameters['EI_LG_StructuralLayerType'] = panel_layer_type.id

    def update_mep(self, panel):
        """

        :param panel:
        :return:
        """
        if not panel.attached_mep:
            return
        for rvt_mep_element in panel.attached_mep:
            log.debug("updating MEP parameters for element {}".format(rvt_mep_element.Id))
            pset = mru.PyParameterSet(rvt_mep_element)
            # pset['EI_ParentID'] = panel.id <- removed 10/3/2022
            pset['EI_HostComponentInstanceID'] = self.component.id
            # Update MEP subelements
            for subelement in mru.RvtSubcomponents.get_all_of_same_category(rvt_mep_element):
                log.debug("updating MEP subelement parameters of element {}".format(rvt_mep_element.Id))
                pset = mru.PyParameterSet(subelement)
                # pset['EI_ParentID'] = panel.id <- removed 10/3/2022
                pset['EI_HostComponentInstanceID'] = self.component.id

    def get_layergroup_by_id(self, lg_id):
        lgs = [lg for lg in self.layer_groups if lg.id == lg_id]
        if lgs:
            return lgs[0]
        return None

    def get_layergroup_from_point(self, rvt_xyz, discriminator=None):
        """
        Returns any layergroup which reference face is almost coplanar with input point
        It ignores panels back faces, so for components with 1 layergroup it will return None

        Args:
            rvt_xyz: DB.XYZ
            discriminator: string to discriminate Layergroup type id by

        Returns: LayerGroup or None

        """
        for lg in self.layer_groups:
            lg_domain = geo.Domain1d(d_min=0.0, d_max=lg.length)
            if discriminator and discriminator not in lg.entity_type.id:
                continue
            point_in_local = lg.face_local_tf.from_world_XYZ_to_local(rvt_xyz)
            if abs(point_in_local.z) < 0.005 and lg_domain.includes(point_in_local.x):
                return lg
        return None

    def get_layergroup_reference_from_point(self, rvt_xyz, discriminator=None):
        """
        More precise way of determining if point is on layergroup
        Example:
            ref = component.component_structure.get_layergroup_reference_from_point(point)
            ref.layergroup
            ref.point_on_back_face

        Args:
            rvt_xyz:
            discriminator:

        Returns: PanelFaceReference

        """
        if len(self.layer_groups) == 1:
            return PanelFaceReference(layergroup=self.layer_groups[0],
                                      revit_xyz=rvt_xyz)
        return PanelFaceReference(layergroup=self.get_layergroup_from_point(rvt_xyz,
                                                                            discriminator=discriminator),
                                  revit_xyz=rvt_xyz)


class ComponentBaseJoin(_BaseObject_):
    """
    Base Join Class

    A join must be unique? (ie: there must be only one given join in that location?)
    Do we need to keeo track of the joins in model?
    When we don't know which join to use do we ask the user?

    """
