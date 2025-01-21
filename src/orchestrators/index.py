from azure.durable_functions import DurableOrchestrationContext
from application.app import app
import os

@app.function_name(name="index")  # The name used by client.start_new("index")
@app.orchestration_trigger(context_name="context")
def index(context: DurableOrchestrationContext):
    # Resolver resolves list of prefixes to iterable ( needs to store state of iterable e.g. marker and array position)
    input = context.get_input()
    continuation_token = None
    array_position = 0
    container_name = "source"
    index_name = input.get("index_name") or os.environ.get("SEARCH_INDEX_NAME", "default-index")
    blob_amount_parallel = int(os.environ.get("BLOB_AMOUNT_PARALLEL", "20"))
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
        yield context.call_activity(name="ensure_index_exists", input_=index_name)
        task_list = []
        for blob_name in blob_list_result["blob_names"]:
            task_list.append(context.call_sub_orchestrator(name="index_document", input_={"blob_url": blob_name, "index_name": index_name}, instance_id=context.new_uuid()))
        yield context.task_all(task_list)
    

@app.function_name(name="index_document")  # The name used by client.start_new("index")
@app.orchestration_trigger(context_name="context")
def index_document(context: DurableOrchestrationContext):
    input = context.get_input()
    document = yield context.call_activity("document_cracking", input["blob_url"])
    chunks = yield context.call_activity("chunking", document)
    chunks_with_embeddings = yield context.call_activity("embedding", chunks)
    yield context.call_activity("add_documents", {"chunks": chunks_with_embeddings, "index_name": input["index_name"]})