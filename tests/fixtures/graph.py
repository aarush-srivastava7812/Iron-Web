"""Stable, isolated FalkorDB graph names for each temporary test directory."""

import hashlib


def graph_name_for(path):
    return "test_" + hashlib.sha256(str(path).encode()).hexdigest()[:32]
