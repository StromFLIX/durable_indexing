from azure.durable_functions import DurableOrchestrationContext, RetryOptions
from application.app import app
import os

@app.function_name(name="index")  # The name used by client.start_new("index")
@app.orchestration_trigger(context_name="context")
def index(context: DurableOrchestrationContext):
    # Resolver resolves list of prefixes to iterable ( needs to store state of iterable e.g. marker and array position)
    input = context.get_input()
    continuation_token = None
    array_position = 0
    container_name = input.get("defaults").get("BLOB_CONTAINER_NAME")
    if container_name is None:
        raise ValueError("BLOB_CONTAINER_NAME is not set")
    index_name = input.get("index_name") or input.get("defaults").get("SEARCH_INDEX_NAME")
    if index_name is None:
        raise ValueError("SEARCH_INDEX_NAME is not set")
    blob_amount_parallel = input.get("defaults").get("BLOB_AMOUNT_PARALLEL")
    if blob_amount_parallel is None:
        raise ValueError("BLOB_AMOUNT_PARALLEL is not set")
    
    yield context.call_activity(name="ensure_index_exists", input_=index_name)
    # For every item in iterable create a sub orchestrator ( should be every file in the blob storage)
    while True:
        prefix_list = [""] if "prefix_list" not in input else input["prefix_list"] 
        blob_list_result = yield context.call_activity("list_blobs_chunk", {
                    "container_name": container_name,
                    "continuation_token": continuation_token,
                    "chunk_size": blob_amount_parallel,
                    "prefix_list_offset": array_position,
                    "prefix_list": prefix_list
            })
        if(len(blob_list_result["blob_names"]) == 0):
            break
        continuation_token = blob_list_result["continuation_token"]
        array_position = blob_list_result["prefix_list_offset"]
        task_list = []
        for blob_name in blob_list_result["blob_names"]:
            document_retry_options = RetryOptions(first_retry_interval_in_milliseconds=60_000, max_number_of_attempts=3)
            task_list.append(context.call_sub_orchestrator_with_retry(
                name="index_document",
                retry_options=document_retry_options,
                input_={"blob_url": blob_name, "index_name": index_name}))
        yield context.task_all(task_list)
    

@app.function_name(name="index_document")  # The name used by client.start_new("index")
@app.orchestration_trigger(context_name="context")
def index_document(context: DurableOrchestrationContext):
    input = context.get_input()
    service_retry_options = RetryOptions(first_retry_interval_in_milliseconds=3000, max_number_of_attempts=3)
    document = yield context.call_activity_with_retry("document_cracking", service_retry_options, input["blob_url"])
    chunks = yield context.call_activity("chunking", document)
    chunks_with_embeddings = yield context.call_activity_with_retry("embedding", service_retry_options, chunks)
    yield context.call_activity_with_retry("add_documents",  service_retry_options,{"chunks": chunks_with_embeddings, "index_name": input["index_name"]})