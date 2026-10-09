"""The hand-written type stub must stay in step with the native module."""

import ast
import inspect
from pathlib import Path

import gitoxide
from gitoxide import _gitoxide

STUB = Path(gitoxide.__file__).with_name("_gitoxide.pyi")


def _public(names):
    return {n for n in names if not n.startswith("_")}


def _declared(body):
    """Names a stub module or class body declares."""
    names = set()
    for node in body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.AnnAssign):
            names.add(node.target.id)
    return _public(names)


def test_stub_declares_every_public_name():
    stub = ast.parse(STUB.read_text())
    assert _public(vars(_gitoxide)) <= _declared(stub.body)


def test_stub_classes_match_runtime_members():
    stub = ast.parse(STUB.read_text())
    stub_classes = {n.name: n for n in stub.body if isinstance(n, ast.ClassDef)}

    for name, cls in inspect.getmembers(_gitoxide, inspect.isclass):
        assert _declared(stub_classes[name].body) == _public(vars(cls)), name
