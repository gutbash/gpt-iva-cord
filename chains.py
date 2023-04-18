from langchain.chains.qa_with_sources.base import BaseQAWithSourcesChain
from typing import Any, Dict, List, Optional
from langchain.docstore.document import Document

class QAWithSourcesChain(BaseQAWithSourcesChain):
    """Question answering with sources over documents."""

    input_docs_key: str = "input_documents"  #: :meta private:

    @property
    def input_keys(self) -> List[str]:
        """Expect input key.

        :meta private:
        """
        return [self.input_docs_key, self.question_key]

    def _get_docs(self, inputs: Dict[str, Any]) -> List[Document]:
        return inputs.pop(self.input_docs_key)

    async def _aget_docs(self, inputs: Dict[str, Any]) -> List[Document]:
        return inputs.pop(self.input_docs_key)