/**
 * Tests for lib/i18n.ts
 */

import { getCopy, type Language } from "./i18n";

describe("getCopy", () => {
  it('getCopy("ja") returns Japanese copy', () => {
    const copy = getCopy("ja");
    expect(copy.heroTitle).toBe("MeetingAI ダッシュボード");
  });

  it('getCopy("en") returns English copy', () => {
    const copy = getCopy("en");
    expect(copy.heroTitle).toBe("MeetingAI Dashboard");
  });

  it("ja and en have the same top-level keys", () => {
    const jaKeys = Object.keys(getCopy("ja")).sort();
    const enKeys = Object.keys(getCopy("en")).sort();
    expect(jaKeys).toEqual(enKeys);
  });

  it("nested objects have matching keys", () => {
    const ja = getCopy("ja");
    const en = getCopy("en");

    const nestedKeys = [
      "jobsHeaders",
      "statusLabels",
      "statusDescriptions",
      "stageLabels",
    ] as const;

    for (const key of nestedKeys) {
      const jaNestedKeys = Object.keys(
        ja[key] as Record<string, string>,
      ).sort();
      const enNestedKeys = Object.keys(
        en[key] as Record<string, string>,
      ).sort();
      expect(jaNestedKeys).toEqual(enNestedKeys);
    }
  });

  it("languageNames keys match between ja and en", () => {
    const ja = getCopy("ja");
    const en = getCopy("en");
    const jaLangKeys = Object.keys(ja.languageNames).sort();
    const enLangKeys = Object.keys(en.languageNames).sort();
    expect(jaLangKeys).toEqual(enLangKeys);
  });

  it("all string fields are non-empty", () => {
    const languages: Language[] = ["ja", "en"];
    for (const lang of languages) {
      const copy = getCopy(lang);
      for (const [, value] of Object.entries(copy)) {
        if (typeof value === "string") {
          expect(value.trim().length).toBeGreaterThan(0);
        }
      }
    }
  });

  it("all nested object string values are non-empty", () => {
    const languages: Language[] = ["ja", "en"];
    const nestedKeys = [
      "jobsHeaders",
      "statusLabels",
      "statusDescriptions",
      "stageLabels",
      "languageNames",
    ] as const;

    for (const lang of languages) {
      const copy = getCopy(lang);
      for (const key of nestedKeys) {
        const nested = copy[key] as Record<string, string>;
        for (const [subKey, val] of Object.entries(nested)) {
          expect(val.trim().length).toBeGreaterThan(0);
        }
      }
    }
  });

  it("uploadSizeError returns message containing limit", () => {
    const ja = getCopy("ja");
    const result = ja.uploadSizeError(500);
    expect(result).toContain("500");
  });

  it("uploadInProgress returns message containing progress", () => {
    const en = getCopy("en");
    const result = en.uploadInProgress(42);
    expect(result).toContain("42");
  });

  it("deleteConfirm includes jobId", () => {
    const ja = getCopy("ja");
    const result = ja.deleteConfirm("job-abc-123");
    expect(result).toContain("job-abc-123");
  });

  it("failedAtStage includes stage name", () => {
    const ja = getCopy("ja");
    const en = getCopy("en");
    expect(ja.failedAtStage("transcription")).toContain("transcription");
    expect(en.failedAtStage("summary")).toContain("summary");
  });

  it("failureOccurredAt includes time string", () => {
    const ja = getCopy("ja");
    const en = getCopy("en");
    expect(ja.failureOccurredAt("2026-01-01T00:00:00Z")).toContain(
      "2026-01-01T00:00:00Z",
    );
    expect(en.failureOccurredAt("2026-02-24")).toContain("2026-02-24");
  });

  it("function fields work for both languages", () => {
    const languages: Language[] = ["ja", "en"];
    for (const lang of languages) {
      const copy = getCopy(lang);
      expect(copy.uploadSizeError(100)).toContain("100");
      expect(copy.uploadInProgress(75)).toContain("75");
      expect(copy.deleteConfirm("job-xyz")).toContain("job-xyz");
      expect(copy.failedAtStage("transcription")).toContain("transcription");
      expect(copy.failureOccurredAt("2026-01-01")).toContain("2026-01-01");
    }
  });

  it("statusLabels contains expected status keys", () => {
    const expectedKeys = ["pending", "processing", "completed", "failed"];
    const languages: Language[] = ["ja", "en"];
    for (const lang of languages) {
      const copy = getCopy(lang);
      for (const key of expectedKeys) {
        expect(copy.statusLabels[key]).toBeDefined();
        expect(copy.statusLabels[key].trim().length).toBeGreaterThan(0);
      }
    }
  });

  it("statusDescriptions contains expected status keys", () => {
    const expectedKeys = ["pending", "processing", "completed", "failed"];
    const languages: Language[] = ["ja", "en"];
    for (const lang of languages) {
      const copy = getCopy(lang);
      for (const key of expectedKeys) {
        expect(copy.statusDescriptions[key]).toBeDefined();
        expect(copy.statusDescriptions[key].trim().length).toBeGreaterThan(0);
      }
    }
  });

  it("stageLabels contains expected stage keys", () => {
    const expectedKeys = ["upload", "chunking", "transcription", "summary"];
    const languages: Language[] = ["ja", "en"];
    for (const lang of languages) {
      const copy = getCopy(lang);
      for (const key of expectedKeys) {
        expect(copy.stageLabels[key]).toBeDefined();
        expect(copy.stageLabels[key].trim().length).toBeGreaterThan(0);
      }
    }
  });
});
