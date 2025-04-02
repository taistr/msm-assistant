#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (Distance, FieldCondition, Filter,
                                  FilterSelector, MatchValue, PointStruct,
                                  VectorParams)
from yaspin import yaspin
from yaspin.spinners import Spinners

from scripts.utils.interfaces import Collection, Summary

logger = logging.getLogger(__name__)

EMBEDDING_MODELS = {
    "text-embedding-3-large": {
        "dimensions": 3072,
    },
    "text-embedding-3-small": {
        "dimensions": 1536,
    },
    "text-embedding-ada-002": {
        "dimensions": 1536,
    },
}


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


class Chunk:
    def __init__(self, file: str, text: str, vector: list[float] | None = None):
        self._id = str(uuid.uuid4())
        self._file = file
        self._text = text
        self._vector = vector

    def add_vector(self, vector: list[int]):
        self._vector = vector

    @property
    def payload(self) -> dict:
        return {"file": self._file, "text": self._text}

    @property
    def text(self) -> str:
        return self._text

    @property
    def id(self) -> str:
        return self._id

    @property
    def vector(self) -> list[float]:
        if self._vector is None:
            raise ValueError("Chunk has not been assigned a vector.")

        return self._vector


class Encoder:
    def __init__(self, model: str):
        if model not in EMBEDDING_MODELS.keys():
            raise ValueError(
                f"The provided model '{model}' is not one of {EMBEDDING_MODELS}"
            )

        self._openai_client = AsyncOpenAI()
        self.model = model

    @property
    def dimensionality(self):
        return EMBEDDING_MODELS[self.model]["dimensions"]

    async def encode(self, text: str) -> list[float]:
        response = await self._openai_client.embeddings.create(
            input=text,
            model=self.model,
        )
        return response.data[0].embedding

    async def encode_collection(self, chunks: list[str]) -> list[list[float]]:
        tasks = [self.encode(chunk) for chunk in chunks]
        encodings = await asyncio.gather(*tasks)
        return encodings


class Database:
    def __init__(self, url: str, model: str):
        self._qdrant_client = AsyncQdrantClient(
            url=url
        )  # * parametrise this later if you want
        self._encoder = Encoder(model)

    async def _create_metadata(self, metadata: Metadata):
        METADATA_COLLECTION_NAME = "metadata"

        # Check if the metadata collection exists
        collection_exists = await self._qdrant_client.collection_exists(
            METADATA_COLLECTION_NAME
        )
        if not collection_exists:
            await self._qdrant_client.create_collection(
                collection_name=METADATA_COLLECTION_NAME,
                vectors_config=VectorParams(size=1, distance=Distance.EUCLID),
            )

        # Delete the existing metadata
        await self._qdrant_client.delete(
            collection_name=METADATA_COLLECTION_NAME,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[
                        FieldCondition(
                            key="name",
                            match=MatchValue(value=metadata.name),
                        ),
                    ],
                )
            ),
        )

        # Create the metadata
        await self._qdrant_client.upsert(
            collection_name=METADATA_COLLECTION_NAME,
            wait=True,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=[0],
                    payload=metadata.to_dict(),
                )
            ],
        )

    @staticmethod
    def _get_collections(directory_path: Path) -> list[Collection]:
        # Get all the JSON collections in the directory
        json_files = directory_path.rglob("*.json")
        collections: list[Collection] = []
        for json_file in json_files:
            with open(json_file, "r") as file:
                collection = json.load(file)
                collections.append(Collection.from_dict(collection))

        return collections

    def _get_chunks(self, collection: Collection) -> list[Chunk]:
        chunks: list[Chunk] = []

        for summary in collection.summaries:
            summary: Summary
            for chunk in summary.chunks:
                chunks.append(Chunk(text=chunk, file=summary.file))

        return chunks

    async def create(self, directory_path: Path):
        if not directory_path.is_dir():
            raise ValueError(
                f"The provided path {directory_path} is not a valid directory."
            )

        # Get all the JSON collections in the directory
        collections: list[Collection] = self._get_collections(directory_path)

        for collection in collections:
            collection: Collection
            with yaspin(
                spinner=Spinners.dots, text=f"{collection.name} - Processing ..."
            ) as sp:
                # Get a list of all text
                chunks: list[Chunk] = self._get_chunks(collection)

                # Embed all text
                sp.spinner = Spinners.binary
                sp.text = f"{collection.name} - Encoding chunks ..."
                embeddings = await self._encoder.encode_collection(
                    chunks=[chunk.text for chunk in chunks]
                )
                for embedding, chunk in zip(embeddings, chunks, strict=True):
                    chunk.add_vector(embedding)

                # Create the collection
                sp.spinner = Spinners.material
                sp.text = f"{collection.name} - Creating collection ..."
                await self._qdrant_client.delete_collection(
                    collection_name=collection.name
                )
                await self._qdrant_client.create_collection(
                    collection_name=collection.name,
                    vectors_config=VectorParams(
                        size=self._encoder.dimensionality, distance=Distance.COSINE
                    ),
                )

                # Add data to database
                await self._qdrant_client.upsert(
                    collection_name=collection.name,
                    wait=True,
                    points=[
                        PointStruct(
                            id=chunk.id, vector=chunk.vector, payload=chunk.payload
                        )
                        for chunk in chunks
                    ],
                )

                # Create the metadata
                await self._create_metadata(
                    Metadata(
                        name=collection.name,
                        embedding_model=self._encoder.model,
                        dimensionality=self._encoder.dimensionality,
                    )
                )


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="Qdrant database creator",
        description="Takes a directory of json 'collections' and populates a Qdrant database",
    )

    parser.add_argument(
        "--directory",
        "-d",
        required=True,
        help="Path to a directory containing PDF files and where the resulting database will be stored to.",
    )

    parser.add_argument(
        "--model",
        "-m",
        help="OpenAI embedding model to use (default: 'text-embedding-3-large')",
    )

    parser.add_argument(
        "--url",
        "-u",
        required=True,
        help="Hostname of the vector database (Qdrant defaults to port 6333)",
    )

    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_arguments()

    model = args.model if args.model else "text-embedding-3-small"

    database = Database(url=args.url, model=model)
    asyncio.run(database.create(Path(args.directory)))


if __name__ == "__main__":
    main()
