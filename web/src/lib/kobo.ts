import models from "../../../shared/kobo_models.json";

export interface KoboBook {
  name: string;
  relativePath: string;
}

export interface KoboInfo {
  isKobo: boolean;
  error: string | null;
  firmware: string;
  modelName: string;
  modelCode: string;
  authorized: boolean;
  books: KoboBook[];
  bookCount: number;
}

const modelNames = models as Record<string, string>;

export function parseVersion(text: string): { firmware: string; modelName: string; modelCode: string } {
  const fields = text.trim().split(",").map((part) => part.trim());
  const firmware = fields.length > 2 ? fields[2] : "";
  const modelId = fields.length > 1 ? fields[fields.length - 1] : "";
  const digits = modelId.replace(/\D/g, "");
  const modelCode = digits.length >= 3 ? digits.slice(-3) : "";
  const modelName = modelCode
    ? modelNames[modelCode] ?? `Kobo (code ${modelCode})`
    : "Kobo";
  return { firmware, modelName, modelCode };
}

export async function inspectHandle(root: FileSystemDirectoryHandle): Promise<KoboInfo> {
  let kobo: FileSystemDirectoryHandle;
  try {
    kobo = await root.getDirectoryHandle(".kobo");
  } catch {
    return empty("Ce dossier ne ressemble pas à une Kobo : le dossier .kobo est introuvable.");
  }
  let versionText = "";
  try {
    const versionHandle = await kobo.getFileHandle("version");
    versionText = await (await versionHandle.getFile()).text();
  } catch {
    return {
      ...empty("Kobo détectée, mais le fichier .kobo/version est introuvable."),
      isKobo: true,
      authorized: await hasActivation(root),
    };
  }
  const parsed = parseVersion(versionText);
  const books = await listBooks(root);
  return {
    isKobo: true,
    error: null,
    firmware: parsed.firmware,
    modelName: parsed.modelName,
    modelCode: parsed.modelCode,
    authorized: await hasActivation(root),
    books,
    bookCount: books.length,
  };
}

function empty(error: string): KoboInfo {
  return {
    isKobo: false,
    error,
    firmware: "",
    modelName: "",
    modelCode: "",
    authorized: false,
    books: [],
    bookCount: 0,
  };
}

async function hasActivation(root: FileSystemDirectoryHandle): Promise<boolean> {
  try {
    const adobe = await root.getDirectoryHandle(".adobe-digital-editions");
    await adobe.getFileHandle("activation.xml");
    return true;
  } catch {
    return false;
  }
}

async function listBooks(root: FileSystemDirectoryHandle): Promise<KoboBook[]> {
  const books: KoboBook[] = [];
  await walk(root, "", books);
  books.sort((a, b) => a.relativePath.localeCompare(b.relativePath, "fr"));
  return books;
}

async function walk(dir: FileSystemDirectoryHandle, prefix: string, books: KoboBook[]): Promise<void> {
  for await (const [name, handle] of dir.entries()) {
    if (name.startsWith(".")) continue;
    if (handle.kind === "directory") {
      await walk(handle, `${prefix}${name}/`, books);
    } else {
      const lower = name.toLowerCase();
      if (lower.endsWith(".epub") || lower.endsWith(".pdf")) {
        books.push({ name, relativePath: `${prefix}${name}` });
      }
    }
  }
}

export function bookFileName(creator: string, title: string): string {
  const base = [creator, title].map((part) => part.trim()).filter(Boolean).join(" - ") || "livre";
  const cleaned = base.replace(/[\\/:*?"<>|\r\n]/g, "_").replace(/[. ]+$/g, "").slice(0, 120);
  return `${cleaned || "livre"}.epub`;
}

export async function writeToKobo(root: FileSystemDirectoryHandle, filename: string, data: Blob): Promise<void> {
  if (filename.includes("/") || filename.includes("\\") || filename.startsWith(".")) {
    throw new Error("Nom de fichier refusé.");
  }
  const folder = await root.getDirectoryHandle("Liseo", { create: true });
  const handle = await folder.getFileHandle(filename, { create: true });
  const writable = await handle.createWritable();
  await writable.write(data);
  await writable.close();
  const written = await handle.getFile();
  if (written.size !== data.size) {
    throw new Error(
      `Copie incomplète (${written.size} octets au lieu de ${data.size}). N'éjectez pas la liseuse et recommencez.`,
    );
  }
}
