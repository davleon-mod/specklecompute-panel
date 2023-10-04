
import Autodesk
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Structure import *
from  Autodesk.Revit.UI import *
from Autodesk.Revit.DB.ExtensibleStorage import *

import ast
import System
from System import *
from System.Collections.Generic import List
import uuid

doc = __revit__.ActiveUIDocument.Document
import System
class Components_database():

	def __init__(self):
		self.element = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_ProjectInformation).ToElements()[0]
		self.guid = Guid("541B565A-7320-40FF-BAB8-CA3E6B78BA8D")
		
		#Construir el schema
		schemaBuilder = ExtensibleStorage.SchemaBuilder(self.guid)
		#Permitir lectura a todo el mundo
		schemaBuilder.SetReadAccessLevel(ExtensibleStorage.AccessLevel.Public)
		#Permitir escritura solo al creador
		schemaBuilder.SetWriteAccessLevel(ExtensibleStorage.AccessLevel.Public)
		schemaBuilder.SetVendorId("011h_tech")
		#Nombre del esquema
		schemaBuilder.SetSchemaName("components_meta_data")
		#Documentacion
		schemaBuilder.SetDocumentation("Campo visible para rellenar por el desarrollador")
		#Crear campo para almacenar la informacion float, int, str, XYZ
		campo = schemaBuilder.AddSimpleField("components_meta_data", System.String)
		#Finalizar el Schema Builder
		self.schema = schemaBuilder.Finish()

		
		entidad = ExtensibleStorage.Entity(self.schema)
		self.entidad = entidad
		#Obtener el campo
		campoARellenar = self.schema.GetField("components_meta_data")
		self.field = campoARellenar
		
		entidad.Set(campoARellenar, self.get_field_value())#campoARellenar.GetSpecTypeId())
		if entidad.IsValid(): self.element.SetEntity(entidad)
		
		dataElem = ExtensibleStorage.DataStorage.Create(doc) ##creates a new data storage to save the entity to
		dataElem.SetEntity(entidad) ##sets the entity to the data storage
		
				 
	def update(self,_data): 

		self.entidad.Set(self.field, _data)   
		self.element.SetEntity(self.entidad)
 

	def get_field_value(self): 
		try:
			element_schema = self.element.GetEntity(self.schema)
			value = element_schema.Get[System.String](self.field)
		except Exception as e:
			value = "[]"
		return value

class Id_Generator():
	
	def __init__(self, parameter, doc_name, length, collector=[], separator="."):
		self.PARAMETER = parameter
		self.COLLECTOR = collector
		self.LENGTH = length
		self.DOC_NAME = doc_name
		self.SEPARATOR = separator


	def orphan_elements(self,elements):
		'''Return a list of elements with no InstanceID'''
		def has_value(elem):
			
			param = elem.LookupParameter(self.PARAMETER)
			if param.AsString():
				return True
			else:
				return False
			
		return list(filter(lambda x: not has_value(x), elements))



	def available_id(self,start):
		'''Return a list of available numbers'''
		
		param_value = [elem.LookupParameter(self.PARAMETER).AsString() for elem in self.COLLECTOR if elem.LookupParameter(self.PARAMETER).AsString()]
		#SPLIT STRING by dot, STRING PATTERN TypeID-DOC.Id
		val = [ map( lambda y: y[-1],[x.split( self.SEPARATOR)])[0] for x in param_value ]
		param_value_int = set( [int(i) for i in [string[-4:] for string in val]] )
		
		numbers = range( start, start+self.LENGTH, 1)
		
		avalaible_numbers = [item for item in numbers if item not in param_value_int]
		
		available_id = ['{0:04}'.format(i) for i in avalaible_numbers]
		
		return available_id
	

	def get_table(self, value):

		'''Read table from given doc global parameter, if not exist then first create'''


			
		"" if value == "[]" else value
		if not value:
			table = []
		else:
			table = ast.literal_eval(value)
		return table


	def add_to_table(self, table):
		'''Add content to Table'''
		# Add untraced ids
		for elem in self.COLLECTOR:
				id = elem.Id
				if str(id) not in table:
					table.append(str(id))
		# If table doesnt exist create it
		if not table:
			for elem in self.COLLECTOR:
				id = str(elem.Id)
				table.append(id)
		# Add orphan elements		
		else:			
			for elem in self.orphan_elements(self.COLLECTOR):				
				id = str(elem.Id)
				table.append(id)
		
		return str(table)

	
	def refresh_table(self, table):
		'''Refresh table in given doc, remove ids from table if element not in current document'''
		table = ast.literal_eval(table)
		#project_elements = filter(lambda elem: elem.LookupParameter("EI_LocalisationCode") ,FilteredElementCollector(doc).WhereElementIsNotElementType().ToElements())
		project_elements = self.COLLECTOR
		collector_ids = [str(elem.Id) for elem in project_elements]
		#print(type(table))
		#print("Table: " + str(table))
		#print(type(collector_ids))
		#print("Collector: " + str(collector_ids))
		refreshed = [i for i in table if i in collector_ids]
		refreshed = list(set(refreshed))
		#print("Refreshed: " + str(refreshed))

		return refreshed


	def elements_with_duplicate_ids(self, table):

		'''Check elements with duplicate ids'''
		
		param_value = [(
		elem,
		elem.LookupParameter(self.PARAMETER).AsString().split(self.SEPARATOR)[-1]
		) for elem in self.COLLECTOR if elem.LookupParameter(self.PARAMETER).AsString()]
		
	
		unique = []
		dupObj = []
		UniqueObj = []
		dup = []
		
		while param_value:
			el = param_value.pop(0)
			if el[1] in unique:
				dup.append(el[1])
				dupObj.append(el)
			else:
				unique.append(el[1])
				UniqueObj.append(el)
		
		if dupObj:
			dupObj.append( [i for i in UniqueObj if i[1] in map(lambda x:x[1],dupObj )][0])
		
		dupElem = map(lambda x: x[0], dupObj)
		
		for i,j in enumerate(dupElem):
			id = str(j.Id)
			if id in table:
				del dupElem[i]
		
		return dupElem
	
	
	def build_Id(self,number):
		'''Build Id'''	
		return self.DOC_NAME + "." + number
	

	def build_PSId(self, number):
		'''Parts Segment Id is different from Component Id...'''
		return self.DOC_NAME + self.SEPARATOR + number


	@property
	def next_avalaible_id(self):
		id = self.available_id(1)[0]
		
		return self.build_Id(id)
	

