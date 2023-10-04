#!/usr/bin/env python
# -*- coding: utf-8 -*-


from zero11h.revit_api import System, DB, UI, RevitExceptions, _REVIT_DOCUMENT_
from zero11h.dynamo import DynLineMixin
import zero11h.geometry as geo


# 230707 Removed. Cross dependency with pyrevit not allowed for library
# from pyrevit import script

# # use this object like: logger.debug("Debug message")
# # Ctrl + Click on app to get a window with debug messages
# logger = script.get_logger()


class EnumLike(object):
    @classmethod
    def __iter__(cls):
        keys = [key for key in cls.__dict__.keys() if not key.startswith("__")]
        return iter([getattr(cls, key) for key in keys])


class ExecutionUnitsSubcategories(EnumLike):
    VEI = '2 EXT FINISH'
    VTS = '1 STR'
    FPPONO = '1 STR FireProtection OnSite'
    WLS = '0 INT Lining'


class LayerGroupSubcategories(EnumLike):
    VTS = '1.0 STR CLT'
    FPP = '1.1 STR FireProtection'
    TRS = '1.2 STR TRS'


class SharedParameterNames(EnumLike):
    EI_LocalisationCodeFloor = "EI_LocalisationCodeFloor"
    JS_C01_ID = "JS_C01_ID"
    JS_C02_ID = "JS_C02_ID"
    JS_C03_ID = "JS_C03_ID"
    JS_C04_ID = "JS_C04_ID"
    EI_Type = "EI_Type"
    JS_ParentJointInstanceID = "JS_ParentJointInstanceID"


class FamilyNames(EnumLike):
    GMO_CajaUnion = "GMO_CajaUnion"
    GMO_CajaUnionParent = "GMO_CajaUnionParent"
    AUX_TRS_Perforator = "AUX_TRS_Perforator"


SUBCATS = sorted([subcat for subcat in ExecutionUnitsSubcategories.__iter__()] +
                 [subcat for subcat in LayerGroupSubcategories.__iter__()])

TOLERANCE = 0.0005  # 0.5 mm

BUILTINCATEGORIES_DICT = {DB.ElementId(bic).IntegerValue: bic for bic in
                          DB.BuiltInCategory.GetValues(DB.BuiltInCategory)}


class WorksetUtils(object):
    @staticmethod
    def get_model_worksets():
        """
        Changed to function from constant because it has to account for changes in model or it will return
        obsolete or deleted ids
        Changed after error in dynamo
        :return:
        """
        return [wks for wks in DB.FilteredWorksetCollector(_REVIT_DOCUMENT_).OfKind(DB.WorksetKind.UserWorkset) if
                _REVIT_DOCUMENT_.IsWorkshared]

    @staticmethod
    def get_workset_name(wks_id_integer):
        res = None
        for wk in WorksetUtils.get_model_worksets():
            if wk.Id.IntegerValue == wks_id_integer:
                res = wk
        return res

    @staticmethod
    def get_workset_by_name(wks_name):
        for wk in WorksetUtils.get_model_worksets():
            if wk.Name == wks_name:
                return wk

        return None

    @staticmethod
    def set_element_workset(element, wks):
        element_workset_param = element.get_Parameter(DB.BuiltInParameter.ELEM_PARTITION_PARAM)
        if element_workset_param.AsInteger() != wks.Id.IntegerValue:
            element_workset_param.Set(wks.Id.IntegerValue)
            return True
        return False

    @staticmethod
    def create_workset(wks_name):
        if not _REVIT_DOCUMENT_.IsWorkshared:
            return None
        if not DB.WorksetTable.IsWorksetNameUnique(_REVIT_DOCUMENT_, wks_name):
            return None
        # We need to be in transaction
        return DB.Workset.Create(_REVIT_DOCUMENT_, wks_name)

    @staticmethod
    def checkout_elements(eids):
        '''
        Checks whether an element is checked out and can be modified or not.
        Returns two lists with checked out elements and not checked out
        '''
        checked_out_ids = DB.WorksharingUtils.CheckoutElements(_REVIT_DOCUMENT_,
                                                               System.Collections.Generic.List[DB.ElementId](eids))
        not_checked_out_ids = list()
        if len(checked_out_ids) != len(eids):
            for eid in eids:
                if eid not in checked_out_ids:
                    not_checked_out_ids.append(eid)

        return checked_out_ids, not_checked_out_ids


class UnitConversion(object):
    @staticmethod
    def feet_to_m(length):
        return DB.UnitUtils.ConvertFromInternalUnits(length, DB.UnitTypeId.Meters)

    @staticmethod
    def feet_to_mm(length):
        return DB.UnitUtils.ConvertFromInternalUnits(length, DB.UnitTypeId.Millimeters)

    @staticmethod
    def m_to_feet(length):
        return DB.UnitUtils.ConvertToInternalUnits(length, DB.UnitTypeId.Meters)

    @staticmethod
    def mm_to_feet(length):
        return DB.UnitUtils.ConvertToInternalUnits(length, DB.UnitTypeId.Millimeters)

    @staticmethod
    def rad_to_deg(angle):
        return DB.UnitUtils.ConvertFromInternalUnits(angle, DB.UnitTypeId.Degrees)

    @staticmethod
    def cubicfeet_to_m3(volume):
        return DB.UnitUtils.ConvertFromInternalUnits(volume, DB.UnitTypeId.CubicMeters)

    @staticmethod
    def squarefeet_to_m2(area):
        return DB.UnitUtils.ConvertFromInternalUnits(area, DB.UnitTypeId.SquareMeters)

    @staticmethod
    def m3_to_cubicfeet(volume):
        return DB.UnitUtils.ConvertToInternalUnits(volume, DB.UnitTypeId.CubicMeters)

    @staticmethod
    def m2_to_squarefeet(area):
        return DB.UnitUtils.ConvertToInternalUnits(area, DB.UnitTypeId.SquareMeters)

    @staticmethod
    def XYZ_to_Vector3(revit_xyz):
        """We use it for basis vectors that are normalized
        """
        return geo.Vector3(revit_xyz.X, revit_xyz.Y, revit_xyz.Z)

    @staticmethod
    def XYZ_to_Point3(revit_xyz):
        return geo.Point3(UnitConversion.feet_to_m(revit_xyz.X),
                          UnitConversion.feet_to_m(revit_xyz.Y),
                          UnitConversion.feet_to_m(revit_xyz.Z))

    @staticmethod
    def Point3_to_XYZ(point):
        return DB.XYZ(UnitConversion.m_to_feet(point.x),
                      UnitConversion.m_to_feet(point.y),
                      UnitConversion.m_to_feet(point.z))


class RvtTransform(object):
    """
    https://danimosite.wordpress.com/2021/09/07/transforms-transformed/
    """

    def __init__(self, rvt_transform):
        self.rvt_transform = rvt_transform

    @property
    def origin(self):
        return UnitConversion.XYZ_to_Point3(self.rvt_transform.Origin)

    def from_local_to_world(self, point):  # -> XYZ
        """
        Example use: mru.UnitConversion.XYZ_to_Point3(wall.local_transform.from_local_to_world(geo.Point3(0,0,0)))
        :param point:
        :return:
        """
        return self.rvt_transform.OfPoint(UnitConversion.Point3_to_XYZ(point))

    def from_world_XYZ_to_local(self, rvt_point):
        return UnitConversion.XYZ_to_Point3(self.rvt_transform.Inverse.OfPoint(rvt_point))


class PyParameterSet(object):
    """
    Collects all of the element parameters

    We handle separately Symbols and Instances
    """

    def __init__(self, rvtdbelement):  # None:
        self.rvtelement = rvtdbelement
        self.builtins = _BuiltInParameterSet(self.rvtelement)

    def __getitem__(self, param_name):  # 'PyParameter':
        parameter = self.rvtelement.LookupParameter(param_name)
        if not parameter:
            # TODO: link this error to missing shared parameters check somehow
            raise ValueError(
                'PyParameterSet Error: Parameter {} not found '.format(param_name) +
                'for element Id {} of category {}'.format(self.rvtelement.Id, self.rvtelement.Category.Name)
            )
        return PyParameter(parameter)

    def get_value(self, param_name, default_value=None):
        try:
            return self.__getitem__(param_name).value
        except ValueError:
            return default_value

    def __setitem__(self, param_name, value):  # None:
        """ Sets value to element's parameter.
        This is a shorcut to using `parameters['Name'].value = value`
        >>> element.parameters['Height'] = value
        """
        parameter = self.__getitem__(param_name)
        parameter.value = value


