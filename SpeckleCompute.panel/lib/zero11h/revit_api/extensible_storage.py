#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals


import json
import time
from zero11h.revit_api import System, DB, _REVIT_DOCUMENT_
import zero11h.revit_api.revit_utils as mru

_011H_DATASTORAGE_SCHEMA_GUID = 'DA8AF72A-73BA-43F6-895C-A0273E0F28C2'
_011H_DATASTORAGE_SCHEMA_NAME = 'cero11h_Document_Metadata'
_011H_DATASTORAGE_SCHEMA_DESCRIPTION = 'Revit Document Metadata container for 011h constructive system information'

_011H_SCHEMA_GUID = 'D2076246-C30B-414B-B7BE-071151D82A39'
_011H_SCHEMA_NAME = 'cero11h_Metadata'
_011H_SCHEMA_DESCRIPTION = 'Revit Metadata container for 011h constructive system information'
_011H_SCHEMA_JSON_METADATA_FIELD = 'JSONData'
_011H_BASE_EMPTY_METADATA_DICT = {'SelfGuid':None,
                                  'SelfTypeId':None,
                                  'TimeStamp':None,
                                  'ComponentHash':None}

"""
JSON Data that I need to store in the model

Elements generated from components:
This would store the ids of the elements dependent on the component
When a sublement is created we add the ids to the metadata
Before creating a subelement we check the metada.
We will use guids like Rhino.Inside or Dynamo

Components:
    GUID of parent
    GUID of self    <-- we can use this to check if a component has been copied and inherited the metadata
    GUID of type    <-- same as above. If guid of type does not coincide, delete and generate metadata from scratch
    Subelements
        ExecutionUnits
        LayerGroups
        Detailing
        
LayerGroups
    GUID of parent
    ID of self
    GeometryData
    LayerTyrpeData
    JoinData
    RegisterData
    PerforatorData
    
Or have all subelements have metadata of who is the parent, although what happens when they are copied?
Subelements:
    GUID of parent
    GUID of self to check for copies

API Reference basics
=====================
Element class methods:
    DeleteEntity
    GetEntity
    SetEntity
    
TODO: As we work with workshared models check DataStorage class in API documentation
"""


def create_json_metadata_schema(guid, schema_name,
                                schema_description,
                                json_field_name=_011H_SCHEMA_JSON_METADATA_FIELD):
    schema_guid = System.Guid(guid)
    schema_builder = DB.ExtensibleStorage.SchemaBuilder(schema_guid)
    schema_builder.SetReadAccessLevel(DB.ExtensibleStorage.AccessLevel.Public)
    schema_builder.SetWriteAccessLevel(DB.ExtensibleStorage.AccessLevel.Public)
    schema_builder.SetSchemaName(schema_name)
    schema_builder.SetDocumentation(schema_description)
    field_builder = schema_builder.AddSimpleField(json_field_name, System.String)
    schema = schema_builder.Finish()
    return schema


def add_json_metadata_schema_instance(schema, rvt_element, jsondata):
    field = schema.GetField(_011H_SCHEMA_JSON_METADATA_FIELD)
    schema_instance = DB.ExtensibleStorage.Entity(schema)
    schema_instance.Set[System.String](field, jsondata)
    rvt_element.SetEntity(schema_instance)
    return schema_instance


def add_empty_schema(schema, rvt_element):
    schema_instance = DB.ExtensibleStorage.Entity(schema)
    rvt_element.SetEntity(schema_instance)
    return schema_instance


def get_schema_from_memory_by_guid(schema_guid):
    return DB.ExtensibleStorage.Schema.Lookup(schema_guid)


def get_schema_from_memory_by_name(schema_name):
    for schema in DB.ExtensibleStorage.Schema.ListSchemas():
        if schema.SchemaName == schema_name:
            return schema
    return None


def get_schemainstance_from_element(rvt_element, schema_name):
    schema = get_schema_from_memory_by_name(schema_name)
    if schema:
        return rvt_element.GetEntity(schema)
    return None


def get_elements_with_schema_guid(schema_guid_str=_011H_SCHEMA_GUID):
    schema_filter = DB.ExtensibleStorage.ExtensibleStorageFilter(System.Guid(schema_guid_str))
    return DB.FilteredElementCollector(_REVIT_DOCUMENT_).WherePasses(schema_filter).ToElements()


