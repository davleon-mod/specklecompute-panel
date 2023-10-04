#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module holds the base Component classes for working in Revit with 011h Components

"""

__author__ = 'Iván Pajares [Modelical]'

import zero11h.geometry as geo
import zero11h.revit_api.revit_utils as mru
from zero11h.revit_api import System, DB, UI, _REVIT_DOCUMENT_, _WORKING_PHASE_
import zero11h.revit_api.extensible_storage as mes
from zero11h.entities import _BaseObject_, FamilyInstancePointBased

DETAILING_OUTPUT_WORKSET = 'WIP_DETAILING'
DETAILING_RVT_WORKSET = mru.WorksetUtils.get_workset_by_name(DETAILING_OUTPUT_WORKSET)
assert DETAILING_RVT_WORKSET, (
    'Detailing ERROR: Workset {} does not exist. Please create it'.format(DETAILING_OUTPUT_WORKSET))
DEFAULT_OPÊNING_TYPE_NAME = 'Default'
CLT_FAMILY_TYPE_NAME = 'STF_CLT_Straight_Detailed_v2'  # US 4785
CLT_DISCRIMINATOR = 'CLT'
PFU_DISCRIMINATOR = 'PFU'
TRS_DISCRIMINATOR = 'TRS'
AUX_TRS_CUTTING_FAMILYNAME = 'AUX_TRS_Perforator'
MEPBOX_LOD450_DISCRIMINATOR = 'MEPBox_LOD450_v2'
OPENINGDETAIL_DISCRIMINATOR = 'OpeningDetail'

LOCALISATION_PARAMETER_NAMES = ['EI_LocalisationCodeArea',
                                'EI_LocalisationCodeRoom',
                                'EI_LocalisationCodeFloor']

ST_PARAMETER_NAMES = ['ST_SurfaceQuality',
                      'ST_LamellaBuildUp',
                      'ST_PanelType',
                      'ST_StrengthClass',
                      'ST_WoodSpecies',
                      'ST_GrainDirection']

MS_PARAMETER_NAMES = ['MS_ApplicationParameter',
                      'MS_OverConcrete',
                      'MS_NoFloor',
                      'MS_NoRoof',
                      'MS_HoldDown']


class OpeningDetail(_BaseObject_):
    """
    OpeningDetail element
    This class is responsible of providing all the opening detail data and geometry to the detailer
    """

    def __init__(self):
        pass


class DetailsCatalog(_BaseObject_):
    def __init__(self):
        self.details_dict = {}

    def initialize(self,
                   builtin_category=DB.BuiltInCategory.OST_GenericModel,
                   discriminator=None):
        types = DB.FilteredElementCollector(_REVIT_DOCUMENT_).OfCategory(builtin_category).WhereElementIsElementType()
        for tp in types:
            if discriminator in tp.FamilyName:
                self.details_dict[tp.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()] = tp

    def get_detail(self, detail_id):
        detail_type = self.details_dict.get(detail_id, None)

        if not detail_type:
            return None

        if not detail_type.IsActive:
            detail_type.Activate()
            _REVIT_DOCUMENT_.Regenerate()

        return detail_type


class OpeningDetailsCatalog(_BaseObject_):
    def __init__(self):
        self.catalog = DetailsCatalog()
        self.catalog.initialize(discriminator=OPENINGDETAIL_DISCRIMINATOR)

    def get_opening(self, opening_detail_id):
        return self.catalog.get_detail(opening_detail_id)


class MEPDetailsCatalog(_BaseObject_):
    def __init__(self):
        self.catalog = DetailsCatalog()
        self.catalog.initialize(discriminator=MEPBOX_LOD450_DISCRIMINATOR)

    def get_mepbox(self, detail_id):
        return self.catalog.get_detail(detail_id)


OPENINGS_DETAIL_CATALOG = OpeningDetailsCatalog()
MEPBOX_DETAIL_CATALOG = MEPDetailsCatalog()


class MEPBoxInstanceLOD450(_BaseObject_):
    def __init__(self,
                 type_id=None,  # i.e OP_MEP-0064
                 layergroup=None,  # LayerGroupInstance
                 mep_box=None  # MEPBoxInstance
                 ):
        assert all([(type_id or mep_box),
                    layergroup]), "MEPBoxInstanceLOD450 init ERROR: layergroup and type_id or mep_box are mandatory inputs"
        self.mep_box_lod350 = mep_box
        self.type_id = type_id if type_id else mep_box.type_parameters['Type_Name_Tag'].value
        self.layergroup = layergroup
        self.instance_parameters = None
        self.type_parameters = None
        self.rvt_element = None
        self.location_room_code = None
        self.location_area_code = None

    @property
    def detail_type(self):
        detail_type = MEPBOX_DETAIL_CATALOG.get_mepbox(self.type_id)
        assert detail_type, "MEPBoxInstanceLOD450 ERROR: Detail for MEP Box {} not found in catalog".format(
            self.type_id)
        return detail_type

    def create_instance_by_parameter(self, x_parameter=None):
        """
        Create insertion point from x_parameter in lg local ref cs
        """
        insertion_xyz = self.layergroup.face_local_tf.from_local_to_world(geo.Point3(x_parameter, 0, 0))
        return self.create_instance(insertion_xyz=insertion_xyz)

    def create_instance(self, insertion_xyz=None):
        flip_face = False if self.layergroup.on_reference_side else True
        self.rvt_element = mru.RvtFamilyInstanceConstructor.by_point_aligned_to_other(
            reference=self.layergroup.parent_component.rvt_element,
            insertion_xyz=insertion_xyz,
            family_type=self.detail_type,
            level=self.layergroup.parent_component.rvt_level,
            flip_reference_facing=flip_face)
        assert self.rvt_element, 'MEPBox LOD450 ERROR: No instance created'
        self.instance_parameters = mru.PyParameterSet(self.rvt_element)
        self.type_parameters = mru.PyParameterSet(mru.get_rvt_element_type(self.rvt_element))
        lg_origin_offset = self.layergroup.face_local_tf.rvt_transform.Origin - self.layergroup.parent_component.local_rvt_transform.Origin
        self.instance_parameters.builtins['INSTANCE_ELEVATION_PARAM'] = lg_origin_offset.Z
        self.instance_parameters['Height'] = mru.UnitConversion.m_to_feet(self.layergroup.height)
        self.instance_parameters.builtins['ELEM_PARTITION_PARAM'] = DETAILING_RVT_WORKSET.Id.IntegerValue
        self.update_parameters()
        self.update_metadata()
        return self.rvt_element

    def update_parameters(self):
        if not self.instance_parameters:
            return

        self.instance_parameters['EI_InstanceID'] = 'MEP_{}_{}.{}'.format(
            'MR' if self.layergroup.on_reference_side else 'MB',
            self.layergroup.parent_component.id,
            self.rvt_element.Id.IntegerValue
        )
        self.instance_parameters['EI_HostEUInstanceID'] = self.layergroup.parent.id
        self.instance_parameters['EI_HostEUType'] = self.layergroup.parent.entity_type.id
        self.instance_parameters['EI_HostComponentType'] = self.layergroup.parent_component.entity_type.id
        self.instance_parameters['EI_HostComponentInstanceID'] = self.layergroup.parent_component.id
        if self.mep_box_lod350:
            self.instance_parameters['Justify_Center'] = self.mep_box_lod350.instance_parameters['Justify_Center'].value
            self.instance_parameters['Justify_Left'] = self.mep_box_lod350.instance_parameters['Justify_Left'].value
            for pname in LOCALISATION_PARAMETER_NAMES:
                self.instance_parameters[pname] = self.mep_box_lod350.instance_parameters[pname].value
        else:
            # Locate the instance
            self.locate()
            self.instance_parameters['EI_LocalisationCodeRoom'] = self.location_room_code
            self.instance_parameters['EI_LocalisationCodeArea'] = self.location_area_code
            self.instance_parameters['EI_LocalisationCodeFloor'] = self.layergroup.parent_component.instance_parameters[
                'EI_LocalisationCodeFloor'].value

    def update_metadata(self):
        instance_metadata = mes.ElementMetadata(self.rvt_element)
        instance_metadata.parent_component_guid = self.layergroup.parent_component.rvt_element.UniqueId

    @property
    def local_origin(self):
        """
        Origin relative to layergroups face_local_cs
        Positive Z points to LG outside
        """
        if not self.rvt_element:
            return None

        return self.layergroup.face_local_tf.from_world_XYZ_to_local(
            self.rvt_element.Location.Point)

    def locate(self):
        local_probe_point = self.local_origin.translate(geo.Vector3(0, 1, 0.5))
        probe_point = self.layergroup.face_local_tf.from_local_to_world(local_probe_point)
        room = _REVIT_DOCUMENT_.GetRoomAtPoint(probe_point,
                                               _WORKING_PHASE_)
        if not room:
            return
        room_code = room.LookupParameter('RI_RoomCode').AsString()
        self.location_room_code = room_code
        self.location_area_code = room_code.split('-')[0]


class DetailTemplate(_BaseObject_):
    """
    Stores a relationship between a low lod element and its high lod counterparts
    """
    pass


class FamilyBasedDetailer(_BaseObject_):
    """
    Base class for Detailing elements through instances

    A detailer takes a base low detail element and generates new geometry & elements based on a
    detailing template


    common attributes:
    base family type
    level
    parameters to set (parameter map?)
    parameter values
    if it needs to be cut: (boolean from component)
    list of cutting elements
    cutting type


    """
    pass


# class OpeningDetailInstance(FamilyInstancePointBased):
#     """
#     Opening element helper class
#
#     id
#
#     width
#     height
#     location, all in metric and local component coordinates
#     window_type_id
#
#     What info will we need from RT to detail the openings?
#     For each type of opening and VTS layer we need the frame 3d component
#     """
#
#     def __init__(self, rvt_element=None, parent=None):  # -> None:
#         super(OpeningDetailInstance, self).__init__(rvt_element=rvt_element, parent=parent)
#         self.clt_perforator = None
#         self.pyl_perforator = None
#         self._get_perforators()
#         self.clt_perforator_width = 0 if not self.clt_perforator else mru.UnitConversion.feet_to_m(
#             self.clt_perforator.LookupParameter('a').AsDouble())
#         self.pyl_perforator_width = 0 if not self.pyl_perforator else mru.UnitConversion.feet_to_m(
#             self.pyl_perforator.LookupParameter('a').AsDouble())
#         self.metadata = mes.ElementMetadata(self.rvt_element)
#         if _REVIT_DOCUMENT_.IsModifiable:
#             self.metadata.parent_component_guid = self.parent.rvt_element.UniqueId
#
#     def _get_perforators(self):
#         subcomponents = [_REVIT_DOCUMENT_.GetElement(eid) for eid in self.rvt_element.GetSubComponentIds()]
#         try:
#             self.clt_perforator = [elem for elem in subcomponents if elem.Name == 'Perforador_Hueco'][0]
#             self.pyl_perforator = [elem for elem in subcomponents if elem.Name == 'Perforador_Pladur'][0]
#         except Exception as ex:
#             # raise RuntimeError('OpeningDetail {} {}:{} does not have valid perforators'.format(self.family_name,
#             #                                                                                    self.type_name,
#             #                                                                                    self.rvt_element.Id.IntegerValue))
#             pass



class ComponentDetailer(_BaseObject_):
    """
    Handles the instantiation of the high LOD fabrication elements of the component
    This class should be generic and call for specific detailers accordingly

    It has to instantiate CLT on VTS layer
    It has to instantiate frames where openings are
    It has to cut the CLT with the frames cutting volumes
    It has to register the created geometry in the component or extensible storage

    """

    def __init__(self, component=None):  # -> None:
        self.component = component

    def get_clt_layergroups(self):
        return [lg for lg in self.component.layer_groups if 'CLT' in lg.entity_type.name.upper()]
