import asyncio
import logging
import unittest
import sys
import os
from unittest.mock import MagicMock, AsyncMock
import tenacity
from google.api_core.exceptions import ServerError, ResourceExhausted

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.research.llm import LLMHandler

# Configure logging
logging.basicConfig(level=logging.INFO)

class TestLLMHandlerRetry(unittest.IsolatedAsyncioTestCase):
    async def test_retry_on_503(self):
        # Mock GoogleGenAI
        mock_llm = MagicMock()
        mock_llm.acomplete = AsyncMock()
        mock_llm.model = "test-model"
        
        # Setup mock to fail with 503 twice then succeed
        mock_llm.acomplete.side_effect = [
            ServerError("Model overloaded"),
            ServerError("Model overloaded"),
            MagicMock(text="Success response")
        ]
        
        llm_handler = LLMHandler(mock_llm)
        
        # Update wait for test speed
        import tenacity
        
        # Dynamically patching LLMHandler.acomplete to wait less during tests
        # This is a bit hacky but avoids waiting 4+ seconds in CI
        acomplete_fn = llm_handler.acomplete.retry
        acomplete_fn.wait = tenacity.wait_fixed(0.1)
        
        response = await llm_handler.acomplete("test prompt")
        
        self.assertEqual(response.text, "Success response")
        self.assertEqual(mock_llm.acomplete.call_count, 3)
        print("\n✅ Verified 503 retry logic")

    async def test_exhaustion_on_too_many_failures(self):
        mock_llm = MagicMock()
        mock_llm.acomplete = AsyncMock()
        mock_llm.model = "test-model"
        
        # Fail indefinitely
        mock_llm.acomplete.side_effect = ServerError("Persistent overload")
        
        llm_handler = LLMHandler(mock_llm)
        
        # Speed up test
        llm_handler.acomplete.retry.wait = tenacity.wait_fixed(0.1)
        
        with self.assertRaises(tenacity.RetryError):
            await llm_handler.acomplete("test prompt")
            
        self.assertEqual(mock_llm.acomplete.call_count, 5) # Default is 5 attempts
        print("✅ Verified exhaustion after repeated 503s")

if __name__ == "__main__":
    unittest.main()
