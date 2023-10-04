#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
This module holds the base Component classes for working in Revit with 011h Components

"""
from .base_classes import _BaseObject_, _REVIT_DOCUMENT_, _WORKING_PHASE_, Zero11hTypes
from zero11h.revit_api import System, DB
import zero11h.revit_api.revit_utils as mru
import zero11h.geometry as geo


class FamilyInstancePointBased(_BaseObject_):
    def __init__(self, rvt_element=None, parent=None):  # -> None:
        self.rvt_element = rvt_element
        self.rvt_type = mru.get_rvt_element_type(self.rvt_element)
        self.rvt_instance_location_point = rvt_element.Location.Point
        self.instance_parameters = mru.PyParameterSet(self.rvt_element)
        self.type_parameters = mru.PyParameterSet(self.rvt_type)
        self.parent = parent
        self.family_name = self.type_parameters.builtins['SYMBOL_FAMILY_NAME_PARAM'].value
        self.type_name = self.type_parameters.builtins['SYMBOL_NAME_PARAM'].value
        self.id = ':'.join([self.family_name,
                            self.type_name,
                            str(self.rvt_element.Id.IntegerValue)])

    @property
    def width(self):
        return mru.UnitConversion.feet_to_m(self.type_parameters['Width'].value)

    @property
    def height(self):
        return mru.UnitConversion.feet_to_m(self.type_parameters['Height'].value)

    @property
    def local_origin(self):
        """

        Returns: Local origin relative to components origin or 0,0,0 if no parent

        """
        if self.parent:
            return mru.RvtTransform(self.parent.local_rvt_transform).from_world_XYZ_to_local(
                self.rvt_instance_location_point)
        return geo.Point3(0, 0, 0)

    def __repr__(self):
        return 'id: {} {} at {} host: {}'.format(self.id,
                                                 self.type_name,
                                                 self.local_origin,
                                                 'No parent set' if not self.parent else self.parent.id)


class OpeningInstance(FamilyInstancePointBased):
    """
    Opening element helper class

    id

    width
    height
    location, all in metric and local component coordinates
    window_type_id

    What info will we need from RT to detail the openings?
    For each type of opening and VTS layer we need the frame 3d component
    """

    def __init__(self,
                 rvt_element=None,
                 parent=None,
                 position=None,
                 phase=_WORKING_PHASE_,
                 room_code_parameter='RI_RoomCode'):  # -> None:
        super(OpeningInstance, self).__init__(rvt_element=rvt_element, parent=parent)
        self.position = position
        self.room_code_parameter = room_code_parameter
        self.phase = phase
        self.location_area_code = 'Not located'
        self.location_room_code = 'Not located'
        self.locate()

    def update_parameters(self):
        """
        Update Openings parameter data in component

        AS we are modifying project shared parameters inside a shared family instance
        it is MANDATORY that no shared parameter with same ID & Name is present in the family definition

        In the project environment the shared parameter inside the family will take precedence and
        we will get a Parameter is read-only error when trying to modify it.
        """
        self.instance_parameters['EI_InstanceID'] = 'O_{}_{}.{}'.format(
            self.instance_parameters['EI_OpeningType'].value,
            self.parent.id_prefix,
            self.position
        )
        self.instance_parameters['EI_HostComponentInstanceID'] = self.parent.id
        self.instance_parameters['EI_HostComponentType'] = self.parent.type_id
        self.instance_parameters['EI_LocalisationCodeRoom'] = self.location_room_code
        self.instance_parameters['EI_LocalisationCodeArea'] = self.location_area_code
        self.instance_parameters['EI_LocalisationCodeFloor'] = self.parent.instance_parameters[
            'EI_LocalisationCodeFloor'].value
        self.type_parameters['EI_Type'] = Zero11hTypes.Opening

        # Update also opening subelements:
        parameter_names_to_update = ['EI_HostComponentInstanceID',
                                     'EI_HostComponentType',
                                     'EI_OpeningType',
                                     'EI_InstanceID',
                                     'EI_LocalisationCodeRoom',
                                     'EI_LocalisationCodeArea',
                                     'EI_LocalisationCodeFloor']
        for subelement in mru.RvtSubcomponents.get_all_of_same_category(self.rvt_element):
            subelement_pset = mru.PyParameterSet(subelement)
            for pname in parameter_names_to_update:
                subelement_pset[pname] = self.instance_parameters[pname].value

    @property
    def is_door(self):
        return self.rvt_element.Category.Id == DB.Category.GetCategory(_REVIT_DOCUMENT_,
                                                                       DB.BuiltInCategory.OST_Doors).Id

    @property
    def is_window(self):
        return self.rvt_element.Category.Id == DB.Category.GetCategory(_REVIT_DOCUMENT_,
                                                                       DB.BuiltInCategory.OST_Windows).Id

    @property
    def opening_type_id(self):
        op_tp_id = self.instance_parameters['EI_OpeningType'].value
        if not op_tp_id:
            return None
        return op_tp_id.strip()

    def locate(self):
        """
        Locate opening instance
        Criteria:
        Doors: ToRoom
        Windows: FromRoom
        Locate main and make shared inherit
        """
        if not self.is_door and not self.is_window:
            return
        located_room = self.rvt_element.ToRoom[self.phase] if self.is_door else self.rvt_element.FromRoom[self.phase]
        if located_room:
            self.location_room_code = located_room.LookupParameter(self.room_code_parameter).AsString()
            self.location_area_code = self.location_room_code.split('-')[0]

    def __repr__(self):
        return 'id: {} {}x{} at {} host: {}'.format(self.id,
                                                    self.width,
                                                    self.height,
                                                    self.local_origin,
                                                    self.parent.id)


class OpeningData(_BaseObject_):
    """
    Class to work with a component's openings
    """


class MEPBoxInstance(FamilyInstancePointBased):
    """

    """

    entity = 'MEPBox'

    def __init__(self, rvt_element=None, parent=None, position=None):  # -> None:
        super(MEPBoxInstance, self).__init__(rvt_element=rvt_element, parent=parent)
        self.position = position
        self.on_reference_side = True if self.local_origin.z < 0 else False
        self.location_area_code = 'Not located'
        self.location_room_code = 'Not located'
        self.locate()


    @property
    def width(self):
        return mru.UnitConversion.feet_to_m(self.type_parameters['Width'].value)

    @property
    def type_id(self):
        return self.type_parameters['Type_Name_Tag'].value

    @property
    def layergroup(self):
        if not self.parent:
            return None
        if len(self.parent.layer_groups) == 1:  # It's a non structural Component with 1 layergroup
            return self.parent.layer_groups[0]
        return self.parent.component_structure.get_layergroup_from_point(
            self.rvt_instance_location_point)

    @property
    def cuts_clt(self):
        try:
            return True if self.type_parameters['Has_Blinds'].value == 1 else False
        except Exception as ex:
            return False

    def update_parameters(self):
        if not self.parent:
            return

        self.instance_parameters['EI_InstanceID'] = 'MEP_{}_{}.{}'.format(
            'MR' if self.on_reference_side else 'MB',
            self.parent.id_prefix,
            self.position
        )
        self.instance_parameters['EI_HostComponentInstanceID'] = self.parent.id
        self.instance_parameters['EI_HostComponentType'] = self.parent.type_id
        self.instance_parameters['EI_LocalisationCodeRoom'] = self.location_room_code
        self.instance_parameters['EI_LocalisationCodeArea'] = self.location_area_code
        self.instance_parameters['EI_LocalisationCodeFloor'] = self.parent.instance_parameters[
            'EI_LocalisationCodeFloor'].value

    def locate(self):
        if not self.parent:
            return

        local_probe_point = self.local_origin.translate(geo.Vector3(0, 1, -0.5 if self.on_reference_side else 0.5))
        probe_point = mru.RvtTransform(self.parent.local_rvt_transform).from_local_to_world(local_probe_point)
        room = _REVIT_DOCUMENT_.GetRoomAtPoint(probe_point,
                                               _WORKING_PHASE_)
        if not room:
            # print('Could not locate room at point {}:{}'.format(local_probe_point,
            #                                                     probe_point))
            return
        room_code = room.LookupParameter('RI_RoomCode').AsString()
        self.location_room_code = room_code
        self.location_area_code = room_code.split('-')[0]

    def update_mepbox(self):
        """
        This method should check dimensions of Layergroup and update mepbox if needed.
        Also apply any other logic to it or flag it?
        """
        lg = self.layergroup
        if not lg:
            if self.parent:
                return
            raise RuntimeError('MEPBOX update ERROR: Layergroup not found for mepbox {}'.format(self))
        self.instance_parameters.builtins['INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM'] = self.parent.rvt_element.LevelId
        lg_origin_offset = lg.face_local_tf.rvt_transform.Origin - lg.parent_component.local_rvt_transform.Origin
        self.instance_parameters.builtins['INSTANCE_ELEVATION_PARAM'] = lg_origin_offset.Z
        self.instance_parameters.builtins['ELEM_PARTITION_PARAM'] = self.parent.instance_parameters.builtins[
            'ELEM_PARTITION_PARAM'].value
        self.instance_parameters['QU_Height_m'] = self.instance_parameters['Height'] = mru.UnitConversion.m_to_feet(
            lg.height)
        self.instance_parameters['QU_Length_m'] = self.type_parameters['Width'].value
        self.instance_parameters['Depth'] = mru.UnitConversion.m_to_feet(lg.thickness)
        # _REVIT_DOCUMENT_.Regenerate()  # We need regen to update geometry
        self.instance_parameters['EI_HostEUInstanceID'] = lg.parent_id
        self.instance_parameters['EI_HostEUType'] = lg.parent.entity_type.id
        self.instance_parameters['EI_SKUNumber'] = self.type_name
        self.type_parameters['EI_Type'] = self.entity
        self.type_parameters['EI_TypeID'] = self.type_id
