import os

path = (r'\Autodesk\Revit\Addins\2022\SpeckleRevit2\SpeckleCore2') #SpeckleCore2

appdata = os.getenv('APPDATA')

fulpath = appdata+path
print (fulpath)
