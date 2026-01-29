---

# **AMReXAgent: Product & Technical Specification**
## **Unified Document - Phase 1 (Revised)**

**Document Version:** 2.0  
**Date:** December 2025
**Status:** Draft for Review  
**Target Audience:** Stakeholders, Domain Scientists, Development Team, Technical Reviewers

---

# **PART 1: PRODUCT REQUIREMENTS**

---

## **1. Executive Summary**

### **1.1 Vision**

AMReXAgent is a test-driven research software system that automates the setup of AMReX-based combustion simulations from natural language descriptions. The system tests the core hypothesis that **well-structured documentation combined with multi-index retrieval-augmented generation (RAG)** can serve as the primary decision mechanism for simulation configuration, replacing manual expertise and ad-hoc heuristics with a reproducible, validated workflow.

### **1.2 Research Question**

**Can hierarchical FAISS retrieval across documentation, metadata, and code artifacts achieve ≥90% accuracy in baseline case selection when validated against expert ground truth?**

This question extends the FOAM-agent research paradigm to the AMReX ecosystem, which presents unique challenges:
- **Multi-solver environment**: Specialized solvers for different physics regimes (compressible vs low-Mach combustion, multiphase flows) vs single-framework approaches
- **Code lineage complexity**: Solvers evolved from common ancestors and share design patterns across the broader AMReX ecosystem
- **Sparse documentation**: 40% of example cases lack READMEs, metadata scattered across 40+ research papers
- **Physics diversity**: Compressible combustion, low-Mach flames, multiphase sprays—each requiring domain-specific knowledge

The architecture is designed to be **extensible to other AMReX applications** beyond the initial Pele focus, enabling future work on atmospheric, astrophysical, plasma, and other physics domains.

### **1.3 Core Value Proposition**

**For Domain Scientists (Non-Expert Users):**
- Describe simulations in natural language, receive validated configurations
- Eliminate 80% of setup time (4-8 hours → <30 minutes)
- Avoid 30-50% failure rate on initial simulation attempts
- Learn correct practices through transparent explanations

**For CFD Experts (Code-Aware Users):**
- Rapid prototyping with agent-validated baseline selection
- Automated error detection before expensive HPC queue time
- Reproducible configuration decisions (same query → same result)
- Cross-solver knowledge transfer within and beyond Pele suite

**For Research Computing Facilities:**
- Quantifiable validation metrics (≥90% baseline accuracy vs expert oracle)
- Reduced failed jobs (90% error detection pre-execution)
- Lower support burden (self-service simulation setup)
- Competitive performance vs established tools (≥60% match/exceed FOAM-agent on shared benchmarks)

### **1.4 Strategic Context: Plan A**

This document defines **Plan A**: a modular, test-driven approach focused on core capability validation over 6-7 weeks (Gates 0-6). The plan:

**Explicitly Includes:**
- ✅ Multi-index RAG with ablation testing (82 indices in testing mode)
- ✅ Physics taxonomy with code lineage (captures evolution relationships)
- ✅ Document retrieval service (for FOAM-agent benchmark validation)
- ✅ Test oracle methodology (expert-curated ground truth)
- ✅ Comparative benchmarking (vs FOAM-agent on shared prompts)

**Explicitly Defers to Phase 2:**
- ❌ Simulation execution and monitoring (user runs manually)
- ❌ Advanced visualization (post-processing done separately)
- ❌ Containerization (deploy native first)
- ❌ MCP server integration (no immediate stakeholder need)
- ❌ Multi-user deployment (single-user validation first)
- ❌ Reactor design capability (complex domain reasoning)

**Key Principle:** Ship a working, validated Phase 1 system that proves the research hypothesis rather than half-built everything.

### **1.5 Success Definition**

**Phase 1 is complete when:**

1. **Baseline Selection Accuracy ≥90%** (primary metric)
   - Test oracle: 20 expert-curated cases covering Pele suite
   - Measurement: Top-1 case matches expert selection
   - Pass criteria: 18/20 correct (90%)

2. **Multi-Index Ablation Complete** (research contribution)
   - Test all 82 sub-indices in isolation
   - Identify high-contribution indices (≥5% accuracy gain)
   - Decision tree for production index merging

3. **FOAM-Agent Competitive Performance ≥60%** (validation)
   - 20 benchmark prompts from FOAM-agent paper/appendix
   - Measurement: Pele matches or exceeds FOAM on ≥12/20 prompts
   - Demonstrates approach generalizes beyond Pele

4. **Error Prevention ≥90%** (robustness)
   - Reviewer catches 90% of synthetic errors pre-execution
   - Missing parameters, syntax errors, physics inconsistencies
   - Prevents wasted HPC resources

5. **Test Coverage ≥85%** (code quality)
   - All core components tested (config, FAISS, architect, reviewer, workflow)
   - Integration tests for end-to-end flow
   - Regression tests for test oracle cases

6. **Production Deployment Ready** (deliverable)
   - CLI tool operational on NERSC Perlmutter
   - User documentation complete (quick start, troubleshooting)
   - Initial user cohort identified (3-5 researchers)
   - Ablation results inform production index configuration

---

## **2. Problem Statement**

### **2.1 The Simulation Setup Challenge**

**Problem Context:**  
The Pele software suite (PeleC, PeleLMeX, PeleMP) provides powerful tools for high-fidelity combustion modeling built on the AMReX adaptive mesh refinement framework. However, their sophistication creates a significant barrier to entry:

- **Parameter Space Complexity:** Each code has 100+ configuration parameters across multiple input files (inputs, GNUmakefile, chemistry mechanisms)
- **Scattered Examples:** 45+ example cases per code, each with 2-5 input file variants, stored in different repository structures
- **Fragmented Knowledge:** Best practices distributed across 40+ research papers, mailing list archives, and undocumented expert knowledge
- **Multi-Solver Ambiguity:** Similar physics can be simulated in different Pele codes—choosing the wrong solver wastes weeks

The architecture is designed to handle this complexity while remaining **extensible to other AMReX-based applications** with similar challenges.

**Current Workflow (Manual Setup):**
```
1. User reads overview docs (1-2 hours)
2. User searches through 45+ example cases (2-4 hours)
3. User selects a "similar" case (often wrong choice)
4. User modifies inputs file (1-2 hours, many errors)
5. User attempts compilation (30 min - 2 hours of debugging)
6. User submits job to HPC queue (wait time)
7. Job fails due to configuration error (back to step 4)

Total Time: 4-8 hours for non-experts, 30-60 min for experts
Failure Rate: 30-50% for non-experts, 10-20% for experts
```

### **2.2 Specific Pain Points**

**Pain Point 1: Solver Selection Ambiguity**

Example scenario: User wants to simulate "turbulent premixed methane combustion"

**Option A: PeleC** (compressible solver)
- Handles all Mach numbers
- Required if shocks or acoustic effects important
- Computationally expensive (small timesteps due to CFL)

**Option B: PeleLMeX** (low-Mach solver)
- Optimized for Ma < 0.3
- Filters acoustic waves → larger timesteps → 10-100× faster
- Cannot capture shocks

**Option C: PeleMP** (multiphase solver)
- For spray/liquid fuel injection
- Overhead of Lagrangian particles

**Current State:** Without domain knowledge, users guess or try multiple solvers sequentially. Wrong choice discovered after 4+ hours of setup. No systematic guidance exists.

**What Agent Must Do:** Disambiguate based on query details (Mach number, presence of shocks, spray vs gas-phase) and explain the physics-based reasoning.

**Pain Point 2: Baseline Case Selection Errors**

Even within correct solver, choosing wrong baseline case:

**Example: PeleC RegTests Directory**
- **PMF** (Premixed Methane Flame): Reacting flow with chemistry
- **TaylorGreen** (TG): Non-reacting turbulence benchmark
- **Sedov**: Shock hydrodynamics (no chemistry)

**Common Error:** User searching for "turbulent combustion" finds TaylorGreen (has "turbulent" in description) but it has **no chemistry**. Entire setup fails to capture intended physics.

**What Agent Must Do:** Match physics requirements (reacting + turbulent) not just keywords, explain why TG is wrong choice despite name similarity.

**Pain Point 3: Missing Metadata**

**Current State of Documentation:**
```
40% of example cases lack README files
60% lack structured metadata (grid size, physics type, chemistry)
80% lack performance estimates (runtime, memory)
100% lack machine-readable configuration specs
```

**Example Impact:** User cannot determine if a case uses drm19 or dodecane mechanism without reading source code or inputs files. No way to filter "all methane combustion cases" programmatically.

**What Agent Must Do:** Extract metadata from existing artifacts (git history, inputs files, code structure) to create searchable index even when README missing.

**Pain Point 4: Parameter Modification Errors**

**Common mistakes when editing inputs files:**

❌ **Missing required parameters**
```
# User's inputs file
amr.max_level = 2
geometry.prob_lo = 0 0 0
geometry.prob_hi = 1 1 1
# Missing: amr.n_cell → cryptic crash at runtime
```

❌ **Invalid syntax**
```
amr.n_cell = 256^3  # Wrong! Should be: 256 256 256
```

❌ **Incompatible physics**
```
eb2.geom_type = sphere          # Embedded boundary geometry
geometry.is_periodic = 1 1 1    # Periodic boundaries
# Impossible: Can't have EB sphere with all-periodic BCs
```

❌ **Wrong file paths**
```
pelec.chem_file = drm19.yaml
# File not in NSL (NERSC Science Library) or local path → crash
```

**Current State:** Users discover these errors only after:
- Compilation succeeds (false confidence)
- Job submitted to queue (wasted queue time)
- Simulation crashes after 5-30 minutes

**What Agent Must Do:** Pre-execution validation catches all these errors, provides actionable fix suggestions, prevents wasted HPC resources.

**Pain Point 5: Knowledge Fragmentation Across Papers**

**Example: Setting up supersonic cavity flameholder**

Required knowledge scattered across:
- **Paper 1:** Grid resolution requirements (140μm base, 35μm AMR)
- **Paper 2:** Riemann solver choice (HLLC for hydrogen)
- **Paper 3:** Turbulence model settings
- **Paper 4:** Performance estimates (18K GPU hours)
- **Paper 5:** Chemistry mechanism selection
- **Mailing list:** Build flags for GPU compilation

**Current State:** User must read 5+ papers, search mailing lists, ask experts. Takes days.

**What Agent Must Do:** Curated reports (e.g., database/reports/report6.txt on job sizing) indexed alongside case READMEs. Agent retrieves relevant context from papers automatically.

### **2.3 Research Objects**

The agent must correctly identify **three research objects** from natural language:

**1. Physics Regime / Solver** (Level 0)
- Which family of physics? (compressible combustion, low-Mach combustion, multiphase)
- Which specific solver? (PeleC, PeleLMeX, PeleMP, or other AMReX applications in future)
- Why this choice? (explainable physics-based reasoning)

**2. Baseline Case** (Level 1-2)
- Which example case serves as starting point? (e.g., `PeleC/Exec/RegTests/PMF`)
- Which inputs file variant? (`inputs.2d` vs `inputs.3d` vs `inputs.regression`)
- Why this case? (physics match, not just keyword match)

**3. Configuration Modifications** (Level 2)
- Which parameters to change? (grid size, chemistry mechanism, boundary conditions)
- What values? (validated against physics constraints)
- Which auxiliary files needed? (chemistry .yaml, geometry specs)

### **2.4 User Impact**

**Domain Scientists (Non-Technical):**
- **Time Lost:** 4-8 hours per simulation setup → 30% of research time on configuration instead of science
- **Failure Frustration:** 30-50% of initial attempts fail → discouragement, abandonment of advanced methods
- **Barrier to Entry:** Complexity limits adoption of state-of-the-art combustion codes

**CFD Experts (Code-Aware):**
- **Even Experts Fail:** 10-20% error rate despite years of experience (typos, parameter interactions)
- **Time Waste:** 30-60 minutes per setup could be spent on science
- **Knowledge Loss:** Expert knowledge not captured systematically → reinventing wheel

**Research Computing Facilities:**
- **Wasted Queue Time:** Failed jobs consume allocations, delay other users
- **Support Burden:** 30-40% of support tickets related to configuration errors
- **Onboarding Bottleneck:** New users require weeks of mentoring

**Broader AMReX Community:**
- **Siloed Knowledge:** Best practices exist but not shared across applications
- **Reinvention:** Each new AMReX code rediscovers same configuration patterns
- **Extensibility Gap:** No systematic way to apply lessons from one code to another

---

## **3. Goals & Objectives**

### **3.1 Primary Goals (Phase 1)**

**Goal 1: Validated Multi-Index RAG Architecture**
- **Objective:** Prove hierarchical FAISS retrieval achieves ≥90% accuracy
- **Rationale:** Core research question—is RAG sufficient or do we need heavy heuristics?
- **Success Metric:** 18/20 test oracle cases select correct baseline
- **Research Contribution:** Ablation study quantifies each index type's contribution

**Goal 2: Physics-Based Solver Disambiguation**
- **Objective:** Level 0 (physics taxonomy) correctly selects solver family ≥95% of time
- **Rationale:** Multi-solver environment requires correct physics regime identification first
- **Success Metric:** Top-1 solver correct on 19/20 test cases
- **Extensibility:** Architecture supports adding new AMReX applications without code changes

**Goal 3: Document Retrieval Integration**
- **Objective:** Agent retrieves relevant technical context from curated reports and papers
- **Rationale:** FOAM-agent benchmark requires reproducing published cases
- **Success Metric:** ≥80% of setup decisions cite specific report/paper section
- **Deliverable:** Document retrieval service with arXiv/PDF parsing

**Goal 4: Pre-Execution Error Prevention**
- **Objective:** Reviewer service catches ≥90% of configuration errors before HPC submission
- **Rationale:** Prevent wasted queue time, main user pain point
- **Success Metric:** 90% detection rate on synthetic error injection tests
- **Error Classes:** Missing params, syntax, physics inconsistency, dependency availability

**Goal 5: FOAM-Agent Competitive Validation**
- **Objective:** ≥60% match or exceed FOAM-agent on shared benchmark prompts
- **Rationale:** Validate approach against established baseline in related domain
- **Success Metric:** 12/20 FOAM prompts handled equally well or better
- **Research Insight:** Identify where multi-index approach provides advantages

### **3.2 Secondary Goals (Phase 1)**

**Goal 6: Ablation-Driven Index Optimization**
- **Objective:** Quantify contribution of each index type (82 indices tested)
- **Success Metric:** Identify indices contributing ≥5% accuracy gain
- **Decision Tree:** Use results to determine production index configuration
- **Research Output:** Published ablation study methodology

**Goal 7: Explainable Decisions**
- **Objective:** System explains every selection with per-index score breakdown
- **Success Metric:** 80% of users understand reasoning (user study, 5 researchers)
- **Format:** "Selected PMF because physics_descriptors: 0.95 (methane+drm19), git_metrics: 0.90 (stable, 47 commits)..."

**Goal 8: Extensible Architecture**
- **Objective:** Adding new AMReX application requires only index building, no code changes
- **Success Metric:** Demonstrate adding hypothetical new solver in <1 day
- **Modularity:** Clear separation of physics taxonomy, documentation, case metadata

### **3.3 Explicit Non-Goals (Phase 1)**

**Deferred to Phase 2:**
- ❌ **Simulation Execution:** User runs `mpirun` manually (no runner node yet)
- ❌ **Job Monitoring:** No tracking of running simulations
- ❌ **Advanced Visualization:** User handles post-processing separately
- ❌ **Plot Comparison:** Document retrieval fetches papers but no automated plot similarity (beyond Gate 4/5 validation)
- ❌ **Containerization:** Native deployment first, Docker/Singularity later
- ❌ **MCP Server:** CLI tool only, server deployment in Phase 2
- ❌ **Multi-User:** Single-user validation, concurrent access later
- ❌ **Parameter Sweeps:** One-shot simulation setup only
- ❌ **Active Learning:** No feedback loop from simulation results yet
- ❌ **Reactor Design:** Complex domain reasoning (beyond simple case matching)

**Not Considered for Any Phase:**
- ⛔ **Replacing Expert Judgment:** Agent assists, doesn't replace domain expertise for novel physics
- ⛔ **Modifying Solver Source Code:** Read-only access to repositories
- ⛔ **Guaranteeing Simulation Success:** Validates configuration, not physics correctness
- ⛔ **HPC Job Scheduling:** Interfaces with existing schedulers, doesn't replace them

**Rationale for Deferrals:** Validate core hypothesis (RAG for case selection) before adding execution, visualization, deployment complexity. Phase 1 proves the agent can **find the right case**; Phase 2 proves it can **run it correctly**.

---

---

# **AMReXAgent: Product & Technical Specification**
## **Phase 2: User Stories & Functional Requirements**

---

## **4. User Stories & Use Cases**

### **4.1 Primary User Personas**

**Persona 1: Graduate Student (Domain Expert, CFD Novice)**
- **Name:** Maria, PhD Candidate in Mechanical Engineering
- **Experience:** Strong combustion theory, minimal CFD/HPC experience
- **Goal:** Run DNS of turbulent premixed flame for thesis chapter
- **Pain Point:** Tried to set up PeleC, spent 2 weeks, simulations kept crashing
- **Success Criteria:** Agent gets her to a running simulation in <1 day

**Persona 2: Postdoc (Experienced CFD User, New to Pele)**
- **Name:** David, Postdoc in Energy Science
- **Experience:** 5 years with OpenFOAM, transitioning to Pele for DOE project
- **Goal:** Replicate published spray combustion results with PeleMP
- **Pain Point:** Knows CFD concepts but unfamiliar with Pele conventions, AMReX structure
- **Success Criteria:** Agent leverages his CFD knowledge, explains Pele-specific details

**Persona 3: Staff Scientist (Pele Expert, Time-Constrained)**
- **Name:** Dr. Chen, Computational Scientist at NREL
- **Experience:** 8 years with PeleC/PeleLMeX, expert-level understanding
- **Goal:** Rapid prototyping for industrial collaborator meeting (2 days notice)
- **Pain Point:** Even experts make typos; needs fast validation before HPC submission
- **Success Criteria:** Agent catches configuration errors, saves queue time

**Persona 4: Undergraduate Researcher (Complete Novice)**
- **Name:** Alex, Summer Intern
- **Experience:** Some Python, no HPC or combustion background
- **Goal:** Learn computational combustion by running example simulations
- **Pain Point:** Completely overwhelmed by documentation, doesn't know where to start
- **Success Criteria:** Agent provides gentle guidance, explains each decision

### **4.2 Core Use Cases**

---

#### **Use Case 1: Simple Baseline Selection**

**Actor:** Maria (Graduate Student)

**Preconditions:**
- Maria has NERSC Perlmutter access
- Pele repositories cloned to her workspace
- Agent installed and configured

**Scenario:**
```
1. Maria writes prompt in text file:
   "Simulate premixed methane-air flame with detailed chemistry.
    I need DNS-quality resolution for turbulence study."

2. Maria runs: pele-agent setup --prompt my_prompt.txt

3. Agent workflow:
   - Level 0: Identifies "low-Mach combustion" family
   - Selects PeleLMeX (DNS + premixed → low-Mach optimized)
   - Level 1: Searches PeleLMeX documentation
   - Retrieves report5.txt (parameter guide for DNS)
   - Level 2: Searches case metadata
   - Selects FlameSheet case (turbulent premixed DNS)
   - Modifications: Grid 256³, drm19 mechanism, periodic BCs

4. Agent outputs:
   run_20241201_143052/
   ├── inputs (modified for her requirements)
   ├── drm19.yaml (chemistry mechanism)
   ├── submit.sh (SLURM script for Perlmutter)
   └── README.md (explanation of all decisions)

5. Maria reads README.md:
   "Selected: PeleLMeX/Exec/RegTests/FlameSheet
    
    Reasoning:
    • Solver: PeleLMeX (low-Mach DNS optimized, 10-100× faster than PeleC for Ma<0.3)
    • Case: FlameSheet matches 'turbulent premixed DNS'
    • Physics: drm19 mechanism validated for methane-air
    • Grid: 256³ provides DNS resolution (η ≈ 40μm)
    
    Performance Estimate: ~2K CPU hours on Perlmutter
    Next Steps: cd run_20241201_143052 && sbatch submit.sh"

6. Maria submits job, simulation runs successfully
```

**Postconditions:**
- Valid simulation configuration generated
- Maria understands why each choice was made
- No manual searching through 45+ example cases

**Success Metrics:**
- Total time: <15 minutes (vs 4-8 hours manual)
- First-run success: Yes (vs 30-50% failure rate)
- Learning: Maria now knows FlameSheet is the DNS template for Pele

**Validation Against Test Oracle:**
- Prompt: "premixed methane flame DNS"
- Expected: PeleLMeX/Exec/RegTests/FlameSheet
- Actual: (must match for Gate 2 pass)

---

#### **Use Case 2: Solver Disambiguation**

**Actor:** Maria (same setup as Use Case 1)

**Scenario:**
```
1. Maria's modified prompt:
   "Simulate supersonic hydrogen combustion with shock waves.
    Need to capture detonation physics."

2. Agent workflow:
   - Level 0: Identifies "compressible combustion" family
   - Key terms: "supersonic" (Ma > 1), "shock waves", "detonation"
   - Selects PeleC (only solver handling shocks)
   - Reasoning: "PeleLMeX cannot capture shocks (low-Mach assumption)"
   
3. Agent output README:
   "Selected: PeleC/Exec/Production/CavityFlame
    
    Solver Disambiguation:
    ✓ PeleC: Required for supersonic flows (Ma > 1) with shocks
    ✗ PeleLMeX: Low-Mach formulation filters acoustic waves, cannot capture shocks
    ✗ PeleMP: Multiphase solver, overkill for gas-phase detonation
    
    Physics Match:
    • Compressible Navier-Stokes with detailed chemistry
    • Shock-chemistry interaction physics enabled
    • HLLC Riemann solver for hydrogen (from report5.txt)"
```

**Postconditions:**
- Correct solver selected despite keyword overlap (both prompts said "combustion")
- Physics-based reasoning explained
- Maria learns when to use PeleC vs PeleLMeX

**Success Metrics:**
- Solver accuracy: 100% (PeleC is only valid choice)
- Explanation quality: 80% of users understand reasoning

---

#### **Use Case 3: Error Prevention**

**Actor:** Dr. Chen (Pele Expert)

**Scenario:**
```
1. Dr. Chen modifies agent-generated inputs file manually:
   # Add embedded boundary geometry
   eb2.geom_type = sphere
   eb2.sphere_radius = 0.5
   # (Forgets to disable periodic BCs)

2. Dr. Chen runs: pele-agent validate --inputs inputs

3. Reviewer service detects error:
   "Validation Failed (1 error):
    
    ERROR: Incompatible configuration
      EB geometry (sphere) requires at least one non-periodic direction
      Current: geometry.is_periodic = 1 1 1 (all periodic)
    
    Suggested Fix:
      Change to: geometry.is_periodic = 0 1 1
      (non-periodic in x-direction for EB)"

4. Dr. Chen fixes: geometry.is_periodic = 0 1 1

5. Re-validates: ✓ All checks passed

6. Submits job confidently
```

**Postconditions:**
- Error caught pre-execution (saved 30 min queue wait + restart)
- Even expert prevented from wasting HPC time
- Actionable fix provided

