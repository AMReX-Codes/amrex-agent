"""
Database indexing modules for FAISS index building.

Level 0: Multi-solver physics regime router
Level 1: Documentation and problem catalogs
Level 2: Granular case metadata (6 sub-indices)
"""

from .level0_builder import Level0Builder
from .level0_searcher import Level0Searcher
from .level1_builder import Level1Builder
from .level1_searcher import Level1Searcher
from .level2_builder import Level2Builder
from .level2_searcher import Level2Searcher

import logging

__all__ = [
    'Level0Builder',
    'Level0Searcher',
    'Level1Builder',
    'Level1Searcher',
    'Level2Builder',
    'Level2Searcher',
]