# Check is schema is in memory, if not create it
_011h_SCHEMA = get_schema_from_memory_by_guid(System.Guid(_011H_SCHEMA_GUID))
_011h_DATASTORAGE_SCHEMA = get_schema_from_memory_by_guid(System.Guid(_011H_DATASTORAGE_SCHEMA_GUID))

if not _011h_SCHEMA:
    _011h_SCHEMA = create_json_metadata_schema(_011H_SCHEMA_GUID,
                                               _011H_SCHEMA_NAME,
                                               _011H_SCHEMA_DESCRIPTION)

if not _011h_SCHEMA:
    raise ValueError('Extensible Storage ERROR: Schema {} not available'.format(_011H_SCHEMA_NAME))

if not _011h_DATASTORAGE_SCHEMA:
    _011h_DATASTORAGE_SCHEMA = create_json_metadata_schema(_011H_DATASTORAGE_SCHEMA_GUID,
                                                           _011H_DATASTORAGE_SCHEMA_NAME,
                                                           _011H_DATASTORAGE_SCHEMA_DESCRIPTION)

if not _011h_DATASTORAGE_SCHEMA:
    raise ValueError('Extensible Storage ERROR: Schema {} not available'.format(_011H_DATASTORAGE_SCHEMA_NAME))


class DocumentDataStorage(object):
    def __init__(self, revit_document=_REVIT_DOCUMENT_, schema=_011h_DATASTORAGE_SCHEMA):
        self.schema_instance = DB.ExtensibleStorage.Entity(schema)
        #Try retrieve existing DataStorage with schema
        schema_filter = DB.ExtensibleStorage.ExtensibleStorageFilter(schema.GUID)
        self.data_storage = DB.FilteredElementCollector(revit_document).WherePasses(schema_filter).FirstElement()
        #Create it if not present in document
        if not self.data_storage and revit_document.IsModifiable:
            self.data_storage = DB.ExtensibleStorage.DataStorage.Create(revit_document)
        if not self.data_storage:
            raise RuntimeError("Can't create DataStorage. Check if out of transaction")
        self.data_storage.SetEntity(self.schema_instance)

    @property
    def metadata(self):
        return json.loads(self.schema_instance.Get[System.String](_011H_SCHEMA_JSON_METADATA_FIELD))

    def _update_metadata(self, new_metadata):
        self.schema_instance.Set[System.String](_011H_SCHEMA_JSON_METADATA_FIELD, json.dumps(new_metadata))
        self.rvt_element.SetEntity(self.schema_instance)


# class ElementData(object):
#     """
#     https://stackoverflow.com/questions/61944707/how-to-use-setitem-properly
#
#     """
#     def __init__(self, data=None):
#         object.__setattr__(self, 'data', {} if data is None else data)
#
#     def __getitem__(self, item):
#         return self.data[item]
#
#     def __setitem__(self, key, value):
#         self.data[key] = value
#
#     def __getattr__(self, item):
#         return self.data[item]
#
#     def __setattr__(self, key, value):
#         self.data[key] = value
#
#     def __repr__(self):
#         return str(self.data)


class GenericElementMetadata(object):
    def __init__(self, element=None, schema=_011h_SCHEMA, metadata_dict=None):
        self.rvt_element = element
        self.schema_instance = self.rvt_element.GetEntity(schema)
        if not self.schema_instance.IsValid():
            if _REVIT_DOCUMENT_.IsModifiable:
                self.schema_instance = DB.ExtensibleStorage.Entity(schema)
                self.schema_instance.Set[System.String](_011H_SCHEMA_JSON_METADATA_FIELD, json.dumps(metadata_dict))
                self.rvt_element.SetEntity(self.schema_instance)
            else:
                raise RuntimeError("Can't create metadata out of transaction")

    @property
    def metadata(self):
        return json.loads(self.schema_instance.Get[System.String](_011H_SCHEMA_JSON_METADATA_FIELD))

    def _update_metadata(self, new_metadata):
        json_data = json.dumps(new_metadata, ensure_ascii=False)  #encoding='utf-8')) # Error con acentos en descripciones
        self.schema_instance.Set[System.String](_011H_SCHEMA_JSON_METADATA_FIELD, json_data)
        self.rvt_element.SetEntity(self.schema_instance)


