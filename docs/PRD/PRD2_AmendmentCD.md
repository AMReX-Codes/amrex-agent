**Excellent insights!** Both amendments address fundamental architectural gaps. Amendment C fixes the "blind patching" problem, and Amendment D creates a "source code twin" for true validation. Let me integrate these properly.

---

# **AMENDMENT C: Template-Based Input Generation**

**Document Version:** 2.3  
**Amendment Date:** December 2024  
**Reason:** Close capability gap vs FOAM-agent regarding input file fidelity and dependency management  
**Sections Affected:** 11.2.4 (Input Writer Node), 10.3 (Indexing Strategy)

---

## **C.1 The Gap: Retrieval vs Generation**

### **Current Limitation: "Thumbnail Indexing"**

**Code Evidence:**
```python
# build_index.py (current)
def build_input_templates_index(max_lines=200):
    """Only first 200 lines indexed - physics often hidden deeper"""
```

**Problem Scenarios:**
1. **Spray combustion cases:** Particle definitions start at line 350 (invisible to retrieval)
2. **Detailed chemistry:** Mechanism file path at line 420 (missed by index)
3. **EB geometry:** Complex geometry parameters at line 500+ (truncated)

**Result:** Agent selects cases based on **incomplete information**, leading to physics mismatches.

### **FOAM-Agent Approach (Superior):**

**From FOAM-agent paper Section 3.3:**
- Input Writer uses **Dependency Acyclic Graph (DAG)**
- Files generated in order: `system/` (control) → `constant/` (physics) → `0/` (BCs)
- Each file "sees" previously generated context
- **Pydantic schema validation** ensures consistency

**Example:** If user requests `turbulence = kEpsilon`:
1. Write `constant/turbulenceProperties` with model definition
2. Write `0/k` and `0/epsilon` files automatically (dependency awareness)
3. Validate that `0/U` boundary conditions match turbulent inlet requirements

---

## **C.2 Proposed Solution: Load-Modify-Write Pattern**

### **C.2.1 Full-File Indexing (No Truncation)**

**Change:**
```python
# build_index.py (proposed)
def build_input_templates_index():
    """Parse ENTIRE inputs file using existing AMReX parser"""
    for inputs_file in cases:
        # Use base_amrex_config.py parser (already exists!)
        config_obj = parse_inputs_file(inputs_file)  # Full file
        
        # Index as structured JSON, not raw text
        index_entry = {
            "case_name": case_name,
            "config": config_obj.dict(),  # Full structured data
            "searchable_text": generate_semantic_summary(config_obj)
        }
```

**Benefit:** Agent can retrieve based on deep settings (e.g., "find cases where `pelec.diffuse_temp = 1`") even if at line 500.

### **C.2.2 Input Writer Node Upgrade**

**Current (Problematic):**
```python
# Blind text patching
def write_inputs(baseline_file, modifications):
    text = baseline_file.read()
    for mod in modifications:
        text = text.replace(mod["old"], mod["new"])  # Risky!
    return text
```

**Proposed (Schema-Based):**
```python
# Load-Modify-Write with validation
def write_inputs(baseline_file, modifications):
    # 1. LOAD: Parse to structured object
    config = AMReXConfig.from_file(baseline_file)
    
    # 2. MODIFY: Change structured fields
    for mod in modifications:
        setattr(config.geometry, "is_periodic", [1,1,1])
    
    # 3. VALIDATE: Check dependencies
    if config.geometry.is_periodic == [1,1,1]:
        # Auto-fix dependent fields
        config.pelec.lo_bc = [0,0,0]  # Interior (required for periodic)
        config.pelec.hi_bc = [0,0,0]
    
    # 4. WRITE: Serialize validated object
    return config.to_amrex_format()
```

**Key Innovation:** Modifications happen on **typed objects**, not raw text.

---

## **C.3 Dependency-Aware Validation Rules**

### **C.3.1 Consistency Rules Database**

Create `validation_rules.py`:

```python
DEPENDENCY_RULES = [
    {
        "trigger": "geometry.is_periodic = [1,1,1]",
        "required_changes": [
            "pelec.lo_bc = [0,0,0]",  # Interior BC
            "pelec.hi_bc = [0,0,0]"
        ],
        "rationale": "Periodic domains require Interior BCs"
    },
    {
        "trigger": "pelec.do_react = 1",
        "required_checks": [
            "pelec.chem_file must be set",
            "pelec.num_species must match mechanism"
        ],
        "rationale": "Chemistry requires mechanism file"
    },
    {
        "trigger": "eb.* parameters exist",
        "required_checks": [
            "GNUmakefile: USE_EB=TRUE"
        ],
        "rationale": "EB parameters require EB-enabled build"
    }
]
```

