import { render, screen } from "@testing-library/react";

import Home from "./page";

describe("Home page", () => {
  it("renders key marketing content", () => {
    render(<Home />);

    expect(
      screen.getByRole("heading", {
        name: /MeetingAI Minutes Generator/i,
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("button", { name: /Upload Recording/i }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("heading", { name: /Accurate Transcripts/i }),
    ).toBeInTheDocument();
  });
});
