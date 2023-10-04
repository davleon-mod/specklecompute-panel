#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module holds the base Component classes for working in Revit with 011h Components

"""

__author__ = 'Iván Pajares [Modelical]'

import zero11h.geometry as geo
import zero11h.revit_api.revit_utils as mru
import zero11h.revit_api.extensible_storage as mes



from .base_classes import log, BaseComponent, _BaseObject_
from zero11h.revit_api.revit_utils import TOLERANCE, ExecutionUnitsSubcategories
from .base_classes import EntityNomenclator, JsonSerializer
from .base_classes import EXECUTION_UNITS_WORKSET


class HorizontalPanel(_BaseObject_):
    """
    Base 3d panel class for LayerGroups and ExecutionUnits

    All geometric properties transformed to its local coordinate system,
    which is parallel to the component's CS.

    """
    # pylint: disable=too-many-instance-attributes

    def __init__(self, rvt_solid,
                 component,
                 id_=None,
                 parent=None,
                 entity = 'HorizontalPanel'):

        self.id = id_
        self.rvt_solid = rvt_solid
        self.top_face = mru.RvtSolidUtils.get_solid_face_from_normal(self.rvt_solid, geo.Vector3(0, 0, 1))
        assert self.rvt_solid, "HorizontalPanel error for panel {}: No valid solid found".format(self.id)
        try:
            self.material_name = mru.RvtSolidUtils.get_material_from_solid(self.rvt_solid).Name
        except AttributeError as ex:
            self.material_name = 'NOT SET'

        self.parent_component = component
        self.parent_id = parent  # probably useless. Review.

        self.entity_type = None
        self.slot = None
        # If is_mirrored, panel normal is facing other side, not reference side.
        self.is_mirrored = False  # This will be set when generating the component's structure
        self.has_subelements = False
        self.local_rvt_transform = self.get_local_rvt_transform()
        self.origin = mru.UnitConversion.XYZ_to_Point3(self.local_rvt_transform.Origin)
        self.local_vx = mru.UnitConversion.XYZ_to_Vector3(self.local_rvt_transform.BasisX)
        self.local_vy = mru.UnitConversion.XYZ_to_Vector3(self.local_rvt_transform.BasisY)
        self.local_vz = mru.UnitConversion.XYZ_to_Vector3(self.local_rvt_transform.BasisZ)
        self.local_cs = geo.CoordinateSystem3(self.origin, self.local_vx, self.local_vy, self.local_vz)
        self.vertices = self.compute_vertices(cs=self.local_cs)
        self.min_local_z = min([vtx.z for vtx in self.vertices])
        self.max_local_z = max([vtx.z for vtx in self.vertices])
        self.min_local_x = min([vtx.x for vtx in self.vertices])
        self.max_local_x = max([vtx.x for vtx in self.vertices])
        self.min_local_y = min([vtx.y for vtx in self.vertices])
        self.max_local_y = max([vtx.y for vtx in self.vertices])

    def __repr__(self):
        if self.is_mirrored:
            mirrored = 'is_mirrored'
        else:
            mirrored = ''

        return '{} {} {}x{}x{} m {}'.format(self.entity,
                                         self.id,
                                         self.length,
                                         self.width,
                                         self.thickness,
                                         mirrored)

    def get_local_rvt_transform(self): #  :  # -> mru.RvtTransform:
        """
        Creates a wrapped local transform
        Get nearest upper face vertex to cs origin. Use that as new origin
        """
        new_local_origin = sorted(mru.get_face_vertices(self.top_face),
                                  key=lambda x: x.DistanceTo(self.parent_component.origin_feet),
                                  reverse=False)[0]

        tf = mru.RvtTransform(self.parent_component.local_rvt_transform)

        rvt_local_tf = tf.rvt_transform.Identity
        rvt_local_tf.Origin = new_local_origin
        rvt_local_tf.BasisX = tf.rvt_transform.BasisX
        rvt_local_tf.BasisY = tf.rvt_transform.BasisZ.Negate()
        rvt_local_tf.BasisZ = rvt_local_tf.BasisX.CrossProduct(rvt_local_tf.BasisY)# tf.rvt_transform.BasisZ

        return rvt_local_tf

    def compute_vertices(self, cs=None):  # -> List[geo.Point3]:
        if not cs:
            cs = self.parent_component.local_cs
        vtx = mru.RvtSolidUtils.get_solid_vertices(self.rvt_solid)
        return [cs.transform_to_local(mru.UnitConversion.XYZ_to_Point3(v)) for v in vtx]

    @property
    def length(self):  # -> float:
        return abs(self.min_local_x - self.max_local_x)

    @property
    def width(self):  # -> float:
        return abs(self.min_local_y - self.max_local_y)

    @property
    def thickness(self):  # -> float:
        return abs(self.min_local_z - self.max_local_z)

    @property
    def net_area(self):  # -> float:
        return mru.UnitConversion.squarefeet_to_m2(self.top_face.Area)

    @property
    def gross_area(self):  # -> float:
        return self.length * self.width

    @property
    def volume(self):  # -> float:
        return mru.UnitConversion.cubicfeet_to_m3(self.rvt_solid.Volume)

    def duplicate(self):  # -> '_Base3DPanel_':
        return HorizontalPanel(self.rvt_solid, self.parent_component, id_=None, parent=None)

    def local_point_to_model_xyz(self, point):  # -> XYZ:
        """
        Returns a local point in world coordinates in metric Point3
        If we need to get a world cs xyz in api units we remove the unit conversion
        or add a UnitConversion.Point3_to_XYZ to the result

        :param point:
        :return:
        """
        return mru.UnitConversion.XYZ_to_Point3(
                mru.RvtTransform(self.local_rvt_transform).from_local_to_world(point)
        )

    def model_xyz_to_local_point(self, revit_xyz):  # -> geo.Point3:
        return mru.RvtTransform(self.local_rvt_transform).from_world_XYZ_to_local(revit_xyz)

    @property
    def panel_center(self):  # -> revit XYZ
        center = geo.Point3(self.length / 2.0,
                            self.width/ 2.0,
                            self.thickness / 2.0)

        return self.local_point_to_model_xyz(center)

    @property
    def interior_center(self):  # -> revit XYZ
        # This is temporary. We should change the local reference for flipped or mirrored panels
        # We could implement an auxiliary object like CADWORK Axis
        if self.is_mirrored:
            interior_center = geo.Point3(self.length / 2.0,
                                         self.width / 2.0,
                                         0.0)
        else:
            interior_center = geo.Point3(self.length / 2.0,
                                         self.width / 2.0,
                                         self.thickness)

        return self.local_point_to_model_xyz(interior_center)

    @property
    def exterior_center(self):  # -> revit XYZ
        if self.is_mirrored:
            exterior_center = geo.Point3(self.length / 2.0,
                                         self.width / 2.0,
                                         self.thickness)
        else:
            exterior_center = geo.Point3(self.length / 2.0,
                                         self.width / 2.0,
                                         0.0)

        return self.local_point_to_model_xyz(exterior_center)

    @property
    def axis_points(self):
        """
        axis_points on cs plane
        :return:
        """
        origin = self.local_point_to_model_xyz(geo.Point3(0, 0, 0))
        end = self.local_point_to_model_xyz(geo.Point3(self.length, 0, 0))
        return origin, end

    @property
    def center_axis_points(self):
        origin = self.local_point_to_model_xyz(geo.Point3(0, self.width / 2.0, self.thickness / 2.0))
        end = self.local_point_to_model_xyz(geo.Point3(self.length, self.width / 2.0, self.thickness / 2.0))
        return origin, end

    @property
    def reference_face_normal(self):
        """
        Returns Revit XYZ normal in model coordinates

        :return: XYZ()
        """
        return -self.local_vz


class ComponentHorizontal(BaseComponent):
    entity = 'HorizontalComponent'

    def __init__(self, rvt_element):
        super(ComponentHorizontal, self).__init__(rvt_element)
        assert not self.rvt_element.HandFlipped, "ComponentHorizontal ERROR: {} with Revit ID:{} is FLIPPED".format(self.id, self.rvt_element.Id)
        # Local CS definition
        # long axis
        self.local_vx = mru.UnitConversion.XYZ_to_Vector3(self.rvt_transform.BasisX)
        # Short axis. Panel width direction
        if self.rvt_element.Mirrored:
            self.local_vy = mru.UnitConversion.XYZ_to_Vector3(self.rvt_transform.BasisY)
        else:
            self.local_vy = mru.UnitConversion.XYZ_to_Vector3(self.rvt_transform.BasisY.Negate())
        # local_vz is pointing down, flip it and you get ext / reference face
        self.local_vz = mru.UnitConversion.XYZ_to_Vector3(self.rvt_transform.BasisZ.Negate())
        # self.update_type_parameters()
        self.component_structure = ComponentHorizontalStructure(self)
        self.clt_panel = self.component_structure.layer_groups[0]



class ComponentHorizontalStructure(_BaseObject_):
    def __init__(self, horizontal_component):
        self.component = horizontal_component
        self._clt_solid = None
        self._clt_rt_execution_unit= None
        self._clt_rt_layergroup = None
        self._screed_rt_execution_unit = None
        self.execution_units = [self.get_clt_panel_execution_unit()]
        self.layer_groups = [self.get_clt_panel_layergroup()]
        self.check_component_thicknesses()

    def check_component_thicknesses(self):
        """
        Check that screed EU and CLT EU thicknesses in model match those in RT
        Returns: Bool

        """
        family_screed_eu_thickness = mru.UnitConversion.feet_to_mm(self.component.type_parameters['ScreedEU_Thickness'].value)
        screed_mat_id = self.component.type_parameters['ScreedEU_Material'].value
        screed_mat = mru.doc.GetElement(screed_mat_id)
        screed_eu = self.component.type_data.get_entity_by_name(screed_mat.Name)
        family_structural_lg_thickness = mru.UnitConversion.feet_to_mm(self.component.type_parameters['StructuralLG_Thickness'].value)

        msg = 'Component Horizontal WRONG CLT THICKNESS. Model:{} RT:{} for Execution Unit {} in component {}'.format(
                family_structural_lg_thickness,
                self._clt_rt_execution_unit.get_default_thickness(),
                self._clt_rt_execution_unit.id,
                self.component.id)
        assert geo.almost_equal(family_structural_lg_thickness,
                                self._clt_rt_execution_unit.get_default_thickness(),
                                tolerance=TOLERANCE), msg
        msg = 'Component Horizontal WRONG SCREED THICKNESS. Model:{} RT:{} for Execution Unit {} in component {}'.format(
            family_screed_eu_thickness,
            screed_eu.get_default_thickness(),
            screed_eu.id,
            self.component.id)
        assert geo.almost_equal(family_screed_eu_thickness,
                                screed_eu.get_default_thickness(),
                                tolerance=TOLERANCE), msg

        self._screed_rt_execution_unit = screed_eu

    def get_clt_panel_execution_unit(self):
        """
        Retrieves panel from family if modeled with right category
        Checks if it is in the proper EU and has the correct thickness

        Returns: HorizontalPanel

        """
        clt_solids = self.component.rvt_solids.get(ExecutionUnitsSubcategories.VTS)
        if clt_solids:
            self._clt_solid = clt_solids[0]
        else:
            msg = 'Component Horizontal ERROR: No Execution Unit modeled of subcat {} for component {} in RT'.format(
                ExecutionUnitsSubcategories.VTS,
                self.component.id)
            raise ValueError(msg)
        clt_panel = HorizontalPanel(self._clt_solid, self.component, id_=ExecutionUnitsSubcategories.VTS)
        # We get the material from the solid and check against RT
        try:
            self._clt_rt_execution_unit = self.component.type_data.get_entity_by_name(clt_panel.material_name)
            clt_id = self._clt_rt_execution_unit.id
        except AttributeError as ex:
            msg = 'Component Horizontal ERROR: No Execution Unit {} for component {} in RT'.format(
                clt_panel.material_name,
                self.component.id)
            raise ValueError(msg)
        # We check dimensional values and if correct return panel
        if not geo.almost_equal(clt_panel.thickness * 1000, self._clt_rt_execution_unit.get_default_thickness(), tolerance=TOLERANCE):
            msg = 'Component Horizontal WRONG THICKNESS Modeled:{} RT:{} for Execution Unit {} in component {} in RT'.format(
                clt_panel.thickness,
                self._clt_rt_execution_unit.get_default_thickness(),
                clt_panel.material_name,
                self.component.id)
            raise ValueError(msg)

        clt_panel.entity_type = self._clt_rt_execution_unit
        clt_panel.entity = 'ExecutionUnit'
        # position -1 because we are not using Slots and RT starts on 1
        clt_panel.id = EntityNomenclator.set_execution_unit_id(clt_panel, self._clt_rt_execution_unit.position - 1)

        return clt_panel

    def get_clt_panel_layergroup(self):
        """
        Duplicates EU creating the CLT LG

        Returns: HorizontalPanel LayerGroup

        """
        try:
            self._clt_rt_layergroup = self._clt_rt_execution_unit.layer_group_types[0]  # For horizontal components only one expected
        except Exception as ex:
            raise ValueError('CLT panel LayerGroup ERROR')

        clt_lg_panel = HorizontalPanel(self._clt_solid, self.component)
        clt_lg_panel.entity_type = self._clt_rt_layergroup
        clt_lg_panel.entity = 'LayerGroup'
        clt_lg_panel.parent_id = self.get_clt_panel_execution_unit().id
        clt_lg_panel.id = EntityNomenclator.set_layergroup_id(clt_lg_panel, self._clt_rt_layergroup.position - 1)

        return clt_lg_panel

    def to_revit_elements(self):
        # Store active workset
        wks_table = mru.doc.GetWorksetTable()
        active_wks_id = wks_table.GetActiveWorksetId()
        # Change to ExecutionUnits workset
        eu_wks = mru.WorksetUtils.get_workset_by_name(EXECUTION_UNITS_WORKSET)
        wks_table.SetActiveWorksetId(eu_wks.Id)
        # Delete all component subelements if present as they need to be regenerated
        self.component.delete_subelements()
        # Update component parameters as we are in a Transaction at this point
        # This should move to a method
        self.component.instance_parameters['IfcName'] = '{}_{}'.format(self.component.type_parameters['EI_TypeID'].value,
                                                                       self.component.type_parameters['EI_TypeName'].value)
        self.component.type_parameters['EI_Type'] = 'HorizontalComponent'

        direct_shapes = []
        all_panels = self.execution_units + self.layer_groups

        execution_unit_guids = []
        layer_group_guids = []

        for panel in all_panels:
            ds_type = mru.RvtDirectShape.get_dstype_byname(panel.entity_type.id)
            ds = mru.RvtDirectShape.ds_from_solid_wdstype(panel.rvt_solid, panel.id, dstype=ds_type)
            self.update_parameters(ds, ds_type, panel)

            if panel.entity == 'ExecutionUnit':
                # self.update_mep(panel)  -- Not for horizontal components
                eu_metadata = mes.ElementMetadata(ds)
                eu_metadata.parent_component_guid = self.component.rvt_element.UniqueId
                execution_unit_guids.append(ds.UniqueId)
            #
            # # Metadata for LayerGroups
            if panel.entity == 'LayerGroup':
            #     # mru.doc.Regenerate()
                data_dict = JsonSerializer(panel, self_guid=ds.UniqueId).serialize()
                lg_metadata = mes.LayerGroupMetadata(ds)
                # lg_metadata._update_metadata_property('LayerGroupMetadata', data_dict['LayerGroupMetadata'])
                lg_metadata.parent_component_guid = self.component.rvt_element.UniqueId
                layer_group_guids.append(ds.UniqueId)

            direct_shapes.append(ds)

        # Write eu and lg guids to component metadata
        self.component.metadata.execution_unit_guids = execution_unit_guids
        self.component.metadata.layer_group_guids = layer_group_guids

        # Reset active workset back
        wks_table.SetActiveWorksetId(active_wks_id)

        return direct_shapes

    def update_parameters(self, ds, ds_type, panel):
        # type parameters
        log.debug("updating parameters for panel {}".format(panel.id))

        # Instance and Type ParameterSets
        pset = mru.PyParameterSet(ds)
        dst_pset = mru.PyParameterSet(ds_type)
        parent_component_pset = mru.PyParameterSet(self.component.rvt_element)

        # TODO: extract all parameter names to an interface class for maintainability
        # Type Parameters
        dst_pset['EI_Type'] = panel.entity
        dst_pset['EI_TypeID'] = "{}_{}".format(panel.entity_type.id.split('_')[0],
                                               panel.entity_type.id.split('_')[1])
        dst_pset['EI_TypeName'] = panel.entity_type.name
        dst_pset['EI_Description'] = panel.entity_type.description
        dst_pset['NameOverride'] = panel.entity_type.id
        dst_pset['IfcExportAs'] = 'IfcSlab'

        # Instance Parameters
        pset['EI_InstanceID'] = panel.id
        pset['EI_HostComponentInstanceID'] = self.component.id
        pset['EI_HostComponentType'] = self.component.type_id
        # pset['EI_ParentID'] = panel.parent_id <- removed 10/3/2022
        pset['QU_GrossArea_m2'] = mru.UnitConversion.m2_to_squarefeet(panel.gross_area)
        pset['QU_Area_m2'] = mru.UnitConversion.m2_to_squarefeet(panel.net_area)
        pset['QU_Length_m'] = mru.UnitConversion.m_to_feet(panel.length)
        pset['QU_Width_m'] = mru.UnitConversion.m_to_feet(panel.width)
        pset['QU_Thickness_m'] = mru.UnitConversion.m_to_feet(panel.thickness)
        pset['QU_Volume_m3'] = mru.UnitConversion.m3_to_cubicfeet(panel.volume)
        # pset['QU_Weight_kg'] = 2000.0  # Removed as it will be handled by DATA
        pset['IfcExportAs'] = 'IfcSlab'
        pset['IfcName'] = panel.entity_type.id