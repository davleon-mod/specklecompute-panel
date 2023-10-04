using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

using Autodesk.Revit.ApplicationServices;
using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using Autodesk.Revit.UI.Selection;
using Autodesk.Revit.DB.Architecture;

using Speckle;
using Speckle.Core.Credentials;
using Speckle.Core.Api;
using Speckle.Core.Transports;
using Objects;

using Newtonsoft.Json;
using Newtonsoft.Json.Linq;


namespace SpeckleComputeReceive
{
    [Transaction(TransactionMode.Manual)]
    [Regeneration(RegenerationOption.Manual)]
    public class SpeckleCompute_Receive : IExternalCommand
    {
        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {

            ////Get application and document objects
            UIApplication uiapp = commandData.Application;
            Document doc = uiapp.ActiveUIDocument.Document;

            ////Define a reference Object to accept the pick result
            Reference pickedref = null;

            ////Pick a group
            Selection sel = uiapp.ActiveUIDocument.Selection;
            pickedref = sel.PickObject(ObjectType.Element, "Please select a group");
            Element layerGroup = doc.GetElement(pickedref);
            //ElementId elemId = elem.Id;

            //convert Revit Geometry to Speckle Base
            var kit = Speckle.Core.Kits.KitManager.GetDefaultKit();
            var converter = kit.LoadConverter(Objects.Converter.Revit.ConverterRevit.RevitAppName);
            converter.SetContextDocument(doc);

            Speckle.Core.Models.Base layerGroupBase = converter.ConvertToSpeckle(layerGroup);


            //send metadata along with base geometry
            string meta = GetMetadata(layerGroup);
            layerGroupBase["metadata"] = meta;


            // get peforator data
            JObject jsonObj = JObject.Parse(meta);

            JToken perforatorData = jsonObj["LayerGroupMetadata"]
                .Value<JToken>("PerforatorData");

            JToken openings = perforatorData["Openings"];
            JToken perforators = perforatorData["Perforators"];

            List<Element> openingsList = new List<Element>();
            List<Element> perforatorsList = new List<Element>();

            MessageBox.Show(perforatorData.ToString());

            //foreach (var item in openings)
            //{
            //    string guid = item.ToString();
            //    MessageBox.Show(item.ToString());
            //    Element opening = doc.GetElement(guid);



            //    Speckle.Core.Models.Base openingBase = converter.ConvertToSpeckle(opening);
            //    layerGroupBase["@perforators"] = openingBase;


            //    //MessageBox.Show(item.ToString());
            //}

            //List<string> openingsList = new List<string>();



            //foreach (var item in perforators)
            //{
            //    int idInt = Convert.ToInt32(item.ToString());
            //    ElementId id = new ElementId(idInt);
            //    Element opening = doc.GetElement(id);
            //    Element perforator = doc.GetElement(item.ToString());
            //    Speckle.Core.Models.Base perforatorBase = converter.ConvertToSpeckle(perforator);
            //    layerGroupBase["@perforators"] = perforatorBase;
            //    //MessageBox.Show(item.ToString());

            //}






            // The id of the stream to work with (we're assuming it already exists in your default account's server)
            var streamId = "6766a6eaa3";
            // The name of the branch we'll send data to.
            var branchName = "main";

            object commitId = null;

            var thread = new Thread(() =>
            {
                Thread.CurrentThread.IsBackground = true;

                // Get default account on this machine
                var defaultAccount = AccountManager.GetDefaultAccount();
                // Or get all the accounts and manually choose the one you want
                // var accounts = AccountManager.GetAccounts();
                // var defaultAccount = accounts.ToList().FirstOrDefault();

                // Authenticate using the account
                var client = new Client(defaultAccount);

                // Now we can start using the client

                // Get the main branch with it's latest commit reference
                Task<Branch> taskBranch = client.BranchGet(streamId, "main", 1);
                taskBranch.Wait();
                var branch = taskBranch.Result;

                // Get the id of the object referenced in the commit
                var hash = branch.commits.items[0].referencedObject;


                // Create the server transport for the specified stream.
                var transport = new ServerTransport(defaultAccount, streamId);

                ////// Receive Objects
                // Receive the object
                //var receivedTask = Operations.Receive(hash, transport);
                //receivedTask.Wait();
                //var receivedBase = receivedTask.Result;
                //ShowDialog(receivedBase.ToString());
                //// Process the object however you'd like
                //Console.WriteLine("Received object:" + receivedBase);


                // Sending the object will return it's unique identifier.
                var hashTask = Operations.Send(layerGroupBase, new List<ITransport> { transport });
                hashTask.Wait();
                var newHash = hashTask.Result;

                // Create a commit in `processed` branch (it must previously exist)
                var commitTask = client.CommitCreate(new CommitCreateInput()
                {
                    branchName = branchName,
                    message = "Commit created with Speckle Compute",
                    objectId = newHash,
                    streamId = streamId,
                    sourceApplication = "SpeckleCompute"

                });
                commitTask.Wait();
                commitId = commitTask.Result;

            });

            thread.Start();
            thread.Join();


            string commitText = String.Format("Successfully created commit with id: {0}", commitId);


            ShowDialog(commitText);


            return Result.Succeeded;
        }

        private void ShowDialog(string text)
        {

            TaskDialog td = new TaskDialog("TaskDialog SpeckleCompute")
            {
                Id = "ID_TaskDialog_SpeckleCompute",
                MainIcon = TaskDialogIcon.TaskDialogIconWarning,
                Title = "Speckle Compute Says...",
                TitleAutoPrefix = true,
                AllowCancellation = true,
                MainContent = text
            };
            td.Show();
        }


        private string GetMetadata(Element elem)
        {
            var guid = Guid.Parse("d2076246-c30b-414b-b7be-071151d82a39");
            var schema = Autodesk.Revit.DB.ExtensibleStorage.Schema.Lookup(guid);
            var value = elem.GetEntity(schema).Get<string>(schema.GetField("JSONData"));

            return value;


        }


    }
}