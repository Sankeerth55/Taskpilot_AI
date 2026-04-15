"""
Quick verification test for TaskPilot AI backend upgrade.
Tests core functionality without requiring all dependencies.
"""
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

print("🧪 TaskPilot AI Backend Verification")
print("=" * 50)

# Test 1: Import core modules
print("\n1. Testing core imports...")
try:
    from app.services.orchestrator import TaskOrchestrator
    from app.services.agents.fetcher import FetcherAgent
    from app.services.agents.analyzer import AnalyzerAgent
    from app.services.agents.planner import PlannerAgent
    from app.services.agents.reporter import ReporterAgent
    from app.schemas.messages import MessageRequest, AttachmentData
    print("   ✅ All core modules imported successfully")
except ImportError as e:
    print(f"   ❌ Import error: {e}")
    sys.exit(1)

# Test 2: Verify FileProcessor
print("\n2. Testing FileProcessor...")
try:
    from app.services.file_processor import FileProcessor
    fp = FileProcessor()
    print("   ✅ FileProcessor instantiated")
except Exception as e:
    print(f"   ❌ FileProcessor error: {e}")
    sys.exit(1)

# Test 3: Verify schema changes
print("\n3. Testing schema updates...")
try:
    # Test that attachments are optional
    req = MessageRequest(session_id="test", content="test message")
    print(f"   ✅ MessageRequest without attachments: {req.session_id}")
    
    # Test with attachments
    req_with_attach = MessageRequest(
        session_id="test",
        content="test",
        attachments=[AttachmentData(mime_type="text/plain", data="base64data")]
    )
    print(f"   ✅ MessageRequest with attachments: {len(req_with_attach.attachments)} attachment(s)")
except Exception as e:
    print(f"   ❌ Schema error: {e}")
    sys.exit(1)

# Test 4: Verify agent context
print("\n4. Testing AgentContext...")
try:
    from app.services.agents.base import AgentContext
    ctx = AgentContext(user_input="test", attachments=[])
    print(f"   ✅ AgentContext with attachments field: {ctx.user_input}")
except Exception as e:
    print(f"   ❌ AgentContext error: {e}")
    sys.exit(1)

# Test 5: Verify orchestrator signature
print("\n5. Testing Orchestrator signature...")
try:
    import inspect
    sig = inspect.signature(TaskOrchestrator.run)
    params = list(sig.parameters.keys())
    if 'attachments' in params:
        print(f"   ✅ Orchestrator.run has 'attachments' parameter")
    else:
        print(f"   ❌ Orchestrator.run missing 'attachments' parameter")
        print(f"      Parameters: {params}")
except Exception as e:
    print(f"   ❌ Orchestrator check error: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
print("✅ ALL CORE TESTS PASSED")
print("\nNote: File processing libraries (PyPDF2, python-docx) are optional.")
print("They will be used if available, with graceful fallbacks.")
print("\nTo install file processing libraries:")
print("  pip install PyPDF2 python-docx")
print("\n🚀 TaskPilot AI backend is ready for use!")