def GetLevel(item):
	val = None
	if item:
		if hasattr(item, "LevelId"): 
			val = item.Document.GetElement(item.LevelId)
			if val: return val
		if hasattr(item, "Level"):
			val = item.Level
			if val: return val
		if hasattr(item, "GenLevel"):
			val = item.GenLevel
			if val: return val
		if (item.GetType().ToString() in ("Autodesk.Revit.DB.Architecture.StairsRun", "Autodesk.Revit.DB.Architecture.StairsLanding")):
			item = item.GetStairs()
		if (item.GetType().ToString() == "Autodesk.Revit.DB.Architecture.Stairs"):
			try: return item.Document.GetElement(item.get_Parameter(BuiltInParameter.STAIRS_BASE_LEVEL_PARAM).AsElementId())
			except: pass
		if (item.GetType().ToString() == "Autodesk.Revit.DB.ExtrusionRoof"):
			try: return item.Document.GetElement(item.get_Parameter(BuiltInParameter.ROOF_CONSTRAINT_LEVEL_PARAM).AsElementId())
			except: pass
		if not val:
			try: return item.Document.GetElement(item.get_Parameter(BuiltInParameter.INSTANCE_REFERENCE_LEVEL_PARAM).AsElementId())
			except: 
				try: return item.Document.GetElement(item.get_Parameter(BuiltInParameter.INSTANCE_SCHEDULE_ONLY_LEVEL_PARAM).AsElementId())
				except: 
					try: return item.Document.GetElement(item.get_Parameter(BuiltInParameter.SCHEDULE_LEVEL_PARAM).AsElementId())
					except: return None
		else: return None
	else: return None


def get_level_number(name, doc):

	collect_levels = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Levels).WhereElementIsNotElementType().ToElements()
	sort_levels = sorted(collect_levels, key = lambda x: x.Elevation)
	level_name = [level.Name for level in sort_levels]
	level_number = range(1,len(collect_levels)+1,1)
	level_dict = dict( zip(level_name,level_number))

	return level_dict[name]


def GetSubComponents(item):
	# FamilyInstances
	if hasattr(item, "GetSubComponentIds"):
		return [item.Document.GetElement(x) for x in item.GetSubComponentIds()]
	# Combined geometry
	if hasattr(item, "AllMembers"):
		return [x for x in item.AllMembers]
	# Stairs
	elif hasattr(item, "GetStairsLandings"):
		stair_comps = [item.Document.GetElement(x) for x in item.GetStairsLandings()]
		stair_comps.extend([item.Document.GetElement(x) for x in item.GetStairsRuns()])
		stair_comps.extend([item.Document.GetElement(x) for x in item.GetStairsSupports()])
		return stair_comps
	# Railings
	elif hasattr(item, "GetHandRails"):
		rail_comps = [item.Document.GetElement(x) for x in item.GetHandRails()]
		rail_comps.append(item.Document.GetElement(item.TopRail))
		return rail_comps
	# Beam systems
	elif hasattr(item, "GetBeamIds"):
		return [item.Document.GetElement(x) for x in item.GetBeamIds()]
	else: return []


def flatten(S):
	
    if S == []:
        return S
    if isinstance(S[0], list):
        return flatten(S[0]) + flatten(S[1:])
    return S[:1] + flatten(S[1:])


def get_familytype_by_name(name):
	"""Returns the first family type found or None if no match was found

	Args:
		name (string): The exact name of the family type

	Returns:
		FamilyType
	"""
	
	family_symbols = FilteredElementCollector(doc).WhereElementIsElementType().ToElements()
	familytype = filter(lambda elem: Element.Name.__get__(elem) == name, family_symbols)
	if familytype:
		return familytype[0]
	else:
		return None


def get_childs(elems):
	aux = []
	for i in elems:

		if hasattr(i, '__iter__'):
			x = get_childs(i)
		else:
			x = GetSubComponents(i)
		aux.append(x)
		
	return aux