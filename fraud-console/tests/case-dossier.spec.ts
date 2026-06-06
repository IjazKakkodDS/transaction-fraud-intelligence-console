import { expect, test } from "@playwright/test";

test("Case Dossier 2.0 renders evidence and preserves analyst workflow", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));

  const response = await page.goto("/cases/21");

  expect(response?.status()).toBeLessThan(500);
  await expect(page.getByText("Case Dossier 2.0", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Score and decision summary" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Intelligence evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Case Timeline" })).toBeVisible();
  await expect(page.getByText("Transaction recorded", { exact: true })).toBeVisible();
  await expect(page.getByText("Analyst verdict recorded", { exact: true })).toBeVisible();
  await expect(page.getByText("AI Investigation", { exact: true })).toBeVisible();
  await expect(page.getByText("Analyst Verdict", { exact: true })).toBeVisible();
  await expect(page.getByText("Workflow Automation", { exact: true })).toBeVisible();
  await expect(page.getByText("Automation Audit Trail", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Dispatch Workflow Automation" })).toBeVisible();
  expect(errors).toHaveLength(0);
});

test("Case Dossier 2.0 stacks cleanly on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/cases/21");

  await expect(page.getByRole("heading", { name: "Score and decision summary" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Intelligence evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Case Timeline" })).toBeVisible();
  await expect(page.getByText("Analyst Verdict", { exact: true })).toBeVisible();

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);
});
