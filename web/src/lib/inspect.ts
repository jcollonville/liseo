import JSZip from "jszip";

export interface AcsmPreview {
  title: string;
  creator: string;
  format: string;
  operatorURL: string;
  expiration: string;
  displayUntil: string;
  fulfillmentType: string;
}

export interface EpubPreview {
  kind: "adobe" | "lcp" | "clear";
  message: string;
}

export function parseAcsm(text: string): AcsmPreview {
  const doc = new DOMParser().parseFromString(text, "application/xml");
  if (doc.querySelector("parsererror")) {
    throw new Error("Ce fichier .acsm n'est pas un XML lisible.");
  }
  const root = doc.documentElement;
  return {
    title: textOf(doc, "title"),
    creator: textOf(doc, "creator"),
    format: textOf(doc, "format"),
    operatorURL: textOf(doc, "operatorURL"),
    expiration: textOf(doc, "expiration"),
    displayUntil: textOf(doc, "until"),
    fulfillmentType: root.getAttribute("fulfillmentType") ?? "",
  };
}

function textOf(doc: Document, localName: string): string {
  const elements = doc.getElementsByTagName("*");
  for (const element of elements) {
    const name = element.localName || element.tagName;
    if (name === localName && element.textContent?.trim()) {
      return element.textContent.trim();
    }
  }
  return "";
}

export async function inspectEpub(file: File): Promise<EpubPreview> {
  const zip = await JSZip.loadAsync(await file.arrayBuffer());
  const names = new Set(Object.keys(zip.files).map((name) => name.replace(/\\/g, "/")));
  const hasRights = names.has("META-INF/rights.xml");
  const hasEncryption = names.has("META-INF/encryption.xml");
  const hasLcp = names.has("META-INF/license.lcpl");
  if (hasLcp) {
    return {
      kind: "lcp",
      message:
        "Ce fichier utilise Readium LCP. Les Kobo anciennes ne savent pas le lire. Liseo peut le copier, sans le modifier.",
    };
  }
  if (hasRights && hasEncryption) {
    return {
      kind: "adobe",
      message: "EPUB protégé par Adobe. Il sera copié tel quel, sans conversion.",
    };
  }
  return {
    kind: "clear",
    message: "EPUB sans DRM détecté. Il sera copié tel quel. La conversion KEPUB n'est pas dans ce prototype.",
  };
}