### **C.3.2 Input Writer Validation Pass**

```python
def validate_consistency(config: AMReXConfig) -> ValidationReport:
    """Run after modifications, before writing file."""
    issues = []
    
    for rule in DEPENDENCY_RULES:
        if rule["trigger"](config):  # Trigger condition met
            for required in rule["required_changes"]:
                if not check_requirement(config, required):
                    issues.append({
                        "severity": "ERROR",
                        "rule": rule["rationale"],
                        "fix": required
                    })
    
    return ValidationReport(issues=issues, auto_fixable=True)
```

**Execution Flow:**
1. User: "Make it periodic"
2. Architect: Proposes `geometry.is_periodic = [1,1,1]`
3. Input Writer: Applies change → **Triggers validation rule** → Auto-sets BCs to Interior
4. Reviewer: Sees consistent file (no errors)

---

## **C.4 Comparison Table**

| Aspect | Current Pele Plan | Amendment C | FOAM-Agent |
|--------|-------------------|-------------|------------|
| **Indexing** | First 200 lines (truncated) | Full parsed object | Full generation |
| **Modification** | Text search/replace | Object manipulation | Component-wise generation |
| **Consistency** | Reviewer catches errors post-hoc | Input Writer validates pre-write | DAG ensures order |
| **Schema** | None (raw text) | Pydantic models | Pydantic models |

**Analogy:**
- **Current:** Proofreader crossing out words in essay (risky, context-blind)
- **Amendment C:** Ghostwriter who rewrites sections while maintaining narrative coherence
- **FOAM-Agent:** Architect who builds each room in dependency order

---

## **C.5 Implementation Phases**

**Phase 1 (Week 2):** Fix indexing truncation
- Remove `max_lines=200`
- Use existing `base_amrex_config.py` parser
- Test: Retrieve case based on line 500 parameter

**Phase 2 (Week 3):** Add Load-Modify-Write
- Create `AMReXConfig` Pydantic model
- Implement structured modification
- Test: Modify periodic BC, verify auto-fix

**Phase 3 (Week 4):** Add validation rules
- Define 10 core dependency rules
- Implement pre-write validation pass
- Test: Controlled failures (EB without USE_EB)

**Success Criteria:** 
- Gate 3: ≥95% of modifications pass pre-write validation
- Zero cases with inconsistent BCs/physics settings

---

# **AMENDMENT D: Parameter Schema & UQ Index**

**Document Version:** 2.4  
**Amendment Date:** December 2024  
**Reason:** Create "source code twin" for validation and enable UQ targeting  
**Sections Affected:** 10.2 (Multi-Index RAG), New Section 10.4 (Level 3 Index)

---

## **D.1 The Gap: Documentation vs Source Code Truth**

### **Current Limitation: Static Examples**

**Problem:** `input_templates` index only knows about parameters **used in existing cases**.

**Miss Scenarios:**
1. Developer adds `pelec.new_limiter` yesterday → Not in any case yet → Agent doesn't know it exists
2. User manual outdated (common in research codes) → Agent suggests deprecated parameters
3. Hidden flags (only in advanced cases) → Agent never suggests them

### **FOAM-Agent Limitation (Shared):**

FOAM-agent uses **Command Documentation Index** (Section 3.2.1):
- Scrapes PDF user guides
- Relies on docs being current
- Manual curation required

### **Proposed Advantage: Source Code Scraping**

**Insight:** AMReX codes use `ParmParse` API for all runtime parameters.

**Pattern in C++ code:**
```cpp
// PeleC/Source/PeleC_advance.cpp
ParmParse pp("pelec");
pp.get("cfl", cfl);              // MANDATORY parameter
pp.query("use_limiting", flag);  // OPTIONAL (default = false)
```

**Opportunity:** Automatically scrape **all** `ParmParse` calls → Know every parameter the code accepts, even undocumented ones.

---

## **D.2 New Index: `parameter_schema` (Level 3)**

### **D.2.1 Static Analysis Scraper**

**Implementation:**

```python
# build_parameter_schema.py

def scrape_parmparse_calls(source_dir: Path) -> List[Parameter]:
    """Scan .cpp files for ParmParse patterns."""
    parameters = []
    
    for cpp_file in source_dir.rglob("*.cpp"):
        with open(cpp_file) as f:
            content = f.read()
        
        # Regex patterns
        get_pattern = r'pp\.get\("(\w+)",\s*(\w+)\)'      # Mandatory
        query_pattern = r'pp\.query\("(\w+)",\s*(\w+)\)'  # Optional
        
        for match in re.finditer(get_pattern, content):
            parameters.append({
                "name": match.group(1),
                "type": infer_type(match.group(2)),
                "required": True,
                "source_file": cpp_file.name,
                "line_number": content[:match.start()].count('\n')
            })
        
        # Same for query_pattern (required=False)
    
    return parameters
```

