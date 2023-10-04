#!/usr/bin/env python
# -*- coding: utf-8 -*-

from zero11h.revit_api import DB, _REVIT_DOCUMENT_

def material_exists_in_model(mname):
    for revit_material in DB.FilteredElementCollector(_REVIT_DOCUMENT_).OfClass(DB.Material):
        if mname == revit_material.Name:
            return revit_material
    return None
