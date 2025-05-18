import pytest

# Import module under test
import msm_assistant.utils.helper.tools.opcua_read as oc_mod
from msm_assistant.utils.helper.configuration import CategoryConfig
from msm_assistant.utils.helper.tools.opcua_read import OPCUARead


# --- Test name() classmethod ---
def test_name():
    assert OPCUARead.name() == "get_opcua_nodes"


# --- Test get_definition() ---
def test_get_definition():
    # Create two categories
    cat1 = CategoryConfig(
        {
            "category_name": "cat1",
            "description": "desc1",
            "nodes": [{"node_id": "n1", "alias": "a1"}],
        }
    )
    cat2 = CategoryConfig(
        {
            "category_name": "cat2",
            "description": "desc2",
            "nodes": [{"node_id": "n2", "alias": "a2"}],
        }
    )
    tool = OPCUARead(url="opc.tcp://fake", categories=[cat1, cat2])

    definition = tool.get_definition()
    # Root structure
    assert definition["type"] == "function"
    func = definition["function"]
    assert func["name"] == "get_opcua_nodes"
    # Parameters structure
    params = func["parameters"]
    assert params["type"] == "object"
    props = params["properties"]["category"]
    # Enum should list category names
    assert set(props["enum"]) == {"cat1", "cat2"}
    # Description contains both descriptions
    desc = props["description"]
    assert "desc1" in desc and "desc2" in desc
    # Required list
    assert params["required"] == ["category"]
    assert params["additionalProperties"] is False


# --- Test init() is a no-op ---
@pytest.mark.asyncio
async def test_init_no_error():
    tool = OPCUARead(url="u", categories=[])
    # Should complete without error and return None
    result = await tool.init()
    assert result is None


# --- Test execute() success path ---
@pytest.mark.asyncio
async def test_execute_success(monkeypatch):
    # Prepare CategoryConfig with two nodes
    nodes_meta = [
        {"node_id": "n1", "alias": "a1"},
        {"node_id": "n2", "alias": "a2"},
    ]
    category = CategoryConfig(
        {
            "category_name": "cat",
            "description": "desc",
            "nodes": nodes_meta,
        }
    )
    tool = OPCUARead(url="opc.tcp://fake", categories=[category])

    # Fake Node and Client
    class FakeNode:
        def __init__(self, node_id):
            self.node_id = node_id

        async def read_value(self):
            return f"value_{self.node_id}"

    class FakeClient:
        def __init__(self, url):
            self.url = url

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        def get_node(self, node_id):
            return FakeNode(node_id)

    # Patch the Client in the module under test
    monkeypatch.setattr(oc_mod, "Client", FakeClient)

    # Execute with valid category
    result = await tool.execute({"category": "cat"})
    assert "results" in result
    expected = [
        {"node_id": "n1", "alias": "a1", "current_value": "value_n1"},
        {"node_id": "n2", "alias": "a2", "current_value": "value_n2"},
    ]
    assert result["results"] == expected


# --- Test execute() with invalid category raises KeyError ---
@pytest.mark.asyncio
async def test_execute_invalid_category():
    tool = OPCUARead(url="opc.tcp://fake", categories=[])
    with pytest.raises(KeyError):
        await tool.execute({"category": "nonexistent"})
