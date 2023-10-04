import sys
import uuid
import ifcopenshell
import ifcopenshell.util
import ifcopenshell.util.pset
import timeit

from pathlib import Path

create_guid = lambda: ifcopenshell.guid.compress(uuid.uuid1().hex)


def ifc_property_type_from_revit_parameter_value(revit_value):
    """
    TODO: check other possible types we might need
    """
    if isinstance(revit_value, bool):
        return "IfcBoolean", revit_value
    elif isinstance(revit_value, int):
        return "IfcInteger", revit_value
    elif isinstance(revit_value, float):
        return "IfcReal", revit_value
    else:
        return "IfcText", str(revit_value)


def get_relating_type(ifc_instance=None):
    for rel in ifc_instance.IsDefinedBy:
        if rel.is_a('IfcRelDefinesByType'):
            return rel.RelatingType
    return None


def get_revit_id_from_ifc_instance(ifc_instance=None):
    if not ifc_instance:
        return None

    if ifc_instance.is_a('IfcSpace'):
        relating_type = get_relating_type(ifc_instance)
        revit_id = relating_type.Tag
    else:
        try:
            revit_id = ifc_instance.Tag
        except AttributeError:
            raise AttributeError(f'No Tag found for id{revit_id}')
    return revit_id


def get_revit_property_value_from_dict(data_dict=None, ifc_instance=None, revit_property_name=None):
    # First check IfcSpace
    revit_id = get_revit_id_from_ifc_instance(ifc_instance)

    revit_instance_data = data_dict.get(revit_id)
    if not revit_instance_data:
        #print(f'No data for Revit id {revit_id}')
        return None
    revit_property_value = revit_instance_data.get(revit_property_name)
    if not revit_property_value:
        #print(f'{revit_property_name} has no value for instance with id {revit_id}')
        return None
    return revit_property_value


class RevitIfcDataHandler:
    """
    Expects a path to an ifc file

    Usage: ifchandler = RevitIfcDataHandler(ifc_file_path=ifc_file_path)

    """
    def __init__(self, ifc_file_path: Path):
        assert ifc_file_path
        self.ifc_file_path = ifc_file_path
        self.ifc_file = ifcopenshell.open(ifc_file_path)
        self.ifc_owner_history = self.ifc_file.by_type("IfcOwnerHistory")[0]

    def get_ifc_instance_from_revit_id(self, revit_id=None):
        """
        TODO: review because Tag is not Unique. i.e. openings have the same Tag as the walls they are hosted in
        That means that if we are looking for a wall we don't want its openings, do we?
        Some data is Ok to put in the opening, although it is linked to its host, so it is not necessary
        This is hardcoded should be modular somehow
        IfcSpaces (Rooms and Areas can be found from the IfcSpaceType Tag through ObjectTypeOf relation
        TODO: Invert the process and drive from the Ifc file: that is:
        create a map from the ifc file that we can search by revit id
        """
        # First we search for spatial elements
        for spt in self.ifc_file.by_type('IfcSpaceType', True):
             if spt.Tag == str(revit_id) and spt.ObjectTypeOf:
                space = spt.ObjectTypeOf[0].RelatedObjects[0]
                return space

        # Rest of building elements
        for ifc_instance in self.ifc_file.by_type('IfcBuildingElement', True):
            if ifc_instance.is_a() == 'IfcOpeningElement':
                continue
            if ifc_instance.Tag == str(revit_id):
                return ifc_instance
        #raise RuntimeError(f'No ifc instance found for id{revit_id}')
        return None

    def save_ifc(self, new_file_path: Path = None):
        if new_file_path:
            self.ifc_file.write(str(new_file_path))
            self.ifc_file_path = new_file_path
        else:
            self.ifc_file.write(str(self.ifc_file_path))

    def save_ifc_as(self, file_path: Path):
        return self.save_ifc(new_file_path=file_path)