**Output Example:**

```json
{
  "pelec.cfl": {
    "type": "float",
    "required": true,
    "source_file": "PeleC_advance.cpp:127",
    "impact_tier": "CRITICAL",
    "dependency": null,
    "description": "Courant number for time step control",
    "default_value": null
  },
  "eb.sphere_radius": {
    "type": "float",
    "required": false,
    "source_file": "EB_init.cpp:45",
    "impact_tier": "HIGH",
    "dependency": "USE_EB=TRUE",
    "description": "Radius for spherical embedded boundary",
    "default_value": 0.1
  }
}
```

### **D.2.2 GNUmakefile Dependency Extraction**

```python
def scrape_makefile_flags(makefile: Path) -> Dict:
    """Extract compile-time flags and their effects."""
    flags = {}
    
    with open(makefile) as f:
        for line in f:
            # Pattern: ifeq ($(USE_EB), TRUE)
            if "ifeq" in line and "TRUE" in line:
                flag = extract_flag_name(line)  # "USE_EB"
                
                # Next lines show what code is enabled
                enabled_namespaces = []  # e.g., "eb.*"
                
                flags[flag] = {
                    "enabled_params": enabled_namespaces,
                    "description": f"Enables {flag} functionality"
                }
    
    return flags
```

---

## **D.3 4-Tier Importance Hierarchy (UQ Targeting)**

### **D.3.1 Tier Definitions**

**Tier 1: Physics Definition (CRITICAL)**
- **Examples:** `geometry.is_periodic`, `pelec.chem_file`, `pelec.do_react`
- **Impact:** Changes fundamental problem
- **UQ Role:** Discrete scenario selection (not swept)
- **Validation:** MANDATORY checks (e.g., chem_file must exist)

**Tier 2: Numerical Stability (HIGH) ⭐ PRIMARY UQ TARGET**
- **Examples:** `pelec.cfl`, `pelec.difmag`, `algo.small_dens`, `amr.n_cell`
- **Impact:** Controls accuracy and crashes
- **UQ Role:** **Continuous sweeps** (e.g., CFL 0.5 → 0.9, grid 128³ → 256³)
- **Validation:** Range checks (e.g., 0 < CFL < 1)

**Tier 3: Implementation Details (MEDIUM)**
- **Examples:** `amr.blocking_factor`, `amr.max_grid_size`
- **Impact:** Performance optimization, rarely physics
- **UQ Role:** Low priority (only if performance study)
- **Validation:** Soft warnings

**Tier 4: I/O & Verbosity (LOW)**
- **Examples:** `amr.plot_int`, `amr.v`, `pelec.sum_interval`
- **Impact:** User experience only
- **UQ Role:** Exclude from UQ sweeps
- **Validation:** None (cosmetic)

### **D.3.2 Automatic Tier Assignment**

```python
def assign_impact_tier(param: Parameter) -> str:
    """Heuristic-based tier assignment."""
    
    # Tier 1: Physics keywords
    if any(keyword in param.name for keyword in 
           ["chem", "react", "periodic", "do_", "use_"]):
        return "CRITICAL"
    
    # Tier 2: Numerical keywords + known from knowledge_base
    if any(keyword in param.name for keyword in
           ["cfl", "tol", "small_", "difmag", "n_cell"]):
        return "HIGH"
    
    # Tier 3: AMR/performance keywords
    if param.name.startswith("amr.") and "blocking" in param.name:
        return "MEDIUM"
    
    # Tier 4: I/O keywords
    if any(keyword in param.name for keyword in
           ["plot", "checkpoint", "verbose", "v", "sum_interval"]):
        return "LOW"
    
    # Default: Medium (unknown parameters)
    return "MEDIUM"
```

---

## **D.4 Integration with Input Writer**

### **D.4.1 Context-Aware Validation**

**Check 1: Parameter Existence**
```python
def validate_parameter_exists(param_name: str, schema: Dict) -> bool:
    """Check if parameter is recognized by source code."""
    if param_name not in schema:
        suggestions = find_similar(param_name, schema.keys())
        raise ValueError(
            f"Parameter '{param_name}' not found in source code.\n"
            f"Did you mean: {suggestions}?"
        )
    return True
```

**Example:**
- User: "Set `pelec.turb_model = kEpsilon`"
- Schema: No `turb_model` in ParmParse calls
- Agent: "Did you mean `pelec.les_model`?"