class _BuiltInParameterSet(object):
    """ Built In Parameter Manager
    Usage:
        location_line = element.parameters.builtins['WALL_LOCATION_LINE']
    Note:
        Item Getter can take the BuilInParameter name string, or the Enumeration.
        >>> element.parameters.builtins['WALL_LOCATION_LINE']
        or
        >>>element.parameters.builtins[Revit.DB.BuiltInParameter.WALL_LOCATION_LINE]
    Attributes:
        _revit_object (DB.Element) = Revit Reference
    """

    def __init__(self, rvtdbelement):  # None:
        self.rvtelement = rvtdbelement

    def getbipparam(self, builtin_enum):  # 'Parameter':
        bip = None
        try:
            bip = getattr(DB.BuiltInParameter, builtin_enum)
        except Exception:
            bip = None
        finally:
            return bip

    def __getitem__(self, builtin_enum):  # 'PyParameter':
        """ Retrieves Built In Parameter. """
        if isinstance(builtin_enum, str):
            builtin_enum = self.getbipparam(builtin_enum)
        parameter = self.rvtelement.get_Parameter(builtin_enum)
        if not parameter:
            raise RuntimeError('BuiltInParameter {} '.format(builtin_enum) +
                               'not found for element {}'.format(self.rvtelement)
                               )
        return PyParameter(parameter)

    def __setitem__(self, name, param_value):  # None:
        """ Sets value for an element's built in parameter. """
        builtin_parameter = self.__getitem__(name)
        builtin_parameter.value = param_value


class PyParameter(object):
    """
    Check for Python 3 compatibility

    Modifiied From RPW Parameter wrapper
    https://github.com/gtalarico/revitpythonwrapper/blob/master/rpw/db/parameter.py

    setters require a Transaction
    """
    # Python 3 in Dynamo return int value of Enum StorageType
    # STORAGE_TYPES = {
    #     3: str,
    #     2: float,
    #     1: int,
    #     4: Autodesk.Revit.DB.ElementId,
    #     0: None,
    # }
    STORAGE_TYPES = {
        'String': str,
        'Double': float,
        'Integer': int,
        'ElementId': DB.ElementId,
        'None': None,
    }

    def __init__(self, parameter):  # None:
        if not isinstance(parameter, DB.Parameter):
            raise TypeError('PyParameter: No Parameter Object to instantiate')
        self.rvtparameter = parameter
        self.id = self.rvtparameter.Id

    @property
    def name(self):  # ->  str:
        return self.rvtparameter.Definition.Name

    @property
    def builtin(self):
        return self.rvtparameter.Definition.BuiltInParameter

    @property
    def builtin_id(self):
        return DB.ElementId(self.builtin)

    @property
    def storage_type(self):
        # in Python 3 we get the enum int. Check this
        # storage_type_name = self.rvtparameter.StorageType
        # In IronPython
        storage_type_name = self.rvtparameter.StorageType.ToString()
        return PyParameter.STORAGE_TYPES[storage_type_name]

    @property
    def parameter_type(self):
        return self.rvtparameter.Definition.ParameterType  # ENUM Text, Length, etc.

    @property
    def value(self):
        if self.storage_type is str:
            return self.rvtparameter.AsString()
        if self.storage_type is float:
            return self.rvtparameter.AsDouble()
        if self.storage_type is DB.ElementId:
            return self.rvtparameter.AsElementId()
        if self.storage_type is int:
            return self.rvtparameter.AsInteger()

        raise TypeError('PyParameter: could not get storage type: {}'.format(self.storage_type))

    @value.setter
    def value(self, value):
        if self.rvtparameter.IsReadOnly:
            definition_name = self.rvtparameter.Definition.Name
            raise RuntimeError('Parameter is Read Only: {}'.format(definition_name))

        # Check if value provided matches storage type
        if not isinstance(value, self.storage_type):
            # If not, try to handle
            if self.storage_type is str and value is None:
                value = ''
            if self.storage_type is str and value is not None:
                value = str(value)
            elif self.storage_type is DB.ElementId and value is None:
                value = DB.ElementId.InvalidElementId
            elif isinstance(value, int) and self.storage_type is float:
                value = float(value)
            elif isinstance(value, float) and self.storage_type is int:
                value = int(value)
            elif isinstance(value, bool) and self.storage_type is int:
                value = int(value)
            else:
                raise TypeError(self.storage_type, value)

        param = self.rvtparameter.Set(value)
        return param


PROJECT_INFORMATION = PyParameterSet(
    DB.FilteredElementCollector(_REVIT_DOCUMENT_).OfCategory(DB.BuiltInCategory.OST_ProjectInformation).FirstElement())

# LEVEL HELPERS AND DATA
LOWER_FINISH_FACE_LEVEL_PREFIX = 'IAC'
STRUCTURAL_FINISH_LEVEL_PREFIX = 'SST'
STRUCTURAL_LEVEL_TYPE_DISCRIMINATOR = 'LVL_Structure'
ARCHITECTURAL_LEVEL_TYPE_DISCRIMINATOR = 'LVL_Architecture'
AUXILIARY_LEVEL_TYPE_DISCRIMINATOR = 'LVL_Auxiliar'


def get_rvt_level_by_name(lvl_name):
    for lvl in DB.FilteredElementCollector(_REVIT_DOCUMENT_).OfCategory(
            DB.BuiltInCategory.OST_Levels).WhereElementIsNotElementType():
        if lvl.Name == lvl_name:
            return lvl
    return None


class BldgLevel(object):
    def __init__(self, rvt_level):
        self.rvt_element = rvt_level
        self.rvt_type = _REVIT_DOCUMENT_.GetElement(self.rvt_element.GetTypeId())
        self.instance_parameters = PyParameterSet(self.rvt_element)
        self.type_parameters = PyParameterSet(self.rvt_type)
        self.name = self.rvt_element.Name
        self.family_name = self.type_parameters.builtins['SYMBOL_FAMILY_NAME_PARAM'].value
        self.type_name = self.type_parameters.builtins['SYMBOL_NAME_PARAM'].value
        self.is_rvt_bldg_story = self.instance_parameters.builtins['LEVEL_IS_BUILDING_STORY'].value
        self.is_structural = True if self.type_name == STRUCTURAL_LEVEL_TYPE_DISCRIMINATOR else False
        self.is_sst = True if self.type_name == STRUCTURAL_LEVEL_TYPE_DISCRIMINATOR and STRUCTURAL_FINISH_LEVEL_PREFIX in self.name else False
        self.is_architectural = True if self.type_name == ARCHITECTURAL_LEVEL_TYPE_DISCRIMINATOR else False
        self.is_auxiliary = True if self.type_name == AUXILIARY_LEVEL_TYPE_DISCRIMINATOR else False
        self.elevation = UnitConversion.feet_to_m(self.rvt_element.Elevation)
        self.storey = None

    @property
    def same_type_above(self):
        # return closest below of same type
        all_above = [lvl for lvl in sorted(ModelBldgLevels().get_all_of_same_type(self),
                                           key=lambda lvl: lvl.elevation,
                                           reverse=False) if lvl.elevation > self.elevation]
        if all_above:
            return all_above[0]
        return None

    @property
    def same_type_below(self):
        all_above = [lvl for lvl in sorted(ModelBldgLevels().get_all_of_same_type(self),
                                           key=lambda lvl: lvl.elevation,
                                           reverse=True) if lvl.elevation < self.elevation]
        if all_above:
            return all_above[0]
        return None

    def __repr__(self):
        return '{}:{} Elevation:{}'.format(self.name, self.type_name, self.elevation)


class BldgStorey(object):
    """A revit storey contains all the related levels to that storeys architectural level"""

    def __init__(self, bldg_levels):
        self.levels = bldg_levels
        self.level_below = None
        self.level_above = None

    @property
    def height(self):
        """computes storey height from self arch level to arch level above"""
        height = self.level_above.elevation - self.ffl.elevation if self.level_above else -1
        return height

    @property
    def ffl(self):
        """nivel de suelo terminado"""
        for lvl in self.levels:
            if lvl.is_architectural:
                return lvl
        return None

    @property
    def sst(self):
        """nivel de estructura terminada"""
        for lvl in self.levels:
            if lvl.is_structural and lvl.is_sst and lvl.is_rvt_bldg_story:
                return lvl
        return None

    @property
    def ist(self):
        """nivel de cara inferior de estructura terminada"""
        for lvl in self.levels:
            if lvl.is_structural and not (lvl.is_sst):
                return lvl
        return None

    @property
    def storey_above(self):
        if self.level_above:
            return self.level_above.storey
        return None

    @property
    def storey_below(self):
        if self.level_below:
            return self.level_below.storey
        return None

    def __repr__(self):
        return 'BuildingStorey {} Height:{}'.format(self.ffl.name, self.height)


