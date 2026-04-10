import re

content = """
import {
  foo
} from 'module-a';

const x = 1;

import {
  bar
} from 'module-b';
"""

for match in re.finditer(
    r'(?:import.*?from\s+[\'"]([^\'"]+)[\'"]|require\([\'"]([^\'"]+)[\'"]\))',
    content,
    re.DOTALL,
):
    print("Match:", match.group(1) or match.group(2))
