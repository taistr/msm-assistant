#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.types import Part
from tqdm.asyncio import tqdm

from scripts.utils.interfaces import Collection, Summary

GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-pro-exp-02-05",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.0-pro-vision",
]

SUMMARY_PROMPT = (
    "### [1] TASK\n"
    "Summarize the document into a series of one-sentence summaries capturing the most important details.\n\n"
    "### [2] GUIDELINES\n"
    "1. Capture a distinct key point.\n"
    "2. Use proper nouns and include a clear subject.\n"
    "3. Incorporate specific details such as actions, outcomes, or entities.\n"
    "4. Avoid vague or abstract language.\n"
    "5. Use active voice and be no longer than 20 words.\n"
    "6. Avoid shortening names to acronyms.\n"
    "### [3] GUIDELINES\n"
    " - Structure your response as an unordered list.\n"
    " - Do not include any preamble or any additional comments - simply fulfil the task.\n"
    "### [4] EXAMPLE\n"
    " - This work investigates the extent to which LLMs used in such embodied contexts can reason over sources of feedback provided "
    "through natural language, without any additional training.\n"
    " - Large Language Models (LLMs) can be applied to domains beyond natural language processing, such as planning and interaction "
    "for robots.\n\n"
)


class CollectionError(Exception):
    """Raised when there is an error with the collection"""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class CollectionFactory:
    def __init__(self, name: str, description: str = None):
        if name == "" or name is None:
            raise ValueError("'name' cannot be empty or None")

        self._name = name
        self._description = description
        self._google_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    async def create(
        self, directory_path: Path, model: str = "gemini-2.0-flash"
    ) -> list[dict]:
        if not directory_path.is_dir():
            raise ValueError(
                f"The provided path {directory_path} is not a valid directory."
            )

        # find all pdf files in directory
        pdf_paths = list(directory_path.rglob("*.pdf"))

        # summarise each pdf - perhaps all at once?
        tasks = [self._summarise(pdf_path, model) for pdf_path in pdf_paths]
        summaries: list[Summary] = await tqdm.gather(*tasks, total=len(tasks))

        return Collection(
            name=self._name, description=self._description, summaries=summaries
        )

    async def _summarise(self, file_path: Path, model: str) -> Summary:
        if model not in GEMINI_MODELS:
            raise ValueError("The selected model is not a supported PDF model")

        # Encode the file (only works for <20MB files)
        # https://ai.google.dev/gemini-api/docs/document-processing?lang=python#prompting-pdfs
        pdf_file = Part.from_bytes(
            data=file_path.read_bytes(), mime_type="application/pdf"
        )

        # Generate the response
        response = await self._google_client.aio.models.generate_content(
            model=model,
            contents=[pdf_file, SUMMARY_PROMPT],
            config={
                "response_mime_type": "application/json",
                "response_schema": list[str],
            },
        )
        chunks = json.loads(response.text)

        return Summary(file=file_path.name, chunks=chunks)


def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="Document chunk creator ",
        description="Takes a directory of documents and converts them to a JSON file of summarised chunks",
    )

    parser.add_argument(
        "--directory",
        "-d",
        required=True,
        help="Path to a directory containing PDF files",
    )

    parser.add_argument("--name", "-n", required=True, help="Name of the collection")

    parser.add_argument(
        "--model", "-m", help="Name of the Google Generative AI model to use"
    )

    parser.add_argument(
        "--description", "-de", help="Description of the collection's intended use"
    )

    return parser.parse_args()


def main():
    load_dotenv()
    args = parse_arguments()

    # Generate the collection
    model = args.model if args.model else "gemini-2.0-flash"
    description = args.description if args.description else ""

    collection_client = CollectionFactory(args.name, description)
    pdf_directory = Path(args.directory)
    collection: Collection = asyncio.run(collection_client.create(pdf_directory, model))

    # Save the output
    output_path = pdf_directory / f"{args.name}.json"
    with open(output_path, "w") as file:
        json.dump(collection.to_dict(), file, indent=4)

    print(f"Saved collection '{args.name}' to {args.directory}")


if __name__ == "__main__":
    main()
