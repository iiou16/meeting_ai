/**
 * Tests for lib/api.ts
 */

import {
  fetchJobs,
  fetchJob,
  fetchMeeting,
  deleteJob,
  uploadVideo,
  updateJobTitle,
} from "./api";

const API_BASE = "http://localhost:8000";
const originalFetch = global.fetch;

afterEach(() => {
  global.fetch = originalFetch;
});

// ---------- fetchJobs (requestJson indirect) ----------

describe("fetchJobs", () => {
  it("returns parsed JSON on success", async () => {
    const payload = [{ job_id: "j1", status: "completed" }];
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(payload),
    });

    const result = await fetchJobs();
    expect(result).toEqual(payload);
  });

  it("throws Error with response text on failure", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve("Internal Server Error"),
    });

    await expect(fetchJobs()).rejects.toThrow("Internal Server Error");
  });

  it("throws Error with status when response text is empty", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 502,
      text: () => Promise.resolve(""),
    });

    await expect(fetchJobs()).rejects.toThrow("502");
  });

  it("calls correct URL with exact match", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    });

    await fetchJobs();
    expect(global.fetch).toHaveBeenCalledWith(
      `${API_BASE}/api/jobs`,
      undefined,
    );
  });
});

// ---------- fetchJob ----------

describe("fetchJob", () => {
  it("encodes jobId in URL", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ job_id: "a/b" }),
    });

    await fetchJob("a/b");
    const calledUrl = (global.fetch as jest.Mock).mock.calls[0][0] as string;
    expect(calledUrl).toBe(`${API_BASE}/api/jobs/${encodeURIComponent("a/b")}`);
  });

  it("throws on non-ok response", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve("Job not found"),
    });

    await expect(fetchJob("missing")).rejects.toThrow("Job not found");
  });
});

// ---------- fetchMeeting ----------

describe("fetchMeeting", () => {
  it("calls correct URL with exact match", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ job_id: "m1" }),
    });

    await fetchMeeting("m1");
    const calledUrl = (global.fetch as jest.Mock).mock.calls[0][0] as string;
    expect(calledUrl).toBe(`${API_BASE}/api/meetings/m1`);
  });

  it("encodes jobId in URL", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ job_id: "x/y" }),
    });

    await fetchMeeting("x/y");
    const calledUrl = (global.fetch as jest.Mock).mock.calls[0][0] as string;
    expect(calledUrl).toBe(
      `${API_BASE}/api/meetings/${encodeURIComponent("x/y")}`,
    );
  });

  it("throws on non-ok response", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve("Server error"),
    });

    await expect(fetchMeeting("m1")).rejects.toThrow("Server error");
  });
});

// ---------- deleteJob ----------

describe("deleteJob", () => {
  it("sends DELETE to correct URL with encoded jobId", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
    });

    await deleteJob("a/b");
    const calledUrl = (global.fetch as jest.Mock).mock.calls[0][0] as string;
    const init = (global.fetch as jest.Mock).mock.calls[0][1];
    expect(calledUrl).toBe(
      `${API_BASE}/api/meetings/${encodeURIComponent("a/b")}`,
    );
    expect(init.method).toBe("DELETE");
  });

  it("throws on non-ok response", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 404,
      text: () => Promise.resolve("Not found"),
    });

    await expect(deleteJob("j1")).rejects.toThrow("Not found");
  });

  it("throws with status fallback when response text is empty", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve(""),
    });

    await expect(deleteJob("j1")).rejects.toThrow("500");
  });

  it("resolves void on success", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
    });

    const result = await deleteJob("j1");
    expect(result).toBeUndefined();
  });
});

// ---------- updateJobTitle ----------

