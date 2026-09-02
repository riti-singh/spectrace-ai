import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SearchWorkspace } from "./SearchWorkspace";

describe("traceability search", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("submits the selected mode and explains result scoring", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ query: "thermal protection", mode: "semantic", result_count: 1, results: [{ id: "REQ-005", entity_type: "Requirement", title: "Thermal protection", text: "The terminal shall protect hardware at bounded temperatures.", score: .92, explanation: { fusion_method: "normalized_component_score", lexical: null, semantic: { raw_score: .92, normalized_score: 1, rank: 1, contribution: 1 }, graph: null, graph_distance: null, anchor_ids: [] } }] }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<SearchWorkspace onSelect={() => undefined} />);

    await user.click(screen.getByRole("radio", { name: /Semantic/ }));
    await user.type(screen.getByLabelText("Traceability query"), "thermal protection");
    await user.click(screen.getByRole("button", { name: /Search/ }));
    expect(await screen.findByText("Thermal protection")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/retrieval/search", expect.objectContaining({ body: expect.stringContaining('"mode":"semantic"') }));
    await user.click(screen.getByText("Why this result"));
    expect(screen.getByText("rank #1")).toBeInTheDocument();
  });

  it("identifies when the graph backend is required", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: { code: "neo4j_backend_required", message: "Neo4j required" } }), { status: 503, headers: { "Content-Type": "application/json" } })));
    const user = userEvent.setup();
    render(<SearchWorkspace onSelect={() => undefined} />);
    await user.click(screen.getByRole("button", { name: "thermal protection verification" }));
    expect(await screen.findByText(/needs the Neo4j-backed local stack/i)).toBeInTheDocument();
  });
});
