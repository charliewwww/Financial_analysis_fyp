"""
Syntax & compile-time checks for all UI modules.

Catches SyntaxError at parse time.  These tests run on every CI push
and prevent the class of bug where a variable is deleted during
refactoring but still referenced (like the timeout_pct NameError).
"""

import ast
import os
import pytest

_UI_DIR = os.path.join(os.path.dirname(__file__), "..", "ui")

_UI_FILES = [
    f for f in os.listdir(_UI_DIR)
    if f.endswith(".py") and f != "__init__.py"
]


class TestUISyntax:
    """Every .py file in ui/ must parse without syntax errors."""

    @pytest.mark.parametrize("py_file", _UI_FILES)
    def test_ast_compiles(self, py_file):
        """compile() each UI file — catches SyntaxError."""
        path = os.path.join(_UI_DIR, py_file)
        with open(path, encoding="utf-8") as f:
            source = f.read()
        compile(source, path, "exec")


class TestUIFunctionBodies:
    """Compile-check that every function body in UI files is valid Python.

    This catches syntax-level issues that only surface when a specific
    Streamlit code path runs (e.g. a progress rendering branch).
    """

    @pytest.mark.parametrize("py_file", _UI_FILES)
    def test_function_bodies_compile(self, py_file):
        """Extract each function and verify it compiles."""
        path = os.path.join(_UI_DIR, py_file)
        with open(path, encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source, path)
        errors = []

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                try:
                    func_source = ast.get_source_segment(source, node)
                    if func_source:
                        compile(func_source, f"{path}:{node.name}", "exec")
                except SyntaxError as e:
                    errors.append(f"{node.name}() line {node.lineno}: {e}")

        assert not errors, (
            f"Compile errors in {py_file}:\n" +
            "\n".join(f"  {e}" for e in errors)
        )
