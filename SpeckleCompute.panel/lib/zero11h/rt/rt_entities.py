#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
This file is a copy of the Segment generator one. They must be integrated eventually
"""

__author__ = "Iván Pajares [Modelical]"


import re




class API_Entity(object):
    """
    Super class for 011h api entities

    value is API field name
    """
    # param_EI_011hClassCode
    maps = {'PartialSegment': {'description': 'description',
                               'title': 'short_name',
                               'id': 'id',
                               'is_active': 'is_active',
                               'layers': 'segment_layers',
                               'ifc_export_as': 'param_IfcExportAs',
                               'keynote': 'builtin_Keynote',
                               'classification': 'segment_classification'},
            'LayerMaterial': {'id': 'id',
                              'title': 'short_name',
                              'revit_cut_pattern_fg_color': 'cut_pattern_foreground_color',
                              'revit_cut_pattern_fg_pattern': 'cut_pattern_foreground_pattern',
                              'revit_appearance_asset_name': 'appearance_asset_name',
                              'dimension_3': 'thickness_mm'
                              },
            'PartialSegmentLayer': {'id': 'id',
                                    'thickness': 'thickness',
                                    'revit_layer_type': 'layer_type',
                                    'material': 'generic_material',  # changed from material_generic
                                    'position': 'position',
                                    'is_active': 'is_active',
                                    'is_revit_layer': 'is_revit_layer',
                                    'is_variable_thickness': 'is_variable_thickness'},
            'Classification011h': {'id': 'id',
                                   'class_code_011h': 'class_code_011h',
                                   'revit_category': 'revit_category'},
            'ComponentType': {'code': 'id',
                              'description': 'description',
                              'version': 'version',
                              'name': 'name',
                              # 'execution_unit_types': '_execution_units_map'}, SC2219 API changes
                              'associated_execution_unit_types': '_execution_units_map',
                              # 'construction_site_type': 'construction_site_type',
                              'status': 'status',
                              'chapter_code': 'chapter_code',
                              'associated_opening_types': 'associated_opening_types'},
            'ExecutionUnitType': {'code': 'id',
                                  'description': 'description',
                                  # 'short_name': 'short_name',
                                  'name': 'name',
                                  'is_mirrored': 'is_mirrored',
                                  # 'layer_group_types': '_layer_groups_map', SC2219 API changes
                                  'associated_layer_group_types': '_layer_groups_map',
                                  'position': 'position',
                                  'construction_site_type': 'construction_site_type',
                                  'construction_site_type_vo': 'construction_site_type_vo',
                                  'class_code': 'class_code',
                                  'workset': 'workset'},
            'LayerGroupType': {'code': 'id',
                               'description': 'description',
                               # 'short_name': 'short_name',
                               'name': 'name',
                               'is_mirrored': 'is_mirrored',
                               'position': 'position',
                               #'layer_types': '_layer_types_map'}, SC2219 API changes
                               'associated_layer_types': '_layer_types_map',
                               'construction_site_type': 'construction_site_type',
                               'class_code': 'class_code',
                               'workset': 'workset'},
            'LayerType':      {'code': 'id',
                               'description': 'description',
                               'material_id': 'material_id',
                               'position': 'position',
                               'absolute_position': 'absolute_position',
                               'construction_site_type': 'construction_site_type',
                               'thickness': 'thickness',
                               'process_type_codes': 'process_type_codes'},
            'TemplateType':   {'code': 'id',
                               'description': 'description',
                               'process_types': 'process_types'
                               },
            'ProcessType':    {'code': 'id',
                               'description': 'description',
                               'operation_number': 'operation_number'
                               }
            }

    def __init__(self, json_dict, attribute_map):
        for value in attribute_map.values():
            self.__dict__[value] = None
        for key, value in json_dict.items():
            if key in attribute_map:
                self.__dict__[attribute_map[key]] = value

    def __repr__(self):
        return "{} instance with id:{}".format(self.entity, self.id)


class PartialSegment(API_Entity):
    def __init__(self, json_dict):
        self.entity = 'PartialSegment'
        super(PartialSegment, self).__init__(json_dict, attribute_map=self.maps.get(self.entity))
        assert self.segment_layers, "PartialSegment error: no layers"
        self._layers_map = self.segment_layers

    @property
    def classification(self):
        return Classification011h(self.segment_classification)

    @property
    def param_EI_011hClassCode(self):
        return self.classification.class_code_011h

    @property
    def revit_category(self):
        return self.classification.revit_category

    @property
    def layers(self):
        return [PartialSegmentLayer(ps_layer_data) for ps_layer_data in self._layers_map]


class PartialSegmentLayer(API_Entity):
    def __init__(self, json_dict):
        self.entity = 'PartialSegmentLayer'
        super(PartialSegmentLayer, self).__init__(json_dict, attribute_map=self.maps.get(self.entity))
        assert self.generic_material, "PartialSegmentLayer error: no material data for layer {}".format(self.id)
        self._material_id_map = self.generic_material

    @property
    def material(self):
        return LayerMaterial(self._material_id_map)


class LayerMaterial(API_Entity):
    def __init__(self, json_dict):
        self.entity = 'LayerMaterial'
        super(LayerMaterial, self).__init__(json_dict, attribute_map=self.maps.get(self.entity))


class Classification011h(API_Entity):
    def __init__(self, json_dict):
        self.entity = 'Classification011h'
        super(Classification011h, self).__init__(json_dict, attribute_map=self.maps.get(self.entity))


class ComponentType(API_Entity):
    def __init__(self, json_dict):
        self.entity = 'ComponentType'
        super(ComponentType, self).__init__(json_dict, attribute_map=self.maps.get(self.entity))
        self.execution_units = self.get_execution_units()
        self.layer_groups = self.get_layer_groups()
        self._set_eu_and_lg_parent_component()

    def get_execution_units(self):
        """
        Ordered Execution Unit Types by position
        """
        return sorted([ExecutionUnitType(eu_type)
                       for eu_type in self._execution_units_map],
                      key=lambda k: k.position)

    def get_layer_groups(self):
        """
        Ordered LayerGroup Types of each ordered ExecutionUnit Type
        """
        layer_groups = list()
        for eu in self.execution_units:
            layer_groups.extend(eu.layer_group_types)

        return layer_groups

    def get_entity_by_name(self, entity_name):
        entities = self.execution_units + self.layer_groups
        result = [entity for entity in entities if entity.id == entity_name]
        if result:
            return result[0]
        return None

    def get_default_composition(self):
        default_layertype_composition = []
        for eu in self.execution_units:
            default_layertype_composition.extend(eu.get_default_composition())

        return default_layertype_composition

    def get_default_thickness(self):
        if not self.get_default_composition():
            return None
        return sum([lt.thickness for lt in self.get_default_composition()])

    @property
    def short_id(self):
        return self.id.split('_')[1]

    def _set_eu_and_lg_parent_component(self):
        for item in self.execution_units + self.layer_groups:
            item.parent_component = self


class LayerType(API_Entity):
    def __init__(self, json_dict):
        self.entity = 'LayerType'
        # Implement API changes where position and is_mirrored wer moved one level up in dictionary
        self.layer_parametrizable_type = json_dict.get('layer_parametrizable_type')
        lt_json_dict = json_dict.get('layer_type')
        lt_json_dict['position'] = json_dict['position']
        super(LayerType, self).__init__(lt_json_dict, attribute_map=self.maps.get(self.entity))

    def __repr__(self):
        return "---{} {} with id {}".format(self.position,
                                           self.entity,
                                           self.id)

    @property
    def contruction_process_type_code(self):
        for item in self.process_type_codes:
            process_code = item.get('construction_process_type_code', None)
            if process_code:
                return process_code
        return None


class LayerGroupType(API_Entity):
    def __init__(self, json_dict, parent):
        self.entity = 'LayerGroupType'
        # Implement API changes where position and is_mirrored wer moved one level up in dictionary
        lg_json_dict = json_dict.get('layer_group_type')
        lg_json_dict['is_mirrored'] = json_dict['is_mirrored']
        lg_json_dict['position'] = json_dict['position']
        super(LayerGroupType, self).__init__(lg_json_dict, attribute_map=self.maps.get(self.entity))
        self.parent = parent

    def get_all_layer_types(self):
        layertypes = sorted([LayerType(layer_type)
                             for layer_type in self._layer_types_map],
                            key=lambda k: k.position,
                            reverse=self.is_mirrored)
        result = list(reversed(layertypes)) if self.parent.is_mirrored else layertypes
        return result

    def get_layer_type_from_material_id(self, material_id):
        for layer_type in self.get_all_layer_types():
            if layer_type.material_id == material_id:
                return layer_type
        return None

    def get_default_composition(self):
        """

        Returns: Default layer or Normal layer when no alternatives defined

        """
        layer_type_list = self.get_all_layer_types()
        if len(layer_type_list) == 1:
            return layer_type_list

        for layer_type in layer_type_list:
            if layer_type.layer_parametrizable_type == 'Default':
                return [layer_type]

        if self.is_mirrored:
            layer_type_list.reverse()
        return layer_type_list

    @property
    def id_prefix(self):
        return self.id.split('_')[1]

    @property
    def short_id(self):
        return self.id_prefix.split('-')[0]

    def __repr__(self):
        if self.is_mirrored:
            return "--{} is mirrored {} with id {}".format(self.position,
                                                           self.entity,
                                                           self.id)
        return "--{} {} with id:{}  {}".format(self.position,
                                              self.entity,
                                              self.id,
                                              self.description)


class ExecutionUnitType(API_Entity):
    def __init__(self, json_dict):
        self.entity = 'ExecutionUnitType'
        # Implement API changes where position and is_mirrored wer moved one level up in dictionary
        eu_json_dict = json_dict.get('execution_unit_type')
        eu_json_dict['is_mirrored'] = json_dict['is_mirrored']
        eu_json_dict['position'] = json_dict['position']
        super(ExecutionUnitType, self).__init__(eu_json_dict, attribute_map=self.maps.get(self.entity))

    @property
    def layer_group_types(self):
        """
        Ordered list of LayerGroup Types by position
        """
        return sorted([LayerGroupType(lg_type, self)
                       for lg_type in self._layer_groups_map],
                      key=lambda k: k.position,
                      reverse=self.is_mirrored)

    @property
    def id_prefix(self):
        return self.id.split('_')[1]

    @property
    def short_id(self):
        pattern = r'(...)\.(...)\-(\d{4})'
        m = re.search(pattern, self.id)
        if m:
            return m.group()
        return None

    @property
    def budget_item(self):
        return self.id_prefix.split('-')[0]

    @property
    def construction_site_type_short_name(self):
        return self.construction_site_type_vo.get('short_name')

    def get_default_composition(self):
        default_layertype_composition = []
        for lg in self.layer_group_types:
            default_layertype_composition.extend(lg.get_default_composition())
        if self.is_mirrored:
            default_layertype_composition.reverse()
        return default_layertype_composition

    def get_default_thickness(self):
        """
        Intended for Horizontal Components
        Vertical Components have embedded material layers (ie: insulation between steel frame) and will report
        larger values.
        """
        if not self.get_default_composition():
            return None
        return sum([lt.thickness for lt in self.get_default_composition()])

    def __repr__(self):
        if self.is_mirrored:
            return "{} mirrored {} {} with id {}".format(self.position,
                                                         self.entity,
                                                         self.budget_item,
                                                         self.id)
        return "{} {} {} with id:{}  {}".format(self.position,
                                               self.entity,
                                               self.budget_item,
                                               self.id,
                                               self.description)


class ProcessType(API_Entity):
    def __init__(self, json_dict):
        self.entity = 'ProcessType'
        super(ProcessType, self).__init__(json_dict, attribute_map=self.maps.get(self.entity))


class TemplateType(API_Entity):
    def __init__(self, json_dict):
        self.entity = 'TemplateType'
        super(TemplateType, self).__init__(json_dict, attribute_map=self.maps.get(self.entity))

    def get_process_type(self, process_type_id=None):
        for item in self.process_types:
            process_type = ProcessType(item.get('process_type'))
            process_type.operation_number = item.get('operation_number')
            if process_type.id == process_type_id:
                return process_type
        return None




