"""Validate shipped registration, role/skill contracts and local resource references."""

import json
import re
from pathlib import Path

import yaml

from darkfactory.domain import Role
from darkfactory.pack import ROLE_SKILLS


def main() -> None:
    """Reject broken frontmatter, registration, role routes and local skill links."""
    root = Path(__file__).resolve().parents[1]
    skills = list((root / "skills").glob("*/SKILL.md"))
    assert len(skills) == 24, "pack must contain the approved 24 skills"
    for path in skills:
        source = path.read_text()
        assert source.startswith("---\n"), path
        metadata = yaml.safe_load(source.split("---", 2)[1])
        assert metadata["name"] == path.parent.name, path
        assert isinstance(metadata["description"], str) and metadata["description"], path
        for link in re.findall(r"\]\(([^)]+)\)", source):
            if "://" not in link and not link.startswith("#"):
                assert (path.parent / link.split("#")[0]).exists(), (path, link)
    plugin = json.loads((root / ".claude-plugin/plugin.json").read_text())
    assert {Path(path).stem for path in plugin["agents"]} == {role.value for role in Role}
    for role in Role:
        assert (root / "agents" / (role.value + ".md")).exists()
        for skill in ROLE_SKILLS[role]:
            assert (root / "skills" / skill / "SKILL.md").exists()
    assert len(list((root / "commands").glob("*.md"))) == 7
    print("Validated 24 skills, 14 registered roles, 7 commands and local skill links.")


if __name__ == "__main__":
    main()
