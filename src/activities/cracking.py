from application.app import app
import os
from azure.identity import DefaultAzureCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult
from urllib.parse import unquote, urlparse
from typing import List

@app.function_name(name="document_cracking")
@app.activity_trigger(input_name="bloburl")
def document_cracking(bloburl: str) -> List[str]:
    endpoint = os.getenv('DI_ENDPOINT')

    client = DocumentIntelligenceClient(endpoint, DefaultAzureCredential())
    poller = client.begin_analyze_document("prebuilt-layout", AnalyzeDocumentRequest(url_source=bloburl))
    result: AnalyzeResult = poller.result()

    return { 
        "pages" : ["".join([line['content'] for line in page.lines]) for page in result.pages],
        "url": bloburl,
        "filename": unquote(urlparse(bloburl)[2].split("/")[-1])
    }