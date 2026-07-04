/**
 * Primitive component tests.
 *
 * The primitives are presentational and design-token driven; tests assert
 * the structural contract (data attributes, semantic text) rather than
 * pixel output, since CSS variables are not resolved by jsdom.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  Pill,
  friendlyValidationStatus,
  KpiCard,
  MetricChip,
  RingSVG,
  SectorDot,
  sectorKindFromId,
  ThesisBanner,
} from "@/components/primitives";

afterEach(() => {
  cleanup();
});

// ── Pill ──────────────────────────────────────────────────────────────────────

describe("Pill", () => {
  it("renders children", () => {
    render(<Pill variant="green">verified</Pill>);
    expect(screen.getByText("verified")).toBeInTheDocument();
  });

  it("exposes the variant via data-variant for CSS to hook into", () => {
    render(<Pill variant="amber">needs review</Pill>);
    const el = screen.getByText("needs review");
    expect(el.getAttribute("data-variant")).toBe("amber");
    expect(el.className).toContain("al-pill");
  });

  it("defaults to gray when no variant provided", () => {
    render(<Pill>idle</Pill>);
    expect(screen.getByText("idle").getAttribute("data-variant")).toBe("gray");
  });
});

describe("friendlyValidationStatus", () => {
  it("maps PASSED → Verified/green", () => {
    expect(friendlyValidationStatus("PASSED")).toEqual({
      label: "Verified",
      variant: "green",
    });
  });

  it("maps FAILED → Needs Review/amber (soft, never red)", () => {
    expect(friendlyValidationStatus("FAILED")).toEqual({
      label: "Needs Review",
      variant: "amber",
    });
  });

  it("maps WARNING → Reviewed/amber", () => {
    expect(friendlyValidationStatus("WARNING")).toEqual({
      label: "Reviewed",
      variant: "amber",
    });
  });

  it("returns null for unknown / empty values", () => {
    expect(friendlyValidationStatus("")).toBeNull();
    expect(friendlyValidationStatus(null)).toBeNull();
    expect(friendlyValidationStatus("OTHER")).toBeNull();
  });
});

// ── KpiCard ───────────────────────────────────────────────────────────────────

describe("KpiCard", () => {
  it("renders label, value and sub", () => {
    render(<KpiCard label="Direction acc." value="66.7%" sub="10/15 checked" />);
    expect(screen.getByText("Direction acc.")).toBeInTheDocument();
    expect(screen.getByText("66.7%")).toBeInTheDocument();
    expect(screen.getByText("10/15 checked")).toBeInTheDocument();
  });

  it("renders adornment slot when provided", () => {
    render(
      <KpiCard label="x" value="1" adornment={<span data-testid="adorn">★</span>} />
    );
    expect(screen.getByTestId("adorn")).toBeInTheDocument();
  });

  it("omits sub when not provided", () => {
    render(<KpiCard label="x" value="1" />);
    // Only label + value text — no extra subtitle.
    expect(screen.queryByText("10/15 checked")).not.toBeInTheDocument();
  });
});

// ── MetricChip ────────────────────────────────────────────────────────────────

describe("MetricChip", () => {
  it("renders label and value", () => {
    render(<MetricChip label="News" value="12" />);
    expect(screen.getByText("News")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
  });

  it("renders sub line when provided", () => {
    render(<MetricChip label="News" value="12" sub="last 7 days" />);
    expect(screen.getByText("last 7 days")).toBeInTheDocument();
  });
});

// ── RingSVG ───────────────────────────────────────────────────────────────────

describe("RingSVG", () => {
  it("renders the percentage and score-of-max text", () => {
    render(<RingSVG score={8} max={10} />);
    expect(screen.getByText("80")).toBeInTheDocument(); // big number
    expect(screen.getByText("8/10")).toBeInTheDocument(); // sub-label
  });

  it("clamps to 100% when score exceeds max", () => {
    render(<RingSVG score={15} max={10} />);
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("clamps to 0% when score is negative", () => {
    render(<RingSVG score={-3} max={10} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("uses warn colour below threshold (4 by default)", () => {
    const { container } = render(<RingSVG score={2} max={10} />);
    // The second circle (foreground) carries the dynamic stroke colour.
    const circles = container.querySelectorAll("circle");
    expect(circles[1].getAttribute("stroke")).toBe("var(--al-bearish)");
  });

  it("uses gold colour at or above threshold", () => {
    const { container } = render(<RingSVG score={7} max={10} />);
    const circles = container.querySelectorAll("circle");
    expect(circles[1].getAttribute("stroke")).toBe("var(--al-gold)");
  });

  it("supports score format (no percent sign)", () => {
    render(<RingSVG score={7} max={10} format="score" />);
    expect(screen.getByText("7")).toBeInTheDocument();
  });
});

// ── SectorDot ─────────────────────────────────────────────────────────────────

describe("SectorDot", () => {
  it("maps a known sector_id to its kind", () => {
    expect(sectorKindFromId("ai_semiconductors")).toBe("ai");
    expect(sectorKindFromId("space_rockets")).toBe("space");
    expect(sectorKindFromId("optical_communications")).toBe("optical");
  });

  it("returns 'unknown' for unmapped or null inputs", () => {
    expect(sectorKindFromId("crypto")).toBe("unknown");
    expect(sectorKindFromId(null)).toBe("unknown");
    expect(sectorKindFromId(undefined)).toBe("unknown");
  });

  it("renders with the resolved data-sector attribute", () => {
    const { container } = render(<SectorDot sectorId="space_rockets" />);
    const span = container.querySelector("span");
    expect(span?.getAttribute("data-sector")).toBe("space");
  });

  it("prefers explicit kind over sectorId", () => {
    const { container } = render(
      <SectorDot kind="optical" sectorId="ai_semiconductors" />
    );
    expect(container.querySelector("span")?.getAttribute("data-sector")).toBe(
      "optical"
    );
  });
});

// ── ThesisBanner ──────────────────────────────────────────────────────────────

describe("ThesisBanner", () => {
  it("renders default label and child text", () => {
    render(<ThesisBanner>Apple is set up well into next quarter.</ThesisBanner>);
    expect(screen.getByText("Investment thesis")).toBeInTheDocument();
    expect(
      screen.getByText("Apple is set up well into next quarter.")
    ).toBeInTheDocument();
  });

  it("respects custom label", () => {
    render(<ThesisBanner label="Today's read">…</ThesisBanner>);
    expect(screen.getByText("Today's read")).toBeInTheDocument();
  });
});
