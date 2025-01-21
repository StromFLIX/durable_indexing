import json
import logging
import azure.functions as func
from azure.durable_functions import DurableOrchestrationClient
from application.app import app
from orchestrators.index import index
from activities.listblob import list_blobs_chunk
from activities.cracking import document_cracking
from activities.chuncking import chunking
from activities.embedding import embedding
from activities.search import ensure_index_exists, add_documents



@app.function_name(name='blob_sharing')
@app.event_grid_trigger(arg_name='event')
@app.durable_client_input(client_name="client")
async def main(event: func.EventGridEvent, client: DurableOrchestrationClient):
    if event.get_json()["api"] != "PutBlob":
        logging.info("Event type is not BlobCreated. Skipping execution.")
        return
    
    path_in_container = extract_path(event)
    logging.info(f'Python EventGrid trigger processed a BlobCreated event. Path: {path_in_container}')

    instance_id = await client.start_new("index", client_input={"prefix_list": [path_in_container]})
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
    result_json["historyEvents"] = [historyItem for historyItem in result.historyEvents] if show_history else None
    return func.HttpResponse(json.dumps(result_json), status_code=200)

@app.function_name(name='index_http')
@app.route(route="index", methods=[func.HttpMethod.POST])
@app.durable_client_input(client_name="client")
async def index_http(req: func.HttpRequest, client: DurableOrchestrationClient) -> func.HttpResponse:
    logging.info('Kick off indexing process.')
    input = req.get_json()
    instance_id = await client.start_new(
        orchestration_function_name="index", 
        client_input={"prefix_list": input['prefix_list'], "index_name": input['index_name']})
    return func.HttpResponse(instance_id, status_code=200)