#!/usr/bin/env python3
import argparse
import json
import logging
import os
import asyncio
from tqdm.asyncio import tqdm
import uuid
from datetime import datetime
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv
from openai import OpenAI

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
        return {
            "file": self._file,
            "text": self._text
        }

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

            self._openai_client = OpenAI()
            self._model = model

    @property
    def dimensionality(self):
        return EMBEDDING_MODELS[self._model]["dimensions"]

    async def encode(self, text: str) -> list[float]:
        response = self._openai_client.embeddings.create(
            input=text,
            model=self._model,
        )
        return response.data[0].embedding
    
    async def encode_collection(self, chunks: list[str]) -> list[list[float]]:
        tasks = [self.encode(chunk) for chunk in chunks]
        encodings = await tqdm.gather(*tasks, total=len(tasks), desc="Embedding")
        return encodings


class Database:
    def __init__(self, hostname: str, model: str):
        self._qdrant_client = QdrantClient(url=f"http://{hostname}:6333") #* parametrise this later if you want
        self._encoder = Encoder(model)

    async def create(self, directory_path: Path):
        if not directory_path.is_dir():
            raise ValueError(
                f"The provided path {directory_path} is not a valid directory."
            )

        # Get all the JSON collections in the directory
        json_files = directory_path.rglob("*.json")
        collections: list[Collection] = []
        for json_file in json_files:
            with open(json_file, "r") as file:
                collection = json.load(file)
                collections.append(Collection.from_dict(collection))

        for collection in collections:
            collection: Collection

            # Get a list of all text
            chunks: list[Chunk] = []
            for summary in collection.summaries:
                summary: Summary
                
                for chunk in summary.chunks:
                    chunks.append(Chunk(text=chunk, file=summary.file))

            # Embed all text
            embeddings = await self._encoder.encode_collection(
                chunks=[chunk.text for chunk in chunks]
            )
            for embedding, chunk in zip(embeddings, chunks, strict=True):
                chunk.add_vector(embedding)


            # Create the collection
            result = self._qdrant_client.delete_collection(collection_name=collection.name)
            logger.debug(result)

            result = self._qdrant_client.create_collection(
                collection_name=collection.name,
                vectors_config=VectorParams(
                    size=self._encoder.dimensionality,
                    distance=Distance.COSINE
                )
            )
            logger.debug(result)

            # Add data to database
            result = self._qdrant_client.upsert(
                collection_name=collection.name,
                wait=True,
                points=[
                    PointStruct(id=chunk.id, vector=chunk.vector, payload=chunk.payload) for chunk in chunks
                ],
            )
            logger.debug(result)

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
        "--hostname",
        "-hn",
        required=True,
        help="Hostname of the vector database (Qdrant defaults to port 6333)"
    )

    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_arguments()

    model = args.model if args.model else "text-embedding-3-small"

    database = Database(hostname=args.hostname, model=model)
    asyncio.run(database.create(Path(args.directory)))


if __name__ == "__main__":
    main()
