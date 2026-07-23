/**
 * `README.md`'s disclosure contract (§11, goal #9).
 *
 * Goal #9 requires the baseline model and its cutoff be stated plainly in the
 * template README, and calls that disclosure "the defence against the
 * cherry-picking charge". A defence that silently drifts out of date is worse
 * than none, so it is a TEST FAILURE when it drifts, not a documentation
 * aspiration.
 *
 * `config.ts` is read as INERT TEXT and its literals regex-extracted — the same
 * crossing `prep/tests/test_config.py`'s drift checks use, and for the same
 * reason: importing the module would assert the README against whatever the
 * constant happens to be, which is circular. Reading the source text makes the
 * README answerable to the declaration a human reads.
 */
import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));

const readText = (relativePath: string): string =>
  readFileSync(resolve(HERE, relativePath), "utf-8");

const README = readText("../README.md");
const CONFIG_SOURCE = readText("../src/config.ts");

/** Regex-extract a pinned string literal from `config.ts`'s source text. */
function declaredConstant(name: string): string {
  const match = CONFIG_SOURCE.match(new RegExp(`export const ${name}[^=]*= "([^"]+)"`));
  if (!match) throw new Error(`config.ts declares no string constant named ${name}`);
  return match[1];
}

describe("README carries goal #9's disclosure", () => {
  test("the file exists and is not a stub", () => {
    expect(README.length).toBeGreaterThan(500);
  });

  // One case per constant rather than a loop: a failure names the constant that
  // drifted, which is the whole point of the check.
  test("states MODEL_ID verbatim", () => {
    expect(README).toContain(declaredConstant("MODEL_ID"));
  });

  test("states MODEL_CUTOFF verbatim", () => {
    expect(README).toContain(declaredConstant("MODEL_CUTOFF"));
  });

  test("states SNAPSHOT_DATE verbatim", () => {
    expect(README).toContain(declaredConstant("SNAPSHOT_DATE"));
  });
});

describe("README makes no claim the project did not build", () => {
  test("does not claim the run is reproducible", () => {
    // D22: the `--replay` harness was CUT, so "the run is reproducible" is false
    // as written and must not be claimed in the README or the report. The honest
    // claim — the one the README makes — is that the run is AUDITABLE: every
    // enforcement decision is on disk and can be read. `evals.test.ts` pins the
    // same property on the HTML report; this pins it on the other named surface.
    expect(README).not.toMatch(/reproducible/i);
  });

});

/**
 * ── WHY D29.2's CITATION-FABRICATION SCOPE IS *NOT* PINNED HERE ─────────────────
 * D29.2 forbids claiming citation-fabrication detection on the TEMPLATE side (the
 * scoreboard has no URL resolver, so it measures wrong dates only) while the same
 * claim about `prep/`, where the resolver lives, remains true and worth making.
 *
 * A first draft of this file pinned that with a proximity regex: flag "fabricat*"
 * near "scoreboard"/"npm test" with no "prep" nearby. **It was deleted after it
 * failed on the sentence "The runtime scoreboard does not detect fabricated
 * citations" — a correct DENIAL of the exact claim D29.2 forbids.**
 *
 * That is not a tunable regex, it is the wrong kind of check. The property is
 * *"does this sentence CLAIM the template detects fabrication?"*, which is
 * semantic: a denial and a claim share every keyword, and any pattern loose enough
 * to catch a real claim phrased freely will keep flagging accurate prose. Such a
 * test is worse than none — it reads as coverage, and the cheapest way to green it
 * is to delete the honest denial, making the README *less* accurate while
 * reporting D29.2 met. That is the defect class this project has ruled against
 * twice (D28: a control that cannot fail; D30: a gate that cannot pass — both from
 * asserting on a proxy instead of the property).
 *
 * So the scope claim is held where a semantic property can be held: by D29.2, by
 * the prose itself, and by review. The `reproducible` ban above is pinned because
 * it is genuinely mechanical — that word has no correct use on this surface, so a
 * blunt ban is exact rather than approximate. The two are not the same shape and
 * are deliberately not treated the same way.
 */
