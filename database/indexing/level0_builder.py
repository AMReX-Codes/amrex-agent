"""
Level 0 Index Builder - Multi-Solver Physics Router

Builds 4 weighted sub-indices:
1. physics_regimes (40%) - Domain families (combustion, astrophysics, etc.)
2. solver_capabilities (30%) - Specific capabilities per code
3. code_lineage (20%) - Evolution history and legacy names
4. cross_cutting_guidance (10%) - Decision frameworks from reports


PRD: Section 5.2 (FR-1, FR-2) and Section 10.1

Solvers referenced for generalization: PeleC, PeleLMeX, ERF, WarpX, incflo.
"""

import json
from pathlib import Path
import logging
from typing import Dict, List, Any, Optional
import faiss
import numpy as np

from database.configs import discover_code_configs


logger = logging.getLogger(__name__)

class Level0Builder:
    """Builds Level 0 multi-solver routing indices."""
    
    def __init__(self, embedder, knowledge_base_path: Optional[Path] = None):
        """
        Initialize Level 0 builder.

        Args:
            embedder: EmbeddingService instance with embeddings attribute
            knowledge_base_path: Path to knowledge base reports (optional)
        """
        self.embedder = embedder
        self.knowledge_base_path = knowledge_base_path or Path("knowledge_base")
        
        # Discover available codes
        self.configs = discover_code_configs()
        
    def build(self, output_dir: Path):
        """
        Build all 4 Level 0 sub-indices.
        
        Args:
            output_dir: Directory to save indices
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Building Level 0 indices for {len(self.configs)} codes...")
        
        # Build each sub-index
        self._build_physics_regimes(output_dir)
        self._build_solver_capabilities(output_dir)
        self._build_code_lineage(output_dir)
        self._build_cross_cutting_guidance(output_dir)
        
        logger.info(f"[PASS] Level 0 indices built in {output_dir}")
    
    def _build_physics_regimes(self, output_dir: Path):
        """
        Build physics_regimes index (40% weight).
        
        Maps high-level physics families to codes:
        - Combustion → PeleC, PeleLMeX
        - Astrophysics → Castro, Nyx
        - Plasma → WarpX
        """
        documents = []
        metadata = []
        
        # Define physics families
        physics_families = {
            'Combustion': {
                'codes': ['PeleC', 'PeleLMeX'],
                'description': 'Reacting flows, flames, detonations, chemical kinetics'
            },
            'Compressible Flow': {
                'codes': ['PeleC', 'Castro'],
                'description': 'Supersonic flows, shocks, high Mach number, compressibility effects'
            },
            'Low Mach Flow': {
                'codes': ['PeleLMeX', 'incflo'],
                'description': 'Low speed flows, incompressible limit, detailed chemistry'
            },
            'Astrophysics': {
                'codes': ['Castro', 'Nyx'],
                'description': 'Stellar dynamics, cosmology, gravity, radiation hydrodynamics'
            },
            'Plasma Physics': {
                'codes': ['WarpX'],
                'description': 'Particle beams, electromagnetic fields, accelerators'
            },
            'Atmospheric Modeling': {
                'codes': ['ERF'],
                'description': 'Weather, climate, mesoscale dynamics'
            },
        }
        
        for family, info in physics_families.items():
            for code in info['codes']:
                # Check if code exists in our registry
                if any(cfg.code_name == code for cfg in self.configs):
                    # Include code name in document for better matching when code is mentioned
                    doc = f"{code} - {family}: {info['description']}"
                    documents.append(doc)
                    metadata.append({
                        'code_name': code,
                        'physics_family': family,
                        'description': info['description']
                    })
        
        # Embed and save
        self._save_index(
            documents, metadata, 
            output_dir / "physics_regimes",
            index_type='physics_regimes'
        )
    
    def _build_solver_capabilities(self, output_dir: Path):
        """
        Build solver_capabilities index (30% weight).
        
        Uses code descriptions and specific capabilities.
        """
        documents = []
        metadata = []
        
        for config in self.configs:
            # Main description
            if hasattr(config, 'description'):
                doc = f"{config.code_name}: {config.description}"
                documents.append(doc)
                metadata.append({
                    'code_name': config.code_name,
                    'capability_type': 'description'
                })
            
            # Add specific capabilities if available
            capabilities = self._extract_capabilities(config)
            for capability in capabilities:
                doc = f"{config.code_name}: {capability}"
                documents.append(doc)
                metadata.append({
                    'code_name': config.code_name,
                    'capability': capability,
                    'capability_type': 'specific'
                })
        
        self._save_index(
            documents, metadata,
            output_dir / "solver_capabilities",
            index_type='solver_capabilities'
        )
    
    def _build_code_lineage(self, output_dir: Path):
        """
        Build code_lineage index (20% weight).
        
        Captures evolution history and legacy names.
        """
        documents = []
        metadata = []
        
        # Define lineage relationships
        lineage_info = {
            'PeleLMeX': {
                'evolved_from': 'PeleLM',
                'description': 'PeleLMeX is the modernized version of PeleLM with improved numerics'
            },
            'PeleC': {
                'related': ['CNS', 'Combustion'],
                'description': 'PeleC evolved from CNS (Compressible Navier-Stokes)'
            },
            'Castro': {
                'related': ['Astrophysics'],
                'description': 'Castro is the AMReX astrophysics hydrodynamics code'
            },
        }
        
        for code, info in lineage_info.items():
            if any(cfg.code_name == code for cfg in self.configs):
                doc = f"{code} lineage: {info['description']}"
                documents.append(doc)
                metadata.append({
                    'code_name': code,
                    'lineage_info': info
                })
        
        self._save_index(
            documents, metadata,
            output_dir / "code_lineage",
            index_type='code_lineage'
        )
    
    def _build_cross_cutting_guidance(self, output_dir: Path):
        """
        Build cross_cutting_guidance index (10% weight).
        
        Extracts decision frameworks from knowledge base reports.
        """
        documents = []
        metadata = []
        
        # Look for decision framework reports
        if self.knowledge_base_path.exists():
            for report_file in self.knowledge_base_path.glob("report_*_solver*.md"):
                content = report_file.read_text()
                
                # Extract sections (simple chunking)
                sections = content.split('\n## ')
                for section in sections[1:]:  # Skip header
                    lines = section.split('\n')
                    title = lines[0]
                    body = '\n'.join(lines[1:])
                    
                    if 'when to use' in title.lower() or 'selection' in title.lower():
                        documents.append(f"{title}: {body[:500]}")
                        metadata.append({
                            'source': report_file.name,
                            'section': title,
                            'guidance_type': 'decision_framework'
                        })
        
        # Add default guidance if no reports found
        if not documents:
            documents.append("Default guidance: Use PeleC for compressible flows, PeleLMeX for low Mach")
            metadata.append({'guidance_type': 'default'})
        
        self._save_index(
            documents, metadata,
            output_dir / "cross_cutting_guidance",
            index_type='cross_cutting_guidance'
        )
    
    def _extract_capabilities(self, config) -> List[str]:
        """Extract specific capabilities from config."""
        capabilities = []
        
        # Capability mapping based on code name
        capability_map = {
            'PeleC': [
                'handles strong shocks',
                'compressible reacting flow',
                'supersonic combustion',
                'detonation physics'
            ],
            'PeleLMeX': [
                'low Mach number formulation',
                'detailed chemical kinetics',
                'flame dynamics',
                'diffusion-dominated physics'
            ],
            'WarpX': [
                'particle-in-cell method',
                'electromagnetic field solver',
                'plasma accelerators',
                'beam dynamics'
            ],
            'ERF': [
                'atmospheric dynamics',
                'mesoscale modeling',
                'terrain-following coordinates',
                # Hard-coded common ERF test cases for better routing
                'buoyancy-driven flows',
                'rising bubble simulations',
                'atmospheric boundary layer'
            ],
        }
        
        return capability_map.get(config.code_name, [])
    
    def _save_index(self, documents: List[str], metadata: List[Dict], 
                    output_path: Path, index_type: str):
        """Save FAISS index and metadata."""
        if not documents:
            logger.warning(f"[WARN]  No documents for {index_type}")
            return

        if hasattr(self.embedder, "expand_documents"):
            documents, metadata = self.embedder.expand_documents(documents, metadata)
        
        # Embed documents
        embeddings = self.embedder.embed_texts(documents)
        embeddings_array = np.array(embeddings).astype('float32')
        
        # Create FAISS index
        dimension = embeddings_array.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings_array)
        
        # Save index
        faiss.write_index(index, str(output_path) + ".faiss")
        
        # Save metadata
        metadata_file = output_path.parent / f"{output_path.name}_metadata.json"
        metadata_file.write_text(json.dumps(metadata, indent=2))
        
        logger.info(f"  [PASS] {index_type}: {len(documents)} documents indexed")
    
    def _get_solver_list(self) -> List[str]:
        """Get list of solvers being indexed."""
        return [cfg.code_name for cfg in self.configs]
    
    def _validate_solver_name(self, name: str) -> bool:
        """Validate solver name against registry."""
        valid_names = {cfg.code_name for cfg in self.configs}
        return name in valid_names
