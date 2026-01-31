from dotenv import load_dotenv
import os
import sys

# Load env
load_dotenv()

print("Verifying Temperature Configuration...")

# Check Env Vars
vars_to_check = [
    "RESEARCH_TEMPERATURE",
    "PLANNING_TEMPERATURE",
    "VERIFICATION_TEMPERATURE",
    "EXTRACTION_TEMPERATURE",
    "DEFAULT_LLM_TEMPERATURE"
]

all_set = True
for v in vars_to_check:
    val = os.getenv(v)
    if val:
        print(f"✅ {v}={val}")
    else:
        print(f"❌ {v} NOT SET")
        all_set = False

if not all_set:
    print("Warning: Some temperature variables are missing.")

# Check Code Imports and Signatures
try:
    from backend.research.llm import get_llm, LLMClient
    import inspect
    
    # Check get_llm signature
    sig = inspect.signature(get_llm)
    if "temperature" in sig.parameters:
        print("✅ get_llm accepts 'temperature'")
    else:
        print("❌ get_llm DOES NOT accept 'temperature'")
        sys.exit(1)

    # Check LLMClient signature
    sig_cls = inspect.signature(LLMClient.__init__)
    if "temperature" in sig_cls.parameters:
        print("✅ LLMClient accepts 'temperature'")
    else:
        print("❌ LLMClient DOES NOT accept 'temperature'")
        sys.exit(1)

    print("Code signature verification passed.")

except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Verification failed: {e}")
    sys.exit(1)

print("Verification Complete.")