class ModelBldgLevels(object):
    def __init__(self, rvt_document=_REVIT_DOCUMENT_):
        self.model_levels = sorted([BldgLevel(lvl)
                                    for lvl in DB.FilteredElementCollector(rvt_document).OfCategory(
                DB.BuiltInCategory.OST_Levels).WhereElementIsNotElementType()
                                    ],
                                   key=lambda lvl: lvl.rvt_element.Elevation,
                                   reverse=False)

    def get_level_by_name(self, lvl_name):
        for lvl in self.model_levels:
            if lvl.name == lvl_name:
                return lvl
        return None

    def get_all_of_same_type(self, bldg_lvl):
        res = []
        for lvl in self.model_levels:
            if (lvl.is_structural == bldg_lvl.is_structural and
                    lvl.is_sst == bldg_lvl.is_sst and
                    lvl.is_architectural == bldg_lvl.is_architectural and
                    lvl.is_rvt_bldg_story == bldg_lvl.is_rvt_bldg_story and
                    lvl.is_auxiliary == bldg_lvl.is_auxiliary and
                    lvl.name != bldg_lvl.name):
                res.append(lvl)
        return res

    def get_filtered_by_typename(self, type_name):
        return [lvl for lvl in self.model_levels if lvl.type_name == type_name]

    def get_structural(self, structural_finish_levels_only=False):
        if structural_finish_levels_only:
            return [lvl for lvl in self.get_filtered_by_typename(STRUCTURAL_LEVEL_TYPE_DISCRIMINATOR) if
                    lvl.name.startswith(STRUCTURAL_FINISH_LEVEL_PREFIX)]
        return self.get_filtered_by_typename(STRUCTURAL_LEVEL_TYPE_DISCRIMINATOR)

    def get_architectural(self):
        return [lvl for lvl in self.model_levels if lvl.is_architectural]  # and lvl.is_rvt_bldg_story]

    def _create_storey(self, arch_lvl, arch_level_below=None, arch_level_above=None):
        storey = BldgStorey([lvl for lvl in self.model_levels if arch_lvl.name in lvl.name])
        storey.level_below = arch_level_below
        storey.level_above = arch_level_above
        return storey

    def get_storeys(self):
        storeys = []
        arch_lvls = self.get_architectural()
        for idx, arch_lvl in enumerate(arch_lvls):
            storey = self._create_storey(arch_lvl,
                                         arch_level_below=arch_lvls[idx - 1] if idx > 0 else None,
                                         arch_level_above=arch_lvls[idx + 1] if idx < (len(arch_lvls) - 1) else None)
            storeys.append(storey)
        return storeys


MODEL_BLDGLEVELS = ModelBldgLevels()
MODEL_BLDGSTOREYS = MODEL_BLDGLEVELS.get_storeys()
# We set the storey of everylevel for reference later
for storey in MODEL_BLDGSTOREYS:
    for lvl in storey.levels:
        lvl.storey = storey


def is_element_vertical_component(rvt_element):
    """
    Used to fast check if an element is a component without instantiating it
    """
    if rvt_element.Category.Id != DB.Category.GetCategory(_REVIT_DOCUMENT_,
                                                          DB.BuiltInCategory.OST_StructuralColumns).Id:
        return False
    element_type = get_rvt_element_type(rvt_element)
    if not element_type:
        return False
    ei_type = element_type.LookupParameter('EI_Type')
    if not ei_type:
        return False
    if ei_type.AsString() != 'Component':
        return False

    return True


def filter_out_structural_vertical_components(rvt_elements):
    rvt_components = []
    for rvt_element in rvt_elements:
        if not is_element_vertical_component(rvt_element):
            continue
        element_type = get_rvt_element_type(rvt_element)
        if not element_type.LookupParameter('IsStructural'):
            continue
        if element_type.LookupParameter('IsStructural').AsInteger() != 1:
            continue
        rvt_components.append(rvt_element)

    return rvt_components


def delete_elements_by_guidstr(revit_elementguidstr_list):
    elements_to_delete = [_REVIT_DOCUMENT_.GetElement(guidstr) for guidstr in revit_elementguidstr_list]
    eids = System.Collections.Generic.List[DB.ElementId]()
    for element in elements_to_delete:
        if element:
            eids.Add(element.Id)
    _REVIT_DOCUMENT_.Delete(eids)


def get_model_components():  # ->  List[Autodesk.Revit.DB.Element]:
    # We get vertical components
    cat_list = System.Collections.Generic.List[DB.BuiltInCategory]([DB.BuiltInCategory.OST_StructuralColumns])
    cat_filter = DB.ElementMulticategoryFilter(cat_list)
    rvt_elements = DB.FilteredElementCollector(_REVIT_DOCUMENT_). \
        WherePasses(cat_filter). \
        WhereElementIsNotElementType()
    rvt_components = []
    for element in rvt_elements:
        el_type = get_rvt_element_type(element)
        if not el_type:
            continue
        ei_type = el_type.LookupParameter('EI_Type')
        if not ei_type:
            continue
        if ei_type.AsString() == 'Component':
            rvt_components.append(element)

    return rvt_components


def get_model_component_by_instance_id(instance_id=None):
    instance_id_parameter_name = 'EI_InstanceID'
    if not instance_id:
        return None
    model_components = get_model_components()
    component = [co for co in get_model_components()
                 if co.LookupParameter(instance_id_parameter_name).AsString() == instance_id]
    if not component:
        return None
    if len(component) == 1:
        return component[0]
    else:
        raise RuntimeError('More than one component in model with id {}'.format(instance_id))


def get_model_elements_by_id(ids):
    try:
        ids_list = list(iter(ids))
    except TypeError:
        ids_list = [ids]

    return [_REVIT_DOCUMENT_.GetElement(DB.ElementId(id)) for id in ids_list]


def get_rvt_element_type(rvt_element):  # ->  ElementType:
    try:
        return _REVIT_DOCUMENT_.GetElement(rvt_element.GetTypeId())
    except AttributeError:
        return None


def get_transform_local_cs_from_family_instance(rvt_family_instance):
    """
    For point based instances the origin is the local_cs origin
    For line based instances the start point of the location line is the local_cs origin

    Args:
        rvt_family_instance:

    Returns:
        Transform: Revit API Transform object with origin in instance location point and local axis
        CoordinateSystem3: local coordinate system of instance (metric)
    """
    rvt_transform = rvt_family_instance.GetTotalTransform()
    local_rvt_transform = rvt_transform.Identity
    location = rvt_family_instance.Location
    if isinstance(location, DB.LocationCurve):
        origin_feet = local_rvt_transform.Origin = location.Curve.GetEndPoint(0)
    else:
        origin_feet = location.Point
    local_rvt_transform.Origin = origin_feet
    local_rvt_transform.BasisX = rvt_transform.BasisX
    local_rvt_transform.BasisY = rvt_transform.BasisZ
    local_rvt_transform.BasisZ = rvt_transform.BasisY

    origin = UnitConversion.XYZ_to_Point3(origin_feet)
    local_vx = UnitConversion.XYZ_to_Vector3(rvt_transform.BasisX)
    local_vy = UnitConversion.XYZ_to_Vector3(rvt_transform.BasisZ)
    local_vz = UnitConversion.XYZ_to_Vector3(rvt_transform.BasisY)
    local_cs = geo.CoordinateSystem3(origin, local_vx, local_vy, local_vz)

    return local_rvt_transform, local_cs  # -> Transform, CoordinateSystem3


def get_symbol_geometry_from_instance(rvt_family_instance,
                                      rvt_view=None,
                                      view_detail=DB.ViewDetailLevel.Fine,
                                      include_invisible=False,
                                      compute_references=False):
    geo_options = DB.Options()

    if rvt_view:
        geo_options.View = rvt_view
    else:
        geo_options.DetailLevel = view_detail

    if compute_references:
        geo_options.ComputeReferences = True

    geo_options.IncludeNonVisibleObjects = include_invisible
    geom = rvt_family_instance.Geometry[geo_options]


