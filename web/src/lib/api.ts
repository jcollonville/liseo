export interface AccountStatus {
  activated: boolean;
  username: string | null;
  activated_at?: string | null;
  version?: string;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* ignore */
  }
  return `Erreur ${response.status}`;
}

export async function login(password: string): Promise<void> {
  const response = await fetch("/api/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!response.ok) throw new Error(await readError(response));
}

export async function logout(): Promise<void> {
  await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
}

export async function status(): Promise<AccountStatus> {
  const response = await fetch("/api/status", { credentials: "same-origin" });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function activate(username: string, password: string): Promise<AccountStatus> {
  const response = await fetch("/api/account/activate", {
    method: "POST",
    credentials: "same-origin",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username, password, replace: false }),
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export async function fulfill(file: File): Promise<Blob> {
  const body = new FormData();
  body.append("file", file, file.name);
  const response = await fetch("/api/fulfill", {
    method: "POST",
    credentials: "same-origin",
    body,
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.blob();
}
