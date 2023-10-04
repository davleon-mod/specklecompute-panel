#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

import zero11h.revit_api.revit_utils as mru
from zero11h.revit_api import (System, UI, DB, RevitExceptions,
                               _REVIT_DOCUMENT_, _REVIT_UI_DOCUMENT_, _WORKING_PHASE_)


def DicotomyDialog(title=None, msg=None):
    if not title or not msg:
        return False

    dialog = UI.TaskDialog(title)
    dialog.MainContent = msg
    dialog.AllowCancellation = False
    dialog.CommonButtons = UI.TaskDialogCommonButtons.Yes | UI.TaskDialogCommonButtons.No
    return dialog


def cancel_if_not_view3d_or_plan():
    if (_REVIT_DOCUMENT_.ActiveView.ViewType != DB.ViewType.ThreeD and
            _REVIT_DOCUMENT_.ActiveView.ViewType != DB.ViewType.FloorPlan):
        UI.TaskDialog.Show("Operation canceled", "Use a 3D or FloorPlan view")
        sys.exit(1)


class CustomISelectionFilter(UI.Selection.ISelectionFilter):
    def __init__(self, builtin_category_list):
        self.category_ids = [DB.Category.GetCategory(_REVIT_DOCUMENT_, builtin_category).Id.IntegerValue for
                             builtin_category in builtin_category_list]

    def AllowElement(self, e):
        if e.Category.Id.IntegerValue in self.category_ids:
            return True
        else:
            return False

    def AllowReference(self, ref, point):
        return true


class RvtSelection:

    @staticmethod
    def select_elements_by_categories(msg_prompt=None, categories=None):
        try:
            sel = _REVIT_UI_DOCUMENT_.Selection.PickObjects(UI.Selection.ObjectType.Element,
                                                            CustomISelectionFilter(categories),
                                                            msg_prompt)

        # If cancelled or no selection exit script
        except RevitExceptions.OperationCanceledException:
            sys.exit(1)

        if not sel:
            UI.TaskDialog.Show('Operation canceled', 'Nothing selected!')
            sys.exit(1)

        return sel

    @staticmethod
    def select_element_by_categories(msg_prompt=None, categories=None):
        try:
            sel = _REVIT_UI_DOCUMENT_.Selection.PickObject(UI.Selection.ObjectType.Element,
                                                           CustomISelectionFilter(categories),
                                                           msg_prompt)

        # If cancelled or no selection exit script
        except RevitExceptions.OperationCanceledException:
            sys.exit(1)

        if not sel:
            UI.TaskDialog.Show('Operation canceled', 'Nothing selected!')
            sys.exit(1)

        return sel

    @staticmethod
    def select_face_on_element(msg_prompt=None):
        try:
            reference = _REVIT_UI_DOCUMENT_.Selection.PickObject(UI.Selection.ObjectType.Face,
                                                                 msg_prompt)
            if not reference:
                UI.TaskDialog.Show('Selection ERROR', 'Please select a face to place MEPBox')
                sys.exit(1)
        except RevitExceptions.OperationCanceledException:
            # UI.TaskDialog.Show("Operation canceled", "Canceled by the user")
            sys.exit(1)

        return reference

    @staticmethod
    def pick_point_on_vertical_face_from_reference(reference=None):
        """
        Checks that face is vertical, cancels if not

        Args:
            reference: DB.Reference

        Returns:
            Tuple(DB.XYZ, DB.Face)

        """
        element = _REVIT_DOCUMENT_.GetElement(reference.ElementId)
        # picked_face = element.GetGeometryObjectFromReference(reference)
        reference_string = reference.ConvertToStableRepresentation(_REVIT_DOCUMENT_)
        ref_string_tokens = reference_string.split(':')

        solids = mru.RvtSolidUtils.get_solids_from_instance(element,
                                                            filtered=False,
                                                            compute_references=True)
        foundface = None
        for solid in solids:
            for placement_face in solid.Faces:
                if ':'.join(ref_string_tokens[-3:]) in placement_face.Reference.ConvertToStableRepresentation(
                        _REVIT_DOCUMENT_):
                    foundface = placement_face

        if not foundface:
            UI.TaskDialog.Show("Operation canceled", "Face not in a component")
            sys.exit(1)

        placement_face = foundface

        # if face is not vertical cancel
        normal = placement_face.ComputeNormal(DB.UV(0.5, 0.5))
        if abs(normal.Z) > 0.001:
            UI.TaskDialog.Show("Operation canceled", "Face is not vertical")
            sys.exit(1)

        # https://jeremytammik.github.io/tbc/a/0686_pick_point_3d.htm
        plane = DB.Plane.CreateByNormalAndOrigin(normal, placement_face.Origin)
        t = DB.Transaction(_REVIT_DOCUMENT_, 'temp plane')
        t.Start("Temporarily set work plane to pick point in 3D")
        sketch_plane = DB.SketchPlane.Create(_REVIT_DOCUMENT_, plane)
        _REVIT_UI_DOCUMENT_.ActiveView.SketchPlane = sketch_plane
        _REVIT_UI_DOCUMENT_.ActiveView.ShowActiveWorkPlane()
        point = None

        try:
            point = _REVIT_UI_DOCUMENT_.Selection.PickPoint("Please pick a point on the component's face")
        except Exception as ex:
            pass

        t.RollBack()  # So we don't leave the temporary plane in the model

        if not point:
            UI.TaskDialog.Show("Operation canceled", "No valid point selected")
            sys.exit(1)

        return point, placement_face