def get_geometry_from_element(rvt_element,
                              rvt_view=None,
                              view_detail=DB.ViewDetailLevel.Fine,
                              include_invisible=False,
                              compute_references=False,
                              get_symbol_geometry=False):
    geo_options = DB.Options()

    if rvt_view:
        geo_options.View = rvt_view
    else:
        geo_options.DetailLevel = view_detail

    if compute_references:
        geo_options.ComputeReferences = True

    geo_options.IncludeNonVisibleObjects = include_invisible
    geom = rvt_element.Geometry[geo_options]

    def convert_geometry_instance(geo, elementlist, get_symbol=False):
        """
        When Revit needs to make a unique copy of the family geometry for a given instance
        (because of the effect of local joins, intersections,
        and other factors related to the instance placement) no GeometryInstance will be encountered;
        instead the Solid geometry will be found at the top level of the hierarchy.
        https://www.revitapidocs.com/2022/fe25b14f-5866-ca0f-a660-c157484c3a56.htm
        """
        for g in geo:
            if isinstance(g, DB.GeometryInstance):
                if get_symbol:
                    elementlist = convert_geometry_instance(g.GetSymbolGeometry(), elementlist)
                else:
                    elementlist = convert_geometry_instance(g.GetInstanceGeometry(), elementlist)
            else:
                elementlist.append(g)
        return elementlist

    return convert_geometry_instance(geom, [], get_symbol=get_symbol_geometry)


def get_symbol_geom_face_from_instance(element=None,
                                       ref_face=None):
    """
    Gets stable representation from face and returns equivalent face from SymbolGeometry
    https://thebuildingcoder.typepad.com/blog/2016/04/stable-reference-string-magic-voodoo.html

    Args:
        element:
        ref_face:

    Returns:

    """
    try:
        reference_string = ref_face.Reference.ConvertToStableRepresentation(_REVIT_DOCUMENT_)
    except Exception as ex:
        return None

    ref_string_tokens = reference_string.split(':')
    foundface = None
    for solid in RvtSolidUtils.get_all_solids_from_instance(element, compute_references=True,
                                                            get_symbol_geometry=True):
        for face in solid.Faces:
            if ':'.join(ref_string_tokens[-3:]) in face.Reference.ConvertToStableRepresentation(_REVIT_DOCUMENT_):
                foundface = face
                break
    if foundface:
        return foundface
    return None


def get_lines_from_family_by_subcategory(rvt_family_instance,
                                         subcat_name=None,
                                         rvt_view=None,
                                         view_detail=DB.ViewDetailLevel.Fine):
    geom = get_geometry_from_element(rvt_family_instance,
                                     rvt_view=rvt_view,
                                     view_detail=view_detail)

    lines = []
    for g1 in geom:
        gst = _REVIT_DOCUMENT_.GetElement(g1.GraphicsStyleId)
        if gst and isinstance(g1, DB.Line):
            if gst.Name == subcat_name:
                lines.append(g1)

    return lines


def get_plane_from_family_reference_by_name(rvt_family_instance, reference_name=None):
    def get_plane(reference=None):
        sketch = DB.SketchPlane.Create(_REVIT_DOCUMENT_, reference)
        plane = sketch.GetPlane()
        sketch.Dispose()
        return plane

    reference = rvt_family_instance.GetReferenceByName(reference_name)
    plane = None
    if _REVIT_DOCUMENT_.IsModifiable:
        try:
            trans1 = DB.SubTransaction(_REVIT_DOCUMENT_)
            trans1.Start()
            plane = get_plane(reference=reference)
            trans1.RollBack()
        except Exception as ex:
            print(ex)
        finally:
            trans1.Dispose()
    else:
        try:
            trans1 = DB.Transaction(_REVIT_DOCUMENT_, 'Ref Plane getter')
            trans1.Start()
            plane = get_plane(reference=reference)
            trans1.RollBack()
        except Exception as ex:
            print(ex)
        finally:
            trans1.Dispose()

    return plane


def get_vertices_from_edgeloop(edgeloop):
    return [edge.AsCurve().GetEndPoint(0) for edge in edgeloop]


def get_vertices_from_edgeloop_list(edgeloop_list):
    result = []
    if isinstance(edgeloop_list, DB.EdgeArrayArray):
        for edgeloop in edgeloop_list:
            result.extend(get_vertices_from_edgeloop(edgeloop))
    return result


def get_face_vertices(face):
    return get_vertices_from_edgeloop_list(face.EdgeLoops)


def get_p_min_and_p_max_from_xyzs(point_list):
    x_coords, y_coords, z_coords = [], [], []
    for p in point_list:
        x_coords.append(p.X)
        y_coords.append(p.Y)
        z_coords.append(p.Z)
    p_min = DB.XYZ(min(x_coords), min(y_coords), min(z_coords))
    p_max = DB.XYZ(max(x_coords), max(y_coords), max(z_coords))
    return p_min, p_max


def get_vertices_from_element(rvt_element,
                              include_invisible=False,
                              view_detail=DB.ViewDetailLevel.Fine):
    solids = RvtSolidUtils.get_all_solids_from_instance(rvt_element,
                                                        view_detail=view_detail,
                                                        include_invisible=include_invisible)
    if not solids:
        return []

    vertice_sets = [RvtSolidUtils.get_solid_vertices(solid) for solid in solids]
    vertices = set()
    for v_set in vertice_sets:
        [vertices.add(v) for v in v_set]
    return vertices


def get_element_face_from_point(rvt_element, rvt_point):
    solids = RvtSolidUtils.get_solids_from_instance(rvt_element,
                                                    filtered=False,
                                                    compute_references=True)
    for solid in solids:
        for face in solid.Faces:
            res = face.Project(rvt_point)
            if res:
                print(
                    'Projected point:{}\nOriginal point:{}\nDistance:{}'.format(res.XYZPoint, rvt_point, res.Distance))
                if abs(res.Distance) < 0.005:
                    return face
    return None


def get_bbox3_from_vertices_and_cs(vertices, local_cs):
    return geo.BoundingBox3.from_points(
        [local_cs.transform_to_local(UnitConversion.XYZ_to_Point3(v)) for v in vertices])


def get_bbox3_from_solid_and_cs(solid, local_cs):
    return get_bbox3_from_vertices_and_cs(RvtSolidUtils.get_solid_vertices(solid), local_cs)


def get_bbox3_from_element(rvt_element,
                           local_cs=None,
                           include_invisible=False,
                           view_detail=DB.ViewDetailLevel.Fine):
    """
    Function will only use solids to extract vertices to create bounding box
    For curved solids the function might return a smaller bounding box because curves are not
    subdivided.

    Args:
        rvt_element:
        local_cs: if provided the bounding box will be alignedf to the local_cs
        include_invisible: include voids for bounding box calculation

    Returns: geo.BoundingBox3 instance

    """
    if not local_cs:
        _, local_cs = get_transform_local_cs_from_family_instance(rvt_element)
    vertices = get_vertices_from_element(rvt_element,
                                         include_invisible=include_invisible,
                                         view_detail=view_detail)
    return get_bbox3_from_vertices_and_cs(vertices, local_cs)


def get_bboxXYZ_from_element(rvt_element):
    vertices = get_vertices_from_element(rvt_element, include_invisible=False)
    bbox = DB.BoundingBoxXYZ()
    bbox.Min, bbox.Max = get_p_min_and_p_max_from_xyzs(vertices)
    return bbox


def get_family_name(family_instance):
    if isinstance(family_instance, DB.FamilyInstance):
        return family_instance.Symbol.FamilyName
    return None


def get_elements_by_name(doc, category, family_name):
    """
    Get a list of all revit elements in the project that match a BuiltInCategory and Family Name.

    If no elements are found, returns None.

    Args:
        doc (Document): The active document
        category (BuintInCategory): The category of the elements
        family_name (str): The name of the family as a string
    """

    rvt_elements = DB.FilteredElementCollector(doc) \
        .OfCategory(category) \
        .WhereElementIsNotElementType() \
        .ToElements()

    # Filter by family name
    filtered_elements = []
    for elem in rvt_elements:
        if get_family_name(elem) == family_name:
            filtered_elements.append(elem)
    if filtered_elements:
        return filtered_elements


