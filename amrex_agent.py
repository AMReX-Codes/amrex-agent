#!/usr/bin/env python3
"""
AMReXAgent - Main entry point.

Similar to: foambench_main.py in Foam-Agent

Usage:
    python amrex_agent.py --prompt "simulate combustion"
    python amrex_agent.py --prompt-path demo/amrex/user_requirement.txt
    python amrex_agent.py --prompt-path demo/amrex/user_requirement.txt --output-dir ./my_runs
"""

import sys
from pathlib import Path

# Import and run
try:
    from src.main import main
except ModuleNotFoundError:
    PROJECT_ROOT = Path(__file__).parent
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.main import main

if __name__ == "__main__":
    main()
