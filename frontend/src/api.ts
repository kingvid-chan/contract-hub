const BASE = "/projects/contract-hub/api";

let token: string | null = null;

export function setToken(t: string | null) {
  token = t;
}

export function getToken(): string | null {
  return token;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  params?: Record<string, string>;
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

export async function api<T = unknown>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { method = "GET", body, params } = options;

  let url = `${BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  if (body !== undefined && !(body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url, {
    method,
    headers,
    body:
      body instanceof FormData
        ? body
        : body !== undefined
        ? JSON.stringify(body)
        : undefined,
  });

  if (res.status === 401) {
    setToken(null);
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || res.statusText);
  }

  // Handle file downloads
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return res.json();
  }

  return res as unknown as T;
}

// ── Auth ────────────────────────────────────────────

export interface UserInfo {
  id: number;
  username: string;
  role: string;
}

export interface LoginResponse {
  access_token: string;
  user: UserInfo;
}

export async function loginApi(
  username: string,
  password: string
): Promise<LoginResponse> {
  return api<LoginResponse>("/auth/login", {
    method: "POST",
    body: { username, password },
  });
}

export async function getMe(): Promise<UserInfo> {
  return api<UserInfo>("/auth/me");
}

// ── Users (admin) ───────────────────────────────────

export interface PaginatedUsers {
  items: UserInfo[];
  total: number;
  page: number;
  page_size: number;
}

export async function getUsers(
  page = 1,
  pageSize = 20
): Promise<PaginatedUsers> {
  return api<PaginatedUsers>(
    `/users?page=${page}&page_size=${pageSize}`
  );
}

export async function createUser(data: {
  username: string;
  password: string;
  role: string;
}): Promise<UserInfo> {
  return api<UserInfo>("/users", { method: "POST", body: data });
}

export async function updateUser(
  id: number,
  data: { username?: string; password?: string; role?: string }
): Promise<UserInfo> {
  return api<UserInfo>(`/users/${id}`, { method: "PUT", body: data });
}

export async function deleteUser(id: number): Promise<void> {
  return api(`/users/${id}`, { method: "DELETE" });
}

// ── Contracts ───────────────────────────────────────

export interface ContractInfo {
  id: number;
  title: string;
  description: string;
  status: string;
  creator_id: number;
  created_at: string;
  updated_at: string;
  creator?: UserInfo;
  attachments: AttachmentInfo[];
}

export interface PaginatedContracts {
  items: ContractInfo[];
  total: number;
  page: number;
  page_size: number;
}

export async function getContracts(
  page = 1,
  pageSize = 20,
  status = ""
): Promise<PaginatedContracts> {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  };
  if (status) params.status = status;
  return api<PaginatedContracts>("/contracts", { params });
}

export async function getContract(id: number): Promise<ContractInfo> {
  return api<ContractInfo>(`/contracts/${id}`);
}

export async function createContract(data: {
  title: string;
  description: string;
}): Promise<ContractInfo> {
  return api<ContractInfo>("/contracts", { method: "POST", body: data });
}

export async function updateContract(
  id: number,
  data: { title?: string; description?: string }
): Promise<ContractInfo> {
  return api<ContractInfo>(`/contracts/${id}`, { method: "PUT", body: data });
}

export async function deleteContract(id: number): Promise<void> {
  return api(`/contracts/${id}`, { method: "DELETE" });
}

export async function submitContract(id: number): Promise<ContractInfo> {
  return api<ContractInfo>(`/contracts/${id}/submit`, { method: "POST" });
}

export async function approveContract(id: number): Promise<ContractInfo> {
  return api<ContractInfo>(`/contracts/${id}/approve`, { method: "POST" });
}

export async function rejectContract(id: number): Promise<ContractInfo> {
  return api<ContractInfo>(`/contracts/${id}/reject`, { method: "POST" });
}

export async function terminateContract(id: number): Promise<ContractInfo> {
  return api<ContractInfo>(`/contracts/${id}/terminate`, { method: "POST" });
}

// ── Attachments ─────────────────────────────────────

export interface AttachmentInfo {
  id: number;
  filename: string;
  original_name: string;
  file_size: number;
  content_type: string;
  contract_id: number;
  uploader_id: number;
  created_at: string;
}

export async function uploadAttachment(
  contractId: number,
  file: File
): Promise<AttachmentInfo> {
  const formData = new FormData();
  formData.append("file", file);
  return api<AttachmentInfo>(`/contracts/${contractId}/attachments`, {
    method: "POST",
    body: formData,
  });
}

export async function deleteAttachment(id: number): Promise<void> {
  return api(`/attachments/${id}`, { method: "DELETE" });
}

export async function downloadAttachment(
  id: number,
  originalName: string
): Promise<void> {
  const url = `${BASE}/attachments/${id}`;
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { headers });

  if (res.status === 401) {
    setToken(null);
  }

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new ApiError(res.status, data.detail || res.statusText);
  }

  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);

  // Use hidden iframe to trigger download — more reliable than a.click()
  // because setting iframe.src does not require a user-gesture context,
  // which is lost after the async fetch/await chain.
  const iframe = document.createElement("iframe");
  iframe.style.display = "none";
  iframe.src = objectUrl;
  document.body.appendChild(iframe);

  // Clean up after download starts (generous timeout for slow connections)
  setTimeout(() => {
    document.body.removeChild(iframe);
    URL.revokeObjectURL(objectUrl);
  }, 60_000);
}