# Does this belong here?
class LineBounded(DynLineMixin, object):
    def __init__(self, p1, p2):  # ->  DB.Line:
        self.p1 = p1
        self.p2 = p2

    @classmethod
    def by_point_direction_distance(cls, p1, v1, dist):
        p2 = p1.translate(v1.normalized() * dist)
        return cls(p1, p2)

    @property
    def direction(self):
        return geo.Vector3.from_two_points(self.p1,
                                           self.p2)

    def to_revit(self):
        return DB.Line.CreateBound(UnitConversion.Point3_to_XYZ(self.p1),
                                   UnitConversion.Point3_to_XYZ(self.p2)
                                   )


class RvtFamilyInstanceConstructor(object):
    @staticmethod
    def line_based(revit_curve,
                   revit_family_type,
                   revit_level,
                   structural_type=DB.Structure.StructuralType.NonStructural):  # ->  FamilyInstance:

        return _REVIT_DOCUMENT_.Create.NewFamilyInstance(revit_curve, revit_family_type, revit_level, structural_type)

    @staticmethod
    def by_point(revit_xyz,
                 revit_family_type,
                 revit_level,
                 structural_type=DB.Structure.StructuralType.NonStructural):  # ->  FamilyInstance:

        return _REVIT_DOCUMENT_.Create.NewFamilyInstance(revit_xyz, revit_family_type, revit_level, structural_type)

    @staticmethod
    def by_point_aligned_to_other(reference=None,
                                  insertion_xyz=None,
                                  family_type=None,
                                  level=None,
                                  flip_reference_facing=False):

        if not all([reference, insertion_xyz, family_type, level]):
            return None

        new_instance = RvtFamilyInstanceConstructor.by_point(insertion_xyz,
                                                             family_type,
                                                             level)

        RvtFamilyInstanceConstructor.orient_instance(instance=new_instance,
                                                     ref_orientation=reference.FacingOrientation.Normalize(),
                                                     flip_reference_facing=flip_reference_facing)

        return new_instance

    @staticmethod
    def by_point_aligned_to_direction_and_orientation(ref_orientation=None,  # i.e. FacingOrientation
                                                      insertion_xyz=None,
                                                      family_type=None,
                                                      level=None,
                                                      flip_reference_facing=False):

        if not all([ref_orientation, insertion_xyz, family_type, level]):
            return None

        new_instance = RvtFamilyInstanceConstructor.by_point(insertion_xyz,
                                                             family_type,
                                                             level)

        RvtFamilyInstanceConstructor.orient_instance(instance=new_instance,
                                                     ref_orientation=ref_orientation.Normalize(),
                                                     flip_reference_facing=flip_reference_facing)

        return new_instance

    @staticmethod
    def orient_instance(instance=None,
                        ref_orientation=None,
                        flip_reference_facing=False):

        _REVIT_DOCUMENT_.Regenerate()
        if instance.FacingOrientation.IsUnitLength():
            instance_y_axis = instance.FacingOrientation
        else:
            instance_y_axis = instance.FacingOrientation.Normalize()

        if flip_reference_facing:
            instance_y_axis = instance_y_axis.Negate()

        reference_y_axis = ref_orientation.Normalize()

        rot_sign = 1 if reference_y_axis.CrossProduct(instance_y_axis).Z >= 0 else -1
        ref_y_axis_v3 = geo.Vector3(reference_y_axis.X,
                                    reference_y_axis.Y,
                                    reference_y_axis.Z)
        inst_y_axis_v3 = geo.Vector3(instance_y_axis.X,
                                     instance_y_axis.Y,
                                     instance_y_axis.Z)

        vectors_angle = abs(inst_y_axis_v3.angle_rad(ref_y_axis_v3)) * rot_sign
        rotation_axis = DB.Line.CreateBound(instance.Location.Point, DB.XYZ(instance.Location.Point.X,
                                                                            instance.Location.Point.Y,
                                                                            instance.Location.Point.Z + 1))

        DB.ElementTransformUtils.RotateElement(_REVIT_DOCUMENT_, instance.Id, rotation_axis, -vectors_angle)


class RvtDirectShape(object):
    def __init__(self, rvt_directshape_instance):
        self.rvt_ds = rvt_directshape_instance
        self.instance_parameters = PyParameterSet(self.rvt_ds)
        self.has_type = False
        try:
            self.rvt_ds_type = _REVIT_DOCUMENT_.GetElement(self.rvt_ds.GetTypeId())
            self.type_parameters = PyParameterSet(self.rvt_ds_type)
            self.has_type = True
        except Exception as ex:
            self.rvt_ds_type = None
            self.type_parameters = None

    @property
    def type_id(self):
        if self.type_parameters:
            return self.type_parameters['EI_TypeID'].value
        return None

    @staticmethod
    def delete_directshapetype(dstype=None):
        """
        Delete DirectShapeType and ALL of its DirectShape instances
        :return:
        """
        instances = [ds for ds in
                     DB.FilteredElementCollector(_REVIT_DOCUMENT_).OfClass(DB.DirectShape)
                     if ds.GetTypeId() == dstype.Id]

        deleted_ids = []
        element_ids = System.Collections.Generic.List[DB.ElementId]()
        for instance in instances:
            element_ids.Add(instance.Id)
        deleted_ids.extend(_REVIT_DOCUMENT_.Delete(element_ids))
        type_ids = System.Collections.Generic.List[DB.ElementId]()
        type_ids.Add(dstype.Id)
        deleted_ids.extend(_REVIT_DOCUMENT_.Delete(type_ids))
        _REVIT_DOCUMENT_.Regenerate()
        return deleted_ids

    @staticmethod
    def delete_directshapetype_if_no_instances(dstype=None):
        """
        Deletes type if no DirectShapes with given type exist in model

        We use this to avoid the bug where we cannot instantiate
        DirectShape with DirectShapeType if the type has no instances
        """
        if [ds for ds in
            DB.FilteredElementCollector(_REVIT_DOCUMENT_).OfClass(DB.DirectShape)
            if ds.GetTypeId() == dstype.Id]:
            return None
        return _REVIT_DOCUMENT_.Delete(dstype.Id)

    @staticmethod
    def get_directshapes():  # ->  DB.FilteredElementCollector:
        return DB.FilteredElementCollector(_REVIT_DOCUMENT_).OfClass(DB.DirectShape).WhereElementIsNotElementType()

    @staticmethod
    def get_directshapetypes():  # ->  DB.FilteredElementCollector:
        return DB.FilteredElementCollector(_REVIT_DOCUMENT_).OfClass(DB.DirectShapeType).WhereElementIsElementType()

    @staticmethod
    def create_dstype(dstype_name):
        """Creates DirectShape type of name dstype_name

        Requires transaction
        """
        dslib = DB.DirectShapeLibrary.GetDirectShapeLibrary(_REVIT_DOCUMENT_)
        dstype = DB.DirectShapeType.Create(_REVIT_DOCUMENT_,
                                           dstype_name,
                                           DB.ElementId(DB.BuiltInCategory.OST_GenericModel))
        # dstype.SetShape([rvt_solid])
        dslib.AddDefinitionType(dstype_name, dstype.Id)
        return dstype

    @staticmethod
    def get_dstype_byname(dstype_name):
        dstypes = DB.FilteredElementCollector(_REVIT_DOCUMENT_).OfClass(DB.DirectShapeType)
        if dstypes.GetElementCount() > 0:
            for dst in dstypes:
                dst_name = dst.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()
                if dst_name == dstype_name:
                    # IMPORTANT: If DirectShapeType has no instances, we delete and create it again
                    if RvtDirectShape.delete_directshapetype_if_no_instances(dstype=dst):
                        break
                    # We add dst to documents DirectShapeLibrary
                    # Omitting this step creates error between Revit sessions
                    dslib = DB.DirectShapeLibrary.GetDirectShapeLibrary(_REVIT_DOCUMENT_)
                    dslib.AddDefinitionType(dstype_name, dst.Id)
                    return dst
        return RvtDirectShape.create_dstype(dstype_name)

    @staticmethod
    def ds_from_solid_wdstype(rvt_solid,
                              name,
                              original_element=None,
                              dstype=None):

        assert dstype, "ds_from_solid_wdstype failed: no dstype"
        assert name, "no panel.id for DirectShape"
        dstype.SetShape([rvt_solid])
        dstype_name = dstype.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()
        ds = DB.DirectShape.CreateElementInstance(_REVIT_DOCUMENT_,
                                                  dstype.Id,
                                                  dstype.Category.Id,
                                                  dstype_name,
                                                  DB.Transform.Identity)
        if not ds:
            # Este error saltaba con DirectShapeTypes que no tienen instancias en el modelo
            msg = "ds_from_solid_wdstype failed with DirectShapeType {} {}. Try purging DS Types".format(dstype.Id,
                                                                                                         name)
            UI.TaskDialog.Show("ERROR", msg)
            raise Exception(msg)
        ds.SetTypeId(dstype.Id)
        ds.ApplicationId = "011h_Componentizator"
        ds.ApplicationDataId = "Geometry object Id"  # TODO: Set this to something meaningful
        ds.SetShape([rvt_solid])
        ds.SetName(name)
        dsOptions = ds.GetOptions()
        dsOptions.ReferencingOption = DB.DirectShapeReferencingOption.Referenceable

        return ds

    @staticmethod
    def update_ds_solid(direct_shape, rvt_solid):
        direct_shape.SetShape([rvt_solid])
        return direct_shape

    @staticmethod
    def get_dshape_by_instance_id(instance_id):
        found = []
        for dshape in RvtDirectShape.get_directshapes():
            ei_instance_id_param = dshape.LookupParameter('EI_InstanceID')
            if not ei_instance_id_param:
                continue
            if ei_instance_id_param.AsString() == instance_id:
                found.append(dshape)

        if found and len(found) == 1:
            return found[0]
        if len(found) > 1:
            raise RuntimeError('LayerGroup instance {} is duplicated in model'.format(instance_id))
        return None


