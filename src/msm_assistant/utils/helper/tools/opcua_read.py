import asyncio

from asyncua import Client, Node

from ..configuration import CategoryConfig
from .base import Tool


class OPCUARead(Tool):
    def __init__(self, url: str, categories: list[CategoryConfig]):
        self._url = url

        # convert to map
        self._configs = {category.category_name: category for category in categories}

    @classmethod
    def name(self) -> str:
        """Get the name of the tool."""
        return "get_opcua_nodes"

    async def init():
        """Initialize the tool."""
        pass

    async def execute(self, arguments: dict) -> dict:  # TODO: configuration dependent
        """Execute the tool with the given arguments."""

        # TODO : check if the category is valid
        category: CategoryConfig = self._configs(arguments["category"])

        with Client(url=self._url) as client:
            client: Client
            # get nodes from the server
            nodes: list[Node] = []
            for node in category.nodes:
                nodes.append(
                    client.get_node(node["node_id"])
                )  # TODO: make this a class once it's finalised

            tasks = [node.read_value() for node in nodes]
            results = await asyncio.gather(tasks)  # TODO: deal with exception

            # augment with alias and nodeid
            augmented = []
            for result, node_descriptor in zip(results, category.nodes):
                augmented.append(
                    {  # TODO: add an extra description to help explain the value?
                        "node_id": node_descriptor["node_id"],
                        "alias": node_descriptor["alias"],
                        "current_value": result,
                    }
                )

            # return the values
            return {"results": augmented}

    def get_definition(self) -> dict:
        category_descriptions = [
            f"{category.category_name} : {category.description}"
            for category in self._configs.values()
        ]
        category_property = {
            "type": "string",
            "enum": list(self._configs.keys()),
            "description": "\n".join(
                ["The category of information to gather from the lab's OPCUA server\n"]
                + category_descriptions
            ),
        }

        return {
            "type": "function",
            "function": {
                "name": "get_opcua_nodes",
                "description": "Gather the current state of OPCUA nodes from the Monash Smart Manufacturing Lab's OPCUA server.",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": category_property,
                    },
                    "required": ["category"],
                    "additionalProperties": False,
                },
            },
        }
