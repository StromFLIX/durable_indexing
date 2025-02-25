import json
import logging
import os
import azure.functions as func
from azure.durable_functions import DurableOrchestrationClient
from application.app import app
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.models import VectorQuery
from azure.identity import DefaultAzureCredential
from orchestrators.index import index
from activities.listblob import list_blobs_chunk
from activities.cracking import document_cracking
from activities.chuncking import chunking
from activities.embedding import embedding
from activities.search import ensure_index_exists, add_documents


defaults = {
    "BLOB_AMOUNT_PARALLEL": int(os.environ.get("BLOB_AMOUNT_PARALLEL", "20")),
    "SEARCH_INDEX_NAME": os.environ.get("SEARCH_INDEX_NAME", "default-index"),
    "BLOB_CONTAINER_NAME": os.environ.get("BLOB_CONTAINER_NAME", "source")
}


@app.function_name(name='index_event_grid')
@app.event_grid_trigger(arg_name='event')
@app.durable_client_input(client_name="client")
async def index_event_grid(event: func.EventGridEvent, client: DurableOrchestrationClient):
    if event.get_json()["api"] != "PutBlob":
        logging.info("Event type is not BlobCreated. Skipping execution.")
        return
    
    path_in_container = extract_path(event)
    logging.info(f'Python EventGrid trigger processed a BlobCreated event. Path: {path_in_container}')

    instance_id = await client.start_new("index", client_input={"prefix_list": [path_in_container], "defaults": defaults})
    logging.info(f'Started indexing with id: {instance_id}')

def extract_path(event: func.EventGridEvent):
    subject = event.subject
    path_in_container = subject.split("/blobs/", 1)[-1]
    return path_in_container

@app.function_name(name='status')
@app.route(route="status", methods=[func.HttpMethod.GET])
@app.durable_client_input(client_name="client")
async def status(req: func.HttpRequest, client: DurableOrchestrationClient) -> func.HttpResponse:
    logging.info('Retrieving status of all orchestrations.')
    results = await client.get_status_all()
    return func.HttpResponse(json.dumps([result.to_json() for result in results]), status_code=200)

@app.function_name(name='status_id')
@app.route(route="status/{id}", methods=[func.HttpMethod.GET])
@app.durable_client_input(client_name="client")
async def status_id(req: func.HttpRequest, client: DurableOrchestrationClient) -> func.HttpResponse:
    logging.info('Retrieving status of all orchestrations.')
    id = req.route_params.get('id')
    def str_to_bool(value):
        if value is None:
            return False
        return value.lower() in ['true', '1']
    show_history = str_to_bool(req.params.get('show_history')) or False
    show_history_output = str_to_bool(req.params.get('show_history_output')) or False
    show_input = str_to_bool(req.params.get('show_input')) or False
    result = await client.get_status(instance_id=id, show_history=show_history, show_history_output=show_history_output, show_input=show_input)
    result_json = result.to_json()
    if show_history and hasattr(result, 'historyEvents'):
        result_json["historyEvents"] = list(result.historyEvents)
    else:
        result_json["historyEvents"] = None

    return func.HttpResponse(json.dumps(result_json), status_code=200)

@app.function_name(name='index_http')
@app.route(route="index", methods=[func.HttpMethod.POST])
@app.durable_client_input(client_name="client")
async def index_http(req: func.HttpRequest, client: DurableOrchestrationClient) -> func.HttpResponse:
    logging.info('Kick off indexing process.')
    input = req.get_json()
    instance_id = await client.start_new(
        orchestration_function_name="index",
        client_input={"prefix_list": input['prefix_list'], "index_name": input['index_name'], "defaults": defaults})
    return func.HttpResponse(instance_id, status_code=200)

@app.function_name(name='orchestration_health')
@app.route(route="orchestration_health", methods=[func.HttpMethod.GET])
@app.durable_client_input(client_name="client")
async def orchestration_health(req: func.HttpRequest, client: DurableOrchestrationClient) -> func.HttpResponse:
    try:
        # check the status of all orchestrations
        await client.get_status_all()

        return func.HttpResponse("Healthy", status_code=200)
    except Exception as ex:
        logging.error(f"Health check failed: {ex}")
        return func.HttpResponse("Unhealthy", status_code=503)
    
@app.route(route="search", methods=[func.HttpMethod.GET])
async def search_index(req: func.HttpRequest) -> func.HttpResponse:
    try:
        # Grab the search query from the URL (e.g., ?q=example)
        query = req.params.get('q')
        if not query:
            return func.HttpResponse(
                "Please provide a search query using the 'q' parameter.", status_code=400
            )
    
        # Get search service configuration from environment variables
        endpoint = os.getenv("SEARCH_SERVICE_ENDPOINT")
        index_name = req.params.get('index_name') or os.environ.get("SEARCH_INDEX_NAME", "default-index")
        if not endpoint or not index_name:
            raise Exception("Missing search service configuration.")

        # Create the async search client
        search_index_client = SearchIndexClient(endpoint=endpoint, credential=DefaultAzureCredential())

        # Execute the search query (using the provided query text)
        search_client = search_index_client.get_search_client(index_name=index_name)
        results = await search_client.search(search_text=query,
                                             query_type="semantic",
                                             select="content, sourcepages, id, storageUrl",
                                             semantic_configuration_name="default")
        docs = []
        async for result in results:
            # Each result has a 'document' property that contains the actual document.
            docs.append(result)

        # Ensure the client is closed properly
        await search_client.close()  
        await search_index_client.close()

        return func.HttpResponse(
            json.dumps(docs), status_code=200, mimetype="application/json"
        )
    except Exception as ex:
        logging.error(f"Search query failed: {ex}")
        return func.HttpResponse("Search failed", status_code=500)