class RvtSolidUtils(object):
    @staticmethod
    def get_material_from_solid(rvt_solid):  # Material:
        """
        Return the most used material id in solid faces

        Args:
            rvt_solid:

        Returns:

        """
        face_materials = {}
        for face in rvt_solid.Faces:
            mat_int_id = face.MaterialElementId.IntegerValue
            if mat_int_id in face_materials.keys():
                face_materials[mat_int_id].append(face)
            else:
                face_materials[mat_int_id] = [face]
        mat_int_id = sorted(face_materials.items(), key=lambda x: len(x[1]), reverse=True)[0][0]
        return _REVIT_DOCUMENT_.GetElement(DB.ElementId(mat_int_id))

    @staticmethod
    def get_all_solids_from_instance(rvt_element,
                                     rvt_view=None,
                                     view_detail=DB.ViewDetailLevel.Fine,
                                     include_invisible=True,
                                     compute_references=False,
                                     get_symbol_geometry=False):

        geom = get_geometry_from_element(rvt_element,
                                         rvt_view=rvt_view,
                                         view_detail=view_detail,
                                         include_invisible=include_invisible,
                                         compute_references=compute_references,
                                         get_symbol_geometry=get_symbol_geometry)

        return [solid for solid in geom if isinstance(solid, DB.Solid) and solid.Volume != 0]

    @staticmethod
    def get_solids_from_instance(rvt_element,
                                 subcats_to_extract=SUBCATS,
                                 detail_level=DB.ViewDetailLevel.Fine,
                                 compute_references=False,
                                 filtered=True):  # -> Dict[str, List[DB.Solid]]
        """
        Voids have the subcat name "Cutting geometry" and Id -1

        Args:
            rvt_element:
            subcats_to_extract:
            detail_level:
            filtered:
            voids_only:

        Returns:

        """

        def get_solids_by_subcat(solid_list, subcat_list):
            solid_dikt = {}
            for solid in solid_list:
                gst_name = _REVIT_DOCUMENT_.GetElement(solid.GraphicsStyleId)
                if gst_name:
                    if gst_name.Name in subcat_list:
                        if solid_dikt.get(gst_name.Name):
                            solid_dikt[gst_name.Name].append(solid)
                        else:
                            solid_dikt[gst_name.Name] = [solid]

            return solid_dikt

        solids_and_voids = RvtSolidUtils.get_all_solids_from_instance(rvt_element,
                                                                      compute_references=compute_references)

        if filtered and not subcats_to_extract:
            return None

        if not filtered:
            return [solid for solid in solids_and_voids if solid.Id != -1]

        return get_solids_by_subcat(solids_and_voids, subcats_to_extract)

    @staticmethod
    def get_cutting_voids_from_instance(rvt_element):
        solids_and_voids = RvtSolidUtils.get_all_solids_from_instance(rvt_element,
                                                                      include_invisible=True)
        return [solid for solid in solids_and_voids if solid.Id == -1]

    @staticmethod
    def get_boundingbox_solid_from_instance(rvt_element,
                                            subcat_name='AUX--BoundingBox'):  # -> DB.Solid:
        """
        Returns: first solid found of subcat AUX--BoundingBox in family instance
        """
        solids = RvtSolidUtils.get_all_solids_from_instance(rvt_element,
                                                            view_detail=DB.ViewDetailLevel.Coarse,
                                                            include_invisible=False)
        for solid in solids:
            if solid.Id != -1 and solid.GraphicsStyleId:
                if _REVIT_DOCUMENT_.GetElement(solid.GraphicsStyleId).Name == subcat_name:
                    return solid

        return None

    @staticmethod
    def get_solid_vertices(rvt_solid):  # -> Set[XYZ]:
        vertices = set()
        for edge in rvt_solid.Edges:
            # TODO: if edge is not a straight edge we would need to subdivide it to get the vertices
            vertices.add(edge.AsCurve().GetEndPoint(0))

        return vertices

    @staticmethod
    def get_solid_face_from_normal(rvt_solid, vect):
        """Returns the one with the biggest area from found"""
        tolerance = 0.01
        if not isinstance(vect, DB.XYZ):
            xyz = DB.XYZ(vect.x, vect.y, vect.z)
        else:
            xyz = vect
        faces = []
        for face in rvt_solid.Faces:
            if (1.0 - tolerance) \
                    < face.ComputeNormal(DB.UV(0.5, 0.5)).DotProduct(xyz) \
                    < (1.0 + tolerance):
                faces.append(face)

        sorted_faces = sorted(faces, key=lambda x: x.Area, reverse=True)
        if not sorted_faces:
            return None
        return sorted_faces[0]

    @staticmethod
    def get_solid_face_area_from_normals(rvt_solid, vect):
        face = RvtSolidUtils.get_solid_face_from_normal(rvt_solid, vect)
        if face:
            return face.Area
        return None

    @staticmethod
    def get_solid_face_normals(rvt_solid):
        return [face.ComputeNormal(DB.UV(0.5, 0.5)) for face in rvt_solid.Faces]

    @staticmethod
    def split_solid_volumes(rvt_solid):  # List[DB.Solid]:
        return DB.SolidUtils.SplitVolumes(rvt_solid)

    @staticmethod
    def get_intersecting_elements_with_solid(rvt_elements, solid):
        filter = DB.ElementIntersectsSolidFilter(solid)
        return [element for element in rvt_elements if filter.PassesFilter(element)]

    @staticmethod
    def create_rectangular_prism_at_point(dim_x, dim_y, dim_z, transform=None, local_origin_p3=None):
        """

        :param dim_x:
        :param dim_y:
        :param dim_z:
        :param new_tf:
        :param local_origin_p3: relative to the transform passed
        :return:
        """
        if transform:
            d1 = dim_x
            d2 = dim_y
            d3 = dim_z
            new_rvt_tf = DB.Transform.Identity
            new_rvt_tf.BasisX = transform.rvt_transform.BasisX
            new_rvt_tf.BasisY = transform.rvt_transform.BasisY
            new_rvt_tf.BasisZ = transform.rvt_transform.BasisZ
            new_rvt_tf.Origin = transform.from_local_to_world(local_origin_p3)
            new_tf = RvtTransform(new_rvt_tf)
            p0 = new_tf.from_local_to_world(geo.Point3(-d1 / 2.0, -d2 / 2.0, -d3 / 2.0))
            p1 = new_tf.from_local_to_world(geo.Point3(-d1 / 2.0, d2 / 2.0, -d3 / 2.0))
            p2 = new_tf.from_local_to_world(geo.Point3(d1 / 2.0, d2 / 2.0, -d3 / 2.0))
            p3 = new_tf.from_local_to_world(geo.Point3(d1 / 2.0, -d2 / 2.0, -d3 / 2.0))
            extrusion_dir = new_tf.rvt_transform.BasisZ
        else:
            d1 = UnitConversion.m_to_feet(dim_x)
            d2 = UnitConversion.m_to_feet(dim_y)
            d3 = UnitConversion.m_to_feet(dim_z)
            p0 = DB.XYZ(-d1 / 2.0, -d2 / 2.0, -d3 / 2.0)
            p1 = DB.XYZ(-d1 / 2.0, d2 / 2.0, -d3 / 2.0)
            p2 = DB.XYZ(d1 / 2.0, d2 / 2.0, -d3 / 2.0)
            p3 = DB.XYZ(d1 / 2.0, -d2 / 2.0, -d3 / 2.0)
            extrusion_dir = DB.XYZ.BasisZ
        profile = System.Collections.Generic.List[DB.Curve]()
        profile.Add(DB.Line.CreateBound(p0, p1))
        profile.Add(DB.Line.CreateBound(p1, p2))
        profile.Add(DB.Line.CreateBound(p2, p3))
        profile.Add(DB.Line.CreateBound(p3, p0))

        curveLoop = DB.CurveLoop.Create(profile)
        options = DB.SolidOptions(DB.ElementId.InvalidElementId, DB.ElementId.InvalidElementId)
        prism = DB.GeometryCreationUtilities.CreateExtrusionGeometry([curveLoop],
                                                                     extrusion_dir,
                                                                     UnitConversion.m_to_feet(dim_z),
                                                                     options)
        return prism

    @staticmethod
    def solid_solid_boolean(solid1, solid2, recursion_depth=0, boolean_type=None):
        """
        See: https://forums.autodesk.com/t5/revit-api-forum/boolean-operation-fail/td-p/7531968
        This method uses recursion
        """
        if recursion_depth > 5:
            return 'Recursion limit exceeded'
        if not boolean_type:
            raise ValueError('_sol_sol_boolean error: No boolean_type specified')

        try:
            result_solid = DB.BooleanOperationsUtils.ExecuteBooleanOperation(solid1,
                                                                             solid2,
                                                                             boolean_type)

        except RevitExceptions.InvalidOperationException as rvex:
            d_move_distance = UnitConversion.m_to_feet(0.0005)
            t1 = DB.Transform.CreateTranslation(DB.XYZ(0, 0, -d_move_distance))
            solid2 = DB.SolidUtils.CreateTransformed(solid2, t1)
            result_solid = RvtSolidUtils.solid_solid_boolean(solid1,
                                                             solid2,
                                                             recursion_depth=recursion_depth + 1,
                                                             boolean_type=boolean_type)
        return result_solid

    @staticmethod
    def solid_solid_valid_intersection(s1, s2):
        """

        :param s1: solid1
        :param s2: solid2
        :return: 0 no intersection, 1 intersection, 2 touching, 9 max recursion depth exceeded
        """
        TOLERANCE = 0.000001

        intersect_solid = RvtSolidUtils.solid_solid_boolean(s1, s2, boolean_type=DB.BooleanOperationsType.Intersect)

        if not intersect_solid:
            return 0
        if intersect_solid == 'Recursion limit exceeded':
            return 9

        if abs(intersect_solid.Volume) > TOLERANCE:
            intersect_solid.Dispose()
            return 1

        union_solid = DB.BooleanOperationsUtils.ExecuteBooleanOperation(s1, s2, DB.BooleanOperationsType.Union)
        dArea = abs(s1.SurfaceArea + s2.SurfaceArea - union_solid.SurfaceArea)
        if dArea < TOLERANCE and s1.Edges.Size + s2.Edges.Size == union_solid.Edges.Size:
            return_value = 0
        else:
            return_value = 2

        union_solid.Dispose()
        return return_value

    @staticmethod
    def solid_solid_valid_difference(s1, s2):
        """
        REFACTOR. NOT VALID

        :return: -1 if InvalidOperationException, 1 difference Ok, 9 max recursion depth exceeded

        """
        raise RuntimeError('NOT VALID. NOT IMPLEMENTED')
        TOLERANCE = 0.0001

        def _sol_sol_difference(solid1, solid2, recursion_depth=0):
            if recursion_depth > 5:
                return None
            booltype = DB.BooleanOperationsType.Difference
            if s2.Volume < 0:
                booltype = DB.BooleanOperationsType.Union
            try:
                difference_solid = DB.BooleanOperationsUtils.ExecuteBooleanOperation(solid1, solid2, booltype)
            except RevitExceptions.InvalidOperationException as rvex:
                # print(rvex.Message)
                # print('Trying again moving in Z')
                d_move_distance = UnitConversion.m_to_feet(0.0005)
                t1 = DB.Transform.CreateTranslation(DB.XYZ(0, 0, -d_move_distance))
                solid2 = DB.SolidUtils.CreateTransformed(solid2, t1)
                difference_solid = _sol_sol_difference(solid1, solid2, recursion_depth=recursion_depth + 1)
            return difference_solid

        print('Volumes of Solid1:{} Solid2:{}'.format(s1.Volume, s2.Volume))

        difference_solid = _sol_sol_difference(s1, s2)
        print('Difference solid volume:{}'.format(difference_solid.Volume))
        if not difference_solid:
            return -1

        diff_volume = abs(abs(difference_solid.Volume) - abs(s2.Volume))
        print('Difference volume:{}'.format(diff_volume))
        if diff_volume < 0.001:
            return -1

        return 1

    @staticmethod
    def create_oriented_boundingbox_from_instance(rvt_family_instance,
                                                  offset_z_m=0.0,
                                                  include_voids=False):
        """

        Args:
            rvt_family_instance: FamilyInstance
            offset_z_m: Float

        Returns:
            b_box_solid: DB.Solid

        """
        local_rvt_transform, local_cs = get_transform_local_cs_from_family_instance(rvt_family_instance)
        vertices = get_vertices_from_element(rvt_family_instance, include_invisible=include_voids)

        local_vertices = [local_cs.transform_to_local(UnitConversion.XYZ_to_Point3(v)) for v in vertices]
        min_local_z = min([vtx.z for vtx in local_vertices])
        max_local_z = max([vtx.z for vtx in local_vertices])
        min_local_x = min([vtx.x for vtx in local_vertices])
        max_local_x = max([vtx.x for vtx in local_vertices])
        min_local_y = min([vtx.y for vtx in local_vertices])
        max_local_y = max([vtx.y for vtx in local_vertices])
        b_box_length = abs(min_local_x - max_local_x)
        b_box_height = abs(min_local_y - max_local_y)
        b_box_thickness = abs(min_local_z - max_local_z + UnitConversion.m_to_feet(offset_z_m))
        b_box_origin = geo.Point3((max_local_x - min_local_x) / 2.0 + min_local_x,
                                  (max_local_y - min_local_y) / 2.0 + min_local_y,
                                  (max_local_z - min_local_z) / 2.0 + min_local_z)

        b_box_solid = RvtSolidUtils.create_rectangular_prism_at_point(dim_x=b_box_length,
                                                                      dim_y=b_box_height,
                                                                      dim_z=b_box_thickness,
                                                                      transform=RvtTransform(local_rvt_transform),
                                                                      local_origin_p3=b_box_origin)

        return b_box_solid

    @staticmethod
    def create_oriented_boundingbox_from_instance_references(rvt_family_instance,
                                                             offset_z_m=0.0):
        """

        Args:
            rvt_family_instance: FamilyInstance
            offset_z_m: Float

        Returns:
            b_box_solid: DB.Solid
        """
        local_rvt_transform, local_cs = get_transform_local_cs_from_family_instance(rvt_family_instance)

        # Process references
        reference_names = ['Top', 'Bottom', 'Left', 'Right']
        planes_dict = {}

        for reference_name in reference_names:
            plane = get_plane_from_family_reference_by_name(rvt_family_instance,
                                                            reference_name=reference_name)
            if not plane:
                raise RuntimeError("Missing reference: {} for instance id {}".format(reference_name,
                                                                                     rvt_family_instance.Id.IntegerValue))
            planes_dict[reference_name] = plane

        bottom = geo.Point3(0.0, 0.0, 0.0)
        top = local_cs.transform_to_local(UnitConversion.XYZ_to_Point3(planes_dict['Top'].Origin))
        left = local_cs.transform_to_local(UnitConversion.XYZ_to_Point3(planes_dict['Left'].Origin))
        right = local_cs.transform_to_local(UnitConversion.XYZ_to_Point3(planes_dict['Right'].Origin))
        top.x, top.z = 0.0, 0.0
        left.y, left.z = 0.0, 0.0
        right.y, right.z = 0.0, 0.0

        b_box_length = geo.Vector3.from_two_points(left, right).length
        b_box_height = geo.Vector3.from_two_points(bottom, top).length
        b_box_thickness = 1.0
        b_box_origin = geo.Point3(0.0,
                                  b_box_height / 2.0,
                                  0.0)

        b_box_solid = RvtSolidUtils.create_rectangular_prism_at_point(dim_x=b_box_length,
                                                                      dim_y=b_box_height,
                                                                      dim_z=b_box_thickness,
                                                                      transform=RvtTransform(local_rvt_transform),
                                                                      local_origin_p3=b_box_origin)

        return b_box_solid

    @staticmethod
    def oriented_BoundingBox3_from_solid(local_cs=None,
                                         solid=None):
        vertices = RvtSolidUtils.get_solid_vertices(rvt_solid=solid)
        local_vertices = [local_cs.transform_to_local(UnitConversion.XYZ_to_Point3(v)) for v in vertices]
        return geo.BoundingBox3.from_points(local_vertices)


