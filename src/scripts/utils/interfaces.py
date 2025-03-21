class Summary:
    def __init__(self, file: str, chunks: list[str]):
        self.file = file
        self.chunks = chunks

    def to_dict(self) -> dict:
        return {"file": self.file, "chunks": self.chunks}

    @classmethod
    def from_dict(cls, object: dict):
        REQUIRED_KEYS = ["file", "chunks"]
        object_keys = object.keys()
        if not all(key in object_keys for key in REQUIRED_KEYS):
            raise ValueError("The provided object is missing required keys")

        return cls(file=object["file"], chunks=object["chunks"])


class Collection:
    def __init__(self, name: str, description: str, summaries: list[Summary]):
        self.name = name
        self.description = description
        self.summaries = summaries

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "summaries": [summary.to_dict() for summary in self.summaries],
        }

    @classmethod
    def from_dict(cls, object: dict):
        REQUIRED_KEYS = ["name", "description", "summaries"]
        object_keys = object.keys()
        if not all(key in object_keys for key in REQUIRED_KEYS):
            raise ValueError("The provided object is missing required keys")

        return cls(
            name=object["name"],
            description=object["description"],
            summaries=[Summary.from_dict(summary) for summary in object["summaries"]],
        )
