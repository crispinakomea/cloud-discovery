import azure.functions as func
import logging

app = func.FunctionApp()

@app.cosmos_db_trigger(arg_name="azcosmosdb", container_name="mycontainer", lease_container_name="leasecontainer",
                        database_name="mydatabase", connection="CosmosAccountConnection")  
def cosmosdb_trigger(azcosmosdb: func.DocumentList):
    logging.info('Python CosmosDB triggered.'
                 f"Item: {azcosmosdb.pop(i=-1)}")
