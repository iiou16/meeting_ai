import { getOrgColor, getSpeakerColor } from "./speaker-colors";

describe("getOrgColor", () => {
  it("returns fallback color for empty string", () => {
    expect(getOrgColor("")).toBe("text-slate-400");
  });

  it("returns a deterministic color for a given organization", () => {
    const color1 = getOrgColor("Engineering");
    const color2 = getOrgColor("Engineering");
    expect(color1).toBe(color2);
  });

  it("returns same color across repeated calls (stable hash)", () => {
    const results = Array.from({ length: 10 }, () => getOrgColor("Sales"));
    const unique = new Set(results);
    expect(unique.size).toBe(1);
  });

  it("returns different colors for different organizations", () => {
    // Verify that at least some orgs get different colors (hash collisions are possible)
    const color1 = getOrgColor("Engineering");
    const color2 = getOrgColor("Finance");
    // These two specific orgs should hash to different indices
    expect(color1).not.toBe(color2);
  });

  it("returns a palette color (not fallback) for non-empty org", () => {
    const color = getOrgColor("開発部");
    expect(color).not.toBe("text-slate-400");
    expect(color).toMatch(/^text-/);
  });
});

describe("getSpeakerColor", () => {
  it("returns fallback color for empty string", () => {
    expect(getSpeakerColor("")).toBe("text-slate-400");
  });

  it("returns a deterministic color for a given label", () => {
    const color1 = getSpeakerColor("Speaker A");
    const color2 = getSpeakerColor("Speaker A");
    expect(color1).toBe(color2);
  });

  it("returns different colors for different labels", () => {
    const colorA = getSpeakerColor("Speaker A");
    const colorB = getSpeakerColor("Speaker B");
    expect(colorA).not.toBe(colorB);
  });

  it("returns a palette color (not fallback) for non-empty label", () => {
    const color = getSpeakerColor("Speaker A");
    expect(color).not.toBe("text-slate-400");
    expect(color).toMatch(/^text-/);
  });
});
