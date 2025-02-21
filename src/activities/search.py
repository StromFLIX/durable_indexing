import base64
import logging
import os
import re
from typing import List, Union

from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.aio import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.core.credentials_async import AsyncTokenCredential
from azure.search.documents.indexes.aio import SearchIndexClient
from application.app import app
from azure.identity import DefaultAzureCredential
from urllib.parse import urlsplit
from typing import List, Dict

class AzureOpenAIEmbeddingConfig():
    """
    Class for using Azure OpenAI embeddings
    To learn more please visit https://learn.microsoft.com/azure/ai-services/openai/concepts/understand-embeddings
    """

    def __init__(
        self,
        open_ai_deployment: Union[str, None],
        open_ai_model_name: str,
        open_ai_dimensions: int,
        open_ai_endpoint: str
    ):
        self.open_ai_deployment = open_ai_deployment
        self.open_ai_model_name = open_ai_model_name
        self.open_ai_dimensions = open_ai_dimensions
        self.open_ai_endpoint = open_ai_endpoint



logger = logging.getLogger("scripts")
class SearchInfo:
    """
    Class representing a connection to a search service
    To learn more, please visit https://learn.microsoft.com/azure/search/search-what-is-azure-search
    """

    def __init__(self, endpoint: str, credential: Union[AsyncTokenCredential, AzureKeyCredential], index_name: str):
        self.endpoint = endpoint
        self.credential = credential
        self.index_name = index_name

    def create_search_client(self) -> SearchClient:
        return SearchClient(endpoint=self.endpoint, index_name=self.index_name, credential=self.credential)

    def create_search_index_client(self) -> SearchIndexClient:
        return SearchIndexClient(endpoint=self.endpoint, credential=self.credential)



class SearchManager:
    """
    Class to manage a search service. It can create indexes, and update or remove sections stored in these indexes
    To learn more, please visit https://learn.microsoft.com/azure/search/search-what-is-azure-search
    """

    def __init__(
        self,
        search_info: SearchInfo,
        embeddings: AzureOpenAIEmbeddingConfig,
    ):
        self.search_info = search_info
        self.embeddings = embeddings

    async def create_index(self):
        logger.info("Checking whether search index %s exists...", self.search_info.index_name)

        async with self.search_info.create_search_index_client() as search_index_client:

            if self.search_info.index_name not in [name async for name in search_index_client.list_index_names()]:
                logger.info("Creating new search index %s", self.search_info.index_name)
                fields = [
                    SearchField(
                        name="id",
                        type="Edm.String",
                        key=True,
                        sortable=True,
                        filterable=True,
                        facetable=True,
                        analyzer_name="keyword",
                    ),
                    SearchableField(
                        name="content",
                        type="Edm.String",
                    ),
                    SearchField(
                        name="embedding",
                        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                        hidden=False,
                        searchable=True,
                        filterable=False,
                        sortable=False,
                        facetable=False,
                        vector_search_dimensions=self.embeddings.open_ai_dimensions,
                        vector_search_profile_name="embedding_config",
                    ),
                    SimpleField(
                        name="sourcepages",
                        type="Edm.String",
                        filterable=True,
                        facetable=True,
                    ),
                    SimpleField(
                        name="sourcefile",
                        type="Edm.String",
                        filterable=True,
                        facetable=True,
                    ),
                    SimpleField(
                        name="storageUrl",
                        type="Edm.String",
                        filterable=True,
                        facetable=False,
                    ),
                ]

                vectorizers = []
                vectorizers.append(
                    AzureOpenAIVectorizer(
                        vectorizer_name=f"{self.search_info.index_name}-vectorizer",
                        parameters=AzureOpenAIVectorizerParameters(
                            resource_url=self.embeddings.open_ai_endpoint,
                            deployment_name=self.embeddings.open_ai_deployment,
                            model_name=self.embeddings.open_ai_model_name,
                        ),
                    )
                )

                index = SearchIndex(
                    name=self.search_info.index_name,
                    fields=fields,
                    semantic_search=SemanticSearch(
                        configurations=[
                            SemanticConfiguration(
                                name="default",
                                prioritized_fields=SemanticPrioritizedFields(
                                    title_field=None, content_fields=[SemanticField(field_name="content")]
                                ),
                            )
                        ]
                    ),
                    vector_search=VectorSearch(
                        algorithms=[
                            HnswAlgorithmConfiguration(
                                name="hnsw_config",
                                parameters=HnswParameters(metric="cosine"),
                            )
                        ],
                        profiles=[
                            VectorSearchProfile(
                                name="embedding_config",
                                algorithm_configuration_name="hnsw_config",
                                vectorizer_name=f"{self.search_info.index_name}-vectorizer",
                            ),
                        ],
                        vectorizers=vectorizers,
                    ),
                )

                await search_index_client.create_index(index)
            else:
                logger.info("Search index %s already exists", self.search_info.index_name)

    async def update_content(
        self, chunks_with_embeddings: List[dict],
    ):
        MAX_BATCH_SIZE = 1000
        section_batches = [chunks_with_embeddings[i : i + MAX_BATCH_SIZE] for i in range(0, len(chunks_with_embeddings), MAX_BATCH_SIZE)]
        
        def filename_to_id(filename: str):
            filename_ascii = re.sub("[^0-9a-zA-Z_-]", "_", filename)
            filename_hash = base64.b16encode(filename.encode("utf-8")).decode("ascii")
        
            return f"file-{filename_ascii}-{filename_hash}"
        async with self.search_info.create_search_client() as search_client:
            for batch_index, batch in enumerate(section_batches):
                documents = [
                    {
                        "id": f"{filename_to_id(section['filename'])}-chunk-{section_index + batch_index * MAX_BATCH_SIZE}",
                        "content": section['text'],
                        "sourcepages": f"{section['filename']}#pages={','.join([f'{i}' for i in range(section['start_page'] + 1, section['end_page'] + 2)])}",
                        "sourcefile": section['filename'],
                        "storageUrl": urlsplit(section['url'])._replace(query=None).geturl(),
                        "embedding": section['embedding'],
                    }
                    for section_index, section in enumerate(batch)
                ]

                await search_client.upload_documents(documents)
                
                

@app.function_name(name="add_documents")
@app.activity_trigger(input_name="documents")
async def add_documents(documents: dict) -> List[str]:
    searchManager = SearchManager(
        SearchInfo(
            endpoint=os.getenv("SEARCH_SERVICE_ENDPOINT"),
            credential=DefaultAzureCredential(),
            index_name=documents["index_name"]
        ), AzureOpenAIEmbeddingConfig(
            open_ai_dimensions=3072,
            open_ai_deployment="embedding",
            open_ai_model_name="text-embedding-3-large",
            open_ai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
    )
    await searchManager.update_content(documents["chunks"])
    
@app.function_name(name="ensure_index_exists")
@app.activity_trigger(input_name="name")
async def ensure_index_exists(name: str) -> List[str]:
    searchManager = SearchManager(
        SearchInfo(
            endpoint=os.getenv("SEARCH_SERVICE_ENDPOINT"),
            credential=DefaultAzureCredential(),
            index_name=name
        ), AzureOpenAIEmbeddingConfig(
            open_ai_dimensions=3072,
            open_ai_deployment="embedding",
            open_ai_model_name="text-embedding-3-large",
            open_ai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
    )
    await searchManager.create_index()
    