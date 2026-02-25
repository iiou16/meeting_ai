/**
 * Deterministic organization-based color assignment for speaker labels.
 *
 * Uses a string hash so the same organization always gets the same color,
 * regardless of sort order or session.
 */

const ORG_PALETTE = [
  "text-sky-300",
  "text-rose-300",
  "text-amber-300",
  "text-violet-300",
  "text-teal-300",
  "text-pink-300",
  "text-lime-300",
  "text-orange-300",
  "text-cyan-300",
  "text-fuchsia-300",
] as const;

const FALLBACK_COLOR = "text-slate-400";

function hashString(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = (hash * 31 + s.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

export function getOrgColor(organization: string): string {
  if (!organization) {
    return FALLBACK_COLOR;
  }
  const index = hashString(organization) % ORG_PALETTE.length;
  return ORG_PALETTE[index];
}

/**
 * Assign a deterministic color based on a speaker label (e.g. "Speaker A").
 * Used when no speaker mappings exist yet, so each raw label still gets
 * a distinct color.
 */
export function getSpeakerColor(label: string): string {
  if (!label) {
    return FALLBACK_COLOR;
  }
  const index = hashString(label) % ORG_PALETTE.length;
  return ORG_PALETTE[index];
}
