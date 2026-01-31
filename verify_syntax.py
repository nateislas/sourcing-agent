
import sys
import os

print("Checking syntax and imports...")

try:
    print("Importing events...")
    import backend.research.events as events
    print("✅ events.py ok")

    print("Importing verification...")
    import backend.research.verification as verification
    print("✅ verification.py ok")

    print("Importing activities...")
    import backend.research.activities as activities
    print("✅ activities.py ok")
    
    # Check for new activities existence
    if hasattr(activities, 'deep_verify_entity'):
        print("✅ deep_verify_entity found")
    else:
        print("❌ deep_verify_entity NOT found")

    if hasattr(activities, 'deduplicate_entities'):
        print("✅ deduplicate_entities found")
    else:
        print("❌ deduplicate_entities NOT found")

    print("Importing orchestrator...")
    import backend.research.orchestrator as orchestrator
    print("✅ orchestrator.py ok")
    
    print("All checks passed.")

except ImportError as e:
    print(f"❌ Import Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
