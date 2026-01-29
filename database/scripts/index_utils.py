"""
FAISS index save/load utilities.

Provides consistent patterns for saving and loading FAISS indices,
eliminating duplication in build_index.py.

Usage:
    from scripts.index_utils import save_faiss_index

    # Save index
    save_faiss_index(vectordb, output_dir)
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_community.vectorstores import FAISS


logger = logging.getLogger(__name__)

def save_faiss_index(vectordb: "FAISS", output_dir: Path) -> Path:
    """
    Save FAISS index to disk with consistent pattern.

    Creates output directory if it doesn't exist, then saves the FAISS index.

    Parameters
    ----------
    vectordb : FAISS
        FAISS vectorstore instance to save.
    output_dir : Path
        Directory path to save the index.

    Returns
    -------
    Path
        Path where the index was saved.

    Example:
        >>> from langchain_community.vectorstores import FAISS
        >>> vectordb = FAISS.from_documents(documents, embeddings)
        >>> save_path = save_faiss_index(vectordb, Path("./database/faiss/pelec_cases"))
        >>> logger.debug(f"Index saved to {save_path}")
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    vectordb.save_local(str(output_dir))
    return output_dir
