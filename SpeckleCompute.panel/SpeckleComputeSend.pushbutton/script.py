import clr
import System
import System.Threading.Tasks
from System.Collections.Generic import List 
import os

from Autodesk.Revit import DB
from Autodesk.Revit.UI.Selection import ObjectType

import json
import threading

import zero11h.revit_api.revit_utils as mru

appdata = os.getenv('APPDATA')

speckleCorePath = (r'\Autodesk\Revit\Addins\2024\SpeckleRevit2\SpeckleCore2') #SpeckleCore2
speckleCoreFullPath = appdata + speckleCorePath

objectsPath = (r'\Speckle\Kits\Objects\Objects.Converter.Revit2024')
objectsPathFullPath = appdata + objectsPath


clr.AddReferenceToFileAndPath(speckleCoreFullPath) #SpeckleCore2
clr.AddReferenceToFileAndPath(objectsPathFullPath) #Revit Objects

from Speckle.Core import Credentials, Api, Transports, Kits
import Objects


# The id of the stream to work with (we're assuming it already exists in your default account's server)
streamId = "319b7f5b40"
branchName = "main"

uiapp = __revit__
uidoc = uiapp.ActiveUIDocument
app = uiapp.Application
doc = uidoc.Document

#Pick a group
sel = uiapp.ActiveUIDocument.Selection;
pickedref = sel.PickObject(ObjectType.Element, "Please select a group");
layerGroup = doc.GetElement(pickedref);

# convert Revit Geometry to Speckle Base
kit = Kits.KitManager.GetDefaultKit()
converter = kit.LoadConverter(Objects.Converter.Revit.ConverterRevit.RevitAppName)
converter.SetContextDocument(doc)

layerGroupBase = converter.ConvertToSpeckle(layerGroup)

#send metadata along with base geometry
guid = System.Guid.Parse("d2076246-c30b-414b-b7be-071151d82a39");
schema = DB.ExtensibleStorage.Schema.Lookup(guid);
field = schema.GetField("JSONData")
meta = layerGroup.GetEntity(schema)
metadata = meta.Get[System.String](field)

# #include metadata
layerGroupBase["metadata"] = metadata


json_metadata = json.loads(metadata)

self_guid =  json_metadata["SelfGuid"]
perforator_data =  json_metadata["LayerGroupMetadata"]["PerforatorData"]

# Component guid (from layergroup metadata)
comp = doc.GetElement(self_guid)

all_curves = []

base_lines = []

#get openings and perforator curves
for k in perforator_data.Keys:

    for guid in perforator_data[k]:
        perf_guid = guid
        perf = doc.GetElement(perf_guid)

        # TODO - perforators come as elementId

        solid = mru.RvtSolidUtils.get_all_solids_from_instance(perf, view_detail=DB.ViewDetailLevel.Coarse)[0]
        face = mru.RvtSolidUtils.get_solid_face_from_normal(solid, perf.FacingOrientation.Negate())

        res = []

        for edge in face.EdgeLoops.Item[0]:
            all_curves.append(edge.AsCurve())

            base_line = converter.LineToSpeckle(edge.AsCurve(), doc)
            base_lines.append(base_line)
    # all_curves.append(res)

layerGroupBase["PerforatorLines"]=  base_lines


# Speckle Stuff .....................



def get_account_with_token():
     
    server_info = Api.ServerInfo()
    server_info.url = "http://139.59.153.219/"
    account = Credentials.Account()
    account.token = "121657036ca1f96cc67872e539d66a545346f08065"
    account.serverInfo = server_info

    return account


def create_branch(streamId, branchName):

    taskBranch = client.BranchGet(streamId, branchName, 1)
    taskBranch.Wait()
    branch = taskBranch.Result

    return branch

def create_hash(base, branch, streamId ):

    # hash_ = branch.commits.items[0].referencedObject
    transport = Transports.ServerTransport(defaultAccount, streamId)
    lst = List[Transports.ITransport]() 
    lst.Add(transport)

    hashTask = Api.Operations.Send(base,lst);
    hashTask.Wait()
    newHash = hashTask.Result
    return newHash


def commit(newHash, streamId, branchName):

    CommitCreateInput = Api.CommitCreateInput()
    CommitCreateInput.branchName = branchName
    CommitCreateInput.message = "Commit created with Speckle Compute"
    CommitCreateInput.objectId = newHash
    CommitCreateInput.streamId = streamId
    CommitCreateInput.sourceApplication = "SpeckleCompute"
    commitTask = client.CommitCreate(CommitCreateInput)
    commitTask.Wait()
    commitId = commitTask.Result
    return commitId


# defaultAccount = Credentials.AccountManager.GetDefaultAccount()
defaultAccount = get_account_with_token()
client = Api.Client(defaultAccount)

branch =  create_branch(streamId,branchName )
newHash = create_hash(layerGroupBase, branch,streamId)
commitId = commit(newHash, streamId, branchName)
print ("Speckle Commit created: {}".format(commitId))

# apparently no need for threading in PyRevit
# thread= threading.Thread(target = send_to_speckle)
# thread.start() 
# thread.join() 