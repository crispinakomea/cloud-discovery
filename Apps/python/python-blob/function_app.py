import azure.functions as func
import logging
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient
import os

app = func.FunctionApp()

@app.blob_trigger(arg_name="myblob", path="mycontainer/incoming/{name}",
                               connection="AzureWebJobsStorage") 
def blob_trigger(myblob: func.InputStream):
    logging.info(f"Python blob trigger function processed blob"
                f"Name: {myblob.name}"
                f"Blob Size: {myblob.length} bytes")

    # Use managed identity to authenticate
    account_name = os.environ["AzureWebJobsStorage__accountName"]
    client_id = os.environ["AzureWebJobsStorage__clientId"]
    account_url = f"https://{account_name}.blob.core.windows.net"
    credential = ManagedIdentityCredential(client_id=client_id)
    blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
    source_blob = myblob.name.replace('mycontainer/', '', 1)
    dest_blob = source_blob.replace('incoming/', 'processed/', 1)
    container_name = "mycontainer"

    source_blob_client = blob_service_client.get_blob_client(container=container_name, blob=source_blob)
    dest_blob_client = blob_service_client.get_blob_client(container=container_name, blob=dest_blob)

    # Copy blob to new location
    dest_blob_client.start_copy_from_url(source_blob_client.url)
    # Delete original blob
    source_blob_client.delete_blob()



# This example uses SDK types to directly access the underlying BlobClient object provided by the Blob storage trigger.
# To use, uncomment the section below and add azurefunctions-extensions-bindings-blob to your requirements.txt file
# Ref: aka.ms/functions-sdk-blob-python
#
# import azurefunctions.extensions.bindings.blob as blob
# @app.blob_trigger(arg_name="client", path="mycontainer",
#                   connection="AzureWebJobsStorage")
# def blob_trigger(client: blob.BlobClient):
#     logging.info(
#         f"Python blob trigger function processed blob \n"
#         f"Properties: {client.get_blob_properties()}\n"
#         f"Blob content head: {client.download_blob().read(size=1)}"
#     )
