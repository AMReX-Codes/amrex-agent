"""
Level 1 Index Builder - Documentation & Catalogs

Builds extensible documentation indices from config.documentation_map.
No hardcoded index names - purely data-driven.

PRD: Section 5.3 (FR-3 - Unified Documentation Search)
Pattern: yt-project extensibility (Cases Service: Config-Driven Discovery)
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Type
import faiss
import numpy as np
import logging

from database.configs import BaseAMReXConfig

logger = logging.getLogger(__name__)

class Level1Builder:
    """Builds Level 1 documentation indices from config maps."""
    
    def __init__(self, config: Type[BaseAMReXConfig], embedder):
        """
        Initialize Level 1 builder.
        
        Args:
            config: Config class (e.g., PeleCConfig) with documentation_map
            embedder: Embedding service
        """
        self.config = config
        self.embedder = embedder
        self.code_name = config.code_name
    
    def build(self, source_dir: Path, output_dir: Path):
        """
        Build all documentation indices specified in config.
        
        Args:
            source_dir: Root directory for source files
            output_dir: Directory to save indices
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get documentation map from config
        doc_map = getattr(self.config, 'documentation_map', {})
        
        logger.info(f"Building Level 1 indices for {self.code_name}...")
        logger.info(f"  Documentation map has {len(doc_map)} categories")
        
        # Build index for each category in config
        for index_name, source_files in doc_map.items():
            self._build_doc_index(
                index_name,
                source_files,
                source_dir,
                output_dir
            )
        
        logger.info(f"[PASS] Level 1 indices built in {output_dir}")
    
    def _build_doc_index(self, index_name: str, source_patterns: List[str],
                         source_dir: Path, output_dir: Path):
        """
        Build a single documentation index.
        
        Args:
            index_name: Logical name (e.g., 'problem_catalogs')
            source_patterns: List of file patterns
            source_dir: Root directory
            output_dir: Output directory
        """
        documents = []
        metadata = []
        
        # Find and read source files
        for pattern in source_patterns:
            # Try as direct path first
            file_path = source_dir / pattern
            fallback_path = self._resolve_agent_path(pattern)
            
            if file_path.exists():
                content = self._read_document(file_path)
                if content:
                    # Chunk if needed
                    chunks = self._chunk_document(content, file_path)
                    documents.extend([c['text'] for c in chunks])
                    metadata.extend([{
                        'source': str(file_path.name),
                        'index_type': index_name,
                        **c.get('metadata', {})
                    } for c in chunks])
            else:
                # Try as glob pattern
                matches = list(source_dir.glob(pattern))
                if fallback_path and fallback_path.exists():
                    matches.append(fallback_path)
                for match in matches:
                    if match.is_file():
                        content = self._read_document(match)
                        if content:
                            chunks = self._chunk_document(content, match)
                            documents.extend([c['text'] for c in chunks])
                            metadata.extend([{
                                'source': str(match.name),
                                'index_type': index_name,
                                **c.get('metadata', {})
                            } for c in chunks])
        
        if not documents:
            logger.warning(f"  [WARN]  No documents found for {index_name}")
            return
        
        # Embed and save
        self._save_index(documents, metadata, index_name, output_dir)
    
    def _read_document(self, file_path: Path) -> Optional[str]:
        """Read document content."""
        try:
            return file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"  [WARN]  Could not read {file_path}: {e}")
            return None
    
    def _chunk_document(self, content: str, file_path: Path) -> List[Dict]:
        """
        Chunk document for indexing.
        
        For problem catalogs: Parse by sections
        For others: Simple chunking
        """
        chunks = []
        
        # Simple markdown section parsing
        if '##' in content:
            sections = content.split('\n## ')
            for i, section in enumerate(sections):
                if i == 0:
                    # Header section
                    if section.strip():
                        chunks.append({
                            'text': section.strip(),
                            'metadata': {'section': 'header'}
                        })
                else:
                    lines = section.split('\n')
                    title = lines[0]
                    body = '\n'.join(lines[1:])
                    
                    if body.strip():
                        chunks.append({
                            'text': f"{title}\n{body}",
                            'metadata': {
                                'category': title,
                                'section': title
                            }
                        })
        else:
            # No sections - chunk by size (simple)
            if len(content) > 1000:
                # Split into ~500 char chunks
                words = content.split()
                current_chunk = []
                current_size = 0
                
                for word in words:
                    current_chunk.append(word)
                    current_size += len(word) + 1
                    
                    if current_size > 500:
                        chunks.append({
                            'text': ' '.join(current_chunk),
                            'metadata': {}
                        })
                        current_chunk = []
                        current_size = 0
                
                if current_chunk:
                    chunks.append({
                        'text': ' '.join(current_chunk),
                        'metadata': {}
                    })
            else:
                chunks.append({'text': content, 'metadata': {}})
        
        return chunks
    
    def _save_index(self, documents: List[str], metadata: List[Dict],
                    index_name: str, output_dir: Path):
        """Save FAISS index and metadata."""
        # Embed documents
        embeddings = self.embedder.embed_texts(documents)
        embeddings_array = np.array(embeddings).astype('float32')
        
        # Create FAISS index
        dimension = embeddings_array.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_array)
        
        # Create filename with code name
        code_lower = self.code_name.lower()
        index_filename = f"{code_lower}_doc_{index_name}.faiss"
        metadata_filename = f"{code_lower}_doc_{index_name}_metadata.json"
        
        # Save index
        faiss.write_index(index, str(output_dir / index_filename))
        
        # Save metadata
        (output_dir / metadata_filename).write_text(
            json.dumps(metadata, indent=2)
        )
        
        logger.info(f"  [PASS] {index_name}: {len(documents)} documents indexed")

    def _resolve_agent_path(self, pattern: str) -> Optional[Path]:
        """Resolve a documentation path relative to the agent repo root."""
        if not pattern.startswith("database/"):
            return None

        current = Path(__file__).resolve()
        candidates = [
            current.parent,
            current.parent.parent,
            current.parent.parent.parent
        ]
        for parent in candidates:
            if (parent / 'pyproject.toml').exists() or (parent / 'setup.py').exists():
                return parent / pattern
        return None