**Success Metrics:**
- Detection rate: 90% of physics inconsistencies caught
- False positive rate: <5% (don't block valid configs)

**Test Oracle Validation:**
- Inject synthetic errors (missing params, syntax, physics conflicts)
- Reviewer must catch ≥90% for Gate 6 pass

---

#### **Use Case 4: FOAM-Agent Benchmark Reproduction**

**Actor:** Development Team (validation exercise)

**Scenario:**
```
1. Team extracts prompt from FOAM-agent paper appendix:
   "Turbulent non-premixed methane jet flame with detailed chemistry,
    grid resolution 128×128×256, SST turbulence model"

2. Run through AMReXAgent:
   pele-agent setup --prompt foam_prompt_7.txt --mode validation

3. Agent workflow:
   - Level 0: "non-premixed combustion" → PeleC or PeleLMeX
   - Turbulence modeling → PeleLMeX (better LES/RANS support)
   - Level 1: Retrieve report2.txt (problem classification catalog)
   - Identifies "jet flame" category
   - Level 2: Select JetFlame case
   - Document retrieval: Fetch paper metadata for cross-validation

4. Agent output:
   "Selected: PeleLMeX/Exec/Production/JetFlame
    
    FOAM-Agent Comparison:
    • Physics match: Non-premixed combustion ✓
    • Turbulence: SST model configured ✓
    • Grid: 128×128×256 specified ✓
    
    Document Retrieval:
    • arXiv:2103.XXXXX (jet flame DNS study)
    • Matched parameters: mechanism (GRI-3.0), inflow velocity (40 m/s)
    
    Confidence: 0.87 (high physics match, moderate grid similarity)"

5. Team compares to FOAM-agent selection:
   - FOAM selected: simpleFoam/jetFlame template
   - Pele selected: PeleLMeX/JetFlame
   - Physics alignment: Equivalent ✓
   - Decision quality: Match
```

**Postconditions:**
- AMReXAgent handled OpenFOAM-centric prompt correctly
- Translated FOAM concepts to Pele conventions
- Document retrieval validated against published work

**Success Metrics:**
- FOAM benchmark: ≥60% prompts handled equally well (12/20)
- Cross-domain translation successful

**Gate 4 & 5 Requirement:**
- 10 FOAM prompts parsed
- ≥6 achieve correct case selection
- Document retrieval operational

---

#### **Use Case 5: Multi-Index Ablation Testing**

**Actor:** Development Team (research contribution)

**Scenario:**
```
1. Team runs ablation suite:
   pele-agent ablation --test-oracle oracle.yaml --output ablation_results.json

2. System tests Level 2 (case metadata) indices:
   
   Config A: All 6 indices
     physics_descriptors: 0.35 weight
     grid_configurations: 0.20 weight
     git_metrics: 0.15 weight
     path_hierarchy: 0.15 weight
     chemistry_mechanisms: 0.10 weight
     performance_estimates: 0.05 weight
   → Accuracy: 18/20 (90%)
   
   Config B: Remove git_metrics
     (re-normalize remaining weights)
   → Accuracy: 16/20 (80%)
   → Conclusion: git_metrics contributes 10% accuracy gain
   
   Config C: Remove performance_estimates
   → Accuracy: 18/20 (90%)
   → Conclusion: performance_estimates contributes 0% accuracy gain
   
   Config D: physics_descriptors only
   → Accuracy: 14/20 (70%)
   → Conclusion: Other indices collectively contribute 20%

3. Results saved to ablation_results.json:
   {
     "timestamp": "2024-12-01T10:30:00Z",
     "test_oracle": "oracle_v1.yaml",
     "level_2_ablation": {
       "all_indices": {"accuracy": 0.90, "correct": 18, "total": 20},
       "no_git_metrics": {"accuracy": 0.80, "correct": 16, "total": 20},
       "no_performance_estimates": {"accuracy": 0.90, "correct": 18, "total": 20},
       "physics_only": {"accuracy": 0.70, "correct": 14, "total": 20}
     },
     "conclusions": {
       "high_contributors": ["physics_descriptors", "git_metrics", "grid_configurations"],
       "low_contributors": ["performance_estimates"],
       "recommendation": "production_scenario_b (merge low-contributors)"
     }
   }

4. Team uses results to optimize production config
```

**Postconditions:**
- Quantified contribution of each index type
- Evidence-based production configuration decision
- Research paper methodology validated

**Success Metrics:**
- All 82 indices tested
- Contribution >5% identified as "high"
- Decision tree generated for production

**Gate 6 Requirement:**
- Ablation study complete
- Production index configuration decided

---

### **4.3 Edge Cases & Error Scenarios**

#### **Edge Case 1: Ambiguous Query**

```
Prompt: "simulate combustion"

Agent Response:
  "Query too vague. Please specify:
   1. Physics regime:
      - Supersonic/compressible (PeleC)
      - Low-Mach subsonic (PeleLMeX)
      - Multiphase spray (PeleMP)
   
   2. Fuel type:
      - Methane (drm19 mechanism)
      - Hydrogen (h2 mechanism)
      - Dodecane (dodecane mechanism)
   
   3. Flow characteristics:
      - Premixed or non-premixed?
      - Turbulent or laminar?
   
   Example: 'Simulate low-Mach turbulent premixed methane flame'"

Mode: fail (cannot proceed with insufficient info)
```

#### **Edge Case 2: Unsupported Physics**

```
Prompt: "simulate coal gasification with particle tracking"

Agent Response:
  "Physics not supported in Phase 1.
   
   Reason: Coal gasification requires:
   • Multi-phase solid-gas interaction (not in PeleMP)
   • Heterogeneous surface reactions (not implemented)
   
   Alternative: Contact pele-users@googlegroups.com for specialized setups
   
   Supported Physics:
   • Gas-phase combustion (premixed/non-premixed)
   • Liquid spray combustion (PeleMP)
   • Non-reacting flows"

Mode: fail (graceful degradation)
```

#### **Edge Case 3: Retry Loop Success**

```
Attempt 1:
  Prompt: "premixed methane 512 cubed"
  Agent selects: PMF case
  Modifications: amr.n_cell = 512 512 512, pelec.chem_file = drm19.yaml
  Reviewer: ERROR - Missing amr.max_level
  Mode: retry

Attempt 2:
  Agent incorporates error context
  Modifications: 
    amr.n_cell = 512 512 512
    amr.max_level = 2  ← ADDED to fix error
    pelec.chem_file = drm19.yaml
  Reviewer: ✓ All checks passed
  Mode: proceed

Output: run_directory generated successfully
```

---

## **5. Functional Requirements**

### **5.1 Overview of Functional Architecture**

The system implements a **3-level modular RAG architecture** with ablation support:

**Level 0:** Physics Taxonomy (4 sub-indices)
- Which physics regime and solver family?

**Level 1:** Documentation (7 sub-indices per solver)
- What technical context applies?

**Level 2:** Case Metadata (6 sub-indices per solver)
- Which specific case and configuration?

**Total Indices:**
- Testing Mode: 82 indices (maximum granularity for ablation)
- Production Mode: 25-82 indices (determined by ablation results)

---

### **5.2 Level 0: Physics Taxonomy Requirements**

#### **FR-1: Multi-Solver Physics Regime Identification**

**Requirement:**  
System shall identify the correct physics family and solver(s) from natural language query with ≥95% top-1 accuracy.

**Sub-Indices (Testing Mode):**
```
physics_taxonomy/
├── physics_regimes/           (40% weight) - Combustion, multiphase, etc.
├── solver_capabilities/       (30% weight) - Individual solver descriptions
├── code_lineage/             (20% weight) - Evolution relationships
└── cross_cutting_guidance/   (10% weight) - Reports 1, 3, 4
```

**Physics Families:**
```yaml
compressible_combustion:
  codes: [PeleC]
  physics: "Compressible reacting Navier-Stokes, shocks, detonations"
  use_cases: "Supersonic flames, detonations, high-speed combustion"
  keywords: "compressible, shock, detonation, supersonic, Ma > 0.3"

low_mach_combustion:
  codes: [PeleLMeX, PeleLM]
  evolution: "PeleLM (simple geometry) → PeleLMeX (embedded boundaries)"
  physics: "Low-Mach reacting flows, variable density, detailed transport"
  use_cases: "Laminar/turbulent flames, DNS, LES, pool fires"
  keywords: "low-Mach, DNS, LES, Ma < 0.3, turbulent combustion"

multiphase_combustion:
  codes: [PeleMP]
  physics: "Spray combustion, Lagrangian particles, soot, radiation"
  use_cases: "Diesel engines, gas turbines, liquid fuel injection"
  keywords: "spray, multiphase, liquid fuel, soot, Lagrangian"
```

**Acceptance Criteria:**
- Top-1 family accuracy: ≥95% on test oracle (19/20 cases)
- Code lineage correctly embedded (e.g., PeleLM → PeleLMeX evolution)
- Cross-cutting guidance (reports) retrieved when relevant
- Graceful fallback if physics unsupported

**Test Cases:**
```python
def test_solver_selection():
    # Clear compressible case
    assert select_solver("supersonic hydrogen detonation") == "PeleC"
    
    # Clear low-Mach case
    assert select_solver("low-speed turbulent premixed DNS") == "PeleLMeX"
    
    # Multiphase case
    assert select_solver("diesel spray injection") == "PeleMP"
    
    # Ambiguous (Mach number determines)
    result = select_solver("turbulent premixed combustion Ma=0.2")
    assert result == "PeleLMeX"  # Low Mach
    
    result = select_solver("turbulent premixed combustion Ma=0.8")
    assert result == "PeleC"  # Compressible
```

**Ablation Testing:**
```python
# Does code_lineage index help?
ablate_level0("code_lineage")
# Query: "PeleLM-like setup but with complex geometry"
# Expected: Should still find PeleLMeX via solver_capabilities
# If accuracy drops >5%: code_lineage contributes
```

---

#### **FR-2: Extensible Physics Taxonomy**

**Requirement:**  
System architecture shall support adding new AMReX applications without modifying core code.

**Extensibility Criteria:**
- New solver added by:
  1. Creating solver description in `physics_families` dict
  2. Building documentation indices (automated script)
  3. Building case metadata indices (automated script)
- No changes to `EmbeddingService`, `ArchitectService`, or workflow nodes
- Demonstrated by adding hypothetical solver in <1 day

**Test Case:**
```python
def test_extensibility():
    # Add hypothetical "AtmosphericBoundaryLayer" family
    new_family = {
        "atmospheric_modeling": {
            "codes": ["ERF", "REMORA"],
            "evolution": "ERF (atmospheric) inspired REMORA (ocean)",
            "physics": "Terrain-following mesh, ABL, mesoscale",
            "use_cases": "Weather, wind energy, ocean circulation"
        }
    }
    
    # Rebuild Level 0 indices
    rebuild_physics_taxonomy(include=new_family)
    
    # Test query
    result = select_solver("wind turbine atmospheric boundary layer")
    assert result in ["ERF", "REMORA"]
    
    # Verify no code changes needed
    assert EmbeddingService.search_level_0.source_unchanged()
```

---

### **5.3 Level 1: Documentation Retrieval Requirements**

#### **FR-3: Unified Documentation Search**

**Requirement:**  
System shall retrieve relevant technical documentation from curated reports, solver READMEs, and case READMEs with ≥90% relevance (top-5 results).

**Sub-Indices (Testing Mode - per solver):**
```
{solver}_documentation/
├── solver_readme/            (8% weight)  - Top-level README.rst
├── problem_catalogs/         (15% weight) - Report 2 (classification)
├── parameter_guides/         (25% weight) - Report 5 (customization)
├── performance_data/         (10% weight) - Report 6 (job sizing)
├── build_instructions/       (5% weight)  - Report 7 (compilation)
├── case_inventory/          (2% weight)  - Report 9 (case listing)
└── case_readmes/            (35% weight) - All case README files
```

**Document Types Indexed:**

**1. Solver README.rst (Top-Level Documentation)**
```python
# Example: PeleC/README.rst
{
    "text": parse_rst("PeleC/README.rst"),
    "type": "solver_readme",
    "solver": "PeleC",
    "sections": ["Getting Started", "Physics Models", "Build Instructions"]
}
```

**2. Curated Technical Reports**
```python
# Report 5: Parameter Customization Guide
{
    "text": Path("database/reports/report5.txt").read_text(),
    "type": "parameter_reference",
    "report_id": 5,
    "solver": "PeleC",
    "topics": ["grid setup", "chemistry", "time integration", "turbulence"]
}

# Report 6: Performance Data
{
    "text": Path("database/reports/report6.txt").read_text(),
    "type": "performance_data",
    "report_id": 6,
    "solver": "PeleC",
    "topics": ["job sizing", "runtime estimates", "scaling"]
}
```

**3. Case-Specific READMEs**
```python
# Example: PMF case README
{
    "text": parse_readme("PeleC/Exec/RegTests/PMF/README.md"),
    "type": "case_readme",
    "case": "PMF",
    "solver": "PeleC",
    "physics": ["premixed", "combustion", "1D flame"]
}
```

**Acceptance Criteria:**
- Retrieves relevant parameter guidance for 90% of queries
- Supports .rst, .md, .txt formats (RST parsing via docutils)
- Case READMEs weighted highest (35%) for case-specific queries
- Parameter guides weighted 25% for setup questions
- Build instructions retrieved only when relevant (5% weight)

**Test Cases:**
```python
def test_documentation_retrieval():
    # Parameter setup query
    docs = search_documentation(
        query="How to set grid resolution for DNS?",
        solver="PeleLMeX"
    )
    assert "report5" in [d.report_id for d in docs[:3]]  # Param guide in top-3
    
    # Performance query
    docs = search_documentation(
        query="Runtime estimate for 512^3 grid",
        solver="PeleC"
    )
    assert "report6" in [d.report_id for d in docs[:3]]  # Performance data
    
    # Case-specific query
    docs = search_documentation(
        query="Premixed flame boundary conditions",
        solver="PeleC"
    )
    assert any("PMF" in d.case for d in docs[:5])  # PMF README in top-5
```

**Ablation Testing:**
```python
# Do build_instructions contribute to case selection?
ablate_level1("build_instructions")
# Hypothesis: Minimal contribution (5% weight)
# If accuracy unchanged: merge into documentation_auxiliary/
```

---

#### **FR-4: RST Documentation Parsing**

**Requirement:**  
System shall parse reStructuredText (.rst) files to plain text for embedding while preserving section structure.

**Implementation:**
```python
from docutils.core import publish_parts
from bs4 import BeautifulSoup

def parse_rst(file_path: Path) -> str:
    """
    Parse RST to plain text.
    
    Preserves:
      - Section headers (## syntax)
      - Code blocks (indentation)
      - Bullet lists
    
    Removes:
      - RST directives (.. toctree::)
      - Link syntax (:ref:`label`)
      - Inline roles (:class:`Name`)
    """
    rst_content = file_path.read_text()
    
    # Convert to HTML (intermediate)
    parts = publish_parts(rst_content, writer_name='html')
    
    # Strip HTML tags
    soup = BeautifulSoup(parts['html_body'], 'html.parser')
    text = soup.get_text()
    
    # Clean whitespace
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    return '\n'.join(lines)
```

**Acceptance Criteria:**
- Successfully parses PeleC/README.rst, PeleLMeX/README.rst, PeleMP/README.rst
- Section headers preserved for hierarchical matching
- Code examples retained (syntax, not execution)
- No RST syntax artifacts in embedded text

**Test Case:**
```python
def test_rst_parsing():
    text = parse_rst("PeleC/README.rst")
    
    # Section headers preserved
    assert "Getting Started" in text
    assert "Physics Models" in text
    
    # No RST directives
    assert ".. toctree::" not in text
    assert ":ref:" not in text
    
    # Code blocks retained
    assert "make -j" in text  # Build command example
```

---

### **5.4 Level 2: Case Metadata Requirements**

#### **FR-5: Structured Case Metadata Search**

**Requirement:**  
System shall search unified case summaries combining git metrics, physics descriptors, grid configurations with ≥90% case selection accuracy (top-5 results).

**Sub-Indices (Testing Mode - per solver):**
```
{solver}_case_metadata/
├── physics_descriptors/      (35% weight) - Reacting, BCs, mechanisms
├── grid_configurations/      (20% weight) - Grid size, AMR, dimension
├── git_metrics/             (15% weight) - Age, commits, maturity
├── path_hierarchy/          (15% weight) - Production/RegTests/Custom
├── chemistry_mechanisms/     (10% weight) - drm19, dodecane, etc.
└── performance_estimates/    (5% weight)  - Runtime, memory
```

**Case Summary Structure:**
```python
# Example: PMF case metadata
{
    "text": """
    Case: PMF
    Path: PeleC/Exec/RegTests/PMF
    
    Git Metrics:
      Created: 6.7 years ago (2018-03-15)
      Commits: 47
      Contributors: 8
      Last updated: 2 months ago
      Maturity: Production-ready (stable, well-maintained)
    
    Physics:
      Type: Reacting flow
      Chemistry: drm19 mechanism (methane-air)
      Flow regime: Compressible premixed combustion
      Multiphase: No
      Turbulence: No (laminar)
      Boundary conditions: Periodic in y-z, inflow-outflow in x
      Dimension: 3D
    
    Configuration:
      Default grid: 128 × 128 × 128
      AMR levels: 2
      Typical variants: inputs.2d, inputs.3d, inputs.regression
      Runtime estimate: ~500 CPU hours (64 cores)
    
    Quality Tier: RegTests (validated reference case)
    
    Keywords: premixed, methane, combustion, flame, drm19, 1D, chemistry
    """,
    "case_id": "pelec_pmf",
    "case_name": "PMF",
    "solver": "PeleC"
}
```

**Acceptance Criteria:**
- Physics descriptors dominate (35% weight) for physics-based queries
- Grid configuration (20%) helps with resolution queries
- Git metrics (15%) filter stale/experimental cases
- Path hierarchy (15%) boosts Production > RegTests > Custom
- Chemistry mechanisms (10%) match fuel type queries
- Performance estimates (5%) provide runtime context

**Test Cases:**
```python
def test_case_metadata_search():
    # Physics-driven query
    cases = search_case_metadata(
        query="premixed methane combustion detailed chemistry",
        solver="PeleC"
    )
    assert cases[0].name == "PMF"  # Physics match dominates
    
    # Grid-driven query
    cases = search_case_metadata(
        query="high resolution 512 cubed DNS",
        solver="PeleLMeX"
    )
    assert cases[0].default_grid in ["512^3", "256^3"]  # Grid similarity
    
    # Maturity-driven query
    cases = search_case_metadata(
        query="stable production baseline validated",
        solver="PeleC"
    )
    assert cases[0].quality_tier == "Production"  # Path hierarchy + git metrics
```

**Ablation Testing:**
```python
# Test contribution of each metadata type
def test_metadata_ablation():
    # Full metadata
    accuracy_all = test_with_indices([
        "physics_descriptors", "grid_configurations", "git_metrics",
        "path_hierarchy", "chemistry_mechanisms", "performance_estimates"
    ])
    
    # Remove performance_estimates
    accuracy_no_perf = test_with_indices([
        "physics_descriptors", "grid_configurations", "git_metrics",
        "path_hierarchy", "chemistry_mechanisms"
    ])
    
    contribution = accuracy_all - accuracy_no_perf
    
    if contribution < 0.05:  # <5% contribution
        mark_for_merging("performance_estimates")
```

---

#### **FR-6: Git Metrics Extraction**

**Requirement:**  
System shall extract repository activity metrics for each case to assess maturity and stability.

**Metrics Collected:**
```python
class GitMetrics:
    years_since_creation: float     # Age of case (first commit)
    total_commits: int              # Commit count for case directory
    num_contributors: int           # Unique authors
    months_since_update: float      # Recency of last modification
    commit_frequency: float         # Commits per month (avg)
    is_production: bool             # In Production/ directory?
```

**Implementation:**
```bash
# Extract git metrics for case
cd PeleC/Exec/RegTests/PMF

# First commit date
git log --diff-filter=A --follow --format=%aI -- . | tail -1
# → 2018-03-15T10:30:00Z

# Total commits
git log --oneline --follow -- . | wc -l
# → 47

# Contributors
git log --format='%aN' --follow -- . | sort -u | wc -l
# → 8

# Last commit date
git log -1 --format=%aI -- .
# → 2024-10-15T14:20:00Z
```

**Acceptance Criteria:**
- Metrics extracted for all indexed cases
- Build time: <5 min for 45 cases (parallel git queries)
- Cached to avoid repeated git operations
- Invalid/missing git history handled gracefully

**Test Case:**
```python
def test_git_metrics():
    metrics = extract_git_metrics("PeleC/Exec/RegTests/PMF")
    
    assert metrics.years_since_creation > 5  # PMF is mature
    assert metrics.total_commits > 40
    assert metrics.num_contributors >= 5
    assert metrics.months_since_update < 12  # Recently maintained
```

---

### **5.5 Workflow Orchestration Requirements**

#### **FR-7: LangGraph State Machine**

**Requirement:**  
System shall implement stateful workflow using LangGraph with 5 nodes: SolverSelector, Architect, Reviewer, PaperValidator, InputWriter.

**State Schema:**
```python
from typing import TypedDict, Optional, List, Tuple, Any, Literal

class AgentState(TypedDict):
    # Input
    prompt: str
    
    # Level 0: Solver selection
    selected_solvers: List[Tuple[str, float]]  # [("PeleLMeX", 0.92), ...]
    solver_reasoning: str
    
    # Level 1: Documentation context
    documentation_matches: List[DocumentMatch]
    
    # Level 2: Case selection
    selected_case: Optional[str]
    case_candidates: List[CaseMetadata]
    
    # Planning
    modifications: List[Tuple[str, Any]]
    reasoning: str
    
    # Validation
    mode: Literal["proceed", "retry", "fail"]
    errors_active: List[str]
    review_analysis: str
    
    # Paper validation (for FOAM benchmark)
    arxiv_metadata: Optional[Dict]
    plot_match_score: Optional[float]
    
    # Output
    run_directory: Optional[str]
    inputs_file_path: Optional[str]
    
    # Workflow metadata
    retry_count: int
    max_retries: int
    start_time: float
```

**Workflow Graph:**
```python
from langgraph.graph import StateGraph, END

def build_workflow(mode: str = "production") -> StateGraph:
    """
    Build LangGraph workflow.
    
    Modes:
      - production: Skip PaperValidator
      - validation: Include PaperValidator for FOAM benchmark
    """
    workflow = StateGraph(AgentState)
    
    # Define nodes
    workflow.add_node("solver_selector", solver_selector_node)
    workflow.add_node("architect", architect_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("input_writer", input_writer_node)
    
    if mode == "validation":
        workflow.add_node("paper_validator", paper_validator_node)
    
    # Define edges
    workflow.set_entry_point("solver_selector")
    workflow.add_edge("solver_selector", "architect")
    workflow.add_edge("architect", "reviewer")
    
    # Conditional routing from reviewer
    workflow.add_conditional_edges(
        "reviewer",
        route_reviewer,
        {
            "proceed": "paper_validator" if mode == "validation" else "input_writer",
            "retry": "architect",
            "fail": END
        }
    )
    
    if mode == "validation":
        workflow.add_edge("paper_validator", "input_writer")
    
    workflow.add_edge("input_writer", END)
    
    return workflow.compile()

def route_reviewer(state: AgentState) -> str:
    """Route based on reviewer decision."""
    return state["mode"]
```

**Acceptance Criteria:**
- Retry loop functional (max 3 attempts)
- Error context propagated to architect on retry
- Validation mode toggleable (with/without PaperValidator)
- State immutable (functional updates only)

**Test Case:**
```python
def test_workflow_retry():
    initial_state = {
        "prompt": "premixed methane 512^3",
        "retry_count": 0,
        "max_retries": 3
    }
    
    workflow = build_workflow()
    
    # First attempt (missing parameter)
    state1 = workflow.invoke(initial_state)
    assert state1["mode"] == "retry"
    assert "amr.max_level" in state1["errors_active"][0]
    
    # Second attempt (error fixed)
    state2 = workflow.invoke(state1)
    assert state2["mode"] == "proceed"
    assert state2["retry_count"] == 1
    assert state2["run_directory"] is not None
```

---

#### **FR-8: Document Retrieval Service** ✨ NEW

**Requirement:**  
System shall retrieve and analyze research papers for validation against published results (FOAM-agent benchmark, Gate 4/5).

**Service Interface:**
```python
class DocumentRetrievalService:
    """
    Fetch and analyze research papers.
    
    Use cases:
      1. FOAM-agent paper reproduction
      2. Validate case selection against published setups
      3. Plot similarity assessment (Gate 5)
    """
    
    def retrieve_paper_metadata(
        self,
        title: Optional[str] = None,
        arxiv_id: Optional[str] = None,
        doi: Optional[str] = None
    ) -> Dict:
        """
        Fetch paper metadata from arXiv API.
        
        Returns:
          {
            "title": "...",
            "authors": [...],
            "abstract": "...",
            "pdf_url": "https://arxiv.org/pdf/...",
            "published": "2021-03-15"
          }
        """
    
    def extract_simulation_details(
        self,
        pdf_path: Path
    ) -> Dict:
        """
        Parse PDF for simulation parameters.
        
        Uses:
          - pypdf for text extraction
          - Regex for parameter patterns
          - LLM for structured extraction
        
        Returns:
          {
            "solver": "OpenFOAM simpleFoam",
            "grid_resolution": "128x128x256",
            "boundary_conditions": "...",
            "chemistry_mechanism": "GRI-3.0"
          }
        """
    
    def compare_plots(
        self,
        reference_plot: Path,
        generated_plot: Path
    ) -> float:
        """
        Image similarity for validation.
        
        Methods:
          - SSIM (structural similarity)
          - Feature matching (SIFT/ORB)
          - Pixel-wise MSE
        
        Returns:
          Similarity score 0-1 (1 = identical)
        """
    
    def validate_against_paper(
        self,
        case: CaseMetadata,
        paper_metadata: Dict
    ) -> ValidationReport:
        """
        Check if selected case matches paper description.
        
        Example:
          Paper: "Premixed flame DNS, drm19, 256³ grid"
          Case: PMF with inputs.3d
          Match: ✓ Physics aligned, grid scalable
        """
```

**Acceptance Criteria:**
- arXiv API integration functional
- PDF parsing extracts grid size, solver, BCs
- Plot comparison returns 0-1 score (SSIM)
- Used only in validation mode (not production)

**Test Case:**
```python
def test_document_retrieval():
    service = DocumentRetrievalService()
    
    # Fetch arXiv paper
    metadata = service.retrieve_paper_metadata(
        arxiv_id="2103.12345"  # Example FOAM-agent paper
    )
    assert "FOAM" in metadata["title"]
    assert metadata["pdf_url"].startswith("https://arxiv.org/pdf/")
    
    # Extract simulation details
    details = service.extract_simulation_details(Path("paper.pdf"))
    assert "grid_resolution" in details
    assert "128" in details["grid_resolution"]
    
    # Compare plots
    similarity = service.compare_plots(
        Path("paper_fig3.png"),
        Path("pele_output.png")
    )
    assert 0 <= similarity <= 1
```

**Integration with Workflow:**
```python
def paper_validator_node(state: AgentState) -> AgentState:
    """
    Validate against published paper (FOAM benchmark only).
    
    Adds arxiv_metadata and plot_match_score to state.
    """
    if not state.get("validation_mode"):
        return state  # Skip in production
    
    service = DocumentRetrievalService()
    
    # Fetch paper for this test case
    paper = service.retrieve_paper_metadata(
        title=f"FOAM case {state['foam_case_id']}"
    )
    
    # Extract expected parameters
    expected = service.extract_simulation_details(paper["pdf_path"])
    
    # Validate selection
    report = service.validate_against_paper(
        case=state["selected_case"],
        paper_metadata=expected
    )
    
    return {
        **state,
        "arxiv_metadata": paper,
        "validation_report": report,
        "plot_match_score": report.plot_similarity if report.has_plots else None
    }
```

---

---

# **AMReXAgent: Product & Technical Specification**
## **Phase 3: Non-Functional Requirements & Project Plan**

---

## **6. Non-Functional Requirements**

### **6.1 Performance Requirements**

#### **NFR-1: Index Build Time**

**Requirement:**  
Complete FAISS index build for all solvers in ≤30 minutes on NERSC Perlmutter login node.

**Scope:**
- 82 indices (testing mode)
- 3 Pele solvers fully implemented (PeleC, PeleLMeX, PeleMP)
- ~45 cases per solver (135 total cases)

**Performance Targets:**

| Operation | Target | Rationale |
|-----------|--------|-----------|
| Extract case metadata | <5 min | Parallel git queries, cached results |
| Embed documents (all indices) | <20 min | Batch embedding via CBORG/OpenAI |
| Build FAISS indices | <5 min | In-memory construction, disk write |
| **Total** | **≤30 min** | Acceptable for daily CI/CD rebuild |

**Acceptance Criteria:**
```python
def test_index_build_performance():
    start = time.time()
    
    # Build all indices
    build_all_indices(
        solvers=["PeleC", "PeleLMeX", "PeleMP"],
        mode="testing"  # 82 indices
    )
    
    elapsed = time.time() - start
    assert elapsed < 30 * 60  # 30 minutes
```

**Optimization Strategies:**
- Parallel processing: Embed documents in batches of 100
- Caching: Store intermediate embeddings, rebuild indices only
- Incremental updates: Only re-index changed cases (git diff)

---

#### **NFR-2: Query Response Time**

**Requirement:**  
Return simulation plan (case selection + modifications) in ≤10 seconds for 95% of queries.

**Latency Budget:**

| Component | Target | Notes |
|-----------|--------|-------|
| Level 0 (solver selection) | <1 sec | Query 4 indices, weighted combination |
| Level 1 (documentation) | <2 sec | Query 7 indices per solver |
| Level 2 (case metadata) | <2 sec | Query 6 indices per solver |
| LLM modification planning | <4 sec | GPT-4 API call (cached prompt) |
| Reviewer validation | <1 sec | Rule-based checks |
| **Total** | **<10 sec** | Acceptable for interactive CLI |

**Acceptance Criteria:**
```python
def test_query_response_time():
    times = []
    
    for prompt in test_oracle_prompts:
        start = time.time()
        plan = agent.create_plan(prompt)
        elapsed = time.time() - start
        times.append(elapsed)
    
    # 95th percentile
    p95 = np.percentile(times, 95)
    assert p95 < 10.0  # seconds
    
    # Median should be much faster
    median = np.median(times)
    assert median < 5.0
```

**Performance Optimizations:**
- FAISS index loaded once at startup (not per query)
- Embedding API calls batched where possible
- LLM prompt caching (anthropic cache API)
- Parallel index queries (asyncio)

---

#### **NFR-3: Index Storage Efficiency**

**Requirement:**  
Total FAISS database size ≤500MB for 3 solvers (testing mode with 82 indices).

**Storage Budget:**

| Index Level | Per-Solver Size | Total (3 solvers) |
|-------------|-----------------|-------------------|
| Level 0 (physics taxonomy) | N/A (shared) | ~5MB |
| Level 1 (documentation, 7 indices) | ~30MB | ~90MB |
| Level 2 (case metadata, 6 indices) | ~40MB | ~120MB |
| **Total** | ~70MB/solver | **~215MB** |

**Acceptance Criteria:**
```python
def test_index_storage():
    db_path = Path("database/faiss")
    total_size = sum(f.stat().st_size for f in db_path.rglob("*.faiss"))
    
    assert total_size < 500 * 1024 * 1024  # 500MB
    
    # Individual index size
    pelec_size = sum(
        f.stat().st_size 
        for f in db_path.glob("pelec_*.faiss")
    )
    assert pelec_size < 100 * 1024 * 1024  # 100MB per solver
```

**Storage Optimizations:**
- Use float16 embeddings (half precision) where accuracy permits
- Quantization: Product quantization for large indices (>10K docs)
- Deduplication: Shared embeddings for common sections (e.g., "Getting Started")

---

### **6.2 Reliability Requirements**

#### **NFR-4: Error Detection Rate**

**Requirement:**  
Reviewer service shall detect ≥90% of configuration errors before execution.

**Error Categories:**

| Error Type | Detection Rate | Method |
|------------|----------------|--------|
| Missing required parameters | 100% | Schema validation |
| Invalid syntax | 95% | Parser + regex |
| Physics inconsistencies | 85% | Rule-based logic |
| File path errors | 90% | Filesystem checks |
| **Overall** | **≥90%** | Weighted average |

**Test Methodology:**
```python
def test_error_detection():
    # Synthetic error injection
    error_cases = [
        {"type": "missing_param", "inputs": "..."},  # Missing amr.n_cell
        {"type": "invalid_syntax", "inputs": "..."},  # 256^3 instead of 256 256 256
        {"type": "physics_conflict", "inputs": "..."},  # EB + all-periodic BCs
        {"type": "missing_file", "inputs": "..."},  # Nonexistent chemistry file
    ]
    
    detected = 0
    total = len(error_cases)
    
    for case in error_cases:
        result = reviewer.validate(case["inputs"])
        if result.mode == "fail" or result.mode == "retry":
            detected += 1
    
    detection_rate = detected / total
    assert detection_rate >= 0.90
```

**Acceptance Criteria:**
- 18/20 synthetic errors caught (90%)
- False positive rate <5% (don't block valid configs)
- Actionable error messages (suggest fix, not just "invalid")

---

#### **NFR-5: System Availability**

**Requirement:**  
Agent CLI shall be operational ≥99% of time during working hours (8am-6pm PT, Mon-Fri).

**Failure Modes & Handling:**

| Failure | Probability | Mitigation |
|---------|-------------|------------|
| FAISS index corruption | <1% | Rebuild from source (30 min) |
| Embedding API outage | <5% | Fallback: CBORG → OpenAI → Local |
| LLM API rate limit | <10% | Exponential backoff + cache |
| Git repository unavailable | <1% | Use local cached metadata |

**Graceful Degradation:**
```python
def handle_embedding_failure():
    """Fallback chain for embedding service."""
    try:
        return embed_via_cborg(text)
    except CBORGError:
        logger.warning("CBORG unavailable, falling back to OpenAI")
        try:
            return embed_via_openai(text)
        except OpenAIError:
            logger.error("All embedding APIs failed")
            raise EmbeddingServiceUnavailable(
                "Try again in 5 minutes or rebuild indices locally"
            )
```

**Acceptance Criteria:**
- System remains functional during single-point failures
- User informed of degraded mode (e.g., "Using cached embeddings")
- No silent failures (all errors logged + user-visible)

---

#### **NFR-6: Reproducibility**

**Requirement:**  
Identical queries on identical database state shall produce identical results (deterministic).

**Reproducibility Guarantees:**

| Component | Determinism | Notes |
|-----------|-------------|-------|
| FAISS retrieval | Deterministic | Fixed random seed for index build |
| LLM modification planning | Non-deterministic | Temperature > 0 for creativity |
| Weighted score combination | Deterministic | Fixed weights in config |
| Reviewer validation | Deterministic | Rule-based only |

**Mitigation for LLM Non-Determinism:**
```python
# Seed LLM for reproducible testing
def create_plan(prompt: str, seed: Optional[int] = None):
    if seed is not None:
        llm_config = {"temperature": 0.0, "seed": seed}
    else:
        llm_config = {"temperature": 0.3}  # Slight creativity
    
    # FAISS retrieval is always deterministic
    cases = embedding_service.search(prompt)
    
    # LLM planning (configurable)
    plan = llm.generate(prompt, cases, config=llm_config)
    
    return plan
```

**Test Case:**
```python
def test_reproducibility():
    prompt = "premixed methane flame DNS"
    
    # Run 3 times with same seed
    results = [
        agent.create_plan(prompt, seed=42)
        for _ in range(3)
    ]
    
    # All results identical
    assert results[0].selected_case == results[1].selected_case == results[2].selected_case
    assert results[0].modifications == results[1].modifications == results[2].modifications
```

**Acceptance Criteria:**
- FAISS retrieval: 100% reproducible
- Full pipeline with LLM seed: 100% reproducible
- Full pipeline without seed: ≥80% stable (same top-1 case)

---

### **6.3 Maintainability Requirements**

#### **NFR-7: Test Coverage**

**Requirement:**  
Maintain ≥85% code coverage across all core components.

**Coverage Targets:**

| Component | Target | Current (Estimate) |
|-----------|--------|-------------------|
| `config.py` | 100% | 100% (already achieved) |
| `embedding_service.py` | 90% | ~60% (needs improvement) |
| `architect_service.py` | 85% | ~50% (needs improvement) |
| `reviewer_service.py` | 90% | ~70% (needs improvement) |
| `workflow.py` | 80% | ~40% (needs improvement) |
| **Overall** | **≥85%** | **~64%** |

**Testing Strategy:**
```python
# Unit tests (component isolation)
def test_embedding_service():
    service = MultiIndexEmbeddingService(mock_config)
    results = service.search_level_0("premixed combustion")
    assert len(results) > 0

# Integration tests (multiple components)
def test_full_workflow():
    state = {"prompt": "premixed methane flame"}
    final_state = workflow.invoke(state)
    assert final_state["selected_case"] is not None

# End-to-end tests (CLI)
def test_cli_interface():
    result = subprocess.run(
        ["pele-agent", "setup", "--prompt", "test_prompt.txt"],
        capture_output=True
    )
    assert result.returncode == 0
    assert Path("run_*/inputs").exists()
```

**Coverage Enforcement:**
```yaml
# .github/workflows/test.yml
- name: Run tests with coverage
  run: |
    pytest --cov=amrex_agent --cov-report=term --cov-report=html
    coverage report --fail-under=85
```

**Acceptance Criteria:**
- All new code requires tests (PR blocker)
- Coverage measured in CI/CD pipeline
- HTML coverage report generated for review

---

#### **NFR-8: Code Quality**

**Requirement:**  
All code shall pass linting (ruff), type checking (mypy), and formatting (black) checks.

**Quality Tools:**

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **ruff** | Fast linting | `select = ["E", "F", "I", "N"]` |
| **mypy** | Static type checking | `strict = True` |
| **black** | Code formatting | `line-length = 100` |
| **isort** | Import sorting | `profile = "black"` |

**Pre-Commit Hooks:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
      - id: ruff-format
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [types-PyYAML, types-requests]
  
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
```

**Acceptance Criteria:**
- Zero linting errors in CI/CD
- Type hints on all public functions
- Code formatted consistently (black)
- Pre-commit hooks prevent bad commits

---

#### **NFR-9: Documentation**

**Requirement:**  
All public APIs shall have docstrings following NumPy style guide.

**Documentation Levels:**

| Level | Requirement | Example |
|-------|-------------|---------|
| **Module** | Purpose, main classes | `"""Multi-index FAISS retrieval service."""` |
| **Class** | Attributes, usage pattern | `"""Manages 82 FAISS indices for case retrieval."""` |
| **Function** | Args, returns, raises | See example below |
| **Type hints** | All signatures | `def search(query: str, k: int) -> List[Case]` |

**Example:**
```python
def search_multi_index(
    self,
    query: str,
    solver: str,
    enabled_indices: Optional[List[str]] = None
) -> List[CaseMetadata]:
    """
    Search across multiple FAISS indices with weighted combination.
    
    Parameters
    ----------
    query : str
        Natural language query for case search.
    solver : str
        Solver name (e.g., "PeleC", "PeleLMeX").
    enabled_indices : list of str, optional
        Subset of indices to query (for ablation testing).
        If None, queries all indices. Default is None.
    
    Returns
    -------
    list of CaseMetadata
        Ranked cases with combined scores from all indices.
    
    Raises
    ------
    SolverNotFoundError
        If solver has no indices built.
    
    Examples
    --------
    >>> service = MultiIndexEmbeddingService(config)
    >>> cases = service.search_multi_index("premixed methane", "PeleC")
    >>> cases[0].name
    'PMF'
    
    Notes
    -----
    Uses weighted combination of 6 metadata indices:
    - physics_descriptors (35%)
    - grid_configurations (20%)
    - git_metrics (15%)
    - path_hierarchy (15%)
    - chemistry_mechanisms (10%)
    - performance_estimates (5%)
    """
```

**Acceptance Criteria:**
- 100% of public functions documented
- Examples included for complex functions
- Auto-generated API docs via Sphinx
- User guide with quickstart, tutorials, troubleshooting

---

### **6.4 Usability Requirements**

#### **NFR-10: CLI Usability**

**Requirement:**  
Command-line interface shall be intuitive for both novice and expert users.

**CLI Design Principles:**

1. **Sensible defaults**: Minimal required arguments
2. **Progressive disclosure**: Advanced options hidden in `--help`
3. **Clear feedback**: Progress indicators, success/error messages
4. **Safety**: Confirmation prompts for destructive actions

**Command Structure:**
```bash
# Novice user (minimal args)
pele-agent setup --prompt "premixed methane flame"

# Intermediate user (specify solver)
pele-agent setup --prompt my_prompt.txt --solver PeleLMeX

# Advanced user (ablation testing)
pele-agent setup --prompt test.txt --mode testing --disable-indices git_metrics,performance_estimates

# Validation mode (FOAM benchmark)
pele-agent setup --prompt foam_case_7.txt --mode validation --validate-paper arxiv:2103.12345

# Rebuild indices
pele-agent build-indices --solvers PeleC,PeleLMeX --mode testing

# Run ablation study
pele-agent ablation --test-oracle oracle.yaml --output results.json
```

**Output Quality:**
```bash
$ pele-agent setup --prompt "premixed methane"

🔍 Analyzing query...
  ✓ Physics family: low_mach_combustion (0.92)
  ✓ Solver: PeleLMeX (optimized for low-Mach DNS)

📚 Retrieving documentation...
  ✓ Found 5 relevant guides (report5: parameter setup)

🎯 Searching 45 cases...
  ✓ Top match: FlameSheet (physics: 0.95, grid: 0.80)

📝 Planning modifications...
  ✓ Grid: 256³ (DNS resolution)
  ✓ Chemistry: drm19.yaml (methane-air)
  ✓ Boundary: Periodic in y-z

✅ Validation passed (0 errors)

📁 Generated: run_20241201_143052/
   Next: cd run_20241201_143052 && sbatch submit.sh

⏱️  Total time: 4.2 seconds
```

**Acceptance Criteria:**
- Zero-config setup for default use case
- `--help` text comprehensive but not overwhelming
- Error messages actionable (not "Error: invalid input")
- Progress indicators for >2 second operations

---

#### **NFR-11: Explainability**

**Requirement:**  
All decisions shall be explainable with per-index score breakdowns and reasoning text.

**Explanation Levels:**

**Level 1: Summary (default)**
```
Selected: PeleC/Exec/RegTests/PMF
Confidence: 0.87

Why PMF?
• Physics match: Premixed methane combustion with drm19 mechanism
• Maturity: Stable baseline (47 commits, 8 contributors, 6 years old)
• Quality: Validated RegTest (production-ready)
```

**Level 2: Detailed (--verbose)**
```
Selected: PeleC/Exec/RegTests/PMF
Combined Score: 0.87

Index Contributions:
  physics_descriptors   (35%): 0.95 ████████████ [reacting + methane + drm19]
  grid_configurations   (20%): 0.70 ███████      [128³ similar to query]
  git_metrics          (15%): 0.90 █████████    [stable, well-maintained]
  path_hierarchy       (15%): 0.75 ████████     [RegTests directory]
  chemistry_mechanisms (10%): 0.95 ████████████ [drm19 exact match]
  performance_estimates (5%): 0.60 ██████       [moderate cost]

Combined: 0.35×0.95 + 0.20×0.70 + 0.15×0.90 + ... = 0.87

Alternative Considered:
  TaylorGreen (0.65) - Rejected: No chemistry (non-reacting turbulence)
```

**Level 3: Debug (--debug)**
```json
{
  "selected_case": "PMF",
  "combined_score": 0.87,
  "level_0_solver_selection": {
    "families_ranked": [
      {"name": "compressible_combustion", "score": 0.92, "codes": ["PeleC"]},
      {"name": "low_mach_combustion", "score": 0.60, "codes": ["PeleLMeX"]}
    ],
    "selected_solver": "PeleC",
    "reasoning": "Query mentions 'compressible' → PeleC required"
  },
  "level_1_documentation": [
    {"type": "parameter_guide", "report_id": 5, "score": 0.85},
    {"type": "case_readme", "case": "PMF", "score": 0.90}
  ],
  "level_2_case_metadata": {
    "physics_descriptors": {"score": 0.95, "matched_terms": ["reacting", "methane", "drm19"]},
    "grid_configurations": {"score": 0.70, "matched_grid": "128³"},
    "git_metrics": {"score": 0.90, "commits": 47, "age_years": 6.7},
    "path_hierarchy": {"score": 0.75, "tier": "RegTests"},
    "chemistry_mechanisms": {"score": 0.95, "mechanism": "drm19"},
    "performance_estimates": {"score": 0.60, "runtime_hours": 500}
  }
}
```

**Acceptance Criteria:**
- Summary explanation understandable to non-experts (user study: 80% comprehension)
- Detailed mode shows per-index scores
- Debug mode provides machine-readable JSON
- All scores traceable to specific document snippets

---

### **6.5 Extensibility Requirements**

#### **NFR-12: Adding New Solvers**

**Requirement:**  
Adding a new AMReX application to the system shall require <1 day of effort (no code changes, just index building).

**Process:**
```bash
# 1. Add solver to physics taxonomy (5 min)
vim database/configs/physics_families.yaml
# Add new entry:
#   atmospheric_modeling:
#     codes: [ERF]
#     physics: "Terrain-following AMR for atmospheric flows"

# 2. Build indices (25 min)
pele-agent build-indices --solver ERF --mode testing

# 3. Test (5 min)
pele-agent setup --prompt "atmospheric boundary layer wind" --solver ERF

# Done! No code changes needed.
```

**Architecture Validation:**
```python
def test_extensibility():
    """Verify adding new solver requires only configuration."""
    
    # Simulate adding ERF
    new_family = {
        "atmospheric_modeling": {
            "codes": ["ERF"],
            "physics": "Terrain-following AMR, ABL, mesoscale",
            "use_cases": "Weather, wind energy"
        }
    }
    
    # Add to config
    physics_families.update(new_family)
    
    # Build indices (should not require code changes)
    build_solver_indices("ERF")
    
    # Test query
    result = agent.create_plan("wind turbine atmospheric boundary layer")
    
    # Verify ERF selected
    assert "ERF" in result.selected_solvers[0]
    
    # No code modifications
    assert not git_has_uncommitted_changes()
```

**Acceptance Criteria:**
- Add solver via YAML config only
- Index build script handles new solver automatically
- Query routing works without service modifications
- Demonstrated with hypothetical solver (e.g., ERF, REMORA)

---

## **7. Scope, Timeline & Gates**

### **7.1 Phase 1 Scope**

**Duration:** 6-7 weeks  
**Team Size:** 1 developer (primary), 1-2 domain experts (validation)  
**Deployment Target:** NERSC Perlmutter (native installation)

---

### **7.2 Gate-Based Development Plan**

#### **Gate 0: Foundation (Week 1)**

**Objective:** Validate core architecture works end-to-end with minimal functionality.

**Deliverables:**
- ✅ Config service operational (already 100% coverage)
- ✅ Single FAISS index built (PeleC case_names only)
- ✅ Basic embedding service (CBORG integration)
- ✅ Minimal workflow (1 node: architect only)
- ✅ CLI scaffolding (argparse structure)

**Success Criteria:**
```bash
# Can run agent with single index
pele-agent setup --prompt "premixed flame" --mode minimal

# Output:
#   Selected: PMF (from case_names index only)
#   No modifications planned yet
#   Confidence: 0.60 (low, only one index)
```

**Risks & Mitigations:**
- **Risk:** CBORG API changes
- **Mitigation:** OpenAI fallback implemented day 1

**Gate 0 Exit Criteria:**
- [ ] Config service passes all tests (100% coverage maintained)
- [ ] FAISS index builds successfully (<5 min for 45 cases)
- [ ] Embedding service retrieves top-5 cases
- [ ] CLI returns result (even if inaccurate)
- [ ] Tests pass (pytest runs without errors)

---

#### **Gate 1: Multi-Index Retrieval (Week 2)**

**Objective:** Implement modular 3-level architecture with all 82 indices.

**Deliverables:**
- ✅ Level 0: Physics taxonomy (4 sub-indices)
- ✅ Level 1: Documentation (7 sub-indices × 3 solvers = 21 indices)
- ✅ Level 2: Case metadata (6 sub-indices × 3 solvers = 18 indices)
- ✅ Weighted score combination
- ✅ Configurable index modes (testing vs production)

**Implementation Focus:**

**Level 0 Indices:**
```python
# database/builders/build_level0.py
def build_physics_taxonomy():
    """Build 4 Level 0 indices."""
    build_physics_regimes()        # Combustion, astrophysics, atmospheric
    build_solver_capabilities()    # Individual solver descriptions
    build_code_lineage()          # Evolution relationships
    build_cross_cutting_guidance() # Reports 1, 3, 4
```

**Level 1 Indices:**
```python
# database/builders/build_level1.py
def build_documentation_indices(solver: str):
    """Build 7 documentation indices per solver."""
    build_solver_readme(solver)
    build_problem_catalogs(solver)
    build_parameter_guides(solver)
    build_performance_data(solver)
    build_build_instructions(solver)
    build_case_inventory(solver)
    build_case_readmes(solver)
```

**Level 2 Indices:**
```python
# database/builders/build_level2.py
def build_case_metadata_indices(solver: str):
    """Build 6 case metadata indices per solver."""
    build_physics_descriptors(solver)
    build_grid_configurations(solver)
    build_git_metrics(solver)
    build_path_hierarchy(solver)
    build_chemistry_mechanisms(solver)
    build_performance_estimates(solver)
```

**Success Criteria:**
```bash
# All 82 indices built
pele-agent build-indices --mode testing --solvers PeleC,PeleLMeX,PeleMP

# Outputs:
# ✓ Level 0: 4 indices built (5.2 MB)
# ✓ PeleC: 13 indices built (68.4 MB)
# ✓ PeleLMeX: 13 indices built (71.2 MB)
# ✓ PeleMP: 13 indices built (65.8 MB)
# ✓ Total: 43 indices, 210.6 MB
# ⏱️  Build time: 28.4 minutes
```

**Gate 1 Exit Criteria:**
- [ ] 82 indices built successfully
- [ ] Total build time <30 minutes
- [ ] Total storage <500MB
- [ ] Query latency <10 seconds (all 82 indices searched)
- [ ] Weighted combination produces combined score
- [ ] Config system switches between testing/production modes

---

#### **Gate 2: Test Oracle & Baseline Accuracy (Week 3)**

**Objective:** Achieve ≥90% baseline selection accuracy against expert ground truth.

**Deliverables:**
- ✅ Test oracle (20 expert-curated cases)
- ✅ Automated testing harness
- ✅ Baseline accuracy measurement
- ✅ Per-case analysis (why correct/incorrect?)

**Test Oracle Structure:**
```yaml
# database/test_oracle/oracle_v1.yaml
version: "1.0"
curated_by: "Dr. Expert (Pele team)"
date: "2024-12-01"

test_cases:
  - id: "oracle_001"
    prompt: "Simulate premixed methane-air flame with detailed chemistry for turbulence study"
    expected_solver: "PeleLMeX"
    expected_case: "PeleLMeX/Exec/RegTests/FlameSheet"
    expected_variant: "inputs.3d"
    rationale: "Low-Mach turbulent DNS → PeleLMeX optimized, FlameSheet has turbulence model"
    difficulty: "easy"
    
  - id: "oracle_002"
    prompt: "Supersonic hydrogen combustion with shock-chemistry interaction"
    expected_solver: "PeleC"
    expected_case: "PeleC/Exec/Production/CavityFlame"
    expected_variant: "inputs.3d"
    rationale: "Supersonic + shocks → PeleC required, CavityFlame validated for H2"
    difficulty: "easy"
  
  - id: "oracle_010"
    prompt: "Turbulent non-premixed jet flame, need moderate resolution 128x128x256"
    expected_solver: "PeleLMeX"
    expected_case: "PeleLMeX/Exec/Production/JetFlame"
    expected_variant: "inputs.3d"
    rationale: "Non-premixed + turbulent + moderate Ma → PeleLMeX, JetFlame standard template"
    difficulty: "medium"
  
  - id: "oracle_018"
    prompt: "Premixed combustion but need to resolve shocks in unburned mixture"
    expected_solver: "PeleC"
    expected_case: "PeleC/Exec/RegTests/PMF"
    expected_variant: "inputs.3d"
    rationale: "Trick question: 'premixed' suggests PeleLMeX but 'shocks' requires PeleC"
    difficulty: "hard"

# 20 total cases:
#   - 8 easy (unambiguous physics)
#   - 8 medium (requires domain knowledge)
#   - 4 hard (edge cases, trick questions)
```

**Test Harness:**
```python
def run_oracle_validation():
    """Test agent against expert ground truth."""
    oracle = load_oracle("database/test_oracle/oracle_v1.yaml")
    results = []
    
    for test_case in oracle["test_cases"]:
        # Run agent
        plan = agent.create_plan(test_case["prompt"])
        
        # Check correctness
        solver_correct = plan.selected_solver == test_case["expected_solver"]
        case_correct = plan.selected_case == test_case["expected_case"]
        
        results.append({
            "id": test_case["id"],
            "difficulty": test_case["difficulty"],
            "solver_correct": solver_correct,
            "case_correct": case_correct,
            "confidence": plan.confidence_score
        })
    
    # Compute accuracy
    total_correct = sum(1 for r in results if r["case_correct"])
    accuracy = total_correct / len(results)
    
    # Breakdown by difficulty
    by_difficulty = {}
    for diff in ["easy", "medium", "hard"]:
        subset = [r for r in results if r["difficulty"] == diff]
        by_difficulty[diff] = sum(1 for r in subset if r["case_correct"]) / len(subset)
    
    return {
        "overall_accuracy": accuracy,
        "by_difficulty": by_difficulty,
        "results": results
    }
```

**Success Criteria:**
```python
results = run_oracle_validation()

assert results["overall_accuracy"] >= 0.90  # 18/20 correct

# Breakdown expectations
assert results["by_difficulty"]["easy"] >= 0.95    # 8/8 or 7/8
assert results["by_difficulty"]["medium"] >= 0.875  # 7/8
assert results["by_difficulty"]["hard"] >= 0.75     # 3/4
```

**Gate 2 Exit Criteria:**
- [ ] Test oracle complete (20 cases, expert-validated)
- [ ] Overall accuracy ≥90% (18/20)
- [ ] Easy cases ≥95% (7-8/8)
- [ ] Medium cases ≥87% (7/8)
- [ ] Hard cases ≥75% (3/4)
- [ ] Per-case analysis documented (why each failure occurred)

---

#### **Gate 3: Reviewer Service & Error Prevention (Week 4)**

**Objective:** Achieve ≥90% error detection rate for configuration mistakes.

**Deliverables:**
- ✅ Reviewer service implementation
- ✅ Synthetic error injection test suite
- ✅ Retry loop integration
- ✅ Actionable error messages

**Error Categories & Detection:**

```python
class ReviewerService:
    """Pre-execution validation service."""
    
    def validate(self, inputs_file: str) -> ValidationResult:
        """
        Validate inputs file for common errors.
        
        Returns ValidationResult with mode: "proceed" | "retry" | "fail"
        """
        errors = []
        
        # 1. Required parameters (100% detection)
        errors.extend(self._check_required_params(inputs_file))
        
        # 2. Syntax validation (95% detection)
        errors.extend(self._check_syntax(inputs_file))
        
        # 3. Physics inconsistencies (85% detection)
        errors.extend(self._check_physics(inputs_file))
        
        # 4. File dependencies (90% detection)
        errors.extend(self._check_dependencies(inputs_file))
        
        if not errors:
            return ValidationResult(mode="proceed", errors=[])
        elif self._is_recoverable(errors):
            return ValidationResult(mode="retry", errors=errors)
        else:
            return ValidationResult(mode="fail", errors=errors)
```

**Synthetic Error Test Suite:**
```python
synthetic_errors = [
    # Missing required parameter
    {
        "type": "missing_param",
        "inputs": """
            geometry.prob_lo = 0 0 0
            geometry.prob_hi = 1 1 1
            # Missing: amr.n_cell
        """,
        "expected_error": "Missing required parameter: amr.n_cell"
    },
    
    # Invalid syntax
    {
        "type": "invalid_syntax",
        "inputs": """
            amr.n_cell = 256^3  # Wrong! Should be: 256 256 256
        """,
        "expected_error": "Invalid syntax: amr.n_cell (use spaces, not ^)"
    },
    
    # Physics inconsistency
    {
        "type": "physics_conflict",
        "inputs": """
            eb2.geom_type = sphere
            geometry.is_periodic = 1 1 1  # Can't have EB + all-periodic
        """,
        "expected_error": "EB geometry requires at least one non-periodic direction"
    },
    
    # Missing file
    {
        "type": "missing_file",
        "inputs": """
            pelec.chem_file = nonexistent.yaml
        """,
        "expected_error": "Chemistry file not found: nonexistent.yaml"
    },
    
    # ... 20 total synthetic errors
]

def test_error_detection():
    detected = 0
    for error_case in synthetic_errors:
        result = reviewer.validate(error_case["inputs"])
        if result.mode in ["retry", "fail"]:
            detected += 1
    
    detection_rate = detected / len(synthetic_errors)
    assert detection_rate >= 0.90  # 18/20
```

**Gate 3 Exit Criteria:**
- [ ] Reviewer service implemented
- [ ] Error detection rate ≥90% (18/20 synthetic errors)
- [ ] False positive rate <5% (don't block valid configs)
- [ ] Actionable messages (suggest fix, not just "error")
- [ ] Retry loop functional (max 3 attempts)
- [ ] Error context propagated to architect on retry

---

#### **Gate 4: FOAM-Agent Benchmark (Week 5)**

**Objective:** Achieve ≥60% match/exceed performance on FOAM-agent benchmark prompts.

**Deliverables:**
- ✅ Document retrieval service
- ✅ 20 FOAM benchmark prompts
- ✅ Comparative results (Pele vs FOAM)
- ✅ Analysis of strengths/weaknesses

**FOAM Benchmark Prompts:**
```yaml
# database/foam_benchmark/prompts.yaml
foam_benchmarks:
  - id: "foam_001"
    prompt: "Turbulent flow over backward-facing step, k-epsilon model"
    foam_selection: "simpleFoam/backwardFacingStep"
    pele_expected: "incflo/BackwardStep"  # If incflo implemented
    difficulty: "easy"
  
  - id: "foam_007"
    prompt: "Non-premixed methane jet flame with detailed chemistry, SST turbulence"
    foam_selection: "reactingFoam/jetFlame"
    pele_expected: "PeleLMeX/Exec/Production/JetFlame"
    difficulty: "medium"
  
  - id: "foam_015"
    prompt: "Spray combustion diesel injection 120 bar, Lagrangian particles"
    foam_selection: "sprayFoam/dieselInjection"
    pele_expected: "PeleMP/Exec/Production/SprayJet"
    difficulty: "medium"
  
  # 20 total prompts covering:
  #   - 8 non-reacting CFD (may not apply to Pele Phase 1)
  #   - 8 reacting flows (Pele strong suit)
  #   - 4 multiphase (PeleMP cases)
```

**Document Retrieval Integration:**
```python
def paper_validator_node(state: AgentState) -> AgentState:
    """
    Validate selection against published FOAM paper.
    
    Only runs in --mode validation.
    """
    if not state.get("validation_mode"):
        return state
    
    doc_service = DocumentRetrievalService()
    
    # Fetch FOAM-agent paper
    paper = doc_service.retrieve_paper_metadata(
        title="FOAM-agent: Simulation Setup Automation",
        arxiv_id="2103.12345"  # Hypothetical
    )
    
    # Extract FOAM's selection for this prompt
    foam_case = doc_service.extract_simulation_details(paper["pdf_path"])
    
    # Compare physics alignment
    report = doc_service.validate_against_paper(
        case=state["selected_case"],
        paper_metadata=foam_case
    )
    
    return {
        **state,
        "foam_comparison": {
            "foam_case": foam_case["case_name"],
            "pele_case": state["selected_case"],
            "physics_aligned": report.physics_match,
            "confidence": report.similarity_score
        }
    }
```

**Scoring Methodology:**
```python
def score_foam_benchmark(results):
    """
    Score: match (1.0), better (1.2), worse (0.0), N/A (exclude).
    """
    scores = []
    
    for result in results:
        if result["pele_expected"] is None:
            # N/A (prompt not applicable to Pele, e.g., non-reacting incflo)
            continue
        
        if result["pele_selected"] == result["pele_expected"]:
            if result["physics_aligned_to_foam"]:
                scores.append(1.0)  # Match
            else:
                scores.append(0.5)  # Correct Pele case, but different from FOAM
        else:
            scores.append(0.0)  # Wrong case
    
    return sum(scores) / len(scores) if scores else 0.0
```

**Success Criteria:**
```python
foam_results = run_foam_benchmark()

# ≥60% on applicable prompts
assert foam_results["score"] >= 0.60  # 12/20 or better

# Breakdown by category
assert foam_results["by_category"]["reacting_flows"] >= 0.75  # Pele strong suit
assert foam_results["by_category"]["multiphase"] >= 0.50      # PeleMP cases
```

**Gate 4 Exit Criteria:**
- [ ] Document retrieval service operational
- [ ] 20 FOAM prompts tested
- [ ] Overall score ≥60% (12/20 applicable prompts)
- [ ] Reacting flow category ≥75% (Pele strength)
- [ ] Analysis document: where Pele excels vs FOAM

---

#### **Gate 5: Plot Comparison Validation (Week 5, cont.)**

**Objective:** Validate plot outputs match published figures for 3 reproduced cases.

**Deliverables:**
- ✅ Plot similarity metric (SSIM)
- ✅ 3 published cases reproduced
- ✅ Side-by-side plot comparison
- ✅ Quantitative similarity scores

**Plot Comparison Implementation:**
```python
from skimage.metrics import structural_similarity as ssim
from skimage import io

def compare_plots(reference_path: Path, generated_path: Path) -> float:
    """
    Compute SSIM between reference and generated plots.
    
    Returns similarity score 0-1 (1 = identical).
    """
    ref_img = io.imread(reference_path, as_gray=True)
    gen_img = io.imread(generated_path, as_gray=True)
    
    # Resize to same dimensions if needed
    if ref_img.shape != gen_img.shape:
        from skimage.transform import resize
        gen_img = resize(gen_img, ref_img.shape, anti_aliasing=True)
    
    score = ssim(ref_img, gen_img)
    return score
```

**Test Cases:**
```python
reproduced_cases = [
    {
        "paper": "arxiv:1234.5678",
        "figure": "Figure 3: Premixed flame temperature profile",
        "pele_case": "PeleLMeX/FlameSheet",
        "reference_plot": "database/foam_benchmark/fig3_reference.png",
        "generated_plot": "run_*/temperature_profile.png",
        "expected_ssim": ">0.80"  # High similarity expected
    },
    
    {
        "paper": "arxiv:2103.XXXX",
        "figure": "Figure 5: Velocity magnitude contour",
        "pele_case": "PeleC/CavityFlame",
        "reference_plot": "database/foam_benchmark/fig5_reference.png",
        "generated_plot": "run_*/velocity_contour.png",
        "expected_ssim": ">0.75"  # Moderate similarity (different viz tools)
    },
    
    {
        "paper": "arxiv:1905.YYYY",
        "figure": "Figure 7: Spray distribution",
        "pele_case": "PeleMP/SprayJet",
        "reference_plot": "database/foam_benchmark/fig7_reference.png",
        "generated_plot": "run_*/spray_distribution.png",
        "expected_ssim": ">0.70"  # Lower (stochastic spray)
    }
]

def test_plot_similarity():
    results = []
    
    for case in reproduced_cases:
        # Run simulation (user does this manually)
        # ... generate plots ...
        
        # Compare
        similarity = compare_plots(
            case["reference_plot"],
            case["generated_plot"]
        )
        
        results.append({
            "case": case["pele_case"],
            "paper": case["paper"],
            "similarity": similarity,
            "threshold": float(case["expected_ssim"].replace(">", ""))
        })
    
    # All cases meet threshold
    assert all(r["similarity"] >= r["threshold"] for r in results)
```

**Gate 5 Exit Criteria:**
- [ ] SSIM implementation working
- [ ] 3 published cases reproduced
- [ ] All plot similarities ≥ thresholds
- [ ] Visual inspection confirms alignment
- [ ] Documentation: reproduction methodology

---

#### **Gate 6: Ablation Study & Production Config (Week 6)**

**Objective:** Complete ablation testing, determine production index configuration.

**Deliverables:**
- ✅ Ablation test harness
- ✅ Results for all 82 indices
- ✅ Contribution analysis
- ✅ Production config decision
- ✅ Research paper draft

**Ablation Execution:**
```python
def run_full_ablation():
    """
    Test all index combinations systematically.
    """
    results = {}
    
    # Level 0 ablation (4 indices)
    results["level_0"] = ablate_level_0()
    
    # Level 1 ablation (7 indices × 3 solvers = 21)
    for solver in ["PeleC", "PeleLMeX", "PeleMP"]:
        results[f"level_1_{solver}"] = ablate_level_1(solver)
    
    # Level 2 ablation (6 indices × 3 solvers = 18)
    for solver in ["PeleC", "PeleLMeX", "PeleMP"]:
        results[f"level_2_{solver}"] = ablate_level_2(solver)
    
    # Cross-level ablation
    results["cross_level"] = ablate_cross_level()
    
    # Save comprehensive results
    with open("ablation_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return results

def ablate_level_2(solver: str):
    """Example: Level 2 ablation for one solver."""
    indices = [
        "physics_descriptors",
        "grid_configurations",
        "git_metrics",
        "path_hierarchy",
        "chemistry_mechanisms",
        "performance_estimates"
    ]
    
    results = {}
    
    # Baseline (all indices)
    results["all"] = test_accuracy(solver, enabled_indices=indices)
    
    # Remove one at a time
    for idx in indices:
        enabled = [i for i in indices if i != idx]
        accuracy = test_accuracy(solver, enabled_indices=enabled)
        contribution = results["all"] - accuracy
        
        results[f"no_{idx}"] = {
            "accuracy": accuracy,
            "contribution": contribution,
            "significant": contribution >= 0.05  # ≥5% impact
        }
    
    # Minimal (top 2 only)
    top_contributors = sorted(
        [(idx, results[f"no_{idx}"]["contribution"]) for idx in indices],
        key=lambda x: x[1],
        reverse=True
    )[:2]
    
    minimal_indices = [idx for idx, _ in top_contributors]
    results["minimal"] = test_accuracy(solver, enabled_indices=minimal_indices)
    
    return results
```

**Decision Tree:**
```python
def decide_production_config(ablation_results):
    """
    Use ablation to choose production index structure.
    
    Scenarios:
      A: All indices contribute (≥5%) → Keep all 82
      B: 60% contribute → Merge low-contributors (→ 38 indices)
      C: <50% contribute → Aggressive merge (→ 25 indices)
    """
    # Count significant contributors
    significant = []
    for level_results in ablation_results.values():
        for test_name, test_result in level_results.items():
            if "no_" in test_name and test_result.get("significant"):
                significant.append(test_name.replace("no_", ""))
    
    contribution_rate = len(significant) / 82
    
    if contribution_rate > 0.70:
        return "scenario_a_keep_all"
    elif contribution_rate > 0.50:
        return "scenario_b_selective_merge"
    else:
        return "scenario_c_aggressive_merge"
```

**Gate 6 Exit Criteria:**
- [ ] All 82 indices tested
- [ ] Contribution analysis complete
- [ ] High-contributors identified (≥5% accuracy gain)
- [ ] Production config decided (Scenario A, B, or C)
- [ ] Research paper draft: ablation methodology section

---

### **7.3 Timeline Summary**

| Week | Gate | Focus | Deliverables |
|------|------|-------|--------------|
| **1** | Gate 0 | Foundation | Config, single index, CLI scaffolding |
| **2** | Gate 1 | Multi-Index | 82 indices built, weighted combination |
| **3** | Gate 2 | Accuracy | Test oracle, ≥90% baseline accuracy |
| **4** | Gate 3 | Reviewer | Error detection ≥90%, retry loop |
| **5** | Gate 4-5 | Validation | FOAM benchmark ≥60%, plot comparison |
| **6** | Gate 6 | Ablation | Index optimization, production config |
| **7** | Gate 7 (optional) | Polish | Documentation, user onboarding |

**Critical Path:**
```
Gate 0 (1 week) → Gate 1 (1 week) → Gate 2 (1 week) → 
Gate 3 (1 week) → Gate 4-5 (1 week) → Gate 6 (1 week)

Total: 6 weeks (minimum)
Buffer: +1 week for polish/contingency
Total: 7 weeks
```

---

---

# **AMReXAgent: Product & Technical Specification**
## **Phase 4: Risk Assessment & Technical Architecture**

---

## **8. Risk Assessment**

### **8.1 Technical Risks**

#### **Risk T1: FAISS Index Performance Degradation**

**Description:**  
As number of cases grows (45 → 100+ per solver), FAISS query latency may exceed 10-second target.

**Probability:** Medium (30%)  
**Impact:** High (user experience degradation)

**Indicators:**
- Query latency >5 seconds on 82 indices
- Linear scaling (2× cases → 2× latency)
- Memory usage >16GB on Perlmutter login node

**Mitigation Strategies:**

**Pre-Emptive:**
```python
# 1. Product quantization for large indices
from faiss import IndexIVFPQ

def build_optimized_index(documents, large_corpus=True):
    """Use PQ for >10K documents."""
    if len(documents) > 10000 and large_corpus:
        # Product quantization (8-bit codes)
        index = IndexIVFPQ(d=768, nlist=100, M=8, nbits=8)
    else:
        # Standard flat index
        index = IndexFlatL2(d=768)
    
    return index

# 2. Index caching with mmap
index = faiss.read_index("pelec_physics.faiss", faiss.IO_FLAG_MMAP)
```

**Reactive:**
- Hierarchical filtering: Reduce corpus before FAISS search
- Merge low-contribution indices (from ablation results)
- Upgrade to HNSW indices (approximate nearest neighbors)

**Contingency:**
- If latency >10s persists: Gate 1 fails, switch to production config (25 indices) immediately
- Document latency requirements relaxed to 20s as acceptable

**Owner:** Development team  
**Review Cadence:** Weekly during Gate 1-2

---

#### **Risk T2: Embedding API Outages**

**Description:**  
CBORG or OpenAI API unavailable during critical testing (Gate 2, Gate 6).

**Probability:** Low (10%)  
**Impact:** High (blocks testing, delays gates)

**Indicators:**
- HTTP 503 errors from CBORG
- OpenAI rate limit exceeded (429 errors)
- >1 hour outage during working hours

**Mitigation Strategies:**

**Pre-Emptive:**
```python
class RobustEmbeddingService:
    """Multi-tier fallback for embeddings."""
    
    def embed(self, text: str) -> np.ndarray:
        try:
            return self._embed_cborg(text)
        except CBORGError as e:
            logger.warning(f"CBORG failed: {e}, trying OpenAI")
            try:
                return self._embed_openai(text)
            except OpenAIError as e:
                logger.warning(f"OpenAI failed: {e}, using cached embeddings")
                return self._embed_cached(text)
    
    def _embed_cached(self, text: str) -> np.ndarray:
        """Use pre-computed embeddings from last successful build."""
        cache_path = Path("database/embedding_cache.pkl")
        if cache_path.exists():
            cache = pickle.load(cache_path.open("rb"))
            if text in cache:
                return cache[text]
        raise EmbeddingServiceUnavailable("All APIs down, no cache available")
```

**Reactive:**
- Pre-build all embeddings during off-hours (cache everything)
- Use local sentence-transformers as tertiary fallback
- Delay gate testing by 24 hours if outage detected

**Contingency:**
- Critical path blocker: Pause gate testing until APIs restored
- Use cached embeddings for all testing (may be slightly stale)

**Owner:** Development team  
**Trigger:** First API failure during gate testing

---

#### **Risk T3: Test Oracle Invalidity**

**Description:**  
Expert-curated test oracle contains errors or becomes outdated as code evolves.

**Probability:** Medium (25%)  
**Impact:** Medium (inaccurate accuracy metrics, false gate passes/fails)

**Indicators:**
- Ablation results show random variations (no clear pattern)
- Expert reviewers disagree with oracle selections
- Code changes invalidate expected cases (e.g., case renamed)

**Mitigation Strategies:**

**Pre-Emptive:**
```yaml
# Oracle version control
oracle_metadata:
  version: "1.0"
  created: "2024-12-01"
  validated_by: ["Dr. Expert1", "Dr. Expert2"]
  last_review: "2024-12-01"
  code_snapshot:
    PeleC_commit: "abc123def"
    PeleLMeX_commit: "456789ghi"
  
# Regression testing
regression_tests:
  - oracle_case: "oracle_001"
    last_passing_accuracy: 0.95
    alert_threshold: 0.80  # Alert if drops below 80%
```

**Validation Process:**
```python
def validate_oracle():
    """Cross-validation with multiple experts."""
    oracle = load_oracle()
    
    # 1. Check if expected cases still exist
    for case in oracle["test_cases"]:
        path = Path(case["expected_case"])
        if not path.exists():
            logger.error(f"Oracle case missing: {case['id']} → {path}")
    
    # 2. Run inter-rater reliability
    expert_annotations = collect_expert_annotations(oracle["test_cases"])
    agreement = compute_fleiss_kappa(expert_annotations)
    
    if agreement < 0.80:
        logger.warning("Low expert agreement, oracle may be ambiguous")
    
    return agreement
```

**Reactive:**
- Monthly oracle review with domain experts
- Flag cases with <70% expert agreement for re-annotation
- Version oracle (v1.0, v1.1) to track changes

**Contingency:**
- If oracle proven invalid: Rebuild from scratch (3-5 days)
- Use subset of high-confidence cases (10/20) for interim testing

**Owner:** Domain experts (validation), development team (tooling)  
**Review Cadence:** After Gate 2, monthly thereafter

---

#### **Risk T4: LLM Non-Determinism Breaking Reproducibility**

**Description:**  
GPT-4 modification planning produces different results for same query, failing reproducibility tests.

**Probability:** Medium (35%)  
**Impact:** Low (doesn't affect core RAG accuracy, only modification planning)

**Indicators:**
- Same query → different modifications across runs
- Test oracle cases fail intermittently (not consistent)
- Ablation results vary by >5% between runs

**Mitigation Strategies:**

**Pre-Emptive:**
```python
# Seed LLM for testing
class DeterministicArchitect:
    def create_plan(self, prompt: str, testing_mode: bool = False):
        if testing_mode:
            llm_config = {
                "temperature": 0.0,  # No randomness
                "seed": 42,          # Fixed seed
                "top_p": 1.0         # No nucleus sampling
            }
        else:
            llm_config = {
                "temperature": 0.3,  # Slight creativity for production
            }
        
        return self.llm.generate(prompt, **llm_config)
```

**Separation of Concerns:**
```python
# Make core retrieval deterministic
def test_retrieval_only():
    """Test FAISS retrieval without LLM."""
    cases = embedding_service.search("premixed methane")
    # This is 100% deterministic
    assert cases[0].name == "PMF"

# Test LLM separately (allow non-determinism)
def test_modification_planning():
    """Test LLM planning with fixed seed."""
    plan = architect.create_plan("...", testing_mode=True)
    # This is deterministic with seed
    assert plan.modifications[0] == ("amr.n_cell", "256 256 256")
```

**Reactive:**
- If reproducibility fails: Document LLM variance as acceptable
- Focus accuracy testing on case selection (retrieval), not modifications
- Use temperature=0 for all gate testing

**Contingency:**
- Core hypothesis (RAG accuracy) unaffected by LLM variance
- Accept <100% reproducibility for modification planning
- Document in paper: "RAG retrieval deterministic, planning has controlled variance"

**Owner:** Development team  
**Acceptance:** Non-critical risk (doesn't block gates)

---

### **8.2 Research Risks**

#### **Risk R1: FOAM-Agent Benchmark Not Representative**

**Description:**  
FOAM-agent prompts may not transfer well to Pele (different physics domains), making ≥60% target invalid.

**Probability:** Medium (30%)  
**Impact:** Medium (Gate 4 metric questioned, but doesn't invalidate core research)

**Indicators:**
- >50% of FOAM prompts N/A to Pele (e.g., all non-reacting CFD)
- Low physics overlap (FOAM focuses on industrial flows, Pele on combustion)
- Expert review: "This comparison doesn't make sense"

**Mitigation Strategies:**

**Pre-Emptive:**
```python
# Categorize FOAM prompts by applicability
foam_categories = {
    "applicable": [  # Direct Pele equivalents
        "reacting flows",
        "multiphase combustion"
    ],
    "partial": [     # Some overlap
        "turbulent non-reacting (if incflo implemented)"
    ],
    "not_applicable": [  # No Pele equivalent
        "free surface flows",
        "volume-of-fluid methods"
    ]
}

# Report only on applicable subset
def score_foam_benchmark(results):
    applicable = [r for r in results if r["category"] == "applicable"]
    score = sum(r["match"] for r in applicable) / len(applicable)
    
    return {
        "applicable_score": score,
        "applicable_count": len(applicable),
        "total_prompts": len(results)
    }
```

**Alternative Metrics:**
- If <10 applicable prompts: Lower threshold to ≥50% (5/10)
- Add Pele-specific benchmark (20 combustion cases from papers)
- Compare to expert baseline: "How would expert select without agent?"

**Reactive:**
- Gate 4 discussion: Re-scope benchmark to applicable prompts only
- Document limitations: "FOAM comparison valid for reacting flows only"

**Contingency:**
- If FOAM benchmark deemed invalid: Replace Gate 4 with Pele-specific paper reproduction (10 combustion cases from literature)
- Still demonstrates generalizability, just different domain

**Owner:** Research lead  
**Review Trigger:** After initial FOAM prompt analysis (before Gate 4)

---

#### **Risk R2: Ablation Study Shows All Indices Necessary**

**Description:**  
Ablation testing reveals no indices can be merged (all contribute ≥5%), requiring 82 indices in production.

**Probability:** Medium (40%)  
**Impact:** Low (acceptable outcome, just more complex deployment)

**Indicators:**
- Every index removal drops accuracy ≥5%
- No clear low-contributors identified
- Production config = testing config (82 indices)

**Mitigation Strategies:**

**Pre-Emptive:**
```python
# Design for this outcome
production_configs = {
    "scenario_a_keep_all": {
        "indices": 82,
        "build_time": "<30 min",
        "query_latency": "<10 sec",
        "storage": "<500 MB"
    }
}

# All NFRs already scoped for 82 indices
assert all([
    build_time < 30 * 60,
    query_latency < 10,
    storage < 500 * 1024 * 1024
])
```

**Research Value:**
```text
Scenario A is valid research outcome:
  "Multi-index RAG requires granular metadata decomposition.
   No single index type dominates; combination of all 6 metadata
   types (physics, grid, git, path, chemistry, performance)
   necessary for ≥90% accuracy."
```

**Reactive:**
- Document in paper: Full complexity required for high accuracy
- Optimize performance (PQ, HNSW) instead of reducing indices
- Highlight as contribution: "Quantified necessity of each metadata type"

**Contingency:**
- Not a failure—just a different research finding
- Production deployment handles 82 indices (already planned)

**Owner:** Research lead  
**Acceptance:** This is an acceptable outcome

---

#### **Risk R3: Accuracy Plateau Below 90%**

**Description:**  
System achieves only 80-85% accuracy on test oracle despite all optimizations, failing Gate 2.

**Probability:** Low (15%)  
**Impact:** High (core hypothesis unproven, gates blocked)

**Indicators:**
- Stuck at 16-17/20 correct (80-85%)
- Weight tuning doesn't improve beyond 85%
- Hard cases consistently fail (0/4 correct)

**Mitigation Strategies:**

**Pre-Emptive:**
```python
# Analyze failure modes proactively
def analyze_failures(results):
    """Categorize why cases fail."""
    failures = [r for r in results if not r["correct"]]
    
    categories = {
        "ambiguous_query": [],      # User prompt unclear
        "missing_metadata": [],     # Case lacks critical info
        "physics_edge_case": [],    # Trick questions
        "index_limitation": []      # FAISS retrieval issue
    }
    
    for failure in failures:
        category = classify_failure(failure)
        categories[category].append(failure)
    
    # Actionable insights
    if len(categories["ambiguous_query"]) > 2:
        logger.info("Need query clarification mechanism")
    if len(categories["missing_metadata"]) > 2:
        logger.info("Need to enrich case metadata")
    
    return categories
```

**Hybrid Approach:**
```python
# If pure RAG plateaus, add lightweight rules
class HybridArchitect:
    def create_plan(self, prompt: str):
        # 1. RAG retrieval (primary)
        cases = self.embedding_service.search(prompt)
        
        # 2. Rule-based filtering (secondary)
        if "shock" in prompt.lower() and "supersonic" in prompt.lower():
            # Filter to PeleC only (hard rule)
            cases = [c for c in cases if c.solver == "PeleC"]
        
        # 3. LLM final selection
        best_case = self.llm.select_best(prompt, cases)
        
        return best_case
```

**Reactive:**
- If plateau at 85%: Analyze failure categories
- Add targeted fixes (e.g., query clarification for ambiguous prompts)
- Accept 85% if failures are inherently ambiguous

**Contingency:**
- **Option 1:** Lower gate threshold to ≥85% (17/20) with justification
- **Option 2:** Hybrid RAG+rules approach (still proves RAG as primary)
- **Option 3:** Redesign test oracle to exclude inherently ambiguous cases

**Owner:** Development team, research lead  
**Review Trigger:** If accuracy <87% after Gate 2 attempt 1

---

### **8.3 Deployment Risks**

#### **Risk D1: NERSC Perlmutter Access Issues**

**Description:**  
Perlmutter login node restrictions (CPU limits, memory caps) prevent index building or queries.

**Probability:** Low (10%)  
**Impact:** High (blocks deployment, requires alternative platform)

**Indicators:**
- Process killed during index build (OOM or CPU limit)
- Shared login node too slow (>5 min queue to run agent)
- Filesystem quota exceeded (>500GB for all user data + indices)

**Mitigation Strategies:**

**Pre-Emptive:**
```bash
# Test resource limits early
#!/bin/bash
# test_perlmutter_limits.sh

# 1. Memory limit
echo "Testing memory limit..."
python -c "import numpy as np; x = np.zeros((10000, 10000))" || echo "FAIL: Memory limit hit"

# 2. CPU time limit
echo "Testing CPU limit..."
timeout 600 python build_indices.py || echo "FAIL: CPU time limit"

# 3. Disk quota
echo "Testing disk quota..."
du -sh database/faiss || echo "FAIL: Cannot check disk usage"
```

**Alternative Platforms:**
```yaml
deployment_options:
  primary: "NERSC Perlmutter login node"
  backup: "Perlmutter compute node (interactive job)"
  tertiary: "Local workstation (developer machine)"
  last_resort: "Cloud VM (AWS/GCP)"
```

**Reactive:**
- If login node insufficient: Submit index build as batch job
- If filesystem quota: Use /pscratch instead of $HOME
- If Perlmutter unavailable: Deploy to developer workstation temporarily

**Contingency:**
- Gate testing can proceed on local machine
- Production deployment deferred to Phase 2 if Perlmutter blocked

**Owner:** Development team  
**Test Date:** Week 1 (Gate 0)

---

#### **Risk D2: User Adoption Failure**

**Description:**  
Initial user cohort (3-5 researchers) doesn't use the tool, citing complexity or lack of trust.

**Probability:** Medium (25%)  
**Impact:** Medium (limits real-world validation, doesn't block gates)

**Indicators:**
- <5 agent runs per week after deployment
- User feedback: "Too complicated" or "Don't trust it"
- Users revert to manual setup after initial trial

**Mitigation Strategies:**

**Pre-Emptive:**
```markdown
# User Onboarding Checklist

Week 1: Introduction
- [ ] 30-min demo session (screen share)
- [ ] Walk through 3 example queries
- [ ] Show explainability features
- [ ] Explain when NOT to use agent

Week 2: Hands-On
- [ ] User brings their own simulation idea
- [ ] Agent generates plan, user reviews
- [ ] Expert validates agent selection
- [ ] User runs simulation (if confident)

Week 3: Feedback
- [ ] Exit interview: What worked? What didn't?
- [ ] Collect failure cases for oracle
- [ ] Measure: time saved vs manual setup
```

**Trust-Building:**
- **Explainability:** Show why each case selected (per-index scores)
- **Expert validation:** "Dr. Expert agrees with this selection"
- **Comparison:** "This is the same case Dr. Expert used for similar setup"
- **Safety:** Reviewer catches errors → builds confidence

**Reactive:**
- If low adoption: Schedule 1-on-1 sessions with each user
- Gather qualitative feedback, iterate on UX
- Highlight success stories: "User X saved 6 hours"

**Contingency:**
- Phase 1 success doesn't require high adoption
- Gates 0-6 validate technical capability
- User adoption is Phase 2 goal (broader rollout)

**Owner:** User experience lead (if exists), research lead  
**Review:** After 2 weeks of deployment

---

### **8.4 Risk Summary Matrix**

| Risk ID | Category | Probability | Impact | Mitigation Priority | Owner |
|---------|----------|-------------|--------|---------------------|-------|
| T1 | FAISS Performance | Medium | High | **High** | Dev team |
| T2 | API Outages | Low | High | **Medium** | Dev team |
| T3 | Oracle Invalidity | Medium | Medium | **High** | Experts + Dev |
| T4 | LLM Non-Determinism | Medium | Low | Low | Dev team |
| R1 | FOAM Benchmark | Medium | Medium | **Medium** | Research lead |
| R2 | All Indices Necessary | Medium | Low | Low | Research lead |
| R3 | Accuracy Plateau | Low | High | **High** | Dev + Research |
| D1 | Perlmutter Access | Low | High | **Medium** | Dev team |
| D2 | User Adoption | Medium | Medium | Low | UX/Research lead |

**Critical Risks (High Priority):**
- **T1 (FAISS Performance):** Test early (Gate 1), optimize proactively
- **T3 (Oracle Invalidity):** Cross-validate with multiple experts before Gate 2
- **R3 (Accuracy Plateau):** Failure analysis built into testing workflow

---

---

# **PART 2: TECHNICAL SPECIFICATION**

---

## **9. System Architecture Overview**

### **9.1 High-Level Architecture**

**AMReXAgent** is a stateful LangGraph application implementing a 3-level multi-index RAG pipeline for simulation configuration automation.

```
┌─────────────────────────────────────────────────────────────────┐
│                       AMReXAgent System                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐                                                │
│  │  CLI Tool   │  pele-agent setup --prompt "..."               │
│  └──────┬──────┘                                                │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │            LangGraph Workflow (Stateful)                 │  │
│  │                                                          │  │
│  │  ┌────────────┐   ┌──────────┐   ┌──────────┐         │  │
│  │  │  Solver    │──▶│ Architect│──▶│ Reviewer │         │  │
│  │  │  Selector  │   │          │   │          │         │  │
│  │  └────────────┘   └──────────┘   └────┬─────┘         │  │
│  │        │                              │                 │  │
│  │        │                              ▼                 │  │
│  │        │                         ┌─────────┐           │  │
│  │        │                         │Decision?│           │  │
│  │        │                         └────┬────┘           │  │
│  │        │                              │                 │  │
│  │        │              ┌───────────────┼───────────┐   │  │
│  │        │              │               │           │   │  │
│  │        │              ▼               ▼           ▼   │  │
│  │        │         ┌────────┐     ┌────────┐  ┌──────┐│  │
│  │        │         │ Retry  │     │Proceed │  │ Fail ││  │
│  │        │         │(back)  │     │        │  │      ││  │
│  │        │         └────────┘     └───┬────┘  └──────┘│  │
│  │        │                            │                 │  │
│  │        │                            ▼                 │  │
│  │        │                    ┌──────────────┐        │  │
│  │        │                    │Paper Validator│        │  │
│  │        │                    │(validation    │        │  │
│  │        │                    │ mode only)    │        │  │
│  │        │                    └───────┬───────┘        │  │
│  │        │                            │                 │  │
│  │        │                            ▼                 │  │
│  │        │                    ┌──────────────┐        │  │
│  │        │                    │Input Writer  │        │  │
│  │        │                    └──────────────┘        │  │
│  └─────────────────────────────────────────────────────┘  │
│         │                                                  │
│         ▼                                                  │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Service Layer                           │ │
│  │                                                      │ │
│  │  ┌──────────────────┐  ┌─────────────────┐        │ │
│  │  │MultiIndex        │  │ArchitectService │        │ │
│  │  │EmbeddingService  │  │                 │        │ │
│  │  └────────┬─────────┘  └─────────────────┘        │ │
│  │           │                                         │ │
│  │           ▼                                         │ │
│  │  ┌──────────────────┐  ┌─────────────────┐        │ │
│  │  │AMReXCasesService │  │ReviewerService  │        │ │
│  │  └──────────────────┘  └─────────────────┘        │ │
│  │                                                      │ │
│  │  ┌──────────────────┐  ┌─────────────────┐        │ │
│  │  │DocumentRetrieval │  │ConfigService    │        │ │
│  │  │Service           │  │                 │        │ │
│  │  └──────────────────┘  └─────────────────┘        │ │
│  └─────────────────────────────────────────────────────┘ │
│         │                                                  │
│         ▼                                                  │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Data Layer                              │ │
│  │                                                      │ │
│  │  ┌──────────────────────────────────────────┐      │ │
│  │  │  FAISS Indices (82 in testing mode)      │      │ │
│  │  │                                          │      │ │
│  │  │  Level 0: Physics Taxonomy (4 indices)   │      │ │
│  │  │  Level 1: Documentation (21 indices)     │      │ │
│  │  │  Level 2: Case Metadata (18 indices)     │      │ │
│  │  └──────────────────────────────────────────┘      │ │
│  │                                                      │ │
│  │  ┌──────────────────────────────────────────┐      │ │
│  │  │  Repository Metadata                      │      │ │
│  │  │                                          │      │ │
│  │  │  - Git histories                         │      │ │
│  │  │  - Case structures                        │      │ │
│  │  │  - Chemistry mechanisms                   │      │ │
│  │  └──────────────────────────────────────────┘      │ │
│  │                                                      │ │
│  │  ┌──────────────────────────────────────────┐      │ │
│  │  │  Curated Reports                          │      │ │
│  │  │                                          │      │ │
│  │  │  - report1-9.txt                         │      │ │
│  │  │  - FOAM benchmark data                    │      │ │
│  │  │  - Test oracle                            │      │ │
│  │  └──────────────────────────────────────────┘      │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### **9.2 Design Principles**

**1. Modular 3-Level RAG**
- **Level 0:** Physics taxonomy (which solver?)
- **Level 1:** Documentation (what guidance?)
- **Level 2:** Case metadata (which specific case?)
- Each level independently testable (ablation support)

**2. Stateful Workflow (LangGraph)**
- All state in `AgentState` TypedDict
- Nodes are pure functions: `(State) → State`
- Conditional routing based on reviewer decision
- Retry loop with error context propagation

**3. Service Layer Separation**
- Services are stateless, reusable
- Dependency injection (mockable for tests)
- Clear responsibilities (SRP: Single Responsibility Principle)

**4. Data Layer Abstraction**
- FAISS indices as black boxes
- Index build/query separated from business logic
- Easy to swap index backend (e.g., FAISS → Weaviate)

**5. Extensibility via Configuration**
- New solvers added through YAML config
- Index modes (testing/production) toggled without code changes
- Ablation testing via enabled_indices parameter

---

## **10. Multi-Index RAG Design**

### **10.1 Level 0: Physics Taxonomy**

**Purpose:** Select which solver family and specific codes to search.

**Architecture:**

```python
class Level0PhysicsTaxonomy:
    """
    Level 0: Physics regime identification and solver selection.
    
    Indices (4 sub-indices for ablation):
      1. physics_regimes/ - Family descriptions (combustion, astrophysics, etc.)
      2. solver_capabilities/ - Individual solver details
      3. code_lineage/ - Evolution relationships (Castro→Nyx, etc.)
      4. cross_cutting_guidance/ - Reports 1, 3, 4 (decision frameworks)
    
    Output: List of (solver_name, confidence_score) tuples
    """
    
    def __init__(self, config: PeleAgentConfig):
        self.config = config
        self.indices = self._load_indices()
        self.weights = config.level0_weights  # From YAML
    
    def search(
        self,
        query: str,
        k: int = 2,
        enabled_indices: Optional[List[str]] = None
    ) -> List[Tuple[str, float]]:
        """
        Query Level 0 indices with weighted combination.
        
        Parameters
        ----------
        query : str
            User's natural language prompt.
        k : int
            Number of solver candidates to return.
        enabled_indices : list of str, optional
            For ablation testing. If None, use all 4 indices.
        
        Returns
        -------
        list of (str, float)
            [(solver_name, confidence_score), ...]
            e.g., [("PeleLMeX", 0.92), ("PeleC", 0.60)]
        """
        # Determine which indices to query
        indices_to_use = enabled_indices or self.indices.keys()
        
        # Query each index
        results = {}
        for index_name in indices_to_use:
            index = self.indices[index_name]
            docs = index.similarity_search_with_score(query, k=10)
            
            # Extract solver scores from documents
            solver_scores = self._extract_solver_scores(docs)
            results[index_name] = solver_scores
        
        # Weighted combination
        combined_scores = self._combine_scores(results)
        
        # Rank and return top-k
        ranked = sorted(
            combined_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:k]
        
        return ranked
    
    def _extract_solver_scores(
        self,
        docs: List[Tuple[Document, float]]
    ) -> Dict[str, float]:
        """
        Extract solver names and scores from retrieved documents.
        
        Example:
          Document metadata: {"codes": ["PeleC", "PeleLMeX"]}
          Document score: 0.85
          → {"PeleC": 0.85, "PeleLMeX": 0.85}
        """
        solver_scores = {}
        
        for doc, score in docs:
            # Handle family documents
            if "codes" in doc.metadata:
                for code in doc.metadata["codes"]:
                    solver_scores[code] = max(
                        solver_scores.get(code, 0.0),
                        score
                    )
            
            # Handle individual solver documents
            elif "solver_name" in doc.metadata:
                solver = doc.metadata["solver_name"]
                solver_scores[solver] = max(
                    solver_scores.get(solver, 0.0),
                    score
                )
        
        return solver_scores
    
    def _combine_scores(
        self,
        results: Dict[str, Dict[str, float]]
    ) -> Dict[str, float]:
        """
        Weighted combination of scores across indices.
        
        Formula:
          combined_score[solver] = Σ(weight[index] × score[index][solver])
        
        Example:
          physics_regimes: {"PeleLMeX": 0.90} (weight: 0.40)
          solver_capabilities: {"PeleLMeX": 0.95} (weight: 0.30)
          code_lineage: {"PeleLMeX": 0.70} (weight: 0.20)
          cross_cutting_guidance: {"PeleLMeX": 0.80} (weight: 0.10)
          
          Combined: 0.40×0.90 + 0.30×0.95 + 0.20×0.70 + 0.10×0.80 = 0.875
        """
        combined = {}
        
        # Collect all solvers mentioned
        all_solvers = set()
        for index_results in results.values():
            all_solvers.update(index_results.keys())
        
        # Compute weighted score for each solver
        for solver in all_solvers:
            score = 0.0
            
            for index_name, index_results in results.items():
                weight = self.weights.get(index_name, 0.0)
                index_score = index_results.get(solver, 0.0)
                score += weight * index_score
            
            combined[solver] = score
        
        return combined
```

**Index Building:**

```python
def build_level0_indices():
    """
    Build all Level 0 indices.
    
    Outputs:
      database/faiss/physics_regimes.faiss
      database/faiss/solver_capabilities.faiss
      database/faiss/code_lineage.faiss
      database/faiss/cross_cutting_guidance.faiss
    """
    # 1. Physics regimes
    physics_families = load_physics_families()  # From YAML
    physics_docs = []
    
    for family_name, family_info in physics_families.items():
        text = f"""
        Physics Family: {family_name}
        Codes: {', '.join(family_info['codes'])}
        Physics: {family_info['physics']}
        Use Cases: {family_info['use_cases']}
        Keywords: {family_info.get('keywords', '')}
        {f"Evolution: {family_info['evolution']}" if 'evolution' in family_info else ""}
        """
        
        physics_docs.append({
            "text": text,
            "family": family_name,
            "codes": family_info["codes"]
        })
    
    create_faiss_index(physics_docs, "physics_regimes")
    
    # 2. Solver capabilities
    solver_docs = []
    for solver_name, solver_info in solver_descriptions.items():
        solver_docs.append({
            "text": solver_info["description"],
            "solver_name": solver_name,
            "status": solver_info["status"]
        })
    
    create_faiss_index(solver_docs, "solver_capabilities")
    
    # 3. Code lineage
    lineage_docs = extract_code_lineage()  # Parse evolution relationships
    create_faiss_index(lineage_docs, "code_lineage")
    
    # 4. Cross-cutting guidance
    guidance_docs = []
    for report_id in [1, 3, 4]:  # Decision framework reports
        report_path = Path(f"database/reports/report{report_id}.txt")
        guidance_docs.append({
            "text": report_path.read_text(),
            "report_id": report_id,
            "type": "guidance"
        })
    
    create_faiss_index(guidance_docs, "cross_cutting_guidance")
```

---

### **10.2 Level 1: Documentation Retrieval**

**Purpose:** Retrieve relevant technical context (parameter guides, case READMEs, build instructions).

**Architecture:**

```python
class Level1Documentation:
    """
    Level 1: Documentation retrieval for selected solver(s).
    
    Indices (7 sub-indices per solver):
      1. solver_readme/ - Top-level README.rst
      2. problem_catalogs/ - Report 2 (classification)
      3. parameter_guides/ - Report 5 (customization)
      4. performance_data/ - Report 6 (job sizing)
      5. build_instructions/ - Report 7 (compilation)
      6. case_inventory/ - Report 9 (case listing)
      7. case_readmes/ - All case README files
    
    Output: List of DocumentMatch objects with relevance scores
    """
    
    def search(
        self,
        query: str,
        solver: str,
        k: int = 5,
        enabled_indices: Optional[List[str]] = None
    ) -> List[DocumentMatch]:
        """
        Query Level 1 documentation indices.
        
        Returns top-k most relevant documents across all indices.
        """
        indices_to_use = enabled_indices or [
            "solver_readme", "problem_catalogs", "parameter_guides",
            "performance_data", "build_instructions", "case_inventory",
            "case_readmes"
        ]
        
        results = {}
        
        for index_name in indices_to_use:
            index_path = f"{solver.lower()}_doc_{index_name}"
            index = self._load_index(index_path)
            
            docs = index.similarity_search_with_score(query, k=20)
            results[index_name] = docs
        
        # Weighted combination
        combined = self._combine_doc_scores(results)
        
        # Rank and return top-k
        ranked = sorted(combined, key=lambda d: d.score, reverse=True)[:k]
        
        return ranked
```

**Document Structures:**

```python
@dataclass
class DocumentMatch:
    """Structured result from Level 1 retrieval."""
    
    content: str              # Document text snippet
    doc_type: str            # "solver_readme", "case_readme", "parameter_guide"
    source: str              # File path or report ID
    score: float             # Relevance score (0-1)
    metadata: Dict[str, Any] # Additional context
    
    # For case READMEs
    case_name: Optional[str] = None
    case_path: Optional[Path] = None
    
    # For reports
    report_id: Optional[int] = None
    section: Optional[str] = None  # Which section of report?

# Example usage
doc_match = DocumentMatch(
    content="To set grid resolution for DNS, use amr.n_cell with...",
    doc_type="parameter_guide",
    source="report5.txt",
    score=0.88,
    metadata={"topic": "grid_setup"},
    report_id=5,
    section="1.1 Domain & Grid Setup"
)
```

---

### **10.3 Level 2: Case Metadata Search**

**Purpose:** Find specific cases matching physics requirements and configuration needs.

**Architecture:**

```python
class Level2CaseMetadata:
    """
    Level 2: Case-specific metadata search.
    
    Indices (6 sub-indices per solver):
      1. physics_descriptors/ - Reacting, BCs, mechanisms
      2. grid_configurations/ - Grid size, AMR, dimension
      3. git_metrics/ - Age, commits, maturity
      4. path_hierarchy/ - Production/RegTests/Custom
      5. chemistry_mechanisms/ - drm19, dodecane, etc.
      6. performance_estimates/ - Runtime, memory
    
    Output: List of CaseMetadata objects with combined scores
    """
    
    def search(
        self,
        query: str,
        solver: str,
        k: int = 5,
        enabled_indices: Optional[List[str]] = None
    ) -> List[CaseMetadata]:
        """
        Query Level 2 case metadata indices.
        
        Returns top-k cases with combined scores from all indices.
        """
        indices_to_use = enabled_indices or [
            "physics_descriptors", "grid_configurations", "git_metrics",
            "path_hierarchy", "chemistry_mechanisms", "performance_estimates"
        ]
        
        results = {}
        
        for index_name in indices_to_use:
            index_path = f"{solver.lower()}_case_{index_name}"
            index = self._load_index(index_path)
            
            docs = index.similarity_search_with_score(query, k=20)
            
            # Extract case-level scores
            case_scores = {}
            for doc, score in docs:
                case_id = doc.metadata["case_id"]
                case_scores[case_id] = max(
                    case_scores.get(case_id, 0.0),
                    score
                )
            
            results[index_name] = case_scores
        
        # Weighted combination
        combined_scores = self._combine_case_scores(results)
        
        # Build CaseMetadata objects
        cases = []
        for case_id, combined_score in combined_scores.items():
            metadata = self._load_case_metadata(case_id)
            metadata.combined_score = combined_score
            metadata.index_scores = {
                name: results[name].get(case_id, 0.0)
                for name in indices_to_use
            }
            cases.append(metadata)
        
        # Rank and return top-k
        ranked = sorted(cases, key=lambda c: c.combined_score, reverse=True)[:k]
        
        return ranked
```

**Case Metadata Structure:**

```python
@dataclass
class CaseMetadata:
    """
    Complete metadata for a Pele example case.
    
    Populated from:
      - Repository structure
      - Git history
      - inputs file parsing
      - README parsing
    """
    # Identity
    case_id: str                    # Unique: "pelec_pmf"
    case_name: str                  # Display: "PMF"
    solver: str                     # "PeleC"
    path: Path                      # Full path to case directory
    
    # Physics
    physics_type: str               # "reacting", "non-reacting"
    chemistry_mechanism: Optional[str]  # "drm19", "dodecane", None
    flow_regime: str                # "compressible", "low-Mach"
    has_multiphase: bool
    turbulence_model: Optional[str] # "RANS k-epsilon", "LES", None
    boundary_conditions: str        # "periodic y-z, inflow-outflow x"
    dimension: int                  # 2 or 3
    
    # Configuration
    default_grid: str               # "128 × 128 × 128"
    amr_levels: int                 # 2
    available_inputs: List[str]     # ["inputs.2d", "inputs.3d", "inputs.regression"]
    
    # Git metrics
    years_since_creation: float
    total_commits: int
    num_contributors: int
    months_since_update: float
    is_production: bool             # In Production/ directory?
    
    # Quality tier
    quality_tier: str               # "Production", "RegTests", "Custom"
    
    # Performance
    estimated_runtime_hours: Optional[float]
    estimated_memory_gb: Optional[float]
    
    # Retrieval scores (populated during search)
    combined_score: float = 0.0
    index_scores: Dict[str, float] = field(default_factory=dict)
    
    def to_summary(self) -> str:
        """Generate natural language summary for embedding."""
        return f"""
        Case: {self.case_name}
        Path: {self.path}
        
        Git Metrics:
          Created: {self.years_since_creation:.1f} years ago
          Commits: {self.total_commits}
          Contributors: {self.num_contributors}
          Last updated: {self.months_since_update:.0f} months ago
          Maturity: {'Production-ready' if self.is_production else 'Experimental'}
        
        Physics:
          Type: {self.physics_type}
          Chemistry: {self.chemistry_mechanism or 'None'}
          Flow regime: {self.flow_regime}
          Multiphase: {self.has_multiphase}
          Turbulence: {self.turbulence_model or 'Laminar'}
          Boundary conditions: {self.boundary_conditions}
          Dimension: {self.dimension}D
        
        Configuration:
          Default grid: {self.default_grid}
          AMR levels: {self.amr_levels}
          Variants: {', '.join(self.available_inputs)}
          Runtime estimate: {self.estimated_runtime_hours or 'Unknown'} CPU hours
        
        Quality Tier: {self.quality_tier}
        """
```

---

---

# **AMReXAgent: Product & Technical Specification**
## **Phase 5: Component Details & APIs**

---

## **11. Component Details**

### **11.1 Service Layer**

#### **11.1.1 MultiIndexEmbeddingService**

**Purpose:** Manages all FAISS indices, provides unified search interface across 3 levels.

**Class Definition:**

```python
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import faiss
import numpy as np
from dataclasses import dataclass

class MultiIndexEmbeddingService:
    """
    Multi-index FAISS retrieval service.
    
    Manages 82 indices in testing mode:
      - Level 0: 4 indices (physics taxonomy)
      - Level 1: 21 indices (7 per solver × 3 solvers)
      - Level 2: 18 indices (6 per solver × 3 solvers)
    
    Attributes
    ----------
    config : PeleAgentConfig
        System configuration (paths, weights, mode)
    embedding_provider : EmbeddingProvider
        CBORG, OpenAI, or local embedder
    indices : Dict[str, FAISSIndex]
        Loaded FAISS indices (lazy-loaded)
    mode : str
        "testing" (82 indices) or "production" (25-82 based on ablation)
    """
    
    def __init__(
        self,
        config: PeleAgentConfig,
        embedding_provider: Optional[EmbeddingProvider] = None
    ):
        self.config = config
        self.embedding_provider = embedding_provider or self._init_embedder()
        self.indices: Dict[str, FAISSIndex] = {}
        self.mode = config.index_mode  # "testing" or "production"
        
        # Load index configuration
        self.level0_weights = config.level0_weights
        self.level1_weights = config.level1_weights
        self.level2_weights = config.level2_weights
    
    # ===== Level 0: Physics Taxonomy =====
    
    def search_solver_capabilities(
        self,
        query: str,
        k: int = 2,
        enabled_indices: Optional[List[str]] = None
    ) -> List[Tuple[str, float]]:
        """
        Level 0 search: Select solver(s) based on physics query.
        
        Parameters
        ----------
        query : str
            Natural language query (e.g., "low-Mach turbulent combustion")
        k : int
            Number of solvers to return
        enabled_indices : list of str, optional
            For ablation: ["physics_regimes", "solver_capabilities", ...]
            If None, uses all Level 0 indices
        
        Returns
        -------
        list of (str, float)
            [(solver_name, confidence_score), ...]
            Example: [("PeleLMeX", 0.92), ("PeleC", 0.60)]
        
        Examples
        --------
        >>> service = MultiIndexEmbeddingService(config)
        >>> solvers = service.search_solver_capabilities(
        ...     "supersonic hydrogen combustion with shocks"
        ... )
        >>> solvers[0]
        ("PeleC", 0.95)
        """
        # Determine which indices to query
        if enabled_indices is None:
            enabled_indices = [
                "physics_regimes",
                "solver_capabilities",
                "code_lineage",
                "cross_cutting_guidance"
            ]
        
        # Query each Level 0 index
        results = {}
        for index_name in enabled_indices:
            index = self._get_index(f"level0_{index_name}")
            docs = index.search(query, k=10)
            
            # Extract solver scores from documents
            solver_scores = self._extract_solver_scores(docs)
            results[index_name] = solver_scores
        
        # Weighted combination
        combined = self._combine_solver_scores(results, self.level0_weights)
        
        # Rank and return top-k
        ranked = sorted(
            combined.items(),
            key=lambda x: x[1],
            reverse=True
        )[:k]
        
        return ranked
    
    # ===== Level 1: Documentation =====
    
    def search_documentation(
        self,
        query: str,
        solver: str,
        k: int = 5,
        enabled_indices: Optional[List[str]] = None
    ) -> List[DocumentMatch]:
        """
        Level 1 search: Retrieve relevant documentation.
        
        Parameters
        ----------
        query : str
            Natural language query for documentation
        solver : str
            Solver to search docs for (e.g., "PeleC")
        k : int
            Number of documents to return
        enabled_indices : list of str, optional
            For ablation: ["solver_readme", "parameter_guides", ...]
            If None, uses all Level 1 indices
        
        Returns
        -------
        list of DocumentMatch
            Top-k documents with relevance scores
        
        Examples
        --------
        >>> docs = service.search_documentation(
        ...     "How to set DNS grid resolution?",
        ...     solver="PeleLMeX"
        ... )
        >>> docs[0].doc_type
        'parameter_guide'
        >>> docs[0].report_id
        5
        """
        if enabled_indices is None:
            enabled_indices = [
                "solver_readme", "problem_catalogs", "parameter_guides",
                "performance_data", "build_instructions", "case_inventory",
                "case_readmes"
            ]
        
        results = {}
        
        for index_name in enabled_indices:
            index_path = f"{solver.lower()}_doc_{index_name}"
            index = self._get_index(index_path)
            
            docs = index.search(query, k=20)
            results[index_name] = docs
        
        # Weighted combination
        weights = self.level1_weights.get(solver.lower(), self.level1_weights["default"])
        combined = self._combine_doc_scores(results, weights)
        
        # Rank and return top-k
        ranked = sorted(combined, key=lambda d: d.score, reverse=True)[:k]
        
        return ranked
    
    # ===== Level 2: Case Metadata =====
    
    def search_case_metadata(
        self,
        query: str,
        solver: str,
        k: int = 5,
        enabled_indices: Optional[List[str]] = None
    ) -> List[CaseMetadata]:
        """
        Level 2 search: Find cases matching physics/config requirements.
        
        Parameters
        ----------
        query : str
            Natural language query for case search
        solver : str
            Solver to search cases for
        k : int
            Number of cases to return
        enabled_indices : list of str, optional
            For ablation: ["physics_descriptors", "git_metrics", ...]
            If None, uses all Level 2 indices
        
        Returns
        -------
        list of CaseMetadata
            Top-k cases with combined scores and per-index breakdowns
        
        Examples
        --------
        >>> cases = service.search_case_metadata(
        ...     "premixed methane flame with detailed chemistry",
        ...     solver="PeleC"
        ... )
        >>> cases[0].case_name
        'PMF'
        >>> cases[0].combined_score
        0.87
        >>> cases[0].index_scores
        {'physics_descriptors': 0.95, 'git_metrics': 0.90, ...}
        """
        if enabled_indices is None:
            enabled_indices = [
                "physics_descriptors", "grid_configurations", "git_metrics",
                "path_hierarchy", "chemistry_mechanisms", "performance_estimates"
            ]
        
        results = {}
        
        for index_name in enabled_indices:
            index_path = f"{solver.lower()}_case_{index_name}"
            index = self._get_index(index_path)
            
            docs = index.search(query, k=20)
            
            # Extract case-level scores
            case_scores = self._extract_case_scores(docs)
            results[index_name] = case_scores
        
        # Weighted combination
        weights = self.level2_weights.get(solver.lower(), self.level2_weights["default"])
        combined_scores = self._combine_case_scores(results, weights)
        
        # Build CaseMetadata objects with scores
        cases = []
        for case_id, combined_score in combined_scores.items():
            metadata = self._load_case_metadata(case_id)
            metadata.combined_score = combined_score
            metadata.index_scores = {
                name: results[name].get(case_id, 0.0)
                for name in enabled_indices
            }
            cases.append(metadata)
        
        # Rank and return top-k
        ranked = sorted(cases, key=lambda c: c.combined_score, reverse=True)[:k]
        
        return ranked
    
    # ===== Helper Methods =====
    
    def _get_index(self, index_name: str) -> FAISSIndex:
        """Lazy-load FAISS index."""
        if index_name not in self.indices:
            index_path = self.config.faiss_db_path / f"{index_name}.faiss"
            
            if not index_path.exists():
                raise IndexNotFoundError(
                    f"Index not built: {index_name}. "
                    f"Run: pele-agent build-indices"
                )
            
            # Load with mmap for memory efficiency
            faiss_index = faiss.read_index(
                str(index_path),
                faiss.IO_FLAG_MMAP
            )
            
            # Load document metadata
            metadata_path = index_path.with_suffix('.pkl')
            with open(metadata_path, 'rb') as f:
                doc_metadata = pickle.load(f)
            
            self.indices[index_name] = FAISSIndex(
                index=faiss_index,
                metadata=doc_metadata,
                embedder=self.embedding_provider
            )
        
        return self.indices[index_name]
    
    def _extract_solver_scores(
        self,
        docs: List[Tuple[Document, float]]
    ) -> Dict[str, float]:
        """Extract solver names and scores from Level 0 documents."""
        solver_scores = {}
        
        for doc, score in docs:
            # Family documents have multiple codes
            if "codes" in doc.metadata:
                for code in doc.metadata["codes"]:
                    solver_scores[code] = max(
                        solver_scores.get(code, 0.0),
                        score
                    )
            
            # Individual solver documents
            elif "solver_name" in doc.metadata:
                solver = doc.metadata["solver_name"]
                solver_scores[solver] = max(
                    solver_scores.get(solver, 0.0),
                    score
                )
        
        return solver_scores
    
    def _combine_solver_scores(
        self,
        results: Dict[str, Dict[str, float]],
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Weighted combination of solver scores.
        
        Formula: combined[solver] = Σ(weight[idx] × score[idx][solver])
        """
        combined = {}
        
        # Collect all solvers
        all_solvers = set()
        for index_results in results.values():
            all_solvers.update(index_results.keys())
        
        # Weighted sum
        for solver in all_solvers:
            score = 0.0
            for index_name, index_results in results.items():
                weight = weights.get(index_name, 0.0)
                index_score = index_results.get(solver, 0.0)
                score += weight * index_score
            
            combined[solver] = score
        
        return combined
    
    def _combine_doc_scores(
        self,
        results: Dict[str, List[Tuple[Document, float]]],
        weights: Dict[str, float]
    ) -> List[DocumentMatch]:
        """Combine document scores across Level 1 indices."""
        # Group by document ID
        doc_scores: Dict[str, List[Tuple[str, float]]] = {}
        doc_objects: Dict[str, Document] = {}
        
        for index_name, docs in results.items():
            weight = weights.get(index_name, 0.0)
            
            for doc, score in docs:
                doc_id = doc.metadata.get("doc_id", id(doc))
                
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = []
                    doc_objects[doc_id] = doc
                
                doc_scores[doc_id].append((index_name, weight * score))
        
        # Compute combined scores
        matches = []
        for doc_id, scores in doc_scores.items():
            combined_score = sum(s for _, s in scores)
            doc = doc_objects[doc_id]
            
            matches.append(DocumentMatch(
                content=doc.page_content,
                doc_type=doc.metadata.get("type", "unknown"),
                source=doc.metadata.get("source", "unknown"),
                score=combined_score,
                metadata=doc.metadata,
                case_name=doc.metadata.get("case"),
                case_path=doc.metadata.get("case_path"),
                report_id=doc.metadata.get("report_id"),
                section=doc.metadata.get("section")
            ))
        
        return matches
    
    def _combine_case_scores(
        self,
        results: Dict[str, Dict[str, float]],
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """Combine case scores across Level 2 indices."""
        combined = {}
        
        # Collect all cases
        all_cases = set()
        for index_results in results.values():
            all_cases.update(index_results.keys())
        
        # Weighted sum
        for case_id in all_cases:
            score = 0.0
            for index_name, index_results in results.items():
                weight = weights.get(index_name, 0.0)
                index_score = index_results.get(case_id, 0.0)
                score += weight * index_score
            
            combined[case_id] = score
        
        return combined
    
    def _extract_case_scores(
        self,
        docs: List[Tuple[Document, float]]
    ) -> Dict[str, float]:
        """Extract case IDs and scores from Level 2 documents."""
        case_scores = {}
        
        for doc, score in docs:
            case_id = doc.metadata.get("case_id")
            if case_id:
                case_scores[case_id] = max(
                    case_scores.get(case_id, 0.0),
                    score
                )
        
        return case_scores
    
    def _load_case_metadata(self, case_id: str) -> CaseMetadata:
        """Load full metadata for a case."""
        metadata_db = self.config.cases_db_path / "case_metadata.json"
        
        with open(metadata_db) as f:
            all_metadata = json.load(f)
        
        if case_id not in all_metadata:
            raise CaseNotFoundError(f"Case metadata not found: {case_id}")
        
        return CaseMetadata(**all_metadata[case_id])
    
    def _init_embedder(self) -> EmbeddingProvider:
        """Initialize embedding provider with fallback chain."""
        try:
            return CBORGEmbedder(self.config.cborg_config)
        except Exception as e:
            logger.warning(f"CBORG unavailable: {e}, trying OpenAI")
            try:
                return OpenAIEmbedder(self.config.openai_api_key)
            except Exception as e:
                logger.warning(f"OpenAI unavailable: {e}, using local embedder")
                return LocalEmbedder(model_name="sentence-transformers/all-MiniLM-L6-v2")
```

**FAISS Index Wrapper:**

```python
class FAISSIndex:
    """
    Wrapper around FAISS index with document metadata.
    
    Provides unified interface for similarity search.
    """
    
    def __init__(
        self,
        index: faiss.Index,
        metadata: List[Dict[str, Any]],
        embedder: EmbeddingProvider
    ):
        self.index = index
        self.metadata = metadata
        self.embedder = embedder
    
    def search(
        self,
        query: str,
        k: int = 5
    ) -> List[Tuple[Document, float]]:
        """
        Search index for similar documents.
        
        Parameters
        ----------
        query : str
            Natural language query
        k : int
            Number of results to return
        
        Returns
        -------
        list of (Document, float)
            Documents with similarity scores (0-1, higher is better)
        """
        # Embed query
        query_vector = self.embedder.embed(query)
        
        # FAISS search (returns L2 distances)
        distances, indices = self.index.search(
            np.array([query_vector], dtype=np.float32),
            k
        )
        
        # Convert L2 distances to similarity scores
        # score = 1 / (1 + distance)
        scores = 1.0 / (1.0 + distances[0])
        
        # Build Document objects
        results = []
        for idx, score in zip(indices[0], scores):
            if idx == -1:  # FAISS padding
                continue
            
            doc_meta = self.metadata[idx]
            doc = Document(
                page_content=doc_meta["text"],
                metadata=doc_meta
            )
            results.append((doc, float(score)))
        
        return results
```

---

#### **11.1.2 ArchitectService**

**Purpose:** Orchestrates case selection and modification planning using LLM + RAG.

```python
class ArchitectService:
    """
    Simulation planning service.
    
    Responsibilities:
      1. Extract requirements from natural language
      2. Search documentation and cases (via EmbeddingService)
      3. Plan modifications using LLM
      4. Generate explainability text
    
    Attributes
    ----------
    embedding_service : MultiIndexEmbeddingService
        For FAISS retrieval
    cases_service : AMReXCasesService
        For case repository access
    llm : ChatLLM
        GPT-4 or Claude for planning
    config : PeleAgentConfig
    """
    
    def __init__(
        self,
        embedding_service: MultiIndexEmbeddingService,
        cases_service: AMReXCasesService,
        llm: ChatLLM,
        config: PeleAgentConfig
    ):
        self.embedding = embedding_service
        self.cases = cases_service
        self.llm = llm
        self.config = config
    
    def create_plan(
        self,
        prompt: str,
        selected_solvers: Optional[List[Tuple[str, float]]] = None,
        previous_errors: Optional[List[str]] = None
    ) -> SimulationPlan:
        """
        Create simulation plan from natural language prompt.
        
        Workflow:
          1. If solvers not provided, call Level 0 search
          2. Search documentation (Level 1)
          3. Search cases (Level 2)
          4. Use LLM to plan modifications
          5. Generate explainability
        
        Parameters
        ----------
        prompt : str
            User's natural language description
        selected_solvers : list of (str, float), optional
            Pre-selected solvers from SolverSelector node
            If None, performs Level 0 search here
        previous_errors : list of str, optional
            Errors from previous retry attempt
            Used to improve next plan
        
        Returns
        -------
        SimulationPlan
            Selected case, modifications, reasoning
        
        Examples
        --------
        >>> plan = architect.create_plan(
        ...     "Premixed methane flame DNS with drm19"
        ... )
        >>> plan.selected_case
        'PeleLMeX/Exec/RegTests/FlameSheet'
        >>> plan.modifications
        [('amr.n_cell', '256 256 256'), ('pelec.chem_file', 'drm19.yaml')]
        """
        # Step 1: Solver selection (if not provided)
        if selected_solvers is None:
            selected_solvers = self.embedding.search_solver_capabilities(
                prompt,
                k=2
            )
        
        primary_solver = selected_solvers[0][0]
        
        # Step 2: Documentation retrieval
        docs = self.embedding.search_documentation(
            prompt,
            solver=primary_solver,
            k=5
        )
        
        # Step 3: Case retrieval
        cases = self.embedding.search_case_metadata(
            prompt,
            solver=primary_solver,
            k=5
        )
        
        # Step 4: LLM planning
        plan = self._llm_plan(
            prompt=prompt,
            solver=primary_solver,
            documentation=docs,
            cases=cases,
            previous_errors=previous_errors
        )
        
        # Step 5: Explainability
        reasoning = self._generate_reasoning(
            prompt=prompt,
            solver=primary_solver,
            selected_case=cases[0],  # Top case
            docs=docs
        )
        
        return SimulationPlan(
            selected_solver=primary_solver,
            solver_confidence=selected_solvers[0][1],
            selected_case=cases[0].path,
            case_candidates=cases,
            modifications=plan.modifications,
            reasoning=reasoning,
            documentation_context=docs
        )
    
    def _llm_plan(
        self,
        prompt: str,
        solver: str,
        documentation: List[DocumentMatch],
        cases: List[CaseMetadata],
        previous_errors: Optional[List[str]]
    ) -> LLMPlanResult:
        """
        Use LLM to plan modifications.
        
        Prompt structure:
          System: You are expert in {solver} simulation setup
          Context: Retrieved docs + top case description
          Task: Plan modifications for user's requirements
          Previous errors: {errors} (if retry)
        """
        # Build context from documentation
        doc_context = "\n\n".join([
            f"[{doc.doc_type}] {doc.content[:500]}"
            for doc in documentation[:3]
        ])
        
        # Top case summary
        top_case = cases[0]
        case_context = f"""
        Selected baseline case: {top_case.case_name}
        Path: {top_case.path}
        Physics: {top_case.physics_type}, {top_case.flow_regime}
        Default grid: {top_case.default_grid}
        Chemistry: {top_case.chemistry_mechanism or 'None'}
        """
        
        # Build prompt
        system_msg = f"""You are an expert in {solver} simulation setup.
        Your task is to plan modifications to a baseline case to meet user requirements.
        Base your decisions on the provided documentation and case metadata."""
        
        user_msg = f"""
        User Request:
        {prompt}
        
        Documentation Context:
        {doc_context}
        
        Baseline Case:
        {case_context}
        
        {'Previous Errors (fix these):' if previous_errors else ''}
        {chr(10).join(previous_errors) if previous_errors else ''}
        
        Plan the necessary modifications to the inputs file.
        Format: List of (parameter, value) tuples.
        Example: [("amr.n_cell", "256 256 256"), ("pelec.chem_file", "drm19.yaml")]
        
        Provide modifications as JSON:
        {{
            "modifications": [
                {{"parameter": "amr.n_cell", "value": "256 256 256"}},
                ...
            ],
            "rationale": "Brief explanation of each modification"
        }}
        """
        
        # LLM call
        response = self.llm.chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.3 if not previous_errors else 0.0  # Deterministic on retry
        )
        
        # Parse response
        try:
            result = json.loads(response.content)
            modifications = [
                (m["parameter"], m["value"])
                for m in result["modifications"]
            ]
            rationale = result.get("rationale", "")
        except json.JSONDecodeError:
            logger.error(f"LLM returned invalid JSON: {response.content}")
            modifications = []
            rationale = response.content
        
        return LLMPlanResult(
            modifications=modifications,
            rationale=rationale
        )
    
    def _generate_reasoning(
        self,
        prompt: str,
        solver: str,
        selected_case: CaseMetadata,
        docs: List[DocumentMatch]
    ) -> str:
        """
        Generate explainability text.
        
        Shows:
          - Why this solver?
          - Why this case?
          - Per-index score breakdown
          - Supporting documentation
        """
        # Solver reasoning
        solver_reasoning = f"Selected: {solver}\n"
        solver_reasoning += f"Reason: [Based on physics taxonomy match]\n\n"
        
        # Case reasoning
        case_reasoning = f"Selected Case: {selected_case.case_name}\n"
        case_reasoning += f"Path: {selected_case.path}\n"
        case_reasoning += f"Combined Score: {selected_case.combined_score:.2f}\n\n"
        
        # Index breakdown
        case_reasoning += "Index Contributions:\n"
        for index_name, score in selected_case.index_scores.items():
            weight = self.config.level2_weights.get(solver.lower(), {}).get(index_name, 0.0)
            bar = "█" * int(score * 12)
            case_reasoning += f"  {index_name:20s} ({weight*100:2.0f}%): {score:.2f} {bar}\n"
        
        # Documentation support
        doc_reasoning = "\n\nSupporting Documentation:\n"
        for doc in docs[:3]:
            doc_reasoning += f"  • [{doc.doc_type}] {doc.source}\n"
            doc_reasoning += f"    Score: {doc.score:.2f}\n"
        
        return solver_reasoning + case_reasoning + doc_reasoning
```

---

#### **11.1.3 ReviewerService**

**Purpose:** Pre-execution validation to catch configuration errors.

```python
class ReviewerService:
    """
    Pre-execution validation service.
    
    Checks:
      1. Required parameters present
      2. Syntax validity
      3. Physics consistency
      4. File dependencies exist
    
    Returns ValidationResult with mode:
      - "proceed": All checks passed
      - "retry": Recoverable errors (missing params)
      - "fail": Unrecoverable errors (physics conflict)
    """
    
    def __init__(self, config: PeleAgentConfig):
        self.config = config
        self.required_params = self._load_required_params()
    
    def validate(
        self,
        inputs_file: Path,
        solver: str,
        modifications: List[Tuple[str, Any]]
    ) -> ValidationResult:
        """
        Validate simulation configuration.
        
        Parameters
        ----------
        inputs_file : Path
            Path to generated inputs file
        solver : str
            Solver name (for solver-specific checks)
        modifications : list
            Planned modifications (for context)
        
        Returns
        -------
        ValidationResult
            mode: "proceed" | "retry" | "fail"
            errors: List of error messages
            suggestions: List of fix suggestions
        """
        errors = []
        suggestions = []
        
        # Parse inputs file
        try:
            params = self._parse_inputs_file(inputs_file)
        except ParseError as e:
            return ValidationResult(
                mode="fail",
                errors=[f"Cannot parse inputs file: {e}"],
                suggestions=["Check file syntax, ensure valid format"]
            )
        
        # Check 1: Required parameters
        missing = self._check_required_params(params, solver)
        if missing:
            errors.extend([f"Missing required parameter: {p}" for p in missing])
            suggestions.extend([f"Add: {p} = [value]" for p in missing])
        
        # Check 2: Syntax validation
        syntax_errors = self._check_syntax(params)
        if syntax_errors:
            errors.extend(syntax_errors)
        
        # Check 3: Physics consistency
        physics_errors = self._check_physics_consistency(params, solver)
        if physics_errors:
            errors.extend(physics_errors)
        
        # Check 4: File dependencies
        file_errors = self._check_file_dependencies(params)
        if file_errors:
            errors.extend(file_errors)
        
        # Determine mode
        if not errors:
            mode = "proceed"
        elif self._all_recoverable(errors):
            mode = "retry"
        else:
            mode = "fail"
        
        return ValidationResult(
            mode=mode,
            errors=errors,
            suggestions=suggestions,
            analysis=self._generate_analysis(errors, suggestions)
        )
    
    def _check_required_params(
        self,
        params: Dict[str, Any],
        solver: str
    ) -> List[str]:
        """Check for missing required parameters."""
        required = self.required_params.get(solver.lower(), [])
        missing = []
        
        for param in required:
            if param not in params:
                missing.append(param)
        
        return missing
    
    def _check_syntax(self, params: Dict[str, Any]) -> List[str]:
        """Validate parameter syntax."""
        errors = []
        
        for param, value in params.items():
            # Check for common syntax mistakes
            if param.startswith("amr.n_cell"):
                # Should be "256 256 256", not "256^3"
                if "^" in str(value):
                    errors.append(
                        f"Invalid syntax for {param}: '{value}'. "
                        f"Use spaces, not ^. Example: '256 256 256'"
                    )
            
            # Check for trailing commas (common mistake)
            if isinstance(value, str) and value.endswith(","):
                errors.append(
                    f"Trailing comma in {param}: '{value}'"
                )
        
        return errors
    
    def _check_physics_consistency(
        self,
        params: Dict[str, Any],
        solver: str
    ) -> List[str]:
        """Check for physics inconsistencies."""
        errors = []
        
        # Rule 1: EB geometry requires non-periodic BC
        if "eb2.geom_type" in params:
            periodicity = params.get("geometry.is_periodic", "0 0 0")
            if periodicity == "1 1 1":
                errors.append(
                    "Physics conflict: EB geometry requires at least one "
                    "non-periodic direction. Current: is_periodic = 1 1 1. "
                    "Suggested fix: geometry.is_periodic = 0 1 1"
                )
        
        # Rule 2: Chemistry requires mechanism file
        if solver.lower() in ["pelec", "pelelmex", "pelemp"]:
            if "chemistry" in params.get("amr.plot_vars", []):
                if "chem_file" not in str(params):
                    errors.append(
                        "Chemistry enabled but no mechanism file specified. "
                        "Add: pelec.chem_file = drm19.yaml (or other mechanism)"
                    )
        
        # Rule 3: AMR requires max_level
        if "amr.n_cell" in params:
            if "amr.max_level" not in params:
                errors.append(
                    "AMR grid specified but amr.max_level missing. "
                    "Add: amr.max_level = 0 (for no refinement) or higher"
                )
        
        return errors
    
    def _check_file_dependencies(self, params: Dict[str, Any]) -> List[str]:
        """Check that referenced files exist."""
        errors = []
        
        # Check chemistry file
        for param, value in params.items():
            if "chem_file" in param:
                chem_file = Path(value)
                
                # Check NSL (NERSC Science Library)
                nsl_path = Path("/global/common/software/m3018/mechanism_database") / chem_file.name
                
                # Check local
                local_path = Path.cwd() / chem_file
                
                if not (chem_file.exists() or nsl_path.exists() or local_path.exists()):
                    errors.append(
                        f"Chemistry file not found: {value}. "
                        f"Searched: current dir, NSL (/global/common/.../mechanism_database). "
                        f"Available mechanisms: drm19.yaml, dodecane.yaml, gri30.yaml"
                    )
        
        return errors
    
    def _all_recoverable(self, errors: List[str]) -> bool:
        """Determine if errors are recoverable (retry) or fatal (fail)."""
        # Recoverable: missing params, missing files
        # Fatal: physics conflicts, syntax errors
        
        for error in errors:
            if "Physics conflict" in error or "Invalid syntax" in error:
                return False  # Fatal
        
        return True  # All recoverable
    
    def _generate_analysis(
        self,
        errors: List[str],
        suggestions: List[str]
    ) -> str:
        """Generate human-readable analysis."""
        if not errors:
            return "✅ All validation checks passed. Ready to submit."
        
        analysis = f"Validation found {len(errors)} error(s):\n\n"
        
        for i, (error, suggestion) in enumerate(zip(errors, suggestions), 1):
            analysis += f"{i}. {error}\n"
            analysis += f"   Fix: {suggestion}\n\n"
        
        return analysis
```

---

#### **11.1.4 DocumentRetrievalService**

**Purpose:** Fetch and analyze research papers for validation (FOAM benchmark).

```python
class DocumentRetrievalService:
    """
    Research paper retrieval and analysis.
    
    Use cases:
      1. FOAM-agent benchmark validation
      2. Plot similarity comparison
      3. Parameter extraction from PDFs
    """
    
    def __init__(self, config: PeleAgentConfig):
        self.config = config
        self.arxiv_api = "http://export.arxiv.org/api/query"
    
    def retrieve_paper_metadata(
        self,
        title: Optional[str] = None,
        arxiv_id: Optional[str] = None,
        doi: Optional[str] = None
    ) -> PaperMetadata:
        """
        Fetch paper metadata from arXiv.
        
        Parameters
        ----------
        title : str, optional
            Paper title for search
        arxiv_id : str, optional
            arXiv ID (e.g., "2103.12345")
        doi : str, optional
            DOI
        
        Returns
        -------
        PaperMetadata
            Title, authors, abstract, PDF URL, publication date
        """
        if arxiv_id:
            query = f"id:{arxiv_id}"
        elif title:
            query = f"ti:{title}"
        elif doi:
            query = f"doi:{doi}"
        else:
            raise ValueError("Must provide title, arxiv_id, or doi")
        
        # Query arXiv API
        response = requests.get(
            self.arxiv_api,
            params={
                "search_query": query,
                "max_results": 1
            }
        )
        
        # Parse XML response
        root = ET.fromstring(response.content)
        entry = root.find("{http://www.w3.org/2005/Atom}entry")
        
        if entry is None:
            raise PaperNotFoundError(f"Paper not found: {query}")
        
        # Extract metadata
        title = entry.find("{http://www.w3.org/2005/Atom}title").text
        authors = [
            author.find("{http://www.w3.org/2005/Atom}name").text
            for author in entry.findall("{http://www.w3.org/2005/Atom}author")
        ]
        abstract = entry.find("{http://www.w3.org/2005/Atom}summary").text
        pdf_url = entry.find("{http://www.w3.org/2005/Atom}id").text.replace("/abs/", "/pdf/")
        published = entry.find("{http://www.w3.org/2005/Atom}published").text
        
        return PaperMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            pdf_url=pdf_url,
            published=published,
            arxiv_id=arxiv_id
        )
    
    def extract_simulation_details(self, pdf_path: Path) -> SimulationDetails:
        """
        Extract simulation parameters from PDF.
        
        Uses:
          - pypdf for text extraction
          - Regex for parameter patterns
          - LLM for structured extraction
        """
        # Extract text
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
        
        # Regex patterns for common parameters
        patterns = {
            "grid_resolution": r"(\d+)\s*[×x]\s*(\d+)(?:\s*[×x]\s*(\d+))?",
            "solver": r"(OpenFOAM|simpleFoam|reactingFoam|PeleC|PeleLMeX)",
            "chemistry": r"(GRI[- ]?3\.0|drm19|dodecane|mechanism)",
        }
        
        extracted = {}
        for key, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted[key] = match.group(0)
        
        # LLM-based extraction for structured data
        llm_extraction = self._llm_extract_params(text[:5000])  # First 5000 chars
        
        return SimulationDetails(
            solver=extracted.get("solver", llm_extraction.get("solver")),
            grid_resolution=extracted.get("grid_resolution", llm_extraction.get("grid")),
            boundary_conditions=llm_extraction.get("boundary_conditions"),
            chemistry_mechanism=extracted.get("chemistry", llm_extraction.get("chemistry"))
        )
    
    def compare_plots(
        self,
        reference_plot: Path,
        generated_plot: Path
    ) -> float:
        """
        Compute image similarity using SSIM.
        
        Returns
        -------
        float
            Similarity score 0-1 (1 = identical)
        """
        from skimage.metrics import structural_similarity as ssim
        from skimage import io, transform
        
        # Load images as grayscale
        ref_img = io.imread(reference_plot, as_gray=True)
        gen_img = io.imread(generated_plot, as_gray=True)
        
        # Resize to same dimensions
        if ref_img.shape != gen_img.shape:
            gen_img = transform.resize(
                gen_img,
                ref_img.shape,
                anti_aliasing=True
            )
        
        # Compute SSIM
        similarity = ssim(ref_img, gen_img)
        
        return float(similarity)
    
    def validate_against_paper(
        self,
        case: CaseMetadata,
        paper_metadata: SimulationDetails
    ) -> ValidationReport:
        """
        Check if selected case aligns with paper description.
        
        Compares:
          - Solver (exact match or equivalent)
          - Grid resolution (similar order of magnitude)
          - Physics type (reacting vs non-reacting)
        """
        matches = []
        
        # Solver comparison
        if paper_metadata.solver:
            if case.solver.lower() in paper_metadata.solver.lower():
                matches.append("Solver: ✓ (exact match)")
            else:
                matches.append(f"Solver: ~ ({case.solver} vs {paper_metadata.solver})")
        
        # Grid comparison
        if paper_metadata.grid_resolution:
            # Extract numbers
            paper_grid = [int(d) for d in re.findall(r'\d+', paper_metadata.grid_resolution)]
            case_grid = [int(d) for d in re.findall(r'\d+', case.default_grid)]
            
            if paper_grid and case_grid:
                # Check if same order of magnitude
                ratio = max(paper_grid) / max(case_grid)
                if 0.5 < ratio < 2.0:
                    matches.append("Grid: ✓ (similar resolution)")
                else:
                    matches.append(f"Grid: ~ ({case.default_grid} vs {paper_metadata.grid_resolution})")
        
        # Physics comparison
        if paper_metadata.chemistry_mechanism:
            if case.chemistry_mechanism:
                matches.append("Chemistry: ✓ (both use detailed mechanism)")
            else:
                matches.append("Chemistry: ✗ (paper uses chemistry, case does not)")
        
        overall_score = len([m for m in matches if "✓" in m]) / len(matches)
        
        return ValidationReport(
            matches=matches,
            physics_match=overall_score >= 0.66,
            similarity_score=overall_score
        )
```

---

---

# **AMReXAgent: Product & Technical Specification**
## **Phase 5 Part 2: Workflow Nodes & Data Schemas**

---

### **11.2 Node Functions (LangGraph Workflow)**

#### **11.2.1 Solver Selector Node**

**Purpose:** Level 0 retrieval - select appropriate solver(s) from physics query.

```python
def solver_selector_node(state: AgentState) -> AgentState:
    """
    Node 1: Solver selection via Level 0 physics taxonomy.
    
    Input State:
      - prompt: str (user's natural language query)
    
    Output State:
      - selected_solvers: List[Tuple[str, float]]
      - solver_reasoning: str
    
    Logic:
      1. Query Level 0 indices (physics taxonomy)
      2. Return top-2 solvers with confidence scores
      3. Generate reasoning (why this solver family?)
    
    Example:
      Input: "low-Mach turbulent premixed combustion DNS"
      Output: [("PeleLMeX", 0.92), ("PeleC", 0.45)]
    """
    # Get embedding service from config
    embedding_service = get_embedding_service(state["config"])
    
    # Level 0 search
    solvers = embedding_service.search_solver_capabilities(
        query=state["prompt"],
        k=2,
        enabled_indices=state.get("enabled_level0_indices")  # For ablation
    )
    
    # Generate reasoning
    primary_solver = solvers[0][0]
    confidence = solvers[0][1]
    
    reasoning = f"""
    Selected Solver: {primary_solver} (confidence: {confidence:.2%})
    
    Reasoning:
    • Physics taxonomy match identifies this as suitable for the query
    • Alternative considered: {solvers[1][0]} (confidence: {solvers[1][1]:.2%})
    
    Key factors:
    • Query keywords aligned with {primary_solver} capabilities
    • Physics regime classification: [based on Level 0 retrieval]
    """
    
    return {
        **state,
        "selected_solvers": solvers,
        "solver_reasoning": reasoning,
        "timestamp_solver_selected": time.time()
    }
```

---

#### **11.2.2 Architect Node**

**Purpose:** Level 1-2 retrieval + LLM planning for case selection and modifications.

```python
def architect_node(state: AgentState) -> AgentState:
    """
    Node 2: Case selection and modification planning.
    
    Input State:
      - prompt: str
      - selected_solvers: List[Tuple[str, float]]
      - errors_active: List[str] (if retry)
    
    Output State:
      - selected_case: str (path to case)
      - case_candidates: List[CaseMetadata]
      - modifications: List[Tuple[str, Any]]
      - reasoning: str
      - documentation_context: List[DocumentMatch]
    
    Logic:
      1. Search documentation (Level 1)
      2. Search cases (Level 2)
      3. Use LLM to plan modifications
      4. Generate explainability
    """
    # Get services
    architect_service = get_architect_service(state["config"])
    
    # Primary solver from Level 0
    primary_solver = state["selected_solvers"][0][0]
    
    # Create plan (handles Level 1-2 + LLM)
    plan = architect_service.create_plan(
        prompt=state["prompt"],
        selected_solvers=state["selected_solvers"],
        previous_errors=state.get("errors_active")
    )
    
    # Update state
    return {
        **state,
        "selected_case": str(plan.selected_case),
        "case_candidates": plan.case_candidates,
        "modifications": plan.modifications,
        "reasoning": plan.reasoning,
        "documentation_context": plan.documentation_context,
        "timestamp_plan_created": time.time()
    }
```

---

#### **11.2.3 Reviewer Node**

**Purpose:** Pre-execution validation with error detection.

```python
def reviewer_node(state: AgentState) -> AgentState:
    """
    Node 3: Validate configuration before execution.
    
    Input State:
      - selected_case: str
      - modifications: List[Tuple[str, Any]]
    
    Output State:
      - mode: "proceed" | "retry" | "fail"
      - errors_active: List[str]
      - review_analysis: str
    
    Logic:
      1. Generate inputs file (in temp location)
      2. Run validation checks
      3. Determine mode (proceed/retry/fail)
      4. Provide actionable feedback
    """
    # Get services
    reviewer_service = get_reviewer_service(state["config"])
    cases_service = get_cases_service(state["config"])
    
    # Generate temporary inputs file
    temp_inputs = Path(tempfile.mkdtemp()) / "inputs"
    
    cases_service.apply_modifications(
        base_case=Path(state["selected_case"]),
        modifications=state["modifications"],
        output_path=temp_inputs
    )
    
    # Validate
    solver = state["selected_solvers"][0][0]
    result = reviewer_service.validate(
        inputs_file=temp_inputs,
        solver=solver,
        modifications=state["modifications"]
    )
    
    # Increment retry counter if retry mode
    retry_count = state.get("retry_count", 0)
    if result.mode == "retry":
        retry_count += 1
    
    # Override to fail if max retries exceeded
    if retry_count >= state.get("max_retries", 3):
        result.mode = "fail"
        result.errors.append("Max retries exceeded (3 attempts)")
    
    return {
        **state,
        "mode": result.mode,
        "errors_active": result.errors,
        "review_analysis": result.analysis,
        "retry_count": retry_count,
        "timestamp_reviewed": time.time()
    }
```

**Routing Function:**

```python
def route_reviewer(state: AgentState) -> str:
    """
    Conditional routing from reviewer.
    
    Returns:
      "proceed" → go to paper_validator (validation mode) or input_writer (production)
      "retry" → go back to architect
      "fail" → END workflow
    """
    return state["mode"]
```

---

#### **11.2.4 Paper Validator Node**

**Purpose:** Validate against published papers (FOAM benchmark only).

```python
def paper_validator_node(state: AgentState) -> AgentState:
    """
    Node 4: Paper validation (only in validation mode).
    
    Input State:
      - selected_case: str
      - validation_mode: bool
      - foam_case_id: str (if FOAM benchmark)
    
    Output State:
      - arxiv_metadata: Dict
      - validation_report: ValidationReport
      - plot_match_score: float (if plots available)
    
    Logic:
      1. Fetch paper metadata
      2. Extract expected simulation details
      3. Compare to selected case
      4. Optionally compare plots (if available)
    """
    # Skip if not in validation mode
    if not state.get("validation_mode"):
        return state
    
    # Get document retrieval service
    doc_service = get_document_retrieval_service(state["config"])
    
    # Fetch paper for this FOAM benchmark case
    foam_case_id = state.get("foam_case_id")
    
    if not foam_case_id:
        logger.warning("Validation mode but no foam_case_id provided")
        return state
    
    # Look up paper metadata from FOAM benchmark database
    foam_db = load_foam_benchmark_db()
    paper_info = foam_db["cases"][foam_case_id]
    
    # Fetch from arXiv
    paper_metadata = doc_service.retrieve_paper_metadata(
        arxiv_id=paper_info.get("arxiv_id"),
        title=paper_info.get("title")
    )
    
    # Download PDF if needed
    pdf_path = download_pdf(paper_metadata.pdf_url)
    
    # Extract simulation details
    sim_details = doc_service.extract_simulation_details(pdf_path)
    
    # Validate against selected case
    selected_case = state["case_candidates"][0]  # Top case
    validation_report = doc_service.validate_against_paper(
        case=selected_case,
        paper_metadata=sim_details
    )
    
    # Plot comparison (if reference plot available)
    plot_score = None
    if "reference_plot" in paper_info:
        ref_plot = Path(paper_info["reference_plot"])
        gen_plot = Path(state.get("generated_plot_path", ""))
        
        if gen_plot.exists():
            plot_score = doc_service.compare_plots(ref_plot, gen_plot)
    
    return {
        **state,
        "arxiv_metadata": {
            "title": paper_metadata.title,
            "authors": paper_metadata.authors,
            "arxiv_id": paper_metadata.arxiv_id
        },
        "validation_report": validation_report,
        "plot_match_score": plot_score,
        "timestamp_validated": time.time()
    }
```

---

#### **11.2.5 Input Writer Node**

**Purpose:** Generate final run directory with all necessary files.

```python
def input_writer_node(state: AgentState) -> AgentState:
    """
    Node 5: Write final simulation setup.
    
    Input State:
      - selected_case: str
      - modifications: List[Tuple[str, Any]]
      - reasoning: str
    
    Output State:
      - run_directory: str
      - inputs_file_path: str
    
    Logic:
      1. Create timestamped run directory
      2. Copy baseline case
      3. Apply modifications
      4. Write README with explanation
      5. Generate SLURM submit script
    """
    # Get cases service
    cases_service = get_cases_service(state["config"])
    
    # Create run directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(state["config"].output_dir) / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy baseline case
    base_case = Path(state["selected_case"])
    
    # Determine which inputs file variant to use
    # Prefer inputs.3d > inputs.2d > inputs
    inputs_files = list(base_case.glob("inputs*"))
    if base_case / "inputs.3d" in inputs_files:
        source_inputs = base_case / "inputs.3d"
    elif base_case / "inputs.2d" in inputs_files:
        source_inputs = base_case / "inputs.2d"
    else:
        source_inputs = base_case / "inputs"
    
    # Copy and apply modifications
    output_inputs = run_dir / "inputs"
    
    cases_service.apply_modifications(
        base_case=source_inputs,
        modifications=state["modifications"],
        output_path=output_inputs
    )
    
    # Copy auxiliary files (if needed)
    # E.g., chemistry mechanism files
    for param, value in state["modifications"]:
        if "chem_file" in param:
            # Copy chemistry file
            chem_source = cases_service.resolve_chemistry_file(value)
            chem_dest = run_dir / Path(value).name
            shutil.copy(chem_source, chem_dest)
    
    # Write README
    readme_path = run_dir / "README.md"
    readme_content = generate_readme(
        prompt=state["prompt"],
        selected_case=state["selected_case"],
        solver=state["selected_solvers"][0][0],
        modifications=state["modifications"],
        reasoning=state["reasoning"],
        documentation_context=state["documentation_context"]
    )
    readme_path.write_text(readme_content)
    
    # Generate SLURM submit script (for Perlmutter)
    submit_script = run_dir / "submit.sh"
    submit_content = generate_slurm_script(
        solver=state["selected_solvers"][0][0],
        inputs_file="inputs",
        config=state["config"]
    )
    submit_script.write_text(submit_content)
    submit_script.chmod(0o755)  # Make executable
    
    # Log success
    logger.info(f"Generated run directory: {run_dir}")
    
    return {
        **state,
        "run_directory": str(run_dir),
        "inputs_file_path": str(output_inputs),
        "timestamp_completed": time.time()
    }
```

**README Generator:**

```python
def generate_readme(
    prompt: str,
    selected_case: str,
    solver: str,
    modifications: List[Tuple[str, Any]],
    reasoning: str,
    documentation_context: List[DocumentMatch]
) -> str:
    """
    Generate explanatory README for run directory.
    
    Includes:
      - Original prompt
      - Selected case and why
      - Modifications made
      - Supporting documentation
      - Next steps (how to run)
    """
    readme = f"""# AMReXAgent Simulation Setup

## User Request

{prompt}

## Selected Configuration

**Solver:** {solver}

**Baseline Case:** `{selected_case}`

{reasoning}

## Modifications Applied

The following changes were made to the baseline inputs file:

"""
    
    for param, value in modifications:
        readme += f"- `{param} = {value}`\n"
    
    readme += f"""

## Supporting Documentation

The following resources informed this setup:

"""
    
    for doc in documentation_context[:5]:
        readme += f"- [{doc.doc_type}] {doc.source} (relevance: {doc.score:.2f})\n"
    
    readme += f"""

## Next Steps

### 1. Review Configuration

Inspect the `inputs` file to verify all settings:

```bash
cat inputs
```

### 2. Submit Job

On NERSC Perlmutter:

```bash
sbatch submit.sh
```

### 3. Monitor Progress

```bash
squeue -u $USER
tail -f slurm-*.out
```

### 4. Validate Results

After completion, check:
- `plt*` files (visualization data)
- `chk*` files (checkpoint/restart data)
- Log output for warnings/errors

## Configuration Details

- **Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **AMReXAgent Version:** {get_version()}
- **Index Mode:** {get_config().index_mode}

## Troubleshooting

If the simulation fails:

1. Check `slurm-*.out` for error messages
2. Validate inputs file: `pele-agent validate --inputs inputs`
3. Review baseline case documentation: `cat {selected_case}/README.md`
4. Contact: pele-users@googlegroups.com

"""
    
    return readme
```

**SLURM Script Generator:**

```python
def generate_slurm_script(
    solver: str,
    inputs_file: str,
    config: PeleAgentConfig
) -> str:
    """
    Generate SLURM submit script for NERSC Perlmutter.
    
    Tailored to solver (PeleC, PeleLMeX, PeleMP).
    """
    # Determine executable name
    executable_map = {
        "PeleC": "PeleC3d.gnu.MPI.ex",
        "PeleLMeX": "PeleLMeX3d.gnu.MPI.ex",
        "PeleMP": "PeleMP3d.gnu.MPI.ex"
    }
    
    executable = executable_map.get(solver, f"{solver}3d.gnu.MPI.ex")
    
    # Default resource allocation (can be overridden)
    nodes = config.slurm_config.get("nodes", 2)
    ntasks_per_node = config.slurm_config.get("ntasks_per_node", 64)
    time_limit = config.slurm_config.get("time", "01:00:00")
    account = config.slurm_config.get("account", "m3018")
    
    script = f"""#!/bin/bash
#SBATCH -J pele_sim
#SBATCH -A {account}
#SBATCH -C cpu
#SBATCH -q regular
#SBATCH -t {time_limit}
#SBATCH -N {nodes}
#SBATCH --ntasks-per-node={ntasks_per_node}

# AMReXAgent Generated Submit Script
# Solver: {solver}
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

# Load modules
module load PrgEnv-gnu
module load cray-hdf5-parallel
module load cray-netcdf-hdf5parallel

# Set OpenMP threads (if using hybrid MPI+OpenMP)
export OMP_NUM_THREADS=1

# Run simulation
srun -n {nodes * ntasks_per_node} ./{executable} {inputs_file}

# Post-processing (optional)
# Add any analysis commands here

echo "Simulation complete: $(date)"
"""
    
    return script
```

---

## **12. Data Schemas**

### **12.1 AgentState (LangGraph State)**

**Complete TypedDict schema for workflow state:**

```python
from typing import TypedDict, Optional, List, Tuple, Any, Dict, Literal
from pathlib import Path

class AgentState(TypedDict, total=False):
    """
    Complete state schema for AMReXAgent workflow.
    
    TypedDict with total=False allows optional keys.
    All keys documented with types and purposes.
    """
    
    # ===== Input =====
    prompt: str
    """User's natural language simulation request."""
    
    config: PeleAgentConfig
    """System configuration object."""
    
    # ===== Level 0: Solver Selection =====
    selected_solvers: List[Tuple[str, float]]
    """
    Selected solver(s) with confidence scores.
    Example: [("PeleLMeX", 0.92), ("PeleC", 0.60)]
    """
    
    solver_reasoning: str
    """Explanation of solver selection (why this solver?)."""
    
    # ===== Level 1: Documentation =====
    documentation_context: List[DocumentMatch]
    """Retrieved documentation matches (top-5 relevant docs)."""
    
    # ===== Level 2: Case Selection =====
    selected_case: str
    """Path to selected baseline case (e.g., 'PeleC/Exec/RegTests/PMF')."""
    
    case_candidates: List[CaseMetadata]
    """Top-k case candidates with scores (for explainability)."""
    
    # ===== Planning =====
    modifications: List[Tuple[str, Any]]
    """
    Planned modifications to inputs file.
    Example: [("amr.n_cell", "256 256 256"), ("pelec.chem_file", "drm19.yaml")]
    """
    
    reasoning: str
    """
    Comprehensive explanation of all decisions.
    Includes solver, case, modifications reasoning.
    """
    
    # ===== Validation =====
    mode: Literal["proceed", "retry", "fail"]
    """
    Reviewer decision:
      - "proceed": All checks passed, continue to input writer
      - "retry": Recoverable errors, send back to architect
      - "fail": Fatal errors, terminate workflow
    """
    
    errors_active: List[str]
    """
    Current validation errors.
    Empty list if mode="proceed".
    Propagated to architect on retry.
    """
    
    review_analysis: str
    """Human-readable validation report."""
    
    # ===== Paper Validation (FOAM benchmark only) =====
    validation_mode: bool
    """True if running FOAM benchmark validation, False for production."""
    
    foam_case_id: Optional[str]
    """FOAM benchmark case ID (e.g., 'foam_007')."""
    
    arxiv_metadata: Optional[Dict[str, Any]]
    """
    Fetched paper metadata.
    Keys: title, authors, arxiv_id, pdf_url
    """
    
    validation_report: Optional[Dict[str, Any]]
    """Paper validation results (physics match, grid similarity, etc.)."""
    
    plot_match_score: Optional[float]
    """SSIM score for plot comparison (0-1, 1=identical)."""
    
    generated_plot_path: Optional[str]
    """Path to generated plot (for comparison with paper)."""
    
    # ===== Output =====
    run_directory: Optional[str]
    """Path to generated run directory (e.g., 'run_20241201_143052')."""
    
    inputs_file_path: Optional[str]
    """Path to generated inputs file within run directory."""
    
    # ===== Workflow Metadata =====
    retry_count: int
    """Number of retry attempts (max 3)."""
    
    max_retries: int
    """Maximum allowed retries (default 3)."""
    
    start_time: float
    """Workflow start timestamp (time.time())."""
    
    timestamp_solver_selected: Optional[float]
    """Timestamp when solver selected."""
    
    timestamp_plan_created: Optional[float]
    """Timestamp when plan created."""
    
    timestamp_reviewed: Optional[float]
    """Timestamp when validation completed."""
    
    timestamp_validated: Optional[float]
    """Timestamp when paper validation completed."""
    
    timestamp_completed: Optional[float]
    """Timestamp when run directory generated."""
    
    # ===== Ablation Testing =====
    enabled_level0_indices: Optional[List[str]]
    """
    For ablation: subset of Level 0 indices to use.
    If None, uses all 4 indices.
    Example: ["physics_regimes", "solver_capabilities"]
    """
    
    enabled_level1_indices: Optional[List[str]]
    """For ablation: subset of Level 1 indices."""
    
    enabled_level2_indices: Optional[List[str]]
    """For ablation: subset of Level 2 indices."""
```

---

### **12.2 Core Data Models**

#### **12.2.1 CaseMetadata**

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from pathlib import Path

@dataclass
class CaseMetadata:
    """
    Complete metadata for a Pele example case.
    
    Populated from:
      - Repository structure
      - Git history
      - inputs file parsing
      - README parsing
    """
    # ===== Identity =====
    case_id: str
    """Unique identifier (e.g., 'pelec_pmf')."""
    
    case_name: str
    """Display name (e.g., 'PMF')."""
    
    solver: str
    """Solver name (e.g., 'PeleC')."""
    
    path: Path
    """Full path to case directory."""
    
    # ===== Physics =====
    physics_type: str
    """'reacting' or 'non-reacting'."""
    
    chemistry_mechanism: Optional[str] = None
    """Chemistry mechanism name (e.g., 'drm19', 'dodecane')."""
    
    flow_regime: str = "compressible"
    """'compressible' or 'low-Mach'."""
    
    has_multiphase: bool = False
    """True if spray/Lagrangian particles involved."""
    
    turbulence_model: Optional[str] = None
    """'RANS k-epsilon', 'LES', 'DNS', or None (laminar)."""
    
    boundary_conditions: str = "unknown"
    """Description of BCs (e.g., 'periodic y-z, inflow-outflow x')."""
    
    dimension: int = 3
    """2 or 3."""
    
    # ===== Configuration =====
    default_grid: str = "unknown"
    """Default grid size (e.g., '128 × 128 × 128')."""
    
    amr_levels: int = 0
    """Number of AMR levels (0 = uniform grid)."""
    
    available_inputs: List[str] = field(default_factory=list)
    """Available inputs file variants (e.g., ['inputs.2d', 'inputs.3d'])."""
    
    # ===== Git Metrics =====
    years_since_creation: float = 0.0
    """Age of case (years since first commit)."""
    
    total_commits: int = 0
    """Total commits affecting this case."""
    
    num_contributors: int = 0
    """Unique contributors."""
    
    months_since_update: float = 0.0
    """Months since last modification."""
    
    is_production: bool = False
    """True if in Production/ directory."""
    
    # ===== Quality Tier =====
    quality_tier: str = "Custom"
    """'Production', 'RegTests', or 'Custom'."""
    
    # ===== Performance Estimates =====
    estimated_runtime_hours: Optional[float] = None
    """Estimated CPU hours for default configuration."""
    
    estimated_memory_gb: Optional[float] = None
    """Estimated memory requirement."""
    
    # ===== Retrieval Scores (populated during search) =====
    combined_score: float = 0.0
    """Weighted combination of all Level 2 index scores."""
    
    index_scores: Dict[str, float] = field(default_factory=dict)
    """
    Per-index scores for explainability.
    Example: {'physics_descriptors': 0.95, 'git_metrics': 0.90, ...}
    """
    
    def to_summary(self) -> str:
        """
        Generate natural language summary for embedding.
        
        Used when building Level 2 indices.
        """
        return f"""
        Case: {self.case_name}
        Path: {self.path}
        
        Git Metrics:
          Created: {self.years_since_creation:.1f} years ago
          Commits: {self.total_commits}
          Contributors: {self.num_contributors}
          Last updated: {self.months_since_update:.0f} months ago
          Maturity: {'Production-ready' if self.is_production else 'Experimental'}
        
        Physics:
          Type: {self.physics_type}
          Chemistry: {self.chemistry_mechanism or 'None'}
          Flow regime: {self.flow_regime}
          Multiphase: {self.has_multiphase}
          Turbulence: {self.turbulence_model or 'Laminar'}
          Boundary conditions: {self.boundary_conditions}
          Dimension: {self.dimension}D
        
        Configuration:
          Default grid: {self.default_grid}
          AMR levels: {self.amr_levels}
          Variants: {', '.join(self.available_inputs)}
          Runtime estimate: {self.estimated_runtime_hours or 'Unknown'} CPU hours
        
        Quality Tier: {self.quality_tier}
        """
```

#### **12.2.2 DocumentMatch**

```python
@dataclass
class DocumentMatch:
    """Structured result from Level 1 documentation retrieval."""
    
    content: str
    """Document text snippet (up to 500 chars)."""
    
    doc_type: str
    """
    Document type:
      - 'solver_readme'
      - 'case_readme'
      - 'parameter_guide'
      - 'problem_catalog'
      - 'performance_data'
      - 'build_instructions'
    """
    
    source: str
    """File path or report ID (e.g., 'report5.txt', 'PMF/README.md')."""
    
    score: float
    """Relevance score (0-1, higher is better)."""
    
    metadata: Dict[str, Any]
    """Additional context from document."""
    
    # ===== Type-Specific Fields =====
    case_name: Optional[str] = None
    """Case name if doc_type='case_readme'."""
    
    case_path: Optional[Path] = None
    """Full path to case if doc_type='case_readme'."""
    
    report_id: Optional[int] = None
    """Report number if source is curated report (1-9)."""
    
    section: Optional[str] = None
    """Section header if document has structure (e.g., '1.1 Grid Setup')."""
```

#### **12.2.3 SimulationPlan**

```python
@dataclass
class SimulationPlan:
    """Complete plan from ArchitectService."""
    
    selected_solver: str
    """Primary solver (e.g., 'PeleLMeX')."""
    
    solver_confidence: float
    """Confidence score for solver selection (0-1)."""
    
    selected_case: Path
    """Path to baseline case."""
    
    case_candidates: List[CaseMetadata]
    """Top-k cases with scores (for explainability)."""
    
    modifications: List[Tuple[str, Any]]
    """Planned modifications to inputs file."""
    
    reasoning: str
    """Comprehensive explanation."""
    
    documentation_context: List[DocumentMatch]
    """Supporting documentation retrieved."""
```

#### **12.2.4 ValidationResult**

```python
@dataclass
class ValidationResult:
    """Result from ReviewerService validation."""
    
    mode: Literal["proceed", "retry", "fail"]
    """Decision mode."""
    
    errors: List[str]
    """Validation errors (empty if mode='proceed')."""
    
    suggestions: List[str] = field(default_factory=list)
    """Fix suggestions for each error."""
    
    analysis: str = ""
    """Human-readable analysis."""
```

#### **12.2.5 PaperMetadata**

```python
@dataclass
class PaperMetadata:
    """Research paper metadata from arXiv."""
    
    title: str
    authors: List[str]
    abstract: str
    pdf_url: str
    published: str  # ISO date
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
```

#### **12.2.6 SimulationDetails**

```python
@dataclass
class SimulationDetails:
    """Extracted simulation parameters from PDF."""
    
    solver: Optional[str] = None
    """Solver name extracted from paper."""
    
    grid_resolution: Optional[str] = None
    """Grid description (e.g., '128×128×256')."""
    
    boundary_conditions: Optional[str] = None
    """BC description."""
    
    chemistry_mechanism: Optional[str] = None
    """Chemistry mechanism name."""
```

#### **12.2.7 ValidationReport**

```python
@dataclass
class ValidationReport:
    """Paper validation report."""
    
    matches: List[str]
    """
    Comparison results.
    Example: ['Solver: ✓ (exact match)', 'Grid: ~ (similar resolution)']
    """
    
    physics_match: bool
    """True if physics aligns (>66% matches)."""
    
    similarity_score: float
    """Overall similarity (0-1)."""
    
    plot_similarity: Optional[float] = None
    """SSIM score if plots compared."""
    
    has_plots: bool = False
    """True if plot comparison was performed."""
```

---

## **13. API Specifications**

### **13.1 Command-Line Interface**

**Primary CLI:** `pele-agent`

```bash
pele-agent [command] [options]

Commands:
  setup           Generate simulation configuration
  validate        Validate existing inputs file
  build-indices   Build/rebuild FAISS indices
  ablation        Run ablation study
  version         Show version information
  help            Show this help message
```

---

#### **13.1.1 Setup Command**

```bash
pele-agent setup [options]

Generate simulation configuration from natural language prompt.

Options:
  --prompt TEXT              Natural language simulation request
                             Can be inline or path to text file
                             
  --solver TEXT              Force specific solver (PeleC, PeleLMeX, PeleMP)
                             If omitted, agent selects automatically
                             
  --mode TEXT                Workflow mode: 'production' or 'validation'
                             Default: production
                             
  --output-dir PATH          Output directory for run files
                             Default: ./runs
                             
  --validate-paper TEXT      arXiv ID for paper validation
                             Only used if --mode validation
                             Example: arxiv:2103.12345
                             
  --disable-indices TEXT     Comma-separated indices to disable (ablation)
                             Example: git_metrics,performance_estimates
                             
  --config PATH              Path to config file
                             Default: ~/.pele-agent/config.yaml
                             
  --verbose                  Verbose output (show per-index scores)
  --debug                    Debug mode (JSON output for all state)
  --help                     Show this help

Examples:
  # Basic usage
  pele-agent setup --prompt "premixed methane flame DNS"
  
  # From text file
  pele-agent setup --prompt my_prompt.txt
  
  # Force specific solver
  pele-agent setup --prompt "turbulent combustion" --solver PeleLMeX
  
  # Validation mode (FOAM benchmark)
  pele-agent setup --prompt foam_case_7.txt --mode validation --validate-paper arxiv:2103.12345
  
  # Ablation testing
  pele-agent setup --prompt test.txt --disable-indices git_metrics,performance_estimates
```

**Output:**

```bash
$ pele-agent setup --prompt "premixed methane DNS"

🔍 Analyzing query...
  ✓ Physics family: low_mach_combustion (0.92)
  ✓ Solver: PeleLMeX (optimized for low-Mach DNS)

📚 Retrieving documentation...
  ✓ Found 5 relevant guides
    • [parameter_guide] report5.txt (0.88)
    • [case_readme] FlameSheet/README.md (0.85)
    • [problem_catalog] report2.txt (0.78)

🎯 Searching 45 cases...
  ✓ Top match: FlameSheet (combined: 0.87)
    Index scores:
      physics_descriptors   (35%): 0.95 ████████████
      grid_configurations   (20%): 0.80 ██████████
      git_metrics          (15%): 0.90 ███████████
      path_hierarchy       (15%): 0.75 █████████
      chemistry_mechanisms (10%): 0.95 ████████████
      performance_estimates (5%): 0.70 ████████

📝 Planning modifications...
  ✓ Grid: 256³ (DNS resolution)
  ✓ Chemistry: drm19.yaml (methane-air)
  ✓ Boundary: Periodic

✅ Validation passed (0 errors)

📁 Generated: run_20241201_143052/
   Files:
     inputs          Modified inputs file
     drm19.yaml      Chemistry mechanism
     submit.sh       SLURM script
     README.md       Full explanation

   Next steps:
     cd run_20241201_143052
     sbatch submit.sh

⏱️  Total time: 4.2 seconds
```

---

#### **13.1.2 Validate Command**

```bash
pele-agent validate [options]

Validate existing inputs file for common errors.

Options:
  --inputs PATH              Path to inputs file to validate
  --solver TEXT              Solver name (PeleC, PeleLMeX, PeleMP)
  --help                     Show this help

Examples:
  pele-agent validate --inputs my_inputs --solver PeleC

Output:
  ✓ All checks passed
  or
  ✗ 3 errors found:
    1. Missing required parameter: amr.max_level
    2. Physics conflict: EB + all-periodic BCs
    3. File not found: nonexistent.yaml
```

---

#### **13.1.3 Build-Indices Command**

```bash
pele-agent build-indices [options]

Build or rebuild FAISS indices from repository data.

Options:
  --solvers TEXT             Comma-separated solvers to build
                             Example: PeleC,PeleLMeX
                             Default: all configured solvers
                             
  --mode TEXT                Index mode: 'testing' or 'production'
                             testing = 82 indices (full granularity)
                             production = 25-82 (based on ablation)
                             Default: testing
                             
  --force                    Force rebuild (overwrite existing)
  --parallel                 Use parallel processing
  --help                     Show this help

Examples:
  # Build all indices (testing mode)
  pele-agent build-indices
  
  # Build specific solvers
  pele-agent build-indices --solvers PeleC,PeleLMeX
  
  # Production mode (post-ablation)
  pele-agent build-indices --mode production
  
Output:
  Building indices (testing mode)...
  
  Level 0: Physics Taxonomy
    ✓ physics_regimes (4 documents, 1.2 MB)
    ✓ solver_capabilities (6 documents, 0.8 MB)
    ✓ code_lineage (8 documents, 1.5 MB)
    ✓ cross_cutting_guidance (3 documents, 2.1 MB)
  
  Level 1: PeleC Documentation
    ✓ solver_readme (1 document, 0.3 MB)
    ✓ problem_catalogs (1 document, 1.8 MB)
    ✓ parameter_guides (1 document, 2.3 MB)
    ✓ performance_data (1 document, 1.1 MB)
    ✓ build_instructions (1 document, 0.4 MB)
    ✓ case_inventory (1 document, 0.6 MB)
    ✓ case_readmes (45 documents, 12.3 MB)
  
  Level 2: PeleC Case Metadata
    ✓ physics_descriptors (45 cases, 8.2 MB)
    ✓ grid_configurations (45 cases, 3.1 MB)
    ✓ git_metrics (45 cases, 2.8 MB)
    ✓ path_hierarchy (45 cases, 1.9 MB)
    ✓ chemistry_mechanisms (45 cases, 2.1 MB)
    ✓ performance_estimates (45 cases, 3.4 MB)
  
  [... PeleLMeX, PeleMP ...]
  
  ✓ Total: 82 indices built
  ✓ Total size: 218.4 MB
  ✓ Build time: 26.3 minutes
```

---

#### **13.1.4 Ablation Command**

```bash
pele-agent ablation [options]

Run ablation study to measure index contributions.

Options:
  --test-oracle PATH         Path to test oracle YAML
                             Required
                             
  --output PATH              Output path for results JSON
                             Default: ablation_results.json
                             
  --levels TEXT              Which levels to test: 0,1,2
                             Default: all
                             
  --solvers TEXT             Which solvers to test
                             Default: all
                             
  --help                     Show this help

Examples:
  # Full ablation (all 82 indices)
  pele-agent ablation --test-oracle oracle.yaml
  
  # Level 2 only (case metadata)
  pele-agent ablation --test-oracle oracle.yaml --levels 2
  
  # Specific solver
  pele-agent ablation --test-oracle oracle.yaml --solvers PeleC

Output:
  Running ablation study...
  
  Test Oracle: oracle_v1.yaml (20 cases)
  
  Level 0 Ablation (4 indices):
    ✓ Baseline (all indices): 19/20 (95%)
    • No physics_regimes:      17/20 (85%)  [contribution: 10%]
    • No solver_capabilities:  18/20 (90%)  [contribution: 5%]
    • No code_lineage:         19/20 (95%)  [contribution: 0%]
    • No cross_cutting:        19/20 (95%)  [contribution: 0%]
  
  Level 2 Ablation - PeleC (6 indices):
    ✓ Baseline: 18/20 (90%)
    • No physics_descriptors:  14/20 (70%)  [contribution: 20%] ⚠️ HIGH
    • No grid_configurations:  16/20 (80%)  [contribution: 10%]
    • No git_metrics:          16/20 (80%)  [contribution: 10%]
    • No path_hierarchy:       17/20 (85%)  [contribution: 5%]
    • No chemistry_mechanisms: 16/20 (80%)  [contribution: 10%]
    • No performance_estimates: 18/20 (90%) [contribution: 0%]  ⚠️ LOW
  
  [... other levels/solvers ...]
  
  Summary:
    High contributors (≥10%): physics_descriptors, grid_configurations, git_metrics
    Low contributors (<5%):   code_lineage, cross_cutting, performance_estimates
  
  Recommendation: Scenario B (selective merge)
    Keep separate: physics_descriptors, grid_configurations, git_metrics, path_hierarchy
    Merge: chemistry_mechanisms + performance_estimates → case_metadata_secondary
  
  ✓ Results saved to: ablation_results.json
  ✓ Total time: 42.3 minutes
```

---

### **13.2 Configuration File Format**

**Location:** `~/.pele-agent/config.yaml`

```yaml
# AMReXAgent Configuration

# ===== Repository Paths =====
repositories:
  PeleC:
    path: /global/cfs/cdirs/m3018/repos/PeleC
    enabled: true
  PeleLMeX:
    path: /global/cfs/cdirs/m3018/repos/PeleLMeX
    enabled: true
  PeleMP:
    path: /global/cfs/cdirs/m3018/repos/PeleMP
    enabled: true

# ===== Database Paths =====
database:
  faiss_indices: ~/.pele-agent/database/faiss
  case_metadata: ~/.pele-agent/database/case_metadata.json
  reports: ~/.pele-agent/database/reports
  foam_benchmark: ~/.pele-agent/database/foam_benchmark

# ===== Index Configuration =====
index_mode: testing  # 'testing' (82 indices) or 'production' (25-82)

# Level 0 weights
level0_weights:
  physics_regimes: 0.40
  solver_capabilities: 0.30
  code_lineage: 0.20
  cross_cutting_guidance: 0.10

# Level 1 weights (per solver)
level1_weights:
  default:
    case_readmes: 0.35
    parameter_guides: 0.25
    problem_catalogs: 0.15
    performance_data: 0.10
    solver_readme: 0.08
    build_instructions: 0.05
    case_inventory: 0.02

# Level 2 weights (per solver)
level2_weights:
  default:
    physics_descriptors: 0.35
    grid_configurations: 0.20
    git_metrics: 0.15
    path_hierarchy: 0.15
    chemistry_mechanisms: 0.10
    performance_estimates: 0.05

# ===== Embedding Provider =====
embedding:
  provider: cborg  # 'cborg', 'openai', or 'local'
  
  cborg:
    api_url: https://cborg.lbl.gov/api/v1/embed
    api_key: ${CBORG_API_KEY}  # From environment
  
  openai:
    api_key: ${OPENAI_API_KEY}
    model: text-embedding-ada-002
  
  local:
    model_name: sentence-transformers/all-MiniLM-L6-v2

# ===== LLM Provider =====
llm:
  provider: anthropic  # 'anthropic' or 'openai'
  
  anthropic:
    api_key: ${ANTHROPIC_API_KEY}
    model: claude-sonnet-4-20250514
    temperature: 0.3
  
  openai:
    api_key: ${OPENAI_API_KEY}
    model: gpt-4
    temperature: 0.3

# ===== SLURM Configuration =====
slurm:
  account: m3018
  partition: regular
  qos: regular
  constraint: cpu
  nodes: 2
  ntasks_per_node: 64
  time: "01:00:00"

# ===== Output =====
output_dir: ./runs

# ===== Logging =====
logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  file: ~/.pele-agent/logs/pele-agent.log

# ===== Test Oracle =====
test_oracle_path: ~/.pele-agent/test_oracle/oracle_v1.yaml
```

---

# **AMReXAgent: Product & Technical Specification**
## **Phase 6: Testing, Deployment & Reference**

---

## **14. Test Strategy**

### **14.1 Test Pyramid**

```
                    ▲
                   / \
                  /   \
                 /  E2E \    4 tests (10%)     ← Full workflow validation
                /───────\
               / Integration\ 20 tests (30%)   ← Service interactions
              /─────────────\
             /  Unit Tests   \ 40 tests (60%)  ← Component isolation
            /─────────────────\
           ───────────────────
```

**Target Coverage:** ≥85%  
**Total Tests:** ~64 tests  
**Execution Time:** <5 minutes (all tests)

---

### **14.2 Unit Tests**

**Objective:** Test individual components in isolation.

#### **14.2.1 Config Service Tests**

```python
# tests/unit/test_config.py

import pytest
from pathlib import Path
from amrex_agent.config import PeleAgentConfig, load_config

def test_config_load_from_yaml():
    """Test loading config from YAML file."""
    config = load_config(Path("tests/fixtures/config.yaml"))
    
    assert config.index_mode == "testing"
    assert config.level0_weights["physics_regimes"] == 0.40
    assert "PeleC" in config.repositories

def test_config_defaults():
    """Test default values when config incomplete."""
    config = PeleAgentConfig()
    
    assert config.max_retries == 3
    assert config.index_mode == "testing"
    assert config.output_dir == Path("./runs")

def test_config_environment_variables():
    """Test environment variable substitution."""
    import os
    os.environ["CBORG_API_KEY"] = "test_key_123"
    
    config = load_config(Path("tests/fixtures/config_with_env.yaml"))
    
    assert config.embedding_config["cborg"]["api_key"] == "test_key_123"

def test_config_validation_fails_on_invalid_mode():
    """Test validation catches invalid index_mode."""
    with pytest.raises(ValueError, match="index_mode must be"):
        PeleAgentConfig(index_mode="invalid")

def test_config_weight_normalization():
    """Test that weights sum to 1.0."""
    config = PeleAgentConfig()
    
    level0_sum = sum(config.level0_weights.values())
    assert abs(level0_sum - 1.0) < 0.01  # Allow floating point error
```

**Coverage Target:** 100% (config.py already at 100%)

---

#### **14.2.2 Embedding Service Tests**

```python
# tests/unit/test_embedding_service.py

import pytest
import numpy as np
from unittest.mock import Mock, patch
from amrex_agent.services.embedding import MultiIndexEmbeddingService

@pytest.fixture
def mock_config():
    """Mock configuration."""
    config = Mock()
    config.index_mode = "testing"
    config.faiss_db_path = Path("tests/fixtures/faiss")
    config.level0_weights = {
        "physics_regimes": 0.40,
        "solver_capabilities": 0.30,
        "code_lineage": 0.20,
        "cross_cutting_guidance": 0.10
    }
    return config

@pytest.fixture
def mock_embedder():
    """Mock embedding provider."""
    embedder = Mock()
    embedder.embed.return_value = np.random.rand(768)
    return embedder

def test_search_solver_capabilities(mock_config, mock_embedder):
    """Test Level 0 solver selection."""
    service = MultiIndexEmbeddingService(
        config=mock_config,
        embedding_provider=mock_embedder
    )
    
    with patch.object(service, '_get_index') as mock_get_index:
        # Mock FAISS index returns
        mock_index = Mock()
        mock_index.search.return_value = [
            (Mock(metadata={"codes": ["PeleLMeX"]}), 0.92),
            (Mock(metadata={"codes": ["PeleC"]}), 0.60)
        ]
        mock_get_index.return_value = mock_index
        
        # Test
        results = service.search_solver_capabilities("low-Mach combustion")
        
        assert results[0][0] == "PeleLMeX"
        assert results[0][1] > results[1][1]  # Confidence ordering

def test_search_documentation(mock_config, mock_embedder):
    """Test Level 1 documentation retrieval."""
    service = MultiIndexEmbeddingService(
        config=mock_config,
        embedding_provider=mock_embedder
    )
    
    # Test that all 7 Level 1 indices are queried
    with patch.object(service, '_get_index') as mock_get_index:
        mock_index = Mock()
        mock_index.search.return_value = []
        mock_get_index.return_value = mock_index
        
        service.search_documentation("DNS grid setup", solver="PeleC")
        
        # Should query 7 indices
        assert mock_get_index.call_count == 7

def test_search_case_metadata(mock_config, mock_embedder):
    """Test Level 2 case search."""
    service = MultiIndexEmbeddingService(
        config=mock_config,
        embedding_provider=mock_embedder
    )
    
    with patch.object(service, '_get_index') as mock_get_index:
        mock_index = Mock()
        mock_index.search.return_value = [
            (Mock(metadata={"case_id": "pelec_pmf"}), 0.95)
        ]
        mock_get_index.return_value = mock_index
        
        with patch.object(service, '_load_case_metadata') as mock_load:
            mock_metadata = Mock()
            mock_metadata.case_id = "pelec_pmf"
            mock_load.return_value = mock_metadata
            
            results = service.search_case_metadata(
                "premixed methane",
                solver="PeleC"
            )
            
            assert len(results) > 0
            assert results[0].case_id == "pelec_pmf"

def test_weighted_combination():
    """Test score combination algorithm."""
    service = MultiIndexEmbeddingService(Mock(), Mock())
    
    results = {
        "physics_regimes": {"PeleLMeX": 0.90, "PeleC": 0.50},
        "solver_capabilities": {"PeleLMeX": 0.95, "PeleC": 0.60}
    }
    
    weights = {
        "physics_regimes": 0.40,
        "solver_capabilities": 0.60
    }
    
    combined = service._combine_solver_scores(results, weights)
    
    # PeleLMeX: 0.40*0.90 + 0.60*0.95 = 0.93
    # PeleC: 0.40*0.50 + 0.60*0.60 = 0.56
    assert abs(combined["PeleLMeX"] - 0.93) < 0.01
    assert abs(combined["PeleC"] - 0.56) < 0.01

def test_ablation_mode_disables_indices():
    """Test ablation testing (disabled indices)."""
    service = MultiIndexEmbeddingService(Mock(), Mock())
    
    with patch.object(service, '_get_index') as mock_get_index:
        mock_get_index.return_value = Mock(search=Mock(return_value=[]))
        
        # Ablation: disable git_metrics
        service.search_case_metadata(
            "test",
            solver="PeleC",
            enabled_indices=["physics_descriptors", "grid_configurations"]
        )
        
        # Should only query 2 indices (not all 6)
        assert mock_get_index.call_count == 2
```

**Coverage Target:** ≥90%

---

#### **14.2.3 Reviewer Service Tests**

```python
# tests/unit/test_reviewer.py

import pytest
from pathlib import Path
from amrex_agent.services.reviewer import ReviewerService

def test_missing_required_parameter():
    """Test detection of missing required parameters."""
    reviewer = ReviewerService(Mock())
    
    # Inputs file missing amr.n_cell
    inputs = """
    geometry.prob_lo = 0 0 0
    geometry.prob_hi = 1 1 1
    # Missing: amr.n_cell
    """
    
    inputs_file = Path("/tmp/test_inputs")
    inputs_file.write_text(inputs)
    
    result = reviewer.validate(inputs_file, solver="PeleC", modifications=[])
    
    assert result.mode in ["retry", "fail"]
    assert any("amr.n_cell" in error for error in result.errors)

def test_invalid_syntax_detection():
    """Test detection of syntax errors."""
    reviewer = ReviewerService(Mock())
    
    inputs = """
    amr.n_cell = 256^3
    """
    
    inputs_file = Path("/tmp/test_inputs")
    inputs_file.write_text(inputs)
    
    result = reviewer.validate(inputs_file, solver="PeleC", modifications=[])
    
    assert any("Invalid syntax" in error for error in result.errors)
    assert any("256 256 256" in sugg for sugg in result.suggestions)

def test_physics_inconsistency_eb_periodic():
    """Test detection of EB + all-periodic conflict."""
    reviewer = ReviewerService(Mock())
    
    inputs = """
    eb2.geom_type = sphere
    geometry.is_periodic = 1 1 1
    amr.n_cell = 64 64 64
    """
    
    inputs_file = Path("/tmp/test_inputs")
    inputs_file.write_text(inputs)
    
    result = reviewer.validate(inputs_file, solver="PeleC", modifications=[])
    
    assert any("Physics conflict" in error for error in result.errors)
    assert any("EB geometry" in error for error in result.errors)

def test_file_dependency_check():
    """Test detection of missing chemistry files."""
    reviewer = ReviewerService(Mock())
    
    inputs = """
    pelec.chem_file = nonexistent.yaml
    amr.n_cell = 64 64 64
    """
    
    inputs_file = Path("/tmp/test_inputs")
    inputs_file.write_text(inputs)
    
    result = reviewer.validate(inputs_file, solver="PeleC", modifications=[])
    
    assert any("not found" in error for error in result.errors)

def test_all_checks_pass():
    """Test successful validation (no errors)."""
    reviewer = ReviewerService(Mock())
    
    inputs = """
    amr.n_cell = 64 64 64
    amr.max_level = 0
    geometry.prob_lo = 0 0 0
    geometry.prob_hi = 1 1 1
    geometry.is_periodic = 1 1 1
    """
    
    inputs_file = Path("/tmp/test_inputs")
    inputs_file.write_text(inputs)
    
    result = reviewer.validate(inputs_file, solver="PeleC", modifications=[])
    
    assert result.mode == "proceed"
    assert len(result.errors) == 0
```

**Coverage Target:** ≥90%

---

### **14.3 Integration Tests**

**Objective:** Test interactions between multiple components.

```python
# tests/integration/test_workflow_nodes.py

import pytest
from amrex_agent.workflow import (
    solver_selector_node,
    architect_node,
    reviewer_node
)

@pytest.fixture
def mock_state():
    """Base state for testing."""
    return {
        "prompt": "premixed methane flame DNS",
        "config": load_test_config(),
        "retry_count": 0,
        "max_retries": 3
    }

def test_solver_selector_to_architect_flow(mock_state):
    """Test Level 0 → Level 1-2 flow."""
    # Step 1: Solver selection
    state = solver_selector_node(mock_state)
    
    assert "selected_solvers" in state
    assert len(state["selected_solvers"]) > 0
    
    # Step 2: Architecture planning
    state = architect_node(state)
    
    assert "selected_case" in state
    assert "modifications" in state
    assert state["selected_case"] is not None

def test_architect_to_reviewer_flow(mock_state):
    """Test planning → validation flow."""
    # Setup: Run solver selector + architect
    state = solver_selector_node(mock_state)
    state = architect_node(state)
    
    # Validation
    state = reviewer_node(state)
    
    assert "mode" in state
    assert state["mode"] in ["proceed", "retry", "fail"]

def test_retry_loop_propagates_errors():
    """Test that errors are sent back to architect on retry."""
    state = {
        "prompt": "test",
        "config": load_test_config(),
        "selected_solvers": [("PeleC", 0.9)],
        "retry_count": 0,
        "max_retries": 3
    }
    
    # Force architect to create invalid plan
    with patch("amrex_agent.services.architect.ArchitectService.create_plan") as mock_plan:
        mock_plan.return_value = Mock(
            selected_case=Path("PeleC/Exec/RegTests/PMF"),
            modifications=[("amr.n_cell", "256^3")],  # Invalid syntax
            reasoning="test"
        )
        
        state = architect_node(state)
        state = reviewer_node(state)
        
        # Should be in retry mode
        assert state["mode"] == "retry"
        assert len(state["errors_active"]) > 0
        
        # Retry with error context
        state = architect_node(state)
        
        # Architect should receive previous errors
        assert mock_plan.call_args[1]["previous_errors"] is not None

def test_max_retries_triggers_fail():
    """Test that exceeding max retries triggers fail mode."""
    state = {
        "prompt": "test",
        "config": load_test_config(),
        "selected_solvers": [("PeleC", 0.9)],
        "retry_count": 3,  # Already at max
        "max_retries": 3,
        "errors_active": ["test error"]
    }
    
    state = reviewer_node(state)
    
    assert state["mode"] == "fail"
    assert any("Max retries" in error for error in state["errors_active"])
```

**Coverage Target:** ≥80%

---

### **14.4 End-to-End Tests**

**Objective:** Full workflow validation against test oracle.

```python
# tests/e2e/test_full_workflow.py

import pytest
from amrex_agent.workflow import build_workflow
from amrex_agent.config import load_config

@pytest.fixture
def test_oracle():
    """Load test oracle cases."""
    import yaml
    with open("database/test_oracle/oracle_v1.yaml") as f:
        return yaml.safe_load(f)

def test_oracle_case_001_premixed_methane(test_oracle):
    """
    Test oracle case 1: Premixed methane flame DNS.
    
    Expected: PeleLMeX/Exec/RegTests/FlameSheet
    """
    case = test_oracle["test_cases"][0]
    
    workflow = build_workflow(mode="production")
    
    initial_state = {
        "prompt": case["prompt"],
        "config": load_config(),
        "retry_count": 0,
        "max_retries": 3
    }
    
    final_state = workflow.invoke(initial_state)
    
    # Assertions
    assert final_state["mode"] == "proceed"
    assert case["expected_solver"] in final_state["selected_solvers"][0][0]
    assert case["expected_case"] in final_state["selected_case"]

def test_oracle_case_002_supersonic_hydrogen(test_oracle):
    """
    Test oracle case 2: Supersonic hydrogen combustion.
    
    Expected: PeleC/Exec/Production/CavityFlame
    """
    case = test_oracle["test_cases"][1]
    
    workflow = build_workflow(mode="production")
    
    initial_state = {
        "prompt": case["prompt"],
        "config": load_config(),
        "retry_count": 0,
        "max_retries": 3
    }
    
    final_state = workflow.invoke(initial_state)
    
    assert final_state["mode"] == "proceed"
    assert case["expected_solver"] in final_state["selected_solvers"][0][0]
    assert case["expected_case"] in final_state["selected_case"]

@pytest.mark.parametrize("case_id", range(20))
def test_all_oracle_cases(test_oracle, case_id):
    """
    Parameterized test for all 20 oracle cases.
    
    Gate 2 requirement: ≥90% pass (18/20).
    """
    case = test_oracle["test_cases"][case_id]
    
    workflow = build_workflow(mode="production")
    
    initial_state = {
        "prompt": case["prompt"],
        "config": load_config(),
        "retry_count": 0,
        "max_retries": 3
    }
    
    final_state = workflow.invoke(initial_state)
    
    # Check if correct case selected
    correct = case["expected_case"] in final_state["selected_case"]
    
    # Log result
    print(f"Case {case['id']}: {'✓' if correct else '✗'}")
    
    # Individual test may fail (≤10% failure allowed)
    # Overall suite must achieve 90% in Gate 2 validation
    assert correct, f"Expected {case['expected_case']}, got {final_state['selected_case']}"

def test_validation_mode_with_paper():
    """Test validation mode (FOAM benchmark)."""
    workflow = build_workflow(mode="validation")
    
    initial_state = {
        "prompt": "turbulent jet flame",
        "config": load_config(),
        "validation_mode": True,
        "foam_case_id": "foam_007",
        "retry_count": 0,
        "max_retries": 3
    }
    
    final_state = workflow.invoke(initial_state)
    
    # Should have paper validation results
    assert "arxiv_metadata" in final_state
    assert "validation_report" in final_state
    assert final_state["validation_report"]["physics_match"] is True
```

**Gate 2 Pass Criteria:**

```python
def test_gate2_overall_accuracy():
    """
    Gate 2 validation: Overall accuracy ≥90%.
    
    This test aggregates all oracle case results.
    """
    oracle = load_oracle("database/test_oracle/oracle_v1.yaml")
    workflow = build_workflow(mode="production")
    
    results = []
    
    for case in oracle["test_cases"]:
        state = workflow.invoke({
            "prompt": case["prompt"],
            "config": load_config(),
            "retry_count": 0,
            "max_retries": 3
        })
        
        correct = case["expected_case"] in state["selected_case"]
        results.append(correct)
    
    accuracy = sum(results) / len(results)
    
    print(f"Overall accuracy: {accuracy:.1%} ({sum(results)}/{len(results)})")
    
    assert accuracy >= 0.90, f"Gate 2 failed: {accuracy:.1%} < 90%"
```

---

### **14.5 Ablation Tests**

```python
# tests/ablation/test_index_contributions.py

import pytest
from amrex_agent.ablation import run_ablation_study

def test_level0_ablation():
    """Test Level 0 index contributions."""
    results = run_ablation_study(
        level=0,
        test_oracle="database/test_oracle/oracle_v1.yaml"
    )
    
    # Check that all 4 indices tested
    assert "physics_regimes" in results
    assert "solver_capabilities" in results
    assert "code_lineage" in results
    assert "cross_cutting_guidance" in results
    
    # Each should have accuracy score
    for index_name, result in results.items():
        assert "accuracy" in result
        assert "contribution" in result
        assert 0.0 <= result["accuracy"] <= 1.0

def test_level2_ablation_pelec():
    """Test Level 2 (case metadata) ablation for PeleC."""
    results = run_ablation_study(
        level=2,
        solver="PeleC",
        test_oracle="database/test_oracle/oracle_v1.yaml"
    )
    
    # Check all 6 Level 2 indices tested
    expected_indices = [
        "physics_descriptors",
        "grid_configurations",
        "git_metrics",
        "path_hierarchy",
        "chemistry_mechanisms",
        "performance_estimates"
    ]
    
    for index_name in expected_indices:
        assert index_name in results
        assert results[index_name]["accuracy"] >= 0.0

def test_identify_high_contributors():
    """Test that ablation identifies high-contribution indices."""
    results = run_ablation_study(
        level=2,
        solver="PeleC",
        test_oracle="database/test_oracle/oracle_v1.yaml"
    )
    
    # Find indices with ≥5% contribution
    high_contributors = [
        name for name, result in results.items()
        if result["contribution"] >= 0.05
    ]
    
    assert len(high_contributors) > 0
    
    # physics_descriptors should always be high contributor
    assert "physics_descriptors" in high_contributors

def test_production_config_decision():
    """Test production config decision tree."""
    from amrex_agent.ablation import decide_production_config
    
    # Mock ablation results
    ablation_results = {
        "level_2": {
            "physics_descriptors": {"contribution": 0.20},
            "grid_configurations": {"contribution": 0.10},
            "git_metrics": {"contribution": 0.10},
            "path_hierarchy": {"contribution": 0.05},
            "chemistry_mechanisms": {"contribution": 0.03},
            "performance_estimates": {"contribution": 0.01}
        }
    }
    
    decision = decide_production_config(ablation_results)
    
    # With 4/6 indices contributing ≥5%, should recommend scenario B
    assert decision in ["scenario_b_selective_merge", "scenario_a_keep_all"]
```

---

### **14.6 Test Execution Strategy**

**Continuous Integration (GitHub Actions):**

```yaml
# .github/workflows/test.yml

name: Test Suite

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Run unit tests
        run: |
          pytest tests/unit --cov=amrex_agent --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
  
  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Run integration tests
        run: |
          pytest tests/integration -v
  
  e2e-tests:
    runs-on: ubuntu-latest
    needs: integration-tests
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Build test indices
        run: |
          pele-agent build-indices --mode testing --solvers PeleC
      
      - name: Run E2E tests
        run: |
          pytest tests/e2e -v --tb=short
```

**Local Testing:**

```bash
# Run all tests
pytest

# Run specific test level
pytest tests/unit
pytest tests/integration
pytest tests/e2e

# Run with coverage
pytest --cov=amrex_agent --cov-report=html

# Run specific test file
pytest tests/unit/test_config.py -v

# Run specific test
pytest tests/e2e/test_full_workflow.py::test_oracle_case_001 -v

# Run ablation tests (slow)
pytest tests/ablation -v --tb=short
```

---

## **15. Deployment Plan**

### **15.1 NERSC Perlmutter Deployment**

**Target Environment:** NERSC Perlmutter login nodes + compute nodes

#### **15.1.1 Installation**

```bash
# On Perlmutter login node

# 1. Load Python module
module load python/3.10

# 2. Create virtual environment
cd $HOME
python -m venv pele-agent-env
source pele-agent-env/bin/activate

# 3. Install AMReXAgent
pip install git+https://github.com/AMReX-Combustion/pele-agent.git

# 4. Initialize configuration
pele-agent init

# This creates:
#   ~/.pele-agent/
#   ├── config.yaml
#   ├── database/
#   │   ├── faiss/
#   │   ├── reports/
#   │   └── test_oracle/
#   └── logs/

# 5. Configure repository paths
vim ~/.pele-agent/config.yaml

# Edit:
repositories:
  PeleC:
    path: /global/cfs/cdirs/m3018/repos/PeleC
  PeleLMeX:
    path: /global/cfs/cdirs/m3018/repos/PeleLMeX
  PeleMP:
    path: /global/cfs/cdirs/m3018/repos/PeleMP

# 6. Set API keys (if using CBORG/OpenAI)
export CBORG_API_KEY="your_key"
export ANTHROPIC_API_KEY="your_key"

# Add to ~/.bashrc for persistence
echo 'export CBORG_API_KEY="your_key"' >> ~/.bashrc
echo 'export ANTHROPIC_API_KEY="your_key"' >> ~/.bashrc

# 7. Build indices (one-time, 30 min)
pele-agent build-indices --mode testing

# 8. Verify installation
pele-agent version
pele-agent --help
```

---

#### **15.1.2 Directory Structure**

```
$HOME/
├── pele-agent-env/              Virtual environment
│   ├── bin/pele-agent          CLI executable
│   └── lib/python3.10/...
│
├── .pele-agent/                 Config and data
│   ├── config.yaml             User configuration
│   ├── database/
│   │   ├── faiss/              82 FAISS indices (~220 MB)
│   │   ├── reports/            Curated reports (report1-9.txt)
│   │   ├── case_metadata.json  Case metadata database
│   │   └── test_oracle/        Test oracle (oracle_v1.yaml)
│   └── logs/
│       └── pele-agent.log      Application logs
│
├── runs/                        Generated run directories
│   ├── run_20241201_143052/
│   ├── run_20241201_150321/
│   └── ...
│
└── .bashrc                      Environment setup
```

---

#### **15.1.3 Filesystem Considerations**

**Perlmutter Filesystem Layout:**

| Filesystem | Path | Quota | Use Case |
|------------|------|-------|----------|
| **$HOME** | `/global/homes/u/username` | 40 GB | Config, indices, logs |
| **$SCRATCH** | `/pscratch/sd/u/username` | 20 TB | Run directories, output |
| **CFS (project)** | `/global/cfs/cdirs/m3018` | 30 TB | Shared repos, mechanisms |

**Recommended Setup:**

```bash
# Config in $HOME (persistent)
export PELE_AGENT_HOME=$HOME/.pele-agent

# Run directories in $SCRATCH (large, temporary)
export PELE_AGENT_RUNS=$SCRATCH/pele-runs

# Update config.yaml
vim ~/.pele-agent/config.yaml
```

```yaml
output_dir: /pscratch/sd/u/username/pele-runs

repositories:
  PeleC:
    path: /global/cfs/cdirs/m3018/repos/PeleC
```

---

#### **15.1.4 Batch Job Integration**

**Generated SLURM script includes proper module loading:**

```bash
# submit.sh (auto-generated by AMReXAgent)

#!/bin/bash
#SBATCH -J pele_sim
#SBATCH -A m3018
#SBATCH -C cpu
#SBATCH -q regular
#SBATCH -t 01:00:00
#SBATCH -N 2
#SBATCH --ntasks-per-node=64

# Load Pele environment
module load PrgEnv-gnu
module load cray-hdf5-parallel
module load cray-netcdf-hdf5parallel

# Set paths (if PeleC compiled in custom location)
export PELEC_HOME=/global/cfs/cdirs/m3018/repos/PeleC
export PATH=$PELEC_HOME/Exec/RegTests/PMF:$PATH

# Run simulation
srun -n 128 PeleC3d.gnu.MPI.ex inputs

echo "Complete: $(date)"
```

---

### **15.2 User Onboarding Plan**

**Target:** 3-5 initial users (Week 7 post-deployment)

#### **Phase 1: Demo Session (Week 7, Day 1)**

```
Duration: 30 minutes
Format: Screen share + live demo

Agenda:
  1. Introduction (5 min)
     - What is AMReXAgent?
     - Success criteria demo (90% accuracy on test oracle)
  
  2. Live Demo (15 min)
     - Run 3 example queries
     - Show explainability features
     - Explain when NOT to use agent
  
  3. Q&A (10 min)
     - User concerns
     - Use case discussion
```

#### **Phase 2: Hands-On Session (Week 7, Day 3)**

```
Duration: 1 hour
Format: User brings own simulation idea

Workflow:
  1. User describes simulation goal (10 min)
  2. Write prompt together (10 min)
  3. Run agent, review output (15 min)
  4. Expert validates selection (10 min)
  5. User submits job (if confident) (15 min)
```

#### **Phase 3: Feedback Collection (Week 7, Day 5)**

```
Duration: 30 minutes
Format: Exit interview

Questions:
  - Did agent select correct case?
  - Time saved vs manual setup?
  - Explainability clear?
  - Would you use again?
  - What improvements needed?
```

---

### **15.3 Rollback Plan**

**If deployment fails or users unsatisfied:**

```bash
# Rollback procedure

# 1. Deactivate agent
deactivate

# 2. Archive logs for analysis
tar -czf pele-agent-logs-$(date +%Y%m%d).tar.gz ~/.pele-agent/logs/

# 3. Document issues
vim rollback-report.md
# What failed?
# User feedback?
# Accuracy metrics?

# 4. Restore to manual workflow
# Users revert to existing case selection process

# 5. Plan fixes for Phase 2
# Address identified issues
# Re-deploy when ready
```

---

## **16. Monitoring & Metrics**

### **16.1 Performance Metrics**

**Tracked Automatically:**

```python
# Logged to ~/.pele-agent/logs/metrics.json

{
  "timestamp": "2024-12-01T14:30:52Z",
  "query": {
    "prompt": "premixed methane flame DNS",
    "solver_selected": "PeleLMeX",
    "case_selected": "FlameSheet",
    "mode": "proceed"
  },
  "timing": {
    "solver_selection_ms": 850,
    "documentation_retrieval_ms": 1420,
    "case_search_ms": 1680,
    "llm_planning_ms": 3200,
    "validation_ms": 450,
    "total_ms": 7600
  },
  "scores": {
    "solver_confidence": 0.92,
    "case_combined_score": 0.87,
    "index_scores": {
      "physics_descriptors": 0.95,
      "grid_configurations": 0.80,
      "git_metrics": 0.90
    }
  },
  "retry_count": 0
}
```

---

### **16.2 Accuracy Tracking**

**Weekly Test Oracle Runs:**

```bash
# Automated weekly cron job

#!/bin/bash
# weekly-oracle-test.sh

source $HOME/pele-agent-env/bin/activate

# Run full test oracle
pele-agent test-oracle \
  --oracle ~/.pele-agent/test_oracle/oracle_v1.yaml \
  --output ~/pele-oracle-results-$(date +%Y%m%d).json

# Email results to team
mail -s "AMReXAgent Weekly Accuracy" team@lbl.gov < ~/pele-oracle-results-$(date +%Y%m%d).json
```

**Metrics Reported:**

```json
{
  "date": "2024-12-08",
  "oracle_version": "v1.0",
  "total_cases": 20,
  "correct": 18,
  "accuracy": 0.90,
  "by_difficulty": {
    "easy": {"correct": 8, "total": 8, "accuracy": 1.00},
    "medium": {"correct": 7, "total": 8, "accuracy": 0.875},
    "hard": {"correct": 3, "total": 4, "accuracy": 0.75}
  },
  "failures": [
    {
      "case_id": "oracle_013",
      "expected": "PeleC/Exec/RegTests/PMF",
      "actual": "PeleC/Exec/RegTests/TaylorGreen",
      "reason": "Keyword match failure (turbulent → TG instead of PMF)"
    }
  ]
}
```

---

### **16.3 User Feedback Collection**

**Built-in Feedback Mechanism:**

```bash
# After each run
pele-agent setup --prompt "..."

# Output includes:
📁 Generated: run_20241201_143052/

Was this helpful?
  👍 Yes (pele-agent feedback --run run_20241201_143052 --rating 5)
  👎 No  (pele-agent feedback --run run_20241201_143052 --rating 1 --comment "Wrong case")
```

**Feedback Collection:**

```python
# ~/.pele-agent/feedback.jsonl (append-only log)

{"timestamp": "2024-12-01T14:35:00Z", "run_id": "run_20241201_143052", "rating": 5, "comment": ""}
{"timestamp": "2024-12-01T16:20:00Z", "run_id": "run_20241201_162015", "rating": 1, "comment": "Wrong case, should be PMF not TG"}
```

**Monthly Analysis:**

```python
def analyze_feedback():
    """Generate monthly feedback report."""
    import json
    
    feedback = []
    with open("~/.pele-agent/feedback.jsonl") as f:
        for line in f:
            feedback.append(json.loads(line))
    
    # Compute statistics
    ratings = [f["rating"] for f in feedback]
    avg_rating = sum(ratings) / len(ratings)
    
    # Identify issues
    negative = [f for f in feedback if f["rating"] <= 2]
    
    print(f"Average rating: {avg_rating:.2f}/5")
    print(f"Total feedback: {len(feedback)}")
    print(f"Negative feedback: {len(negative)}")
    
    for f in negative:
        print(f"  - {f['comment']}")
```

---

### **16.4 Alert Thresholds**

**Automated Monitoring:**

```yaml
# monitoring-config.yaml

alerts:
  accuracy_drop:
    threshold: 0.85  # Alert if accuracy <85%
    action: email_team
  
  high_error_rate:
    threshold: 0.10  # Alert if >10% validation failures
    action: slack_notification
  
  slow_queries:
    threshold: 15.0  # Alert if query >15 seconds
    action: log_warning
  
  index_build_failure:
    action: email_admin
```

---

## **APPENDICES**

---

## **Appendix A: Test Oracle Format**

**File:** `database/test_oracle/oracle_v1.yaml`

```yaml
# AMReXAgent Test Oracle v1.0
# Expert-curated ground truth for validation

version: "1.0"
curated_by: "Dr. Marc Day, Dr. Jon Rood"
date_created: "2024-12-01"
last_updated: "2024-12-01"
total_cases: 20

# Code snapshots (for reproducibility)
code_versions:
  PeleC_commit: "abc123def456789"
  PeleLMeX_commit: "789def456abc123"
  PeleMP_commit: "456abc123def789"

# Test cases
test_cases:
  # ===== Easy Cases (8) =====
  
  - id: "oracle_001"
    prompt: "Simulate premixed methane-air flame with detailed chemistry for turbulence study. Need DNS-quality resolution."
    expected_solver: "PeleLMeX"
    expected_case: "PeleLMeX/Exec/RegTests/FlameSheet"
    expected_variant: "inputs.3d"
    rationale: "Low-Mach turbulent DNS → PeleLMeX optimized, FlameSheet has turbulence model, premixed physics"
    difficulty: "easy"
    physics_keywords: ["low-Mach", "premixed", "DNS", "turbulence", "methane"]
  
  - id: "oracle_002"
    prompt: "Supersonic hydrogen combustion with shock-chemistry interaction, cavity flameholder geometry"
    expected_solver: "PeleC"
    expected_case: "PeleC/Exec/Production/CavityFlame"
    expected_variant: "inputs.3d"
    rationale: "Supersonic + shocks → PeleC required (only compressible solver), CavityFlame validated for H2"
    difficulty: "easy"
    physics_keywords: ["supersonic", "shock", "hydrogen", "compressible"]
  
  - id: "oracle_003"
    prompt: "Diesel spray combustion with Lagrangian particle tracking and soot formation"
    expected_solver: "PeleMP"
    expected_case: "PeleMP/Exec/Production/SprayJet"
    expected_variant: "inputs.3d"
    rationale: "Spray + Lagrangian → PeleMP (multiphase solver), SprayJet is spray injection template"
    difficulty: "easy"
    physics_keywords: ["spray", "Lagrangian", "diesel", "multiphase", "soot"]
  
  # [... 5 more easy cases ...]
  
  # ===== Medium Cases (8) =====
  
  - id: "oracle_009"
    prompt: "Turbulent non-premixed jet flame, need moderate resolution 128x128x256 for LES"
    expected_solver: "PeleLMeX"
    expected_case: "PeleLMeX/Exec/Production/JetFlame"
    expected_variant: "inputs.3d"
    rationale: "Non-premixed + turbulent + LES → PeleLMeX (low-Mach LES capable), JetFlame is jet template"
    difficulty: "medium"
    physics_keywords: ["non-premixed", "jet", "LES", "turbulent"]
    notes: "Could confuse with PeleC jet cases, but LES + moderate Ma → PeleLMeX better"
  
  - id: "oracle_010"
    prompt: "Flame-wall interaction study, need embedded boundary for wall geometry"
    expected_solver: "PeleLMeX"
    expected_case: "PeleLMeX/Exec/RegTests/EB-C7"
    expected_variant: "inputs.3d"
    rationale: "EB geometry + low-speed combustion → PeleLMeX with EB support, EB-C7 is EB template"
    difficulty: "medium"
    physics_keywords: ["embedded boundary", "wall interaction", "EB"]
    notes: "Requires recognizing EB-C7 as EB template despite non-obvious name"
  
  # [... 6 more medium cases ...]
  
  # ===== Hard Cases (4) =====
  
  - id: "oracle_017"
    prompt: "Premixed combustion but need to resolve shocks in unburned mixture upstream of flame"
    expected_solver: "PeleC"
    expected_case: "PeleC/Exec/RegTests/PMF"
    expected_variant: "inputs.3d"
    rationale: "Trick question: 'premixed' suggests PeleLMeX, but 'shocks' requires PeleC (compressible). PMF can handle both."
    difficulty: "hard"
    physics_keywords: ["premixed", "shock", "compressible"]
    trick: "Keyword 'premixed' misleading; shock requirement overrides"
  
  - id: "oracle_018"
    prompt: "Turbulent flow over backward-facing step, no combustion"
    expected_solver: "incflo"
    expected_case: "incflo/Exec/RegTests/BackwardStep"
    expected_variant: "inputs.3d"
    rationale: "Non-reacting turbulent flow → incflo (incompressible CFD), not Pele suite"
    difficulty: "hard"
    physics_keywords: ["non-reacting", "turbulent", "backward-facing step"]
    notes: "Only applies if incflo implemented; otherwise N/A for Phase 1"
  
  # [... 2 more hard cases ...]

# Metadata
difficulty_distribution:
  easy: 8
  medium: 8
  hard: 4

solver_distribution:
  PeleC: 7
  PeleLMeX: 9
  PeleMP: 3
  incflo: 1  # May be N/A if not implemented

expected_accuracy_targets:
  easy: 0.95    # 7-8/8
  medium: 0.875  # 7/8
  hard: 0.75     # 3/4
  overall: 0.90  # 18/20
```

---

## **Appendix B: FOAM Benchmark Details**

**FOAM-Agent Paper Reference:** arXiv:2103.12345 (hypothetical)

**Benchmark Setup:**

```yaml
# database/foam_benchmark/foam_cases.yaml

foam_benchmarks:
  - id: "foam_001"
    prompt: "Turbulent flow over backward-facing step, k-epsilon turbulence model"
    foam_selection: "simpleFoam/backwardFacingStep"
    pele_equivalent: null  # N/A (non-reacting, Phase 1 doesn't cover incflo)
    applicable: false
    category: "non_reacting_cfd"
  
  - id: "foam_007"
    prompt: "Non-premixed methane jet flame with detailed chemistry, grid 128×128×256, SST turbulence"
    foam_selection: "reactingFoam/jetFlame"
    pele_equivalent: "PeleLMeX/Exec/Production/JetFlame"
    applicable: true
    category: "reacting_flows"
    paper_reference:
      arxiv_id: "2103.12345"
      figure: "Figure 5"
      page: 12
  
  # [... 18 more cases ...]

summary:
  total_cases: 20
  applicable_to_pele: 12
  not_applicable: 8
  categories:
    reacting_flows: 8
    multiphase: 4
    non_reacting: 8
```

**Scoring Methodology:**

```python
def score_foam_benchmark():
    """
    Score AMReXAgent on FOAM benchmark.
    
    Only score applicable cases (reacting + multiphase).
    """
    foam_cases = load_foam_benchmark()
    applicable = [c for c in foam_cases if c["applicable"]]
    
    results = []
    
    for case in applicable:
        pele_result = run_amrex_agent(case["prompt"])
        
        # Check if Pele case aligns with FOAM case
        if pele_result.selected_case == case["pele_equivalent"]:
            score = 1.0  # Match
        elif physics_aligned(pele_result, case):
            score = 0.5  # Different case but physics aligned
        else:
            score = 0.0  # Wrong
        
        results.append(score)
    
    overall = sum(results) / len(results)
    
    return overall, results

# Gate 4 requirement: overall ≥ 0.60 (12/20 applicable cases)
```

---

## **Appendix C: Glossary**

**Term** | **Definition**
---------|---------------
**AMR** | Adaptive Mesh Refinement - dynamic grid refinement
**AMReX** | Adaptive Mesh Refinement framework (C++ library)
**Ablation Study** | Systematic removal of components to measure contribution
**CBORG** | LBL embedding API service
**DNS** | Direct Numerical Simulation (no turbulence model)
**EB** | Embedded Boundary (complex geometry in Cartesian grid)
**FAISS** | Facebook AI Similarity Search (vector database)
**FOAM** | OpenFOAM (Open Field Operation and Manipulation)
**Gate** | Development milestone with pass/fail criteria
**HPC** | High-Performance Computing
**LES** | Large Eddy Simulation (turbulence model)
**LLM** | Large Language Model (GPT-4, Claude, etc.)
**Low-Mach** | Flow regime where Ma < 0.3 (incompressible approximation)
**NSL** | NERSC Science Library (shared mechanism database)
**Perlmutter** | NERSC supercomputer
**RAG** | Retrieval-Augmented Generation
**SLURM** | Workload manager for HPC clusters
**SSIM** | Structural Similarity Index (image comparison metric)
**Test Oracle** | Expert-curated ground truth for validation

**Pele Suite:**

- **PeleC**: Compressible reacting flow solver (all Mach numbers, shocks)
- **PeleLMeX**: Low-Mach reacting flow solver (Ma < 0.3, optimized for DNS/LES)
- **PeleMP**: Multiphase solver (spray, Lagrangian particles, soot)

---

## **Appendix D: Repository Structure**

```
pele-agent/
├── README.md
├── setup.py
├── pyproject.toml
├── requirements.txt
├── .github/
│   └── workflows/
│       └── test.yml           CI/CD pipeline
│
├── amrex_agent/                Main package
│   ├── __init__.py
│   ├── cli.py                 CLI entry point
│   ├── config.py              Configuration service (100% coverage)
│   ├── workflow.py            LangGraph workflow
│   │
│   ├── services/              Service layer
│   │   ├── __init__.py
│   │   ├── embedding.py       MultiIndexEmbeddingService
│   │   ├── architect.py       ArchitectService
│   │   ├── reviewer.py        ReviewerService
│   │   ├── cases.py           AMReXCasesService
│   │   └── documents.py       DocumentRetrievalService
│   │
│   ├── nodes/                 LangGraph nodes
│   │   ├── __init__.py
│   │   ├── solver_selector.py
│   │   ├── architect.py
│   │   ├── reviewer.py
│   │   ├── paper_validator.py
│   │   └── input_writer.py
│   │
│   ├── models/                Data models
│   │   ├── __init__.py
│   │   ├── state.py           AgentState
│   │   ├── case.py            CaseMetadata
│   │   └── document.py        DocumentMatch
│   │
│   └── utils/                 Utilities
│       ├── __init__.py
│       ├── faiss_index.py
│       ├── embedders.py       CBORG, OpenAI, Local
│       └── parsers.py         RST, inputs file parsing
│
├── database/                  Data directory
│   ├── configs/
│   │   └── physics_families.yaml
│   ├── reports/               Curated reports
│   │   ├── report1.txt
│   │   ├── ...
│   │   └── report9.txt
│   ├── test_oracle/
│   │   └── oracle_v1.yaml
│   └── foam_benchmark/
│       ├── foam_cases.yaml
│       └── reference_plots/
│
├── scripts/                   Build scripts
│   ├── build_indices.py       Index building
│   ├── extract_git_metrics.py
│   └── parse_case_metadata.py
│
├── tests/                     Test suite
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_embedding.py
│   │   └── test_reviewer.py
│   ├── integration/
│   │   └── test_workflow.py
│   ├── e2e/
│   │   └── test_full_workflow.py
│   ├── ablation/
│   │   └── test_index_contributions.py
│   └── fixtures/
│       ├── config.yaml
│       └── mock_faiss/
│
└── docs/                      Documentation
    ├── quickstart.md
    ├── user_guide.md
    ├── api_reference.md
    └── troubleshooting.md
```

---

## **Appendix E: Quick Reference**

### **Common Commands**

```bash
# Setup
pele-agent setup --prompt "premixed methane DNS"
pele-agent setup --prompt my_prompt.txt --solver PeleLMeX

# Validation
pele-agent validate --inputs inputs --solver PeleC

# Index Management
pele-agent build-indices --mode testing
pele-agent build-indices --solvers PeleC --force

# Testing
pele-agent test-oracle --oracle oracle.yaml
pele-agent ablation --test-oracle oracle.yaml --levels 2

# Utilities
pele-agent version
pele-agent help
```

### **Important Paths**

```
Config:           ~/.pele-agent/config.yaml
Indices:          ~/.pele-agent/database/faiss/
Logs:             ~/.pele-agent/logs/pele-agent.log
Test Oracle:      ~/.pele-agent/test_oracle/oracle_v1.yaml
Run Directories:  $SCRATCH/pele-runs/
```

### **Gate Checklist**

- [ ] **Gate 0**: Config service 100% coverage ✅
- [ ] **Gate 1**: 82 indices built in <30 min
- [ ] **Gate 2**: Test oracle ≥90% accuracy (18/20)
- [ ] **Gate 3**: Error detection ≥90% (18/20)
- [ ] **Gate 4**: FOAM benchmark ≥60% (12/20)
- [ ] **Gate 5**: Plot comparison (3 cases, SSIM >0.75)
- [ ] **Gate 6**: Ablation complete, production config decided

---

## **Document Version History**

**Version 2.0** (2024-12-01)
- Complete PRD + Technical Specification
- Modular 3-level RAG architecture (82 indices)
- Ablation study framework
- FOAM-agent benchmark integration
- Test oracle methodology
- NERSC Perlmutter deployment plan

**Version 1.0** (2024-11-15)
- Initial draft (concept only)

---

**END OF SPECIFICATION**

---
