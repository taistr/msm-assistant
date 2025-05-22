from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (FieldCondition, Filter, MatchValue,
                                  ScoredPoint)

from .base import Tool

# todo: move this to a constants file
METADATA_COLLECTION_NAME = "metadata"


class Metadata:
    def __init__(self, name: str, embedding_model: str, dimensionality: int):
        self.name = name
        self.embedding_model = embedding_model
        self.dimensionality = dimensionality

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "embedding_model": self.embedding_model,
            "dimensionality": self.dimensionality,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            name=data["name"],
            embedding_model=data["embedding_model"],
            dimensionality=data["dimensionality"],
        )


class DatabaseRead(Tool):
    def __init__(
        self, url: str, collection: str, description: str | None = None
    ):  #! consider making the description a parameter
        self._url = url
        self._collection = collection
        self._description = description if description else "Query a vector database to retrieve additional information to the Monash Smart Manufacturing Lab or your subsystem."


        self._qdrant_client = AsyncQdrantClient(url=self._url)
        self._openai_client = AsyncOpenAI()

        self._metadata: Metadata | None = None

    @classmethod
    def name(self) -> str:
        return "search_knowledge_base"

    async def init(self) -> None:
        """Initialize the knowledge base with metadata."""
        scroll_result = await self._qdrant_client.scroll(
            collection_name=METADATA_COLLECTION_NAME,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="name", match=MatchValue(value=self._collection)
                    ),
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )

        if scroll_result[0]:
            self._metadata = Metadata.from_dict(scroll_result[0][0].payload)
        else:
            raise ValueError(f"Metadata for collection {self._collection} not found.")

    async def execute(self, arguments: dict) -> list:
        """
        Execute the knowledge base search.

        args (dict): Tool call arguments
        """
        if not self._metadata:
            await self.init()

        query = arguments["query"]
        limit = arguments["limit"]

        # Get the embedding for the query
        query_embedding = await self._encode(query)

        # Search the knowledge base
        search_result = await self._qdrant_client.query(
            collection_name=self._collection,
            query_vector=query_embedding,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        # Extract the results
        results = []
        for point in search_result:
            point: ScoredPoint
            results.append(point.payload)

        return results

    async def _encode(self, query: str) -> list:
        """
        Encode the query using the OpenAI embedding model.

        query (str): The query to encode.
        """
        response = await self._openai_client.embeddings.create(
            input=query,
            model=self._metadata.embedding_model,
        )
        return response.data[0].embedding

    def get_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name(),
                "description": self._description,
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The question, keywords, or phrase to use for searching the database.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "The maximum number of results to return.",
                        },
                    },
                    "required": ["query", "limit"],
                    "additionalProperties": False,
                },
            },
        }
