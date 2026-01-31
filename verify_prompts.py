
import sys
import os

try:
    from backend.research import prompts
    from backend.research import extraction
    from backend.research import verification
    
    print("Successfully imported prompts, extraction, and verification modules.")
    
    # Check if PROMPTS have correct keys
    if "{query}" not in prompts.INITIAL_PLANNING_PROMPT:
        print("ERROR: INITIAL_PLANNING_PROMPT missing {query} placeholder")
        sys.exit(1)
        
    print("Prompts check passed.")

except Exception as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)
