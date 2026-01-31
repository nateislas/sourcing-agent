
import sys
import os

try:
    from backend.research import prompts
    
    print("Successfully imported prompts module.")
    
    # Check if PROMPTS have correct keys
    if "{query}" not in prompts.INITIAL_PLANNING_PROMPT:
        print("ERROR: INITIAL_PLANNING_PROMPT missing {query} placeholder")
        sys.exit(1)

    if "{iteration}" not in prompts.ADAPTIVE_PLANNING_PROMPT:
         print("ERROR: ADAPTIVE_PLANNING_PROMPT missing {iteration} placeholder")
         sys.exit(1)
        
    print("Prompts check passed.")

except Exception as e:
    print(f"Error importing prompts: {e}")
    sys.exit(1)
