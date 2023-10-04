# This node has been made by Modelical
# www.modelical.com

# import sys
# import os
# import clr
#
#
# clr.AddReference('ProtoGeometry')
# from Autodesk.DesignScript.Geometry import Vector
# from Autodesk.DesignScript.Geometry import Point as DSPoint
# from Autodesk.DesignScript.Geometry import Line as DSLine

# # Load DesignScript DSCore to use functions like List.Flatten
# clr.AddReference('DSCoreNodes')
# import DSCore
# from DSCore import *
#
# # Load Dynamo wrappers
# clr.AddReference("RevitNodes")
# import Revit
# from Revit.Elements import *

# clr.ImportExtensions(Revit.GeometryConversion)
# clr.ImportExtensions(Revit.Elements)
from zero11h.revit_api import DYN


class DynLineMixin:
    def to_dsline(self):
        return DYN.Line.ByStartPointEndPoint(self.p1.to_dspoint(),
                                           self.p2.to_dspoint())


class DynPoint3Mixin:
    def to_dspoint(self):
        return DYN.Point.ByCoordinates(self.x, self.y, self.z)


class DynVector3Mixin:
    def to_dsvector(self):
        return DYN.Vector.ByCoordinates(self.x, self.y, self.z)



def dyn_line_by_point_vector_distance(point, vector3, distance=0.5):
    startp = DYN.Point.ByCoordinates(point.x, point.y, point.z)
    dir = DYN.Vector.ByCoordinates(vector3.x, vector3.y, vector3.z)
    return DYN.Line.ByStartPointDirectionLength(startp, dir, distance)

#
# def Point3_pairs_list_to_dyn(point_pairs_list):
#     res = []
#     for pair in point_pairs_list:
#         res.append([Point3_to_DSPoint(point) for point in pair])
#     return res
