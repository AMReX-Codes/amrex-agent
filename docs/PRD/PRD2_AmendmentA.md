# **AMENDMENT A: Architecture & Goals Clarification**

**Document Version:** 2.1  
**Amendment Date:** December 2024  
**Reason for Amendment:** Clarifications based on existing implementation review and stakeholder feedback  
**Sections Affected:** 11.2 (Node Functions), 10.1 (Scoring System), 1.3 (Project Goals)

---

## **A.1 Workflow Architecture Corrections**

### **A.1.1 Complete 8-Node Workflow**

The system implements **8 nodes** (not 5 as initially documented):

**Pre-Execution Nodes:**
1. **Solver Selector Node** (NEW) - Level 0 retrieval, explicit solver family selection
2. **Architect Node** - Level 1-2 retrieval + LLM planning
3. **Reviewer Node** - Pre-execution validation with retry loop

**Execution Nodes:**
4. **Input Writer Node** - Generate run directory
5. **Runner Node** - Execute simulation (local/SLURM)

**Post-Execution Nodes:**
6. **Analysis Node** - Extract quantities of interest from run logs
7. **Visualization Node** - Generate plots (YT, fextract, matplotlib)
8. **Paper Validator Node** (NEW) - Multi-mode validation (see A.2)

**Rationale for Separation:**
- **Solver Selector** extracted from Architect to make Level 0 explicit and testable independently
- **Paper Validator** added to support FOAM benchmark validation and paper reproduction workflows
- **Post-execution nodes** (Analysis, Visualization) are critical for end-to-end automation, not just setup

---

## **A.2 Paper Validator Node: Multi-Mode Architecture**

### **A.2.1 Dual Operating Modes**

The Paper Validator operates in two distinct modes depending on workflow entry point:

**Mode 1: Extraction (Pre-Run)**
- **Trigger:** Entry Point B (paper reproduction workflow)
- **Input:** arXiv hash, PDF file, TeX directory, or text description + plot image
- **Process:** 
  - Download/parse paper using existing Python scripts (arXiv API, pypdf, OpenCV)
  - Extract simulation parameters (grid size, BCs, solver hints, chemistry mechanism)
  - Extract reference plots/figures for post-run comparison
  - Parse tables for quantitative data (Re, Ma, domain dimensions)
- **Output:** Structured `extracted_params` dict → feeds to Solver Selector as query context
- **Implementation:** Leverages user's existing paper extraction codebase

**Mode 2: Validation (Post-Run)**
- **Trigger:** After Visualization Node completes (if validation_mode=True)
- **Input:** Generated plots, reference plots (from Mode 1 or test oracle), simulation metadata
- **Process:**
  - SSIM (Structural Similarity Index) comparison of generated vs. reference plots
  - Physics consistency checks (flame speed, Reynolds number, grid resolution)
  - Quantitative metric extraction and comparison
- **Output:** `ValidationReport` with match scores, discrepancy analysis

**Conditional Execution:**
```python
if state.get("paper_mode") == "extract":
    # Mode 1: Pre-run extraction
    state = extract_paper_parameters(state)
elif state.get("paper_mode") == "validate":
    # Mode 2: Post-run validation
    state = validate_against_paper(state)
else:
    # Pass-through (not in paper reproduction mode)
    return state
```

### **A.2.2 Dual Entry Points**

**Entry Point A: Natural Language Query** (Original workflow)
- User provides text prompt describing simulation goal
- Flow: Solver Selector → Architect → ... → Visualization → END
- Paper Validator skipped (pass-through)

**Entry Point B: Paper Reproduction** (NEW workflow)
- User provides paper reference (arXiv/PDF/TeX/plot)
- Flow: Paper Validator (Mode 1) → [extracted params become query] → Solver Selector → ... → Visualization → Paper Validator (Mode 2) → END with validation report
- Enables FOAM benchmark testing and reproducibility studies

---

## **A.3 Scoring System Corrections**

