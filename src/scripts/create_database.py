#!/usr/bin/env python3
import argparse
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path

import chromadb
import chromadb.utils.embedding_functions as embedding_functions
from dotenv import load_dotenv

from scripts.utils.interfaces import Collection, Summary

logger = logging.getLogger(__name__)

EMBEDDING_MODELS = [
    "text-embedding-3-large",
    "text-embedding-3-small",
    "text-embedding-ada-002",
]


class Database:
    @staticmethod
    def create(directory_path: Path, model: str):
        if not directory_path.is_dir():
            raise ValueError(
                f"The provided path {directory_path} is not a valid directory."
            )

        if model not in EMBEDDING_MODELS:
            raise ValueError(
                f"The provided model '{model}' is not one of {EMBEDDING_MODELS}"
            )

        # Get all the JSON collections in the directory
        json_files = directory_path.rglob("*.json")
        collections: list[Collection] = []
        for json_file in json_files:
            with open(json_file, "r") as file:
                collection = json.load(file)
                collections.append(Collection.from_dict(collection))

        client = chromadb.PersistentClient(
            path=str(directory_path),
        )

        openai_ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"), model_name="text-embedding-3-large"
        )
        for collection in collections:
            collection: Collection

            # Create the collection
            client.delete_collection(name=collection.name)
            chroma_collection = client.create_collection(
                name=collection.name,
                embedding_function=openai_ef,
                metadata={
                    "description": collection.description,
                    "created": str(datetime.now()),
                },
            )

            # Create data
            documents = []
            metadata = []
            ids = []
            for summary in collection.summaries:
                summary: Summary
                documents += summary.chunks
                metadata += [{"file": summary.file}] * len(summary.chunks)
                ids += [str(uuid.uuid4()) for _ in range(len(summary.chunks))]

            # Add data to database
            chroma_collection.add(documents=documents, metadatas=metadata, ids=ids)


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="ChromaDB database creator",
        description="Takes a directory of json 'collections' and generates a ChromaDB database file",
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
        help="Embedding model to use (default: 'text-embedding-3-large')",
    )

    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_arguments()

    model = args.model if args.model else "text-embedding-3-large"

    Database.create(Path(args.directory), model)


if __name__ == "__main__":
    main()
