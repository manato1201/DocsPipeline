import importlib
import sys

import pytest

from docspipeline.config import STUBS_DIR


@pytest.fixture
def hou(monkeypatch):
    monkeypatch.syspath_prepend(str(STUBS_DIR))
    monkeypatch.delitem(sys.modules, "hou", raising=False)
    module = importlib.import_module("hou")
    yield module
    sys.modules.pop("hou", None)


def test_attributes_are_classes_that_can_be_subclassed(hou):
    class MyNode(hou.Node):
        def twice(self):
            return 2

    assert isinstance(hou.Node, type)
    assert MyNode().twice() == 2
    assert MyNode.__mro__[1].__name__ == "Node"


def test_calls_and_attribute_chains_do_not_raise(hou):
    node = hou.node("/obj/geo1")
    assert node.children().anything.at.all() is not None
    assert list(hou.selectedNodes()) == []


def test_identity_is_stable(hou):
    assert hou.Node is hou.Node


def test_dunder_lookups_still_fail_so_tools_are_not_confused(hou):
    with pytest.raises(AttributeError):
        hou.__wrapped__


def test_stub_is_marked(hou):
    assert hou.IS_STUB is True