### **A.3.1 Current Implementation: 5 Buckets (Not 4)**

The existing baseline uses **5 equally-weighted buckets** (20% each):

1. **Git Metrics (20%)** - Age, commit count, contributors, last modification
2. **Path Heuristics (20%)** - Production > RegTests > Custom directory scoring
3. **Domain Matching (20%)** - Chemistry, flow regimes, multi-physics, boundary conditions
4. **Vector Embeddings (20%)** - Nomic embeddings, semantic similarity
5. **Knowledge Reports (20%)** - ⭐ **LLM prompt enhancement from 40 research papers**

**Knowledge Reports Bucket Details:**
- Extracts heuristics from ~40 papers referenced on AMReX-Combustion page
- Creates structured reports covering:
  - Problem sizes and grid recommendations
  - Input file parameter patterns
  - Simulation setup decision frameworks
- Used to enhance LLM prompts in Architect planning phase
- **Key Observation:** When this was the only scoring mechanism, accuracy was higher than current 5-bucket average
- **Implication:** This motivates the test-driven rebuild to understand *why* it worked better alone

**Current Formula:**
```
Score = 0.2×Git + 0.2×Path + 0.2×Domain + 0.2×Vector + 0.2×Knowledge
```

### **A.3.2 Proposed System: 82-Index RAG**

The multi-index RAG system **replaces** the 5-bucket approach with hierarchical retrieval:

- **Level 0 (4 indices):** Solver selection - includes evolved version of knowledge reports as `cross_cutting_guidance` (10% weight)
- **Level 1 (21 indices):** Documentation context - includes `parameter_guides` (25% weight) derived from knowledge reports
- **Level 2 (57 indices):** Case metadata - includes `physics_descriptors` (35% weight) incorporating domain heuristics

**Migration Path:**
- Knowledge reports content distributed across all 3 levels
- Git metrics enhanced with richer history analysis (Level 2, 15% weight)
- Path heuristics refined into `path_hierarchy` index (Level 2, 15% weight)
- Domain matching decomposed into `physics_descriptors` + `chemistry_mechanisms` (Level 2, 35% + 10%)
- Vector embeddings upgraded to CBORG physics-aware models (all levels)

---

## **A.4 Project Goals Clarification**

### **A.4.1 Scope: End-to-End Workflow Automation**

**Original (Incomplete) Goal Statement:**
> "Automate simulation setup for Pele suite using RAG-based case selection"

**Revised Goal Statement:**
> "Automate the complete simulation workflow—from natural language query or paper reproduction through setup, execution, analysis, and validation—achieving ≥90% accuracy against expert ground truth"

**What Changed:**
- **Expanded scope:** Setup → Setup + Run + Analyze + Visualize + Validate
- **Added paper reproduction:** Not just user queries, but also reproduce published results
- **Explicit validation:** FOAM benchmark comparison, plot SSIM metrics, test oracle accuracy

### **A.4.2 FOAM Benchmark Implications**

**Original Assumption:** FOAM benchmark validation = retrieve similar case, compare metadata

**Corrected Understanding:** FOAM benchmark validation requires:
1. Actually running the simulation (Runner Node)
2. Generating plots (Visualization Node)
3. Comparing plots to reference figures (Paper Validator Mode 2)
4. SSIM scores ≥0.75 for 3 validation cases (Gate 5)

**Impact on Timeline:**
- Gate 5 now includes simulation execution time (not just retrieval)
- Requires access to compute resources (NERSC Perlmutter) by Week 5
- Plot comparison tools (SSIM, OpenCV) must be integrated by Week 4

### **A.4.3 Test-Driven Rebuild Philosophy**

**Context:** This is a **rewrite/refinement** of existing code, not greenfield development.

**Current Baseline Performance:**
- 5-bucket scoring: **40% accuracy** on informal test cases
- Observation: Knowledge Reports bucket alone performed better than combined 5-bucket system
- Hypothesis: Weighted combination dilutes the signal from best-performing components

