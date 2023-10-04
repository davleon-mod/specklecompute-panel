import clr
from Autodesk.Revit import DB
import zero11h.revit_api.revit_utils as mru
import os

# clr.AddReferenceToFileAndPath(r'C:\Users\David\AppData\Roaming\Autodesk\Revit\Addins\2024\SpeckleRevit2\SpeckleCore2') #SpeckleCore2
# clr.AddReferenceToFileAndPath(r'C:\Users\David\AppData\Roaming\Speckle\Kits\Objects\Objects.Converter.Revit2024') #Revit Objects

appdata = os.getenv('APPDATA')

speckleCorePath = (r'\Autodesk\Revit\Addins\2024\SpeckleRevit2\SpeckleCore2') #SpeckleCore2
speckleCoreFullPath = appdata + speckleCorePath

objectsPath = (r'\Speckle\Kits\Objects\Objects.Converter.Revit2024')
objectsPathFullPath = appdata + objectsPath

clr.AddReferenceToFileAndPath(speckleCoreFullPath) #SpeckleCore2
clr.AddReferenceToFileAndPath(objectsPathFullPath) #Revit Objects

from Speckle.Core import Api, Transports, Credentials, Kits
import Objects


# The id of the stream to work with (we're assuming it already exists in your default account's server)
# streamId = "af8cf2bfa5"
streamId = "799b5af828"
branchName = "main"

uiapp = __revit__
uidoc = uiapp.ActiveUIDocument
app = uiapp.Application
doc = uidoc.Document




def get_account_with_token():
     
    server_info = Api.ServerInfo()
    server_info.url = "http://139.59.153.219/"
    account = Credentials.Account()
    account.token = "121657036ca1f96cc67872e539d66a545346f08065"
    account.serverInfo = server_info

    return account



def get_branch(streamId,branchName ):
    branch = client.BranchGet(streamId, branchName, 1)
    branch.Wait()
    branch_result = branch.Result

    return branch_result

def receive(objectId, transport):
    received_data = Api.Operations.Receive( objectId,  transport)
    received_data.Wait()
    revit_data = received_data.Result
    return revit_data

# defaultAccount = Credentials.AccountManager.GetDefaultAccount()
defaultAccount = get_account_with_token()

client = Api.Client(defaultAccount)

branch = get_branch(streamId, branchName)
objectId = branch.commits.items[0].referencedObject

transport = Transports.ServerTransport(defaultAccount, streamId)

data = receive(objectId, transport)

xdata = data['@data']
unwrapped_data = dict(data['@data'].GetMembers())

keys = []

for k in unwrapped_data.keys():
	keys.append(k)

direct_shapes = xdata[keys[0]]


# convert Speckle Base to Revit Geometry 
kit = Kits.KitManager.GetDefaultKit()
converter = kit.LoadConverter(Objects.Converter.Revit.ConverterRevit.RevitAppName)
converter.SetContextDocument(doc)

print(converter)

for dshape in direct_shapes:
    print(dshape)
    directShape = converter.ConvertToNative(dshape)
     
# t = DB.Transaction(doc,'Create DirectShape')
# t.Start()

# try:

#     # fallback = Objects.Converter.Revit.ConverterRevit.ToNativeMeshSettingEnum.Default
#     # directShape = converter.DirectShapeToNative(data, fallback)
#     for dshape in direct_shapes:
#         directShape = converter.ConvertToNative(dshape)
#         for guid in directShape.CreatedIds:
#             print "Created DirectShape Id {}".format(doc.GetElement(guid).Id)

#     t.Commit()
# except Exception as ex:
#     print(ex)
#     # print(traceback.format_exc())
#     t.RollBack()
# finally:
#     t.Dispose()


