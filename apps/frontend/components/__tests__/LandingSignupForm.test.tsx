import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { LandingSignupForm } from "../LandingSignupForm";

describe("LandingSignupForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("prefills the email field when defaultEmail is provided", () => {
    render(<LandingSignupForm apiBase="http://localhost:4000" defaultEmail="test@example.com" />);
    const input = screen.getByPlaceholderText("you@firm.com") as HTMLInputElement;
    expect(input.value).toBe("test@example.com");
  });

  it("shows success message when submission succeeds", async () => {
    const fetchMock = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "stored" }), { status: 200 }),
    );

    render(<LandingSignupForm apiBase="http://localhost:4000" />);
    const emailInput = screen.getByPlaceholderText("you@firm.com") as HTMLInputElement;
    fireEvent.change(emailInput, { target: { value: "hello@example.com" } });
    fireEvent.submit(emailInput.closest("form") as HTMLFormElement);

    await waitFor(() => expect(screen.getByText(/Thanks!/i)).toBeVisible());
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});