**Rebuild Objectives:**
1. **Systematic decomposition:** Break 5 buckets into 82 granular, testable indices
2. **Ablation-driven design:** Quantify each index's contribution (Gates 2-6)
3. **Test oracle validation:** 20 expert-curated cases provide objective accuracy metric
4. **Preserve what works:** Knowledge reports content distributed across all levels, not discarded

**Key Insight Driving TDD Approach:**
> "When Knowledge Reports was the only scoring mechanism, it seemed to work better. This suggests we don't understand which metadata signals actually matter. Ablation study will reveal the truth."

**Integrated Testing Motivation:**
- CI/CD pytest suite for each of 82 indices (unit tests)
- Integration tests for 3-level pipeline (e2e tests)
- Weekly oracle runs (regression tests)
- Prevents dilution of high-signal components by low-signal noise

---

## **A.5 Updated Success Criteria**

### **A.5.1 Gate Adjustments**

**Gate 2 (Week 2):** Add Paper Validator Mode 1 test
- Success: Extract parameters from 3 sample papers (arXiv API + PDF parsing)
- Criteria: ≥80% parameter extraction accuracy (grid, BCs, chemistry)

**Gate 4 (Week 4):** Clarify FOAM benchmark scope
- Success: Run 3 FOAM benchmark cases end-to-end (not just retrieve)
- Criteria: SSIM ≥0.75 for generated vs. reference plots

**Gate 5 (Week 5):** Add post-run validation
- Success: 18/20 test oracle cases correct + 15/20 produce valid plots
- Criteria: Combined setup accuracy (90%) + execution success rate (75%)

### **A.5.2 Metrics Dashboard Additions**

**New Metrics to Track:**

| Metric | Target | Rationale |
|--------|--------|-----------|
| **End-to-End Success Rate** | ≥75% | % of queries that run to completion without errors |
| **Plot Generation Rate** | ≥80% | % of successful runs that produce valid visualizations |
| **SSIM Score (FOAM)** | ≥0.75 | Structural similarity to published figures |
| **Parameter Extraction Accuracy** | ≥85% | % of paper params correctly extracted (Mode 1) |
| **Ablation Index Contribution** | Quantified | Per-index accuracy delta (for production config decision) |

---

## **A.6 Implementation Notes**

### **A.6.1 Backward Compatibility**

**Existing Code Preservation:**
- Current 5-bucket scoring remains functional during rebuild (fallback mode)
- Paper extraction scripts integrated as-is (no rewrite required)
- YT/fextract visualization tools already implemented (Visualization Node)

### **A.6.2 Incremental Migration**

**Week 1-2:** Both systems run in parallel
- 5-bucket baseline continues producing results
- 82-index system scores same queries
- Comparative logging for ablation analysis

**Week 3-4:** Feature flag toggle
- Default switches to 82-index system
- 5-bucket accessible via `--legacy-scoring` CLI flag

**Week 5-6:** Legacy deprecation
- 5-bucket system archived (code retained for reference)
- All tests migrate to 82-index baseline

---

## **A.7 Document Control**

**Changes Summary:**
- Section 11.2: Added Solver Selector Node (11.2.1a), Paper Validator Node (11.2.5a)
- Section 10.1: Corrected to 5-bucket current system, clarified Knowledge Reports role
- Section 1.3: Expanded goals to include end-to-end workflow + paper reproduction
- Section 14: Updated Gate 2, 4, 5 success criteria

**Affected Diagrams:**
- Figure 3 (Workflow): Update to show 8 nodes with dual entry points
- Figure 5 (Scoring): Update to show 5-bucket → 82-index migration
- Figure 8 (Gates): Update Gate 2, 4, 5 deliverables

**Supersedes:** Sections 11.2.1 (partial), 10.1 (complete), 1.3 (partial) in Document Version 2.0

**Approved By:** [Stakeholder signatures]

**Effective Date:** Upon final review approval

---

**END OF AMENDMENT A**

---