class ElementMetadata(object):
    """
    Clase genérica para leer y escribir json con metadatos en elementos de revit

    Como los metadatos son un JSON genérico abrá que comprobar si son válidos de alguna manera

    Uso:

    instanciamos ElementMetadata para un elemento
    element_meta = ElementMetadata(rvt_element)
    element_meta.metadata = dict()
    element_meta._update_metadata() <- este método no debería ser privado

    """
    def __init__(self, rvt_element):
        self.rvt_element = rvt_element
        self.schema_instance = self.rvt_element.GetEntity(_011h_SCHEMA)
        # Si el elemento no tiene schema creamos uno para poder añadir metadatos
        # Si no hay transacción abierta no podremos actualizar el esquema.
        debug_msg = 'ElementMetadata initialized for element {}'.format(self.rvt_element.Id.IntegerValue)
        flag = False
        if not self.schema_instance.IsValid():
            flag = True
        elif not self.has_valid_metadata:
            flag = True
        if flag:
            msg = 'Not valid Schema in element {}'.format(self.rvt_element.Id)
            if _REVIT_DOCUMENT_.IsModifiable:
                self.reset_metadata()
                debug_msg = 'NEW ElementMetadata created for element {}'.format(self.rvt_element.Id.IntegerValue)
 
        # print(debug_msg)

    @property
    def has_valid_metadata(self):
        """
        Base validations are:
        metadata guid == component.guid
        if type_id: metadata type guid == component type guid

        :return:
        """
        if self.guid == self.rvt_element.UniqueId:
            # Elements without valid type have typeid == -1
            return self.rvt_element.GetTypeId().IntegerValue == self.type_id
        return False

    @property
    def is_orphan(self):
        # If it is a component can't be orphan
        if self.rvt_element.GetTypeId() != -1:
            type_params = mru.PyParameterSet(_REVIT_DOCUMENT_.GetElement(self.rvt_element.GetTypeId()))
            try:
                if type_params['EI_Type'].value == 'Component':
                    return False
            except ValueError:
                pass

        if not self.has_valid_metadata: return True
        if not self.parent_component_guid: return True
        parent = _REVIT_DOCUMENT_.GetElement(self.parent_component_guid)
        if not parent: return True
        parent_metadata = ComponentMetadata(parent)
        if not parent_metadata.is_element_child_of_component(self.guid):
            return True

        return False

    def delete_metadata(self):
        self.rvt_element.DeleteEntity(_011h_SCHEMA)

    def reset_metadata(self):
        self.schema_instance = DB.ExtensibleStorage.Entity(_011h_SCHEMA)
        self.schema_instance.Set[System.String](_011H_SCHEMA_JSON_METADATA_FIELD,
                                                json.dumps(_011H_BASE_EMPTY_METADATA_DICT))
        self.rvt_element.SetEntity(self.schema_instance)
        self.guid = self.rvt_element.UniqueId
        self.type_id = self.rvt_element.GetTypeId().IntegerValue
        self.update_timestamp()

    def _update_metadata_property(self, property_name, value):
        metadata = self.metadata
        metadata[property_name] = value
        self._update_metadata(metadata)

    def update_timestamp(self):
        pname = 'TimeStamp'
        value = time.time()
        self._update_metadata_property(pname, value)

    @property
    def guid(self):
        return self.metadata.get('SelfGuid')

    @guid.setter
    def guid(self, value):
        pname = 'SelfGuid'
        self._update_metadata_property(pname, value)

    @property
    def type_id(self):
        return self.metadata.get('SelfTypeId')

    @type_id.setter
    def type_id(self, value):
        pname = 'SelfTypeId'
        self._update_metadata_property(pname, value)

    @property
    def parent_component_guid(self):
        return self.metadata.get('ParentComponentGuid')

    @parent_component_guid.setter
    def parent_component_guid(self, value):
        pname = 'ParentComponentGuid'
        self._update_metadata_property(pname, value)

    @property
    def component_hash(self):
        return self.metadata.get('ComponentHash')

    @component_hash.setter
    def component_hash(self, value):
        pname = 'ComponentHash'
        self._update_metadata_property(pname, value)

    @property
    def metadata(self):
        return json.loads(self.schema_instance.Get[System.String](_011H_SCHEMA_JSON_METADATA_FIELD))

    def _update_metadata(self, new_metadata):
        json_data =  json.dumps(new_metadata, ensure_ascii=False)
        self.schema_instance.Set[System.String](_011H_SCHEMA_JSON_METADATA_FIELD, json_data)
        self.rvt_element.SetEntity(self.schema_instance)


