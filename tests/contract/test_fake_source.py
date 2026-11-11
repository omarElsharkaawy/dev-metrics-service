import pytest

from devmetrics.sources.base import SourceAdapter
from devmetrics.sources.fake import FakeSource
from tests.contract.source_contract import SourceContract


class TestFakeSourceContract(SourceContract):
    @pytest.fixture
    def source(self) -> SourceAdapter:
        return FakeSource(seed=42)