class RvtSubcomponents(object):
    @staticmethod
    def get_openings_from_instance(rvt_family_instance, filtered=True, builtin_cat_list=None):  # List[FamilyInstance]:
        """
        The responsibility of this function is to return the opening elements cutting the component.
        If the windows are cutting instances and not hosted instances we will use:

        InstanceVoidCutUtils.GetElementsBeingCut(window) -> returns the component
        InstanceVoidCutUtils.GetCuttingVoidInstances(component) -> returns a list of the cutting elements

        TODO: flag windows cutting more than one component or create a QC test for that
        cut_element_ids = InstanceVoidCutUtils.GetElementsBeingCut(opening)

        :param rvt_family_instance:
        :return:
        """
        # subcomponents = [_REVIT_DOCUMENT_.GetElement(eid) for eid in rvt_family_instance.GetSubComponentIds()]
        # Con esto tenemos la familia de primer nivel, con GetSubcomponentIs tendríamos la familia compartida
        subcomponents = [_REVIT_DOCUMENT_.GetElement(eid) for eid in
                         DB.InstanceVoidCutUtils.GetCuttingVoidInstances(rvt_family_instance)]
        default_bics = [DB.BuiltInCategory.OST_Windows, DB.BuiltInCategory.OST_Doors]

        if not filtered:
            return subcomponents

        cat_ids = [DB.Category.GetCategory(_REVIT_DOCUMENT_, bic).Id.IntegerValue for bic in default_bics]
        if builtin_cat_list:
            cat_ids = [DB.Category.GetCategory(_REVIT_DOCUMENT_, bic).Id.IntegerValue for bic in builtin_cat_list]
        return [element for element in subcomponents
                if element.Category.Id.IntegerValue in cat_ids]

    @staticmethod
    def get_all_of_same_category(rvt_family_instance):
        subcomponents = [_REVIT_DOCUMENT_.GetElement(eid) for eid in rvt_family_instance.GetSubComponentIds()]
        return [element for element in subcomponents
                if element.Category.Id == rvt_family_instance.Category.Id]

    @staticmethod
    def is_subcomponent_cutting_host(rvt_family_instance, rvt_element_host):
        """
        Function tests if instance is actually cutting host
        """
        pass


