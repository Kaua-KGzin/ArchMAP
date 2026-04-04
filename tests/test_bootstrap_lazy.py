import threading
import unittest

from archmap.core.parser.bootstrap import ensure_default_registry
from archmap.core.parser.registry import registry


class TestBootstrapLazy(unittest.TestCase):
    def test_ensure_default_registry_functionality(self):
        """Verify that ensure_default_registry populates the registry and is idempotent."""
        reg = ensure_default_registry()

        # Should return the global registry
        self.assertEqual(reg, registry)

        # Should be populated
        langs = reg.get_all_languages()
        self.assertIn("python", langs)
        self.assertIn("javascript", langs)
        self.assertTrue(len(langs) >= 5)

    def test_thread_safety_concurrency(self):
        """Verify that multiple threads calling bootstrap simultaneously doesn't crash."""
        results = []

        def worker():
            try:
                ensure_default_registry()
                results.append(True)
            except Exception:
                results.append(False)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(results), 20)
        self.assertTrue(all(results), "At least one bootstrap worker failed")

if __name__ == "__main__":
    unittest.main()