class ComponentMetadata(ElementMetadata):
    def __init__(self, rvt_element):
        super(ComponentMetadata, self).__init__(rvt_element)
        self.subelements = self.metadata.get('Subelements')

    @property
    def execution_unit_guids(self):
        if self.subelements:
            return self.subelements.get('ExecutionUnits', [])
        return []

    @execution_unit_guids.setter
    def execution_unit_guids(self, list_of_guidstrs):
        if not list_of_guidstrs:
            return
        metadata = self.metadata
        if not self.subelements:
            metadata['Subelements'] = {}
        metadata['Subelements']['ExecutionUnits'] = list_of_guidstrs
        self._update_metadata(metadata)

    @property
    def layer_group_guids(self):
        if self.subelements:
            return self.subelements.get('LayerGroups', [])
        return []

    @layer_group_guids.setter
    def layer_group_guids(self, list_of_guidstrs):
        if not list_of_guidstrs:
            return
        metadata = self.metadata
        if not metadata.get('Subelements'):
            metadata['Subelements'] = {}
        metadata['Subelements']['LayerGroups'] = list_of_guidstrs
        self._update_metadata(metadata)

    @property
    def detailing_guids(self):
        if self.subelements:
            return self.subelements.get('Detailing', [])
        return []

    @detailing_guids.setter
    def detailing_guids(self, list_of_guidstrs):
        if not list_of_guidstrs:
            return
        metadata = self.metadata
        if not metadata.get('Subelements'):
            metadata['Subelements'] = {}
        metadata['Subelements']['Detailing'] = list_of_guidstrs
        self._update_metadata(metadata)

    def update_detailing_guids(self, list_of_guidstrs):
        if not list_of_guidstrs:
            return
        existing = self.detailing_guids
        updated = list(set(existing + list_of_guidstrs))
        self.detailing_guids = updated

    @property
    def structural_connections_guids(self):
        if self.subelements:
            return self.subelements.get('StructuralConnections', [])
        return []

    @structural_connections_guids.setter
    def structural_connections_guids(self, list_of_guidstrs):
        if not list_of_guidstrs:
            return
        metadata = self.metadata
        if not metadata.get('Subelements'):
            metadata['Subelements'] = {}
        metadata['Subelements']['StructuralConnections'] = list_of_guidstrs
        self._update_metadata(metadata)

    def is_element_child_of_component(self, element_guid_str):
        return any([element_guid_str in self.detailing_guids,
                    element_guid_str in self.execution_unit_guids,
                    element_guid_str in self.layer_group_guids,
                    element_guid_str in self.structural_connections_guids])