describe("updateJobTitle", () => {
  it("sends PATCH to correct URL with JSON body", async () => {
    const responsePayload = { job_id: "j1", title: "My Meeting" };
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(responsePayload),
    });

    const result = await updateJobTitle("j1", "My Meeting");
    expect(result).toEqual(responsePayload);

    const calledUrl = (global.fetch as jest.Mock).mock.calls[0][0] as string;
    const init = (global.fetch as jest.Mock).mock.calls[0][1];
    expect(calledUrl).toBe(`${API_BASE}/api/jobs/j1`);
    expect(init.method).toBe("PATCH");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ title: "My Meeting" });
  });

  it("encodes jobId in URL", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ job_id: "a/b" }),
    });

    await updateJobTitle("a/b", "test");
    const calledUrl = (global.fetch as jest.Mock).mock.calls[0][0] as string;
    expect(calledUrl).toBe(
      `${API_BASE}/api/jobs/${encodeURIComponent("a/b")}`,
    );
  });

  it("throws on non-ok response", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 422,
      text: () => Promise.resolve("Validation error"),
    });

    await expect(updateJobTitle("j1", "")).rejects.toThrow("Validation error");
  });
});

// ---------- uploadVideo ----------

describe("uploadVideo", () => {
  let xhrMock: {
    open: jest.Mock;
    send: jest.Mock;
    abort: jest.Mock;
    upload: { onprogress: ((e: Partial<ProgressEvent>) => void) | null };
    onload: (() => void) | null;
    onerror: (() => void) | null;
    status: number;
    responseText: string;
  };

  const originalXHR = global.XMLHttpRequest;

  beforeEach(() => {
    xhrMock = {
      open: jest.fn(),
      send: jest.fn(),
      abort: jest.fn(),
      upload: { onprogress: null },
      onload: null,
      onerror: null,
      status: 200,
      responseText: '{"job_id":"j1"}',
    };
    global.XMLHttpRequest = jest.fn(() => xhrMock) as unknown as typeof XMLHttpRequest;
  });

  afterEach(() => {
    global.XMLHttpRequest = originalXHR;
  });

  const dummyFile = new File(["data"], "video.mp4", { type: "video/mp4" });

  it("resolves with UploadResponse on success", async () => {
    const promise = uploadVideo(dummyFile);
    xhrMock.status = 200;
    xhrMock.responseText = '{"job_id":"j1"}';
    xhrMock.onload!();

    const result = await promise;
    expect(result).toEqual({ job_id: "j1" });
  });

  it("calls open with POST and correct URL", async () => {
    const promise = uploadVideo(dummyFile);
    expect(xhrMock.open).toHaveBeenCalledWith(
      "POST",
      `${API_BASE}/api/videos`,
      true,
    );

    xhrMock.status = 200;
    xhrMock.responseText = '{"job_id":"j1"}';
    xhrMock.onload!();
    await promise;
  });

  it("sends FormData via xhr.send", async () => {
    const promise = uploadVideo(dummyFile);
    expect(xhrMock.send).toHaveBeenCalledTimes(1);
    const sentData = xhrMock.send.mock.calls[0][0];
    expect(sentData).toBeInstanceOf(FormData);

    xhrMock.status = 200;
    xhrMock.responseText = '{"job_id":"j1"}';
    xhrMock.onload!();
    await promise;
  });

  it("includes language in FormData when provided", async () => {
    const promise = uploadVideo(dummyFile, { language: "en" });
    const sentData = xhrMock.send.mock.calls[0][0] as FormData;
    expect(sentData.get("language")).toBe("en");

    xhrMock.status = 200;
    xhrMock.responseText = '{"job_id":"j1"}';
    xhrMock.onload!();
    await promise;
  });

  it("omits language from FormData when not provided", async () => {
    const promise = uploadVideo(dummyFile);
    const sentData = xhrMock.send.mock.calls[0][0] as FormData;
    expect(sentData.has("language")).toBe(false);

    xhrMock.status = 200;
    xhrMock.responseText = '{"job_id":"j1"}';
    xhrMock.onload!();
    await promise;
  });

  it("rejects on network error", async () => {
    const promise = uploadVideo(dummyFile);
    xhrMock.onerror!();

    await expect(promise).rejects.toThrow("Network error");
  });

  it("calls onProgress callback", async () => {
    const onProgress = jest.fn();
    const promise = uploadVideo(dummyFile, { onProgress });

    xhrMock.upload.onprogress!({
      lengthComputable: true,
      loaded: 50,
      total: 100,
    });

    expect(onProgress).toHaveBeenCalledWith(50);

    xhrMock.status = 200;
    xhrMock.responseText = '{"job_id":"j1"}';
    xhrMock.onload!();
    await promise;
  });

  it("does not call onProgress when lengthComputable is false", async () => {
    const onProgress = jest.fn();
    const promise = uploadVideo(dummyFile, { onProgress });

    xhrMock.upload.onprogress!({
      lengthComputable: false,
      loaded: 50,
      total: 0,
    });

    expect(onProgress).not.toHaveBeenCalled();

    xhrMock.status = 200;
    xhrMock.responseText = '{"job_id":"j1"}';
    xhrMock.onload!();
    await promise;
  });

  it("rejects with DOMException AbortError when signal is already aborted", async () => {
    const controller = new AbortController();
    controller.abort();

    const promise = uploadVideo(dummyFile, { signal: controller.signal });
    try {
      await promise;
      fail("expected rejection");
    } catch (e) {
      expect(e).toBeInstanceOf(DOMException);
      expect((e as DOMException).name).toBe("AbortError");
      expect((e as DOMException).message).toBe("Upload aborted");
    }
  });

  it("aborts xhr when signal fires after request started", async () => {
    const controller = new AbortController();
    const listeners: Record<string, () => void> = {};
    controller.signal.addEventListener = jest.fn((event: string, handler: () => void) => {
      listeners[event] = handler;
    });
    controller.signal.removeEventListener = jest.fn();

    const promise = uploadVideo(dummyFile, { signal: controller.signal });

    // Simulate abort after request started
    listeners["abort"]();

    await expect(promise).rejects.toThrow("Upload aborted");
    expect(xhrMock.abort).toHaveBeenCalled();
  });

  it("removes abort listener on successful completion", async () => {
    const controller = new AbortController();
    const addSpy = jest.spyOn(controller.signal, "addEventListener");
    const removeSpy = jest.spyOn(controller.signal, "removeEventListener");

    const promise = uploadVideo(dummyFile, { signal: controller.signal });

    xhrMock.status = 200;
    xhrMock.responseText = '{"job_id":"j1"}';
    xhrMock.onload!();
    await promise;

    expect(addSpy).toHaveBeenCalledWith("abort", expect.any(Function));
    expect(removeSpy).toHaveBeenCalledWith("abort", expect.any(Function));
  });

  it("rejects on non-2xx status", async () => {
    const promise = uploadVideo(dummyFile);
    xhrMock.status = 500;
    xhrMock.responseText = "Server error";
    xhrMock.onload!();

    await expect(promise).rejects.toThrow("Server error");
  });

  it("rejects with status fallback on non-2xx with empty body", async () => {
    const promise = uploadVideo(dummyFile);
    xhrMock.status = 503;
    xhrMock.responseText = "";
    xhrMock.onload!();

    await expect(promise).rejects.toThrow("503");
  });

  it("rejects when response JSON is invalid", async () => {
    const promise = uploadVideo(dummyFile);
    xhrMock.status = 200;
    xhrMock.responseText = "not-json{";
    xhrMock.onload!();

    await expect(promise).rejects.toThrow();
  });

  it("does not remove abort listener on network error", async () => {
    const controller = new AbortController();
    const removeSpy = jest.spyOn(controller.signal, "removeEventListener");

    const promise = uploadVideo(dummyFile, { signal: controller.signal });
    xhrMock.onerror!();

    await expect(promise).rejects.toThrow("Network error");
    expect(removeSpy).not.toHaveBeenCalled();
  });

  it("removes abort listener on non-2xx error via onload", async () => {
    const controller = new AbortController();
    const removeSpy = jest.spyOn(controller.signal, "removeEventListener");

    const promise = uploadVideo(dummyFile, { signal: controller.signal });
    xhrMock.status = 500;
    xhrMock.responseText = "Server error";
    xhrMock.onload!();

    await expect(promise).rejects.toThrow("Server error");
    // removeEventListener is called at the start of onload, before status check
    expect(removeSpy).toHaveBeenCalledWith("abort", expect.any(Function));
  });
});

