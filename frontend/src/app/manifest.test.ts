import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import manifest from "./manifest";

describe("manifest", () => {
  const result = manifest();

  it("has the required top-level fields", () => {
    expect(result.name).toBe("Vox Quieta");
    expect(result.short_name).toBe("Vox Quieta");
    expect(result.display).toBe("standalone");
    expect(result.start_url).toBe("/");
    expect(result.background_color).toBe("#faf5f0");
    expect(result.theme_color).toBe("#874a30");
  });

  it("includes a 192x192 icon, a plain 512x512 icon, and a maskable 512x512 icon", () => {
    const icons = result.icons ?? [];

    const icon192 = icons.find((icon) => icon.sizes === "192x192");
    expect(icon192).toBeDefined();

    const icon512Plain = icons.find(
      (icon) => icon.sizes === "512x512" && !icon.purpose,
    );
    expect(icon512Plain).toBeDefined();

    const icon512Maskable = icons.find(
      (icon) => icon.sizes === "512x512" && icon.purpose === "maskable",
    );
    expect(icon512Maskable).toBeDefined();
  });

  it("points every icon at a file that actually exists in public/", () => {
    const icons = result.icons ?? [];
    expect(icons.length).toBeGreaterThan(0);

    for (const icon of icons) {
      const relativeSrc = icon.src.replace(/^\//, "");
      const resolvedPath = path.join(process.cwd(), "public", relativeSrc);
      expect(
        fs.existsSync(resolvedPath),
        `Expected icon file to exist: ${resolvedPath}`,
      ).toBe(true);
    }
  });
});