class LayerGroupMetadata(ElementMetadata):
    def __init__(self, rvt_element):
        super(LayerGroupMetadata, self).__init__(rvt_element)

    @property
    def is_panelizable(self):
        lg_metadata = self.metadata.get('LayerGroupMetadata', None)
        if lg_metadata:
            return lg_metadata.get('IsPanelizable', False)
        else:
            return False

    @is_panelizable.setter
    def is_panelizable(self, boolean):
        metadata = self.metadata
        metadata['LayerGroupMetadata']['IsPanelizable'] = boolean
        self._update_metadata(metadata)

    @property
    def is_frameable(self):
        lg_metadata = self.metadata.get('LayerGroupMetadata', None)
        if lg_metadata:
            return lg_metadata.get('IsFrameable', False)
        else:
            return False

    @is_frameable.setter
    def is_frameable(self, boolean):
        metadata = self.metadata
        metadata['LayerGroupMetadata']['IsFrameable'] = boolean
        self._update_metadata(metadata)

    @property
    def perforators(self):
        perforators = []
        lg_metadata = self.metadata.get('LayerGroupMetadata', None)
        if lg_metadata:
            try:
                perforators = lg_metadata['PerforatorData']['Perforators']
            except KeyError:
                pass
        return perforators

    @perforators.setter
    def perforators(self, guids):
        metadata = self.metadata
        metadata['LayerGroupMetadata']['PerforatorData']['Perforators'] = guids
        self._update_metadata(metadata)

    @property
    def openings(self):
        openings = []

        lg_metadata = self.metadata.get('LayerGroupMetadata', None)
        if lg_metadata:
            try:
                openings = lg_metadata['PerforatorData']['Openings']
            except KeyError:
                pass
        return openings

    @openings.setter
    def openings(self, guids):
        metadata = self.metadata
        metadata['LayerGroupMetadata']['PerforatorData']['Openings'] = guids
        self._update_metadata(metadata)

    @property
    def mep(self):
        result = []
        lg_metadata = self.metadata.get('LayerGroupMetadata', None)
        if lg_metadata:
            try:
                result = lg_metadata['MEPBoxData']
            except KeyError:
                pass
        return result

    @mep.setter
    def mep(self, dikt):
        metadata = self.metadata
        # if not metadata.get('MEPBoxData', None):
        #     metadata['LayerGroupMetadata']['MEPBoxData'] = {}
        metadata['LayerGroupMetadata']['MEPBoxData'] = dikt
        self._update_metadata(metadata)

    @property
    def ref_face_normal(self):
        return self.metadata.get('LayerGroupMetadata').get('GeometryData').get('local_z')

    @property
    def is_mirrored(self):
        return self.metadata.get('LayerGroupMetadata').get('GeometryData').get('is_mirrored')

    @property
    def layer_types(self):
        return self.metadata.get('LayerGroupMetadata').get('LayerTypeData')

    @layer_types.setter
    def layer_types(self, layer_type_dict_list):
        """
        a layer type dict looks like:

        {'id': 'L_0034_PYL15F.D800_PYL.ON.CLT.2-2_OFM',
         'sku': 'MBOA0867',
         'title': 'MBOA0867-Placa NF Borde Afinado-3000-1200-15-',
         'thickness_mm' = 15.0
        }

        """
        metadata = self.metadata
        metadata['LayerGroupMetadata']['LayerTypeData'] = layer_type_dict_list
        self._update_metadata(metadata)

    @property
    def join_data(self):
        return self.metadata.get('LayerGroupMetadata').get('JoinData')

    @join_data.setter
    def join_data(self, join_data_dict):
        """
        example:
                "JoinData": {
            "t_joins": {
                "C_FAC-0005_2116-00.0686_C_EIV-0008_2116-00.0705": {
                    "vector": [5.2850017444217131e-15, 0.0, -1.0],
                    "register_vectors": [],
                    "parameter": 3.3474999999996262,
                    "width": 0.19599999999997064
                },
                "C_FAC-0005_2116-00.0686_C_EIV-0008_2116-00.0706": {
                    "parameter": 6.5334999999998589,
                    "register_vectors": [],
                    "vector": [5.0629571394966818e-15, 0.0, -1.0],
                    "width": 0.19599999999998041
                }
            }
        },

        """
        metadata = self.metadata
        metadata['LayerGroupMetadata']['JoinData'] = join_data_dict
        self._update_metadata(metadata)


class JointMetadata(ElementMetadata):
    def __init__(self, rvt_element):
        super(JointMetadata, self).__init__(rvt_element)

    @property
    def parent_guid(self):
        return self.metadata.get("ParentGUID")
    @parent_guid.setter
    def parent_guid(self, value):
        self._update_metadata_property("ParentGUID", value)

    @property
    def children_guids(self):
        return self.metadata.get("ChildrenGUIDs")
    @children_guids.setter
    def children_guids(self, value):
        self._update_metadata_property("ChildrenGUIDs", value)

    @property
    def component_guids(self):
        ''' The ids of joined components '''
        return self.metadata.get("ComponentGUIDs")
    @component_guids.setter
    def component_guids(self, value):
        self._update_metadata_property("ComponentGUIDs", value)
        
    
class PerforatorMetadata(ElementMetadata):
    def __init__(self, rvt_element):
        super(PerforatorMetadata, self).__init__(rvt_element)

    @property
    def joint_guid(self):
        """The UniqueId of the Joint that generated the perforator.

        Returns:
            str: The joint's UniqueId as string
        """
        return self.metadata.get("JointGUID")
    
    @joint_guid.setter
    def joint_guid(self, value):
        self._update_metadata_property("JointGUID", value)