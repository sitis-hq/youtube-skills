"""The recipes README lists every script of the set with the briefs and steps that run it.

A step that needs a script must name it: the agent treats a script described only in its skill as
optional and improvises instead. These tests keep the README's table true to the scripts in
skills/ and to the briefs, so a new script cannot go unassigned and a brief cannot name a script
its row does not cite.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "recipes" / "README.md"
ROW = re.compile(r"^\| `([a-z-]+)` \| `([a-z_]+\.py)` \| (.+) \|$")
CITE = re.compile(r"(?<![\w.])(\d+): ([\d, ]+)")
STEP_NOTE = re.compile(r"^\*\*(\d+)(?:–(\d+))? — ", re.M)
SCRIPT = re.compile(r"(?<![\w/.-])(?:scripts/)?([a-z_]+\.py)\b")


def table() -> dict[str, tuple[str, dict[int, set[int]], str]]:
    text = README.read_text(encoding="utf-8").split("## Scripts and the steps that run them", 1)[1]
    rows = {}
    for line in text.splitlines():
        m = ROW.match(line)
        if m:
            skill, script, run_by = m.groups()
            cites = {int(b): {int(s) for s in steps.replace(" ", "").split(",") if s}
                     for b, steps in CITE.findall(run_by.split("planned")[0])}
            rows[script] = (skill, cites, run_by)
    return rows


def scripts_on_disk() -> dict[str, str]:
    return {p.name: p.parents[1].name for p in ROOT.glob("skills/*/scripts/*.py") if not p.name.startswith("_")}


def briefs() -> dict[int, Path]:
    return {int(p.name[:2]): p for p in (ROOT / "recipes").glob("[0-9][0-9]-*.md")}


def step_mentions(brief: Path) -> dict[str, list[set[int]]]:
    """For each script the brief's design notes name, the step range of every note naming it."""
    text = brief.read_text(encoding="utf-8")
    notes = text.split("## Design notes per step", 1)[1].split("\n## ", 1)[0]
    heads = list(STEP_NOTE.finditer(notes))
    out: dict[str, list[set[int]]] = {}
    for i, head in enumerate(heads):
        body = notes[head.start():heads[i + 1].start() if i + 1 < len(heads) else len(notes)]
        first = int(head.group(1))
        steps = set(range(first, int(head.group(2) or first) + 1))
        for script in set(SCRIPT.findall(body)):
            out.setdefault(script, []).append(steps)
    return out


class Table(unittest.TestCase):
    def test_every_script_of_the_set_has_a_row_under_its_own_skill(self):
        rows, disk = table(), scripts_on_disk()
        self.assertEqual(sorted(set(disk) - set(rows)), [], "scripts with no row in recipes/README.md")
        for script, skill in disk.items():
            self.assertEqual(rows[script][0], skill, f"{script} is listed under the wrong skill")

    def test_every_row_names_a_script_that_exists(self):
        self.assertEqual(sorted(set(table()) - set(scripts_on_disk())), [])

    def test_every_row_says_who_runs_the_script(self):
        for script, (_, cites, run_by) in table().items():
            self.assertTrue(cites or "planned" in run_by or "inside" in run_by, f"{script}: nobody runs it")


class Briefs(unittest.TestCase):
    def test_a_script_a_brief_names_exists(self):
        disk = scripts_on_disk()
        for number, brief in briefs().items():
            for script in step_mentions(brief):
                self.assertIn(script, disk, f"brief {number} names {script}, which is not in skills/")

    def test_a_script_a_brief_names_cites_the_brief_and_its_steps(self):
        rows = table()
        for number, brief in briefs().items():
            for script, ranges in step_mentions(brief).items():
                cited = rows.get(script, ("", {}, ""))[1].get(number)
                self.assertIsNotNone(cited, f"brief {number} names {script}; its README row does not cite {number}")
                for steps in ranges:
                    self.assertTrue(cited & steps, f"{script}: brief {number} names it in steps {sorted(steps)}, "
                                                   f"the README row cites {sorted(cited)}")
                self.assertLessEqual(cited, set().union(*ranges),
                                     f"{script}: the README cites brief {number} steps the brief does not name it in")

    def test_a_row_citing_a_brief_is_named_by_that_brief(self):
        written = briefs()
        for script, (_, cites, _) in table().items():
            for number in cites:
                self.assertIn(number, written, f"{script} cites brief {number}, which is not written")
                self.assertIn(script, step_mentions(written[number]), f"brief {number} does not name {script}")


if __name__ == "__main__":
    unittest.main()
