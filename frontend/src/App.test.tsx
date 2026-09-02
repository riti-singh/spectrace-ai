import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { dashboardFixture } from "./test/fixtures";

function mockDashboard() {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input);
    const byPath: Record<string, unknown> = {
      "/requirements": dashboardFixture.requirements,
      "/components": dashboardFixture.components,
      "/risks": dashboardFixture.risks,
      "/test-cases": dashboardFixture.tests,
      "/traceability/uncovered": dashboardFixture.uncovered,
      "/traceability/summary": dashboardFixture.summary,
      "/retrieval/evaluation": dashboardFixture.evaluation
    };
    return new Response(JSON.stringify(byPath[path]), { status: 200, headers: { "Content-Type": "application/json" } });
  }));
}

describe("executive dashboard", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads backend metrics and opens linked artifact details", async () => {
    mockDashboard();
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByText("50%")).toBeInTheDocument();
    expect(screen.getByText("5", { selector: ".metric-card > strong" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /REQ-002 Credential validation/i }));
    expect(screen.getByRole("dialog", { name: "Credential validation" })).toBeInTheDocument();
    expect(screen.getByText(/validate credentials before enabling user traffic/i)).toBeInTheDocument();
  });

  it("shows a useful API error and retry control", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: { message: "Dataset unavailable" } }), { status: 503, headers: { "Content-Type": "application/json" } })));
    render(<App />);
    expect(await screen.findByText(/Dataset unavailable/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeEnabled();
  });
});
