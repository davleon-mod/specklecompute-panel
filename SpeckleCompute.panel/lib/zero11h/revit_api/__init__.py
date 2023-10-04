#!/usr/bin/env python
# -*- coding: utf-8 -*-

import clr
import System

# Load Revit API
clr.AddReference('RevitAPI')
import Autodesk.Revit.DB as DB
clr.AddReference("RevitAPIUI")
import Autodesk.Revit.UI as UI
import Autodesk.Revit.Exceptions as RevitExceptions

# Load Dynamo API
clr.AddReference('ProtoGeometry')
import Autodesk.DesignScript.Geometry as DYN


try:
    # RPS
    _REVIT_UI_DOCUMENT_ = __revit__.ActiveUIDocument
    _REVIT_DOCUMENT_ = __revit__.ActiveUIDocument.Document
    app = __revit__.Application
    uiapp = __revit__

except NameError as ex:
    try:
        from RhinoInside.Revit import Revit
        _REVIT_DOCUMENT_ = Revit.ActiveDBDocument
        _REVIT_UI_DOCUMENT_ = Revit.ActiveUIDocument
        # uiapp = DocumentManager.Instance.CurrentUIApplication
        # app = uiapp.Application
    except:
        # Load document reference
        clr.AddReference("RevitServices")
        from RevitServices.Persistence import DocumentManager
        _REVIT_DOCUMENT_ = DocumentManager.Instance.CurrentDBDocument
        _REVIT_UI_DOCUMENT_ = DocumentManager.Instance.CurrentUIApplication.ActiveUIDocument

if not _REVIT_DOCUMENT_:
    raise RuntimeError('No active Revit document')

for f in _REVIT_DOCUMENT_.Phases:
    if f.Name == "Nueva construcción" or f.Name == "New Construction":
        _WORKING_PHASE_ = f