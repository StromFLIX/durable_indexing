from application.app import app
import os
from azure.identity import DefaultAzureCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult
from urllib.parse import unquote, urlparse

@app.function_name(name="document_cracking")
@app.activity_trigger(input_name="params")
def document_cracking(params: dict) -> list[str]:
    blob_url = params.get("blob_url")
    endpoint = os.getenv('DI_ENDPOINT')

    client = DocumentIntelligenceClient(endpoint, DefaultAzureCredential())
    poller = client.begin_analyze_document("prebuilt-layout", AnalyzeDocumentRequest(url_source=blob_url))
    result: AnalyzeResult = poller.result()

    return { 
        "pages" : ["".join([line['content'] for line in page.lines]) for page in result.pages],
        "url": blob_url,
        "filename": unquote(urlparse(blob_url)[2].split("/")[-1])
    }