class RevitIfcInstance:
    """
    Usage:

    inst = RevitIfcInstance(ifchandler, revit_id=2030408)

    """
    def __init__(self, handler: RevitIfcDataHandler, revit_id=None, ifc_instance=None):
        self.handler = handler
        if ifc_instance:
            self.instance = ifc_instance
            self.id = get_revit_id_from_ifc_instance(self.instance)
        else:
            self.id = str(revit_id)
            self.instance = self.handler.get_ifc_instance_from_revit_id(revit_id=self.id)

    def __repr__(self):
        return f'Ifc instance of {self.instance.is_a()} with Revit Id: {self.id}'

    @property
    def PSets(self):
        psets_dict = dict()
        for definition in self.instance.IsDefinedBy:
            if definition.is_a('IfcRelDefinesByProperties'):
                property_set = definition.RelatingPropertyDefinition
                psets_dict[property_set.Name] = property_set
        return psets_dict

    @property
    def is_ifc_instance_valid(self):
        try:
            return self.instance.is_a()
        except AttributeError:
            return False

    def get_pset_by_name(self, pset_name):
        for definition in self.instance.IsDefinedBy:
            if definition.is_a('IfcRelDefinesByProperties'):
                property_set = definition.RelatingPropertyDefinition
                if property_set.Name == pset_name:
                    return property_set
        return None

    def get_property_from_pset_by_name(self, instance_pset=None, ifc_property_name=None):
        for ifc_property in instance_pset.HasProperties:
            if ifc_property.Name == ifc_property_name:
                return ifc_property
        return None

    def edit_ifc_property(self,
                          ifc_property_set_name=None,
                          ifc_property_name=None,
                          ifc_property_description=None,
                          ifc_property_value=None):
        """
        Edits a property value if the property exists in the instance.

        It will use the revit data dict if no value is passed

        Usage:

        edit = inst.edit_ifc_property(ifc_property_set_name='EI_Interoperability',
                              ifc_property_name='Floor Span Vector',
                              ifc_property_description='CHANGED DESCRIPTION',
                              ifc_property_value='CHANGED TEST VALUE',
                              )
        """
        ifc_property_set = self.get_pset_by_name(pset_name=ifc_property_set_name)
        if not ifc_property_set:
            #print(f'Property set {ifc_property_set_name} not found for instance with id {self.id}')
            return None

        ifc_property = self.get_property_from_pset_by_name(instance_pset=ifc_property_set, ifc_property_name=ifc_property_name)
        if not ifc_property:
            #print(f'Instance with id {self.id} has no property {ifc_property_name}')
            return None

        assert ifc_property_value

        revit_property_type, revit_property_value = ifc_property_type_from_revit_parameter_value(ifc_property_value)
        existing_property_type = ifc_property.NominalValue.is_a()
        if revit_property_type != existing_property_type:
            #print(f'revit data type {revit_property_type} does not match ifctype {existing_property_type}')
            return None
        else:
            #print('datatypes match')
            ifc_property.NominalValue = self.handler.ifc_file.create_entity(revit_property_type, revit_property_value)
            if ifc_property_description: ifc_property.Description = ifc_property_description
        return self

    def add_ifc_property(self,
                         ifc_property_set_name=None,
                         ifc_property_name=None,
                         ifc_property_description=None,
                         ifc_property_value=None):
        """
        Doc
        """
        if not ifc_property_value: return None

        def create_ifc_property():
            revit_property_type, revit_property_value = ifc_property_type_from_revit_parameter_value(
                ifc_property_value)
            return self.handler.ifc_file.createIfcPropertySingleValue(ifc_property_name,
                                                                      ifc_property_description,
                                                                      self.handler.ifc_file.create_entity(
                                                                         revit_property_type,
                                                                         revit_property_value),
                                                                      None)


        # If property set exists we use it, else we create it
        ifc_property_set = self.get_pset_by_name(pset_name=ifc_property_set_name)
        if ifc_property_set:
            ifc_property = self.get_property_from_pset_by_name(instance_pset=ifc_property_set,
                                                           ifc_property_name=ifc_property_name)
            if ifc_property:
                edit = self.edit_ifc_property(ifc_property_set_name=ifc_property_set_name,
                                              ifc_property_name=ifc_property_name,
                                              ifc_property_description=ifc_property_description,
                                              ifc_property_value=ifc_property_value)
                return self
            else:
                ifc_property_set.HasProperties = ifc_property_set.HasProperties + tuple([create_ifc_property()])
                return self
        # If we get here we have to create property set as well as the property
        property_set = self.handler.ifc_file.createIfcPropertySet(create_guid(),
                                                                  self.handler.ifc_owner_history,
                                                                  ifc_property_set_name,
                                                                  None,
                                                                  [create_ifc_property()])
        # link property set to instance
        self.handler.ifc_file.createIfcRelDefinesByProperties(create_guid(),
                                                              self.handler.ifc_owner_history,
                                                              None,
                                                              None,
                                                              [self.instance],
                                                              property_set)

        return self


def test_ifc_patcher():
    ifc_filepath = r'C:\1_Temporal\EXPORT IFC_20220412_082436_IFC2x3.ifc'
    ifchandler = RevitIfcDataHandler(ifc_file_path=ifc_filepath)
    data_dict = {'3338946': {"Rooms_area":0.6666}}
    ifcinstance = RevitIfcInstance(ifchandler, revit_id='3311894')
    ifcinstance.add_ifc_property(ifc_property_set_name='RI_Rooms Information',
                                 ifc_property_name='Room_area',
                                 ifc_property_description='Test value',
                                 ifc_property_value=0.7777)
    ifcinstance = RevitIfcInstance(ifchandler, revit_id='2738092')
    ifcinstance.add_ifc_property(ifc_property_set_name='AI_Area Information',
                                 ifc_property_name='Area_area',
                                 ifc_property_description='Test value',
                                 ifc_property_value=0.6666)
    ifchandler.save_ifc()


def edit_ifc_data(ifchandler=None, ifc_instance=None, parameter_map=None, data_dict=None):
    if not ifc_instance:
        return

    rvt_ifc_instance = RevitIfcInstance(ifchandler, ifc_instance=ifc_instance)
    if not rvt_ifc_instance.is_ifc_instance_valid:
        return

    revit_id = rvt_ifc_instance.id

    for pset in parameter_map.keys():
        for data in parameter_map[pset]:
            revit_param, ifc_prop, prop_descr = data
            value = get_revit_property_value_from_dict(data_dict=data_dict,
                                                       ifc_instance=rvt_ifc_instance.instance,
                                                       revit_property_name=revit_param)
            if not value: continue
            rvt_ifc_instance.add_ifc_property(ifc_property_set_name=pset,
                                              ifc_property_name=ifc_prop,
                                              ifc_property_description=prop_descr,
                                              ifc_property_value=value)



if __name__ == "__main__":
    pass