class RvtNearbyElements(object):
    @staticmethod
    def get_nearby_elements(rvt_element, rvt_builtin_category_list=None, tolerance=0.1):
        tolerance_xyz = DB.XYZ(UnitConversion.m_to_feet(tolerance),
                               UnitConversion.m_to_feet(tolerance),
                               UnitConversion.m_to_feet(tolerance))

        # category_list = System.Collections.Generic.List[DB.BuiltInCategory]([DB.BuiltInCategory.Parse(DB.BuiltInCategory, System.Enum.GetName(DB.BuiltInCategory, eid.IntegerValue)) for eid in cat_id_list])
        if not rvt_builtin_category_list:
            # use same category as element
            rvt_builtin_category_list = [BUILTINCATEGORIES_DICT[rvt_element.Category.Id.IntegerValue]]

        cat_list = System.Collections.Generic.List[DB.BuiltInCategory](rvt_builtin_category_list)
        if not cat_list:
            return None
        if len(cat_list) == 1:
            cat_filter = DB.ElementCategoryFilter(rvt_builtin_category_list[0])
        else:
            cat_filter = DB.ElementMulticategoryFilter(cat_list)

        element_bbox = get_bboxXYZ_from_element(rvt_element)  # rvt_element.get_BoundingBox(None)
        outline = DB.Outline(element_bbox.Min.Subtract(tolerance_xyz), element_bbox.Max.Add(tolerance_xyz))
        bbox_intersects_filter = DB.BoundingBoxIntersectsFilter(outline)

        return [elem for elem in DB.FilteredElementCollector(_REVIT_DOCUMENT_).WherePasses(cat_filter).WherePasses(
            bbox_intersects_filter)
                if elem.Id != rvt_element.Id]

    @staticmethod
    def get_nearby_components(rvt_element,
                              tolerance=0.1,
                              same_level=False):
        # check that element is component
        if not is_element_vertical_component(rvt_element):
            return []
        # get nearby components
        nearby = [element for element in RvtNearbyElements.get_nearby_elements(rvt_element,
                                                                               tolerance=tolerance) if
                  is_element_vertical_component(element)]
        if same_level:
            source_level_id = rvt_element.get_Parameter(DB.BuiltInParameter.FAMILY_LEVEL_PARAM).AsElementId()
            nearby = [element for element in nearby
                      if
                      element.get_Parameter(DB.BuiltInParameter.FAMILY_LEVEL_PARAM).AsElementId() == source_level_id]
        # We create the bounding box from solid vertices thus eliminating the model lines in component that
        # make bounding box a little bit wider. This way its more precise.
        element_bbox = get_bboxXYZ_from_element(rvt_element)
        element_bbox_z_domain = geo.Domain1d(d_min=element_bbox.Min.Z,
                                             d_max=element_bbox.Max.Z)
        nearby_components = []
        for other_element in nearby:
            other_element_bbox = get_bboxXYZ_from_element(other_element)
            other_element_bbox_z_domain = geo.Domain1d(d_min=other_element_bbox.Min.Z,
                                                       d_max=other_element_bbox.Max.Z)

            if element_bbox_z_domain.overlaps(other_element_bbox_z_domain):
                nearby_components.append(other_element)

        return nearby_components

    @staticmethod
    def get_non_structural_perpendicular_components(rvt_element):
        res = []
        local_x = UnitConversion.XYZ_to_Vector3(rvt_element.HandOrientation)
        for comp in RvtNearbyElements.get_nearby_components(rvt_element, tolerance=0.05, same_level=False):
            if comp.Symbol.LookupParameter('IsStructural').AsInteger() == 1:
                continue
            vx = UnitConversion.XYZ_to_Vector3(comp.HandOrientation)
            if local_x.almost_perpendicular(vx):
                res.append(comp)
        return res


class GenericIdGenerator():
    """ Construct an id generator that get's the next availiable id given a list of revit elements. """

    def __init__(self, parameter_name, collector, prefix="", suffix=""):
        """After instantiation call next_id.

        The constructed id will be: <prefix> <4digits> <suffix>

        Args:
            parameter_name (str): The parameter name where the id is stored
            collector (list): The collection of existing elements with ids
            prefix (str, optional): Optional prefix for the id. Defaults to "".
            suffix (str, optional): Optional suffix for the id. Defaults to "".

        Returns:
            _type_: _description_
        """
        self.parameter_name = parameter_name
        self.collector = collector
        self.prefix = prefix
        self.suffix = suffix

    @property
    def next_id(self):
        number = self._get_next_availiable_number()
        four_digits = "{0:04d}".format(number)
        return self.prefix + four_digits + self.suffix

    def _get_next_availiable_number(self):
        # Get ids (ex: prefix0234suffix)
        collected_ids = []
        for elem in self.collector:
            param = elem.LookupParameter(self.parameter_name)
            if param:
                param_name = param.AsString()
                if param_name:
                    collected_ids.append(param_name)
        # logger.debug("Collected ids are:")
        # logger.debug(collected_ids)
        # Get integers list (ex: 234)
        numbers = []
        for id in collected_ids:
            num = id.replace(self.prefix, "")
            num = num.replace(self.suffix, "")
            if num.isdigit():
                num = int(num)
                numbers.append(num)
        # logger.debug("Numbers are: ")
        # logger.debug(numbers)
        # Get next availiable integer
        if len(numbers) == 0:
            return 1
        r = range(1, max(numbers) + 2)
        diff = set(r) - set(numbers)
        # logger.debug("Min number is: {}".format(min(diff)))
        return min(diff)
        # https://stackoverflow.com/questions/67305368/find-next-available-integer-in-sorted-list
