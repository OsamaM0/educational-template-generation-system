import json
from template.mindmap_template import MindMapTemplate
from template.base_template import BaseTemplate
from config.settings import Settings

class DummyModel:
    """A dummy LLM model stand-in providing a predictable JSON output."""
    def __init__(self, response: str):
        self._response = response
    def invoke(self, inputs):
        # langchain chain passes through .invoke on the LLM with a list of messages; we mimic output
        return self._response

class DummyChain:
    def __init__(self, response: str):
        self.response = response
    def invoke(self, _):
        return self.response

def test_clean_and_parse_json_basic():
    mt = MindMapTemplate(model=None)  # real model not used in parsing test
    good_json = '{"class": "go.TreeModel", "nodeDataArray": [{"key":1,"text":"Root"}]}'
    parsed = mt.clean_and_parse_json(good_json)
    assert parsed['class'] == 'go.TreeModel'


def test_clean_and_parse_json_with_code_fence():
    mt = MindMapTemplate(model=None)
    fenced = """```json\n{\n  \"class\": \"go.TreeModel\",\n  \"nodeDataArray\": [ {\n    \"key\": 1, \"text\": \"Root\" } ]\n}\n```"""
    parsed = mt.clean_and_parse_json(fenced)
    assert parsed['nodeDataArray'][0]['text'] == 'Root'


def test_clean_and_parse_json_repair():
    mt = MindMapTemplate(model=None)
    broken = '{"class": "go.TreeModel", "nodeDataArray": [{"key":1,"text":"Root"}]'  # missing closing brace
    parsed = mt.clean_and_parse_json(broken)
    assert parsed['class'] == 'go.TreeModel'

if __name__ == '__main__':
    test_clean_and_parse_json_basic()
    test_clean_and_parse_json_with_code_fence()
    test_clean_and_parse_json_repair()
    print('MindMapTemplate parsing tests passed.')
