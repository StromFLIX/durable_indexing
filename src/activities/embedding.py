from application.app import app
import os
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI
from typing import List, Dict

@app.function_name(name="embedding")
@app.activity_trigger(input_name="chunks")
def embedding(chunks: List[Dict]) -> List[Dict]:
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    client = AzureOpenAI(
        api_version="2024-02-15-preview",
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
    )
    embeddings = client.embeddings.create(input = [chunk["text"] for chunk in chunks], model="embedding")
    for i, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings.data[i].embedding 
    return chunks