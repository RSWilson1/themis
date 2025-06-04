import pytest
from TAT_audit import TAT_queries

def test_tat_queries_module_exists():
    assert TAT_queries is not None

def test_arguments_class_exists():
    assert hasattr(TAT_queries, 'Arguments')

def test_main_function_exists():
    assert hasattr(TAT_queries, 'main')
