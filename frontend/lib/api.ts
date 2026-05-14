const API_BASE = "/api";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("procura_token");
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || "Request failed");
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<{ access_token: string; user: { id: string; email: string; name: string; role: string } }>(
        "/auth/login",
        { method: "POST", body: JSON.stringify({ email, password }) }
      ),
    register: (email: string, name: string, password: string) =>
      request<{ access_token: string; user: { id: string; email: string; name: string; role: string } }>(
        "/auth/register",
        { method: "POST", body: JSON.stringify({ email, name, password }) }
      ),
    me: () => request<{ id: string; email: string; name: string; role: string }>("/auth/me"),
  },

  procurements: {
    list: (params?: { skip?: number; limit?: number; status?: string; stage?: string }) => {
      const q = new URLSearchParams();
      if (params?.skip != null) q.set("skip", String(params.skip));
      if (params?.limit != null) q.set("limit", String(params.limit));
      if (params?.status) q.set("status", params.status);
      if (params?.stage) q.set("stage", params.stage);
      return request<{ items: import("@/types").Procurement[]; total: number }>(
        `/procurements?${q}`
      );
    },
    get: (id: string) => request<import("@/types").Procurement>(`/procurements/${id}`),
    create: (data: Record<string, unknown>) =>
      request<import("@/types").Procurement>("/procurements", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    update: (id: string, data: Record<string, unknown>) =>
      request<import("@/types").Procurement>(`/procurements/${id}`, {
        method: "PATCH",
        body: JSON.stringify(data),
      }),
  },

  proposals: {
    list: (procurementId: string) =>
      request<import("@/types").SupplierProposal[]>(`/procurements/${procurementId}/proposals`),

    uploadText: (procurementId: string, supplierName: string, textContent: string) => {
      const token = getToken();
      const form = new FormData();
      form.append("supplier_name", supplierName);
      form.append("text_content", textContent);
      return fetch(`${API_BASE}/procurements/${procurementId}/proposals`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      }).then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail || "Upload failed");
        }
        return res.json() as Promise<import("@/types").SupplierProposal>;
      });
    },

    uploadFile: (procurementId: string, supplierName: string, file: File) => {
      const token = getToken();
      const form = new FormData();
      form.append("supplier_name", supplierName);
      form.append("file", file);
      return fetch(`${API_BASE}/procurements/${procurementId}/proposals`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
      }).then(async (res) => {
        if (!res.ok) {
          const err = await res.json().catch(() => ({ detail: res.statusText }));
          throw new Error(err.detail || "Upload failed");
        }
        return res.json() as Promise<import("@/types").SupplierProposal>;
      });
    },

    delete: (procurementId: string, proposalId: string) =>
      request<void>(`/procurements/${procurementId}/proposals/${proposalId}`, {
        method: "DELETE",
      }),
  },

  results: {
    rfp: (id: string) => request<import("@/types").RFPDocument>(`/procurements/${id}/rfp`),
    evaluation: (id: string) =>
      request<import("@/types").EvaluationResult>(`/procurements/${id}/evaluation`),
    contract: (id: string) =>
      request<import("@/types").ContractResult>(`/procurements/${id}/contract`),
    _download: async (url: string, filename: string) => {
      const token = getToken();
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objectUrl;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(objectUrl);
    },
    downloadRfp: (id: string, filename: string) =>
      api.results._download(`${API_BASE}/procurements/${id}/rfp/download`, filename),
    downloadContract: (id: string, filename: string) =>
      api.results._download(`${API_BASE}/procurements/${id}/contract/download`, filename),
  },

  workflows: {
    start: (procurementId: string, workflowType: string, data: Record<string, unknown>) =>
      request<import("@/types").WorkflowRun>(
        `/procurements/${procurementId}/workflows/${workflowType}/start`,
        { method: "POST", body: JSON.stringify(data) }
      ),
    getActiveRun: (procurementId: string, workflowType: string) =>
      request<import("@/types").WorkflowRun | null>(
        `/procurements/${procurementId}/workflows/${workflowType}/run`
      ),
    getEvents: (procurementId: string, workflowType: string, threadId?: string) => {
      const q = threadId ? `?thread_id=${threadId}` : "";
      return request<import("@/types").WorkflowEvent[]>(
        `/procurements/${procurementId}/workflows/${workflowType}/events${q}`
      );
    },
    getModelConfigs: (procurementId: string) =>
      request<import("@/types").WorkflowModelConfig[]>(
        `/procurements/${procurementId}/workflows/model-config`
      ),
    getInterrupt: (procurementId: string, workflowType: string, threadId: string) =>
      request<{ node: string; data: Record<string, unknown> }>(
        `/procurements/${procurementId}/workflows/${workflowType}/interrupt?thread_id=${threadId}`
      ),
    getCheckpoints: (procurementId: string, workflowType: string, threadId: string) =>
      request<import("@/types").CheckpointItem[]>(
        `/procurements/${procurementId}/workflows/${workflowType}/checkpoints?thread_id=${threadId}`
      ),
    streamUrl: (procurementId: string, workflowType: string, threadId: string) =>
      `${API_BASE}/procurements/${procurementId}/workflows/${workflowType}/stream?thread_id=${threadId}`,
    resumeUrl: (procurementId: string, workflowType: string) =>
      `${API_BASE}/procurements/${procurementId}/workflows/${workflowType}/resume`,
    replayUrl: (procurementId: string, workflowType: string) =>
      `${API_BASE}/procurements/${procurementId}/workflows/${workflowType}/replay`,
    downloadAuditLog: async (procurementId: string) => {
      const token = getToken();
      const res = await fetch(`${API_BASE}/procurements/${procurementId}/workflows/audit-log`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `procura-audit-log-${procurementId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    },
  },

  revisions: {
    rfp: (procurementId: string) =>
      request<import("@/types").DocumentRevision[]>(`/procurements/${procurementId}/rfp/revisions`),
    contract: (procurementId: string) =>
      request<import("@/types").DocumentRevision[]>(`/procurements/${procurementId}/contract/revisions`),
  },
};
