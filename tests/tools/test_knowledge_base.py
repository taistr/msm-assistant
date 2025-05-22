# ─── tests/test_knowledge_base.py ───────────────────────────────────────────

import sys
import types

# ─── STUB OUT `openai` and `qdrant_client` ──────────────────────────────────
# This must happen before you import the code under test!

# 1) stub openai.AsyncOpenAI
fake_openai = types.ModuleType("openai")
# make AsyncOpenAI a no-op constructor (you'll monkeypatch its methods later)
fake_openai.AsyncOpenAI = lambda *a, **k: None
sys.modules["openai"] = fake_openai

# 2) stub qdrant_client.AsyncQdrantClient
fake_qdrant = types.ModuleType("qdrant_client")
fake_qdrant.AsyncQdrantClient = lambda *a, **k: None
sys.modules["qdrant_client"] = fake_qdrant

# 3) stub qdrant_client.models
fake_models = types.SimpleNamespace(
    FieldCondition=lambda *a, **k: None,
    Filter=lambda *a, **k: None,
    MatchValue=lambda *a, **k: None,
    ScoredPoint=type("ScoredPoint", (), {}),
)
sys.modules["qdrant_client.models"] = fake_models


from types import SimpleNamespace  # noqa: E402

# ─── NOW import your module under test ───────────────────────────────────────
import pytest  # noqa: E402

from msm_assistant.utils.helper.tools.database_read import \
    DatabaseRead  # noqa: E402
from msm_assistant.utils.helper.tools.database_read import \
    Metadata  # noqa: E402


# ─── METADATA tests ──────────────────────────────────────────────────────────
def test_metadata_to_from_dict():
    orig = Metadata("foo", "emb-model", 42)
    d = orig.to_dict()
    assert d == {
        "name": "foo",
        "embedding_model": "emb-model",
        "dimensionality": 42,
    }
    back = Metadata.from_dict(d)
    assert back.name == "foo"
    assert back.embedding_model == "emb-model"
    assert back.dimensionality == 42


# ─── name() and get_definition() ────────────────────────────────────────────
def test_name_and_definition():
    assert DatabaseRead.name() == "search_knowledge_base"
    kb = DatabaseRead(url="u", collection="col")
    fn = kb.get_definition()["function"]
    assert fn["name"] == "search_knowledge_base"
    assert "Query a knowledge base" in fn["description"]
    params = fn["parameters"]
    assert params["required"] == ["query", "limit"]
    assert set(params["properties"]) == {"query", "limit"}


# ─── init() ──────────────────────────────────────────────────────────────────
class FakePoint:
    def __init__(self, payload):
        self.payload = payload


# ─── _encode() ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_encode(monkeypatch):
    kb = DatabaseRead(url="u", collection="col")
    kb._metadata = Metadata("col", "emb-model", 5)
    fake_resp = SimpleNamespace(data=[SimpleNamespace(embedding=[1, 2, 3])])

    async def fake_create(input, model):
        assert input == "hello"
        assert model == "emb-model"
        return fake_resp

    # Now that AsyncOpenAI() is a no-op, it has no `embeddings` attribute, so we
    # need to attach one:
    kb._openai_client = SimpleNamespace(embeddings=SimpleNamespace(create=fake_create))

    emb = await kb._encode("hello")
    assert emb == [1, 2, 3]
