"""
Level 2 Index Builder - Granular Case Metadata

Builds weighted sub-indices per solver:
1. physics_parameters (30%) - Physics parameters and descriptions
2. grid_specifications (20%) - AMR settings and geometry
3. development_activity (10%) - Development/gitrepo signals
4. configuration_complexity (10%) - Parameter customization depth
5. path_hierarchy (15%) - Organizational structure
6. domain_models (10%) - Chemistry/domain-specific knobs
7. resource_requirements (5%) - Runtime/resource heuristics


PRD: Section 5.4 (FR-5 - Structured Metadata Search)
Amendment C: Uses Metadata Schema's extract_metadata (NO truncation)
"""

import json
from pathlib import Path
import logging
from typing import Dict, List, Any, Optional, Type, Tuple
import faiss
import numpy as np

from database.configs import BaseAMReXConfig
from database.scripts.dependency_discovery import DependencyDiscovery
from database.scripts.utils import find_case_directories, tokenize


logger = logging.getLogger(__name__)

class Level2Builder:
    """Builds Level 2 case metadata indices."""
    
    # PRD Section 5.4: Exact weights
    WEIGHTS = {
        'physics_parameters': 0.30,        # Physics parameters (reduced from 0.35)
        'grid_specifications': 0.20,        # AMR settings
        'development_activity': 0.10,       # Git health (split from git_metrics)
        'configuration_complexity': 0.10,   # Customization level (split from git_metrics)
        'path_hierarchy': 0.15,             # Path quality
        'domain_models': 0.10,       # Domain-specific features
        'resource_requirements': 0.05,      # Runtime estimates
    }
    # Total: 1.00 (7 indices - Indexing Engine: Path Hierarchy Weights)
    
    def __init__(self, config: Type[BaseAMReXConfig], embedder):
        """
        Initialize Level 2 builder.
        
        Args:
            config: Config class with extract_metadata method
            embedder: Embedding service
        """
        self.config = config
        self.embedder = embedder
        self.code_name = config.code_name

    def _get_keywords(self, primary_key: str, fallback_keys: Optional[List[str]] = None) -> List[str]:
        """Resolve level2 keyword filters with backward-compatible fallbacks."""
        keywords = self.config.level2_index_keywords.get(primary_key, [])
        if keywords:
            return keywords
        if fallback_keys:
            for key in fallback_keys:
                fallback = self.config.level2_index_keywords.get(key, [])
                if fallback:
                    return fallback
        return []
    
    def build(self, repo_root: Path, output_dir: Path):
        """
        Build all 6 Level 2 sub-indices.
        
        Args:
            repo_root: Repository root directory
            output_dir: Directory to save indices
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Building Level 2 indices for {self.code_name}...")
        
        # Discover dependencies (submodules) to exclude
        try:
            deps = DependencyDiscovery.discover_recursive(repo_root)
            submodule_paths = set()
            for dep in deps:
                path_value = getattr(dep, 'path', None)
                if path_value:
                    submodule_paths.add(path_value)
            logger.info(f"  Discovered {len(submodule_paths)} submodule paths to exclude")
        except Exception as e:
            logger.warning(f"  Could not discover dependencies: {e}. Using empty filter.")
            submodule_paths = set()
        
        # Discover cases using existing utility (no duplication)
        rel_paths, abs_paths = find_case_directories(repo_root)
        
        # Filter out submodule cases
        filtered_rel = []
        filtered_abs = []
        for rel_path, abs_path in zip(rel_paths, abs_paths):
            is_submodule = any(
                str(abs_path).startswith(str(submod)) 
                for submod in submodule_paths
            )
            if is_submodule:
                logger.debug(f"  Skipping submodule case: {rel_path}")
                continue
            filtered_rel.append(rel_path)
            filtered_abs.append(abs_path)
        
        rel_paths = filtered_rel
        abs_paths = filtered_abs
        
        if not abs_paths:
            logger.warning(f"  [WARN]  No cases found in {repo_root}")
            return
        
        logger.info(f"  Found {len(abs_paths)} cases")
        
        # Extract metadata for all cases using Metadata Schema
        # CRITICAL: This uses extract_metadata (Amendment C - NO truncation)
        case_metadata = []
        for case_path in abs_paths:
            try:
                # Amendment C: Use Metadata Schema's full parsing
                metadata = self.config.extract_metadata(case_path, repo_root=repo_root)
                case_metadata.append(metadata)
            except Exception as e:
                logger.warning(f"  [WARN]  Could not extract metadata for {case_path}: {e}")
        
        if not case_metadata:
            logger.warning("  [WARN]  No metadata extracted")
            return
        
        # Build each of the 6 sub-indices
        self._build_physics_parameters(case_metadata, output_dir)
        self._build_grid_specifications(case_metadata, output_dir)
        self._build_development_activity(case_metadata, output_dir)
        self._build_configuration_complexity(case_metadata, output_dir)
        self._build_path_hierarchy(case_metadata, output_dir)
        self._build_domain_models(case_metadata, output_dir)
        self._build_resource_requirements(case_metadata, output_dir)
        self._build_additional_indices(case_metadata, output_dir)
        
        logger.info(f"[PASS] Level 2 indices built in {output_dir}")
    
    def _build_physics_parameters(self, case_metadata: List[Dict], output_dir: Path):
        """
        Build physics_parameters index (30% weight).
        
        Includes:
        - Physics parameters from inputs_content
        - README descriptions
        - Problem type (combustion, astrophysics, etc.)
        """
        documents = []
        metadata = []
        
        for case_meta in case_metadata:
            # Get inputs_content (Amendment C - complete dict)
            inputs_content = case_meta.get('inputs_content', {})
            
            # Extract physics-related parameters
            physics_params = []
            for key, value in inputs_content.items():
                keywords = self._get_keywords(
                    "physics_parameters",
                    fallback_keys=["physics_descriptors"]
                )
                if keywords and any(kw in key.lower() for kw in keywords):
                    physics_params.append(f"{key} = {value}")
            
            # Create document text
            doc_parts = []
            
            # Case name and path
            case_name = case_meta.get('case_name', 'Unknown')
            repo_path = case_meta.get('repo_path', '')
            doc_parts.append(f"Case: {case_name}")
            doc_parts.append(f"Path: {repo_path}")
            
            # Description (if available)
            if 'description' in case_meta:
                doc_parts.append(f"Description: {case_meta['description']}")
            
            # Physics parameters
            if physics_params:
                doc_parts.append("Physics Configuration:")
                doc_parts.extend(physics_params[:20])  # Limit to avoid huge docs
            
            # README content (if available)
            if 'readme_content' in case_meta:
                doc_parts.append(case_meta['readme_content'][:500])
            
            document = '\n'.join(doc_parts)
            
            documents.append(document)
            metadata.append({
                'case_name': case_name,
                'repo_path': repo_path,  # Amendment B: Portable
                'inputs_content': inputs_content,  # Amendment C: Complete
                'index_type': 'physics_parameters'
            })
        
        self._save_index(documents, metadata, 'physics_parameters', output_dir)
    
    def _build_grid_specifications(self, case_metadata: List[Dict], output_dir: Path):
        """
        Build grid_specifications index (20% weight).
        
        Includes:
        - amr.n_cell
        - amr.max_level
        - amr.ref_ratio
        - geometry.* parameters
        """
        documents = []
        metadata = []
        
        for case_meta in case_metadata:
            inputs_content = case_meta.get('inputs_content', {})
            
            # Extract grid parameters
            grid_params = {}
            for key, value in inputs_content.items():
                keywords = self._get_keywords(
                    "grid_specifications",
                    fallback_keys=["grid_configurations"]
                )
                if keywords and any(kw in key.lower() for kw in keywords):
                    grid_params[key] = value
            
            # Create document
            doc_parts = [
                f"Case: {case_meta.get('case_name', 'Unknown')}",
                f"Path: {case_meta.get('repo_path', '')}",
            ]
            
            # Grid summary
            if 'n_cell' in case_meta or 'amr.n_cell' in inputs_content:
                n_cell = case_meta.get('n_cell') or inputs_content.get('amr.n_cell')
                doc_parts.append(f"Grid: {n_cell}")
            
            if 'max_level' in case_meta or 'amr.max_level' in inputs_content:
                max_level = case_meta.get('max_level') or inputs_content.get('amr.max_level')
                doc_parts.append(f"Max Level: {max_level}")
            
            # All grid params
            for key, value in grid_params.items():
                doc_parts.append(f"{key} = {value}")
            
            documents.append('\n'.join(doc_parts))
            metadata.append({
                'case_name': case_meta.get('case_name'),
                'repo_path': case_meta.get('repo_path'),
                'inputs_content': inputs_content,  # Amendment C: Complete
                'grid_params': grid_params,
                'index_type': 'grid_specifications'
            })
        
        self._save_index(documents, metadata, 'grid_specifications', output_dir)
    
    def _build_path_hierarchy(self, case_metadata: List[Dict], output_dir: Path):
        """
        Build path_hierarchy index (15% weight).
        
        Uses repo_path (Amendment B - portable identifiers).
        """
        documents = []
        metadata = []
        
        for case_meta in case_metadata:
            repo_path = case_meta.get('repo_path', '')
            case_name = case_meta.get('case_name', '')
            inputs_content = case_meta.get('inputs_content', {})

            # Tokenize path components for better matching
            path_parts = repo_path.split('/')
            tokenized_parts = [tokenize(part) for part in path_parts]

            doc = f"Case: {case_name}\n"
            doc += f"Path: {repo_path}\n"
            doc += f"Tokenized: {' '.join(tokenized_parts)}\n"
            doc += f"Hierarchy: {' > '.join(path_parts)}"

            documents.append(doc)
            metadata.append({
                'case_name': case_name,
                'repo_path': repo_path,  # Portable!
                'inputs_content': inputs_content,  # Amendment C: Complete
                'path_components': path_parts,
                'index_type': 'path_hierarchy'
            })
        
        self._save_index(documents, metadata, 'path_hierarchy', output_dir)
    

    def _build_domain_models(self, case_metadata: List[Dict], output_dir: Path):
        """Build domain_models index (10% weight)."""
        documents = []
        metadata = []
        
        for case_meta in case_metadata:
            inputs_content = case_meta.get('inputs_content', {})
            
            # Extract chemistry parameters
            chem_params = {}
            for key, value in inputs_content.items():
                keywords = self._get_keywords(
                    "domain_models",
                    fallback_keys=["chemistry_mechanisms"]
                )
                if keywords and any(kw in key.lower() for kw in keywords):
                    chem_params[key] = value

            doc = f"Case: {case_meta.get('case_name')}\n"
            doc += f"Path: {case_meta.get('repo_path')}\n"
            
            for key, value in chem_params.items():
                doc += f"{key} = {value}\n"
            
            documents.append(doc)
            metadata.append({
                'case_name': case_meta.get('case_name'),
                'repo_path': case_meta.get('repo_path'),
                'inputs_content': inputs_content,  # Amendment C: Complete
                'chemistry_params': chem_params,
                'index_type': 'domain_models'
            })

        self._save_index(documents, metadata, 'domain_models', output_dir)
    
    def _build_resource_requirements(self, case_metadata: List[Dict], output_dir: Path):
        """Build resource_requirements index (5% weight) - stub for now."""
        documents = []
        metadata = []

        for case_meta in case_metadata:
            inputs_content = case_meta.get('inputs_content', {})
            doc = f"Case: {case_meta.get('case_name')}\nPath: {case_meta.get('repo_path')}"
            documents.append(doc)
            metadata.append({
                'case_name': case_meta.get('case_name'),
                'repo_path': case_meta.get('repo_path'),
                'inputs_content': inputs_content,  # Amendment C: Complete
                'index_type': 'resource_requirements'
            })

        self._save_index(documents, metadata, 'resource_requirements', output_dir)
    

    def _build_additional_indices(self, case_metadata: List[Dict], output_dir: Path):
        """
        Build additional indices from config.additional_level2_indices.
        
        Allows configs to define domain-specific indices beyond the base 7.
        Uses same keyword filtering pattern as base indices.
        
        Example config:
            additional_level2_indices = {
                'diagnostic_outputs': {
                    'weight': 0.05,
                    'keywords': ['diag', 'output', 'plot'],
                }
            }
        """
        additional = getattr(self.config, 'additional_level2_indices', {})
        
        if not additional:
            return  # No additional indices defined
        
        for index_name, index_config in additional.items():
            keywords = index_config.get('keywords', [])
            
            documents = []
            metadata = []
            
            for case_meta in case_metadata:
                inputs_content = case_meta.get('inputs_content', {})
                case_name = case_meta.get('case_name', 'Unknown')
                repo_path = case_meta.get('repo_path', '')
                
                # Filter by keywords (same logic as base indices)
                if keywords:
                    relevant_params = {
                        k: v for k, v in inputs_content.items()
                        if any(kw in k.lower() for kw in keywords)
                    }
                else:
                    relevant_params = inputs_content
                
                if not relevant_params:
                    continue  # Skip if no matching parameters
                
                # Build document
                doc = f"Case: {case_name}\n"
                doc += f"Path: {repo_path}\n"
                doc += f"Index: {index_name}\n"
                
                for key, value in list(relevant_params.items())[:20]:
                    doc += f"{key} = {value}\n"
                
                documents.append(doc)
                metadata.append({
                    'case_name': case_name,
                    'repo_path': repo_path,
                    'index_type': index_name,
                    'inputs_content': inputs_content,
                })
            
            # Save this additional index
            if documents:
                self._save_index(documents, metadata, index_name, output_dir)

    def _save_index(self, documents: List[str], metadata: List[Dict],
                    index_name: str, output_dir: Path):
        """Save FAISS index and metadata."""
        if not documents:
            logger.warning(f"  [WARN]  No documents for {index_name}")
            return
        
        # Embed documents
        embeddings = self.embedder.embed_texts(documents)
        embeddings_array = np.array(embeddings).astype('float32')
        
        # Create FAISS index
        dimension = embeddings_array.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_array)
        
        # Create filenames
        code_lower = self.code_name.lower()
        index_filename = f"{code_lower}_case_{index_name}.faiss"
        metadata_filename = f"{code_lower}_case_{index_name}_metadata.json"
        
        # Save
        faiss.write_index(index, str(output_dir / index_filename))
        (output_dir / metadata_filename).write_text(
            json.dumps(metadata, indent=2)
        )
        
        logger.info(f"  [PASS] {index_name}: {len(documents)} cases indexed")

    def _build_development_activity(self, case_metadata: List[Dict], output_dir: Path):
        """Build development_activity index (10% weight)."""
        documents = []
        metadata = []

        for case_meta in case_metadata:
            case_name = case_meta.get('case_name', 'Unknown')
            repo_path = case_meta.get('repo_path', '')
            inputs_content = case_meta.get('inputs_content', {})

            doc = f"Case: {case_name}\n"
            doc += f"Path: {repo_path}\n"
            doc += "Development Activity: Active"

            documents.append(doc)
            metadata.append({
                'case_name': case_name,
                'repo_path': repo_path,
                'inputs_content': inputs_content,  # Amendment C: Complete
                'index_type': 'development_activity'
            })

        self._save_index(documents, metadata, 'development_activity', output_dir)
    
    def _build_configuration_complexity(self, case_metadata: List[Dict], output_dir: Path):
        """Build configuration_complexity index (10% weight)."""
        documents = []
        metadata = []
        
        for case_meta in case_metadata:
            inputs_content = case_meta.get('inputs_content', {})
            case_name = case_meta.get('case_name', 'Unknown')
            repo_path = case_meta.get('repo_path', '')
            
            param_count = len(inputs_content)
            complexity_score = min(param_count / 50.0, 1.0)
            
            doc = f"Case: {case_name}\n"
            doc += f"Path: {repo_path}\n"
            doc += f"Parameters: {param_count}\n"
            doc += f"Complexity Score: {complexity_score:.2f}\n"
            
            for j, (key, value) in enumerate(list(inputs_content.items())[:10]):
                doc += f"{key} = {value}\n"
            
            documents.append(doc)
            metadata.append({
                'case_name': case_name,
                'repo_path': repo_path,
                'inputs_content': inputs_content,  # Amendment C: Complete
                'param_count': param_count,
                'complexity_score': complexity_score,
                'index_type': 'configuration_complexity'
            })

        self._save_index(documents, metadata, 'configuration_complexity', output_dir)