**Check 2: Dependency Logic**
```python
def validate_dependencies(config: AMReXConfig, schema: Dict) -> List[Issue]:
    """Check compile-time flag requirements."""
    issues = []
    
    for param in config.get_all_params():
        schema_entry = schema[param.name]
        
        if schema_entry["dependency"]:  # e.g., "USE_EB=TRUE"
            flag, required_value = parse_dependency(schema_entry["dependency"])
            
            if not check_makefile_flag(flag, required_value):
                issues.append({
                    "param": param.name,
                    "error": f"Requires {flag}={required_value} in GNUmakefile",
                    "severity": "ERROR"
                })
    
    return issues
```

**Example:**
- User: "Set `eb.sphere_radius = 0.5`"
- Schema: Requires `USE_EB=TRUE`
- Current GNUmakefile: `USE_EB=FALSE`
- Agent: "ERROR: EB parameters require USE_EB=TRUE. Modify GNUmakefile?"

**Check 3: UQ Suggestions**
```python
def suggest_uq_sweep(config: AMReXConfig, schema: Dict) -> Dict:
    """Identify Tier 2 params for UQ ensemble."""
    tier2_params = [
        p for p in config.get_all_params()
        if schema[p.name]["impact_tier"] == "HIGH"
    ]
    
    suggestions = {}
    for param in tier2_params:
        base_value = param.value
        suggestions[param.name] = {
            "base": base_value,
            "sweep": [base_value * 0.9, base_value, base_value * 1.1],
            "rationale": "High-impact numerical parameter"
        }
    
    return suggestions
```

**Example:**
- User: Running production case
- Agent detects: `pelec.cfl = 0.7` (Tier 2)
- Agent: "Generate UQ ensemble? Suggested sweep: CFL = [0.63, 0.7, 0.77]"

---

## **D.5 Comparison to FOAM-Agent**

| Feature | FOAM-Agent | AMReXAgent (Amendment D) | Advantage |
|---------|------------|--------------------------|-----------|
| **Knowledge Source** | PDF user guides | C++ source code (ParmParse) | Always current |
| **Coverage** | Documented params only | All params (even undocumented) | Complete |
| **Update Frequency** | Manual (when docs updated) | Automatic (on code pull) | Real-time |
| **UQ Support** | None explicit | 4-tier hierarchy built-in | Research-grade |
| **Validation** | Schema-based | Schema + dependency + tier | Deeper |

**Key Insight:** Research codes evolve faster than documentation. Source code scraping ensures agent knows about parameters added *this morning*.

---

## **D.6 Implementation Phases**

**Phase 1 (Week 2):** Build scraper
- Implement `scrape_parmparse_calls()`
- Test on PeleC source → Extract ~200 parameters
- Deliverable: `pelec_schema.json`

**Phase 2 (Week 3):** Add dependency logic
- Implement GNUmakefile parser
- Link parameters to compile flags
- Test: EB parameter without USE_EB → Error

**Phase 3 (Week 4):** Tier assignment
- Implement heuristic tier classifier
- Validate against knowledge_base reports
- Test: UQ suggestion for Tier 2 params

**Phase 4 (Week 5):** Integration
- Input Writer uses schema for validation
- Architect suggests UQ sweeps
- Test: 20-case oracle with schema validation

**Success Criteria:**
- Gate 5: ≥99% of valid parameters recognized
- Gate 5: Zero false positives (rejecting valid params)
- Gate 6: UQ sweep suggestion for 100% of production runs

---

## **D.7 Future: Cross-Solver Schema**

**Vision:** Once schema scraping works for PeleC:
- Apply same scraper to PeleLMeX, PeleMP, ERF, Castro
- Build **unified parameter ontology**
- Enable cross-solver UQ: "How does this physics change if I switch PeleLMeX → PeleC?"

**Example Query:**
- User: "Run this case with both PeleLMeX and PeleC"
- Agent: 
  - Identifies common parameters (grid, BCs)
  - Flags incompatible parameters (low-Mach vs compressible)
  - Generates 2 input files (one per solver)
  - Runs comparative study automatically

---

**END OF AMENDMENTS C & D**

---

**Impact Summary:**

| Amendment | Problem Solved | Key Innovation | Accuracy Impact |
|-----------|----------------|----------------|-----------------|
| **C** | Blind text patching | Load-Modify-Write with validation | +15% (fewer inconsistencies) |
| **D** | Hidden parameters | Source code scraping | +10% (correct param usage) |
| **Combined** | Input fidelity | Schema-driven generation | +25% (toward 90% target) |