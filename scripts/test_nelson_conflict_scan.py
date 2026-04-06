import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import unittest
import tempfile
import os
from nelson_conflict_scan import parse_battle_plan, parse_imports, detect_conflicts


class TestConflictScan(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.test_dir.name)

    def tearDown(self):
        self.test_dir.cleanup()

    def test_parse_battle_plan(self):
        plan_content = """
Task ID: 1
- Name: Setup API
- Owner: Backend Team
- Ship (if crewed): HMS Victory
- File ownership (if code): src/api.py, src/models.py

Task ID: 2
- Name: Frontend UI
- Ship: HMS Enterprise
- File ownership: src/ui.js
        """
        plan_path = self.root / "battle-plan.md"
        plan_path.write_text(plan_content)

        ownership = parse_battle_plan(plan_path)
        self.assertEqual(ownership["HMS Victory"], {"src/api.py", "src/models.py"})
        self.assertEqual(ownership["HMS Enterprise"], {"src/ui.js"})

    def test_parse_imports_python(self):
        py_file = self.root / "test.py"
        py_file.write_text("import os\nfrom pathlib import Path\nimport mymodule")

        imports = parse_imports(py_file)
        self.assertEqual(imports, {"os", "pathlib", "mymodule"})

    def test_detect_conflicts(self):
        ownership = {"HMS Victory": {"src/api.py"}, "HMS Enterprise": {"src/models.py"}}
        graph = {"src/api.py": {"models", "os"}, "src/models.py": {"sys"}}

        conflicts = detect_conflicts(ownership, graph)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(
            conflicts[0],
            ("HMS Victory", "src/api.py", "HMS Enterprise", "src/models.py"),
        )

    def test_stdlib_re_does_not_conflict_with_app_py(self):
        """Importing 're' must NOT flag a conflict with src/core/app.py."""
        ownership = {
            "HMS Victory": {"src/core/app.py"},
            "HMS Enterprise": {"src/main.py"},
        }
        # src/main.py imports 're' — this should never be flagged against app.py
        graph = {
            "src/main.py": {"re"},
            "src/core/app.py": set(),
        }
        conflicts = detect_conflicts(ownership, graph)
        self.assertEqual(conflicts, [])

    def test_stdlib_os_does_not_conflict_with_button_js(self):
        """Importing 'os' must NOT flag a conflict with src/components/button.js."""
        ownership = {
            "HMS Victory": {"src/components/button.js"},
            "HMS Enterprise": {"src/server.py"},
        }
        graph = {
            "src/server.py": {"os"},
            "src/components/button.js": set(),
        }
        conflicts = detect_conflicts(ownership, graph)
        self.assertEqual(conflicts, [])

    def test_stdlib_json_does_not_conflict_with_data_json(self):
        """Importing 'json' must NOT flag a conflict with config/data.json."""
        ownership = {
            "HMS Victory": {"config/data.json"},
            "HMS Enterprise": {"src/parser.py"},
        }
        graph = {
            "src/parser.py": {"json"},
            "config/data.json": set(),
        }
        conflicts = detect_conflicts(ownership, graph)
        self.assertEqual(conflicts, [])

    def test_parse_battle_plan_missing_file_raises(self):
        """parse_battle_plan should raise FileNotFoundError for a missing file."""
        with self.assertRaises(FileNotFoundError):
            parse_battle_plan(self.root / "nonexistent.md")


if __name__ == "__main__":
    unittest.main()
