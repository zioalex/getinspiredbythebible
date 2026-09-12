import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const { reportClientErrorMock } = vi.hoisted(() => ({
  reportClientErrorMock: vi.fn(),
}));
vi.mock("@/lib/clientErrorReporter", () => ({
  reportClientError: reportClientErrorMock,
}));

import { registerServiceWorker } from "./registerServiceWorker";

function setSecureContext(value: boolean) {
  Object.defineProperty(window, "isSecureContext", {
    value,
    configurable: true,
  });
}

function setServiceWorkerContainer(container: unknown) {
  Object.defineProperty(navigator, "serviceWorker", {
    value: container,
    configurable: true,
  });
}

describe("registerServiceWorker", () => {
  let registerMock: ReturnType<typeof vi.fn>;
  let getRegistrationsMock: ReturnType<typeof vi.fn>;
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    reportClientErrorMock.mockClear();
    registerMock = vi.fn().mockResolvedValue({ scope: "/" });
    getRegistrationsMock = vi.fn().mockResolvedValue([]);
    setServiceWorkerContainer({
      register: registerMock,
      getRegistrations: getRegistrationsMock,
    });
    setSecureContext(true);
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("registers /sw.js?v=<buildId> in production when build-info.json is valid", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ buildId: "sha1" }),
    });

    const result = await registerServiceWorker({ isProduction: true });

    expect(fetchMock).toHaveBeenCalledWith("/build-info.json", {
      cache: "no-store",
    });
    expect(registerMock).toHaveBeenCalledWith("/sw.js?v=sha1", {
      scope: "/",
      updateViaCache: "none",
    });
    expect(result).toEqual({ scope: "/" });
  });

  it("does not register when build-info.json 404s", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 404 });

    const result = await registerServiceWorker({ isProduction: true });

    expect(registerMock).not.toHaveBeenCalled();
    expect(result).toBeNull();
  });

  it("does not register when build-info.json has no buildId", async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({}) });
    expect(await registerServiceWorker({ isProduction: true })).toBeNull();
    expect(registerMock).not.toHaveBeenCalled();

    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ buildId: "" }) });
    expect(await registerServiceWorker({ isProduction: true })).toBeNull();
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("unregisters existing service workers and never registers in non-production", async () => {
    const reg1 = { unregister: vi.fn().mockResolvedValue(true) };
    const reg2 = { unregister: vi.fn().mockResolvedValue(true) };
    getRegistrationsMock.mockResolvedValue([reg1, reg2]);

    const result = await registerServiceWorker({ isProduction: false });

    expect(reg1.unregister).toHaveBeenCalled();
    expect(reg2.unregister).toHaveBeenCalled();
    expect(registerMock).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(result).toBeNull();
  });

  it("returns null without throwing when navigator.serviceWorker is unsupported", async () => {
    delete (navigator as unknown as { serviceWorker?: unknown }).serviceWorker;
    await expect(registerServiceWorker({ isProduction: true })).resolves.toBeNull();
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("returns null without throwing when the context is not secure", async () => {
    setSecureContext(false);
    await expect(registerServiceWorker({ isProduction: true })).resolves.toBeNull();
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("returns null and reports the error when register() rejects", async () => {
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({ buildId: "sha1" }) });
    registerMock.mockRejectedValue(new Error("boom"));

    const result = await registerServiceWorker({ isProduction: true });

    expect(result).toBeNull();
    expect(reportClientErrorMock).toHaveBeenCalledTimes(1);
    const [type, detail] = reportClientErrorMock.mock.calls[0];
    expect(type).toBe("api_failure");
    expect(detail).toContain("boom");
  });
});