// ---------- fetch rejection (network-level) ----------

describe("fetch rejection propagation", () => {
  it("fetchJobs rejects when fetch itself throws", async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(fetchJobs()).rejects.toThrow("Failed to fetch");
  });

  it("fetchJob rejects when fetch itself throws", async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(fetchJob("j1")).rejects.toThrow("Failed to fetch");
  });

  it("fetchMeeting rejects when fetch itself throws", async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(fetchMeeting("m1")).rejects.toThrow("Failed to fetch");
  });

  it("deleteJob rejects when fetch itself throws", async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError("Failed to fetch"));

    await expect(deleteJob("j1")).rejects.toThrow("Failed to fetch");
  });
});

// ---------- uploadVideo edge cases ----------

describe("uploadVideo edge cases", () => {
  let xhrMock: {
    open: jest.Mock;
    send: jest.Mock;
    abort: jest.Mock;
    upload: { onprogress: ((e: Partial<ProgressEvent>) => void) | null };
    onload: (() => void) | null;
    onerror: (() => void) | null;
    status: number;
    responseText: string;
  };

  const originalXHR = global.XMLHttpRequest;

  beforeEach(() => {
    xhrMock = {
      open: jest.fn(),
      send: jest.fn(),
      abort: jest.fn(),
      upload: { onprogress: null },
      onload: null,
      onerror: null,
      status: 200,
      responseText: '{"job_id":"j1"}',
    };
    global.XMLHttpRequest = jest.fn(() => xhrMock) as unknown as typeof XMLHttpRequest;
  });

  afterEach(() => {
    global.XMLHttpRequest = originalXHR;
  });

  const dummyFile = new File(["data"], "video.mp4", { type: "video/mp4" });

  it("rounds progress percentage correctly at boundary", async () => {
    const onProgress = jest.fn();
    const promise = uploadVideo(dummyFile, { onProgress });

    // 1/3 = 33.333...% → Math.round → 33
    xhrMock.upload.onprogress!({
      lengthComputable: true,
      loaded: 1,
      total: 3,
    });
    expect(onProgress).toHaveBeenCalledWith(33);

    // 2/3 = 66.666...% → Math.round → 67
    xhrMock.upload.onprogress!({
      lengthComputable: true,
      loaded: 2,
      total: 3,
    });
    expect(onProgress).toHaveBeenCalledWith(67);

    xhrMock.status = 200;
    xhrMock.responseText = '{"job_id":"j1"}';
    xhrMock.onload!();
    await promise;
  });

  it("safely ignores progress when onProgress is not provided", async () => {
    const promise = uploadVideo(dummyFile);

    // Should not throw even with lengthComputable=true
    xhrMock.upload.onprogress!({
      lengthComputable: true,
      loaded: 50,
      total: 100,
    });

    xhrMock.status = 200;
    xhrMock.responseText = '{"job_id":"j1"}';
    xhrMock.onload!();
    await promise;
  });
});

// ---------- requestJson JSON parse failure ----------

describe("requestJson JSON parse failure", () => {
  it("fetchJobs rejects when response.json() fails", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.reject(new SyntaxError("Unexpected token")),
    });

    await expect(fetchJobs()).rejects.toThrow("Unexpected token");
  });
});
