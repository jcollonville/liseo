<script lang="ts">
  import { get, set } from "idb-keyval";
  import { onMount } from "svelte";
  import { activate, fulfill, login, logout, status, type AccountStatus } from "./lib/api";
  import { inspectEpub, parseAcsm, type AcsmPreview, type EpubPreview } from "./lib/inspect";
  import { bookFileName, inspectHandle, writeToKobo, type KoboInfo } from "./lib/kobo";

  const HANDLE_KEY = "liseo-kobo-handle";

  let authed = false;
  let adminPassword = "";
  let account: AccountStatus | null = null;
  let bytebooksUser = "";
  let bytebooksPassword = "";
  let kobo: KoboInfo | null = null;
  let rootHandle: FileSystemDirectoryHandle | null = null;
  let progress = "";
  let error = "";
  let notice = "";
  let busy = false;
  let preview: AcsmPreview | null = null;
  let epubNote: EpubPreview | null = null;
  let showEject = false;
  let browserOk = true;

  onMount(async () => {
    browserOk = window.isSecureContext && typeof window.showDirectoryPicker === "function";
    try {
      account = await status();
      authed = true;
    } catch {
      authed = false;
    }
    if (authed) await restoreKobo();
  });

  async function submitLogin() {
    error = "";
    try {
      await login(adminPassword);
      adminPassword = "";
      account = await status();
      authed = true;
      await restoreKobo();
    } catch (err) {
      error = message(err);
    }
  }

  async function submitLogout() {
    await logout();
    authed = false;
    account = null;
  }

  async function submitActivate() {
    error = "";
    notice = "";
    busy = true;
    progress = "Activation du compte…";
    const password = bytebooksPassword;
    bytebooksPassword = "";
    try {
      account = await activate(bytebooksUser, password);
      notice = "Compte activé. Le mot de passe n'est pas conservé.";
    } catch (err) {
      error = message(err);
    } finally {
      busy = false;
      progress = "";
    }
  }

  async function pickKobo() {
    error = "";
    notice = "";
    showEject = false;
    try {
      const handle = await window.showDirectoryPicker({ mode: "readwrite" });
      await remember(handle);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      error = "Le navigateur a refusé l'accès au dossier. Utilisez Chrome ou Edge, sur localhost ou en HTTPS.";
    }
  }

  async function restoreKobo() {
    try {
      const stored = await get<FileSystemDirectoryHandle>(HANDLE_KEY);
      if (!stored) return;
      const permission = await stored.queryPermission({ mode: "readwrite" });
      if (permission !== "granted") {
        notice = "La liseuse a déjà été choisie. Confirmez l'accès pour la relire.";
        rootHandle = stored;
        return;
      }
      await remember(stored);
    } catch {
      /* IndexedDB may be unavailable. */
    }
  }

  async function remember(handle: FileSystemDirectoryHandle) {
    rootHandle = handle;
    kobo = await inspectHandle(handle);
    try {
      await set(HANDLE_KEY, handle);
    } catch {
      /* Persistence is optional. */
    }
  }

  async function onDrop(event: DragEvent) {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (file) await receive(file);
  }

  async function onFile(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (file) await receive(file);
  }

  async function receive(file: File) {
    error = "";
    notice = "";
    showEject = false;
    preview = null;
    epubNote = null;
    const lower = file.name.toLowerCase();
    try {
      if (lower.endsWith(".acsm")) await receiveAcsm(file);
      else if (lower.endsWith(".epub")) await receiveEpub(file);
      else error = "Déposez un fichier .acsm ou un EPUB.";
    } catch (err) {
      error = message(err);
      progress = "";
      busy = false;
    }
  }

  async function receiveAcsm(file: File) {
    const text = await file.text();
    preview = parseAcsm(text);
    if (!rootHandle || !kobo?.isKobo) {
      error = "Sélectionnez d'abord le dossier de la Kobo.";
      return;
    }
    if (!kobo.authorized) {
      error = "Kobo non autorisée : faites l'étape Adobe Digital Editions avec le même compte ByteBooks.";
      return;
    }
    busy = true;
    progress = "Récupération du prêt…";
    const blob = await fulfill(file);
    progress = "Écriture sur la liseuse…";
    const filename = bookFileName(preview.creator, preview.title);
    await writeToKobo(rootHandle, filename, blob);
    kobo = await inspectHandle(rootHandle);
    progress = "";
    busy = false;
    showEject = true;
    notice = `${filename} a été écrit dans le dossier Liseo.`;
  }

  async function receiveEpub(file: File) {
    epubNote = await inspectEpub(file);
    if (!rootHandle || !kobo?.isKobo) {
      error = "Sélectionnez d'abord le dossier de la Kobo.";
      return;
    }
    busy = true;
    progress = "Écriture sur la liseuse…";
    const filename = file.name.toLowerCase().endsWith(".epub") ? file.name : `${file.name}.epub`;
    await writeToKobo(rootHandle, filename.split(/[/\\]/).pop() || "livre.epub", file);
    kobo = await inspectHandle(rootHandle);
    progress = "";
    busy = false;
    showEject = true;
    notice = `${filename} a été écrit dans le dossier Liseo.`;
  }

  function message(err: unknown): string {
    return err instanceof Error ? err.message : "Une erreur est survenue.";
  }
</script>

<main>
  <h1>Liseo</h1>
  <p class="lede">Copier un prêt de bibliothèque ou un EPUB sur une Kobo, sans retirer la protection.</p>

  {#if !browserOk}
    <p class="error">
      La sélection de la liseuse demande Chrome ou Edge, ouvert sur localhost ou en HTTPS.
    </p>
  {/if}

  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if notice}<p class="ok" role="status">{notice}</p>{/if}
  {#if progress}<p class="hint" role="status">{progress}</p>{/if}
  {#if showEject}
    <p class="ok">Éjectez la liseuse proprement avant de la débrancher. Elle indexera ensuite le livre.</p>
  {/if}

  {#if !authed}
    <form class="card" on:submit|preventDefault={submitLogin}>
      <h2>Connexion</h2>
      <label>
        Mot de passe de Liseo
        <input type="password" bind:value={adminPassword} autocomplete="current-password" />
      </label>
      <button type="submit">Entrer</button>
    </form>
  {:else}
    <div class="row">
      <p class="meta">Session ouverte.</p>
      <button class="secondary" type="button" on:click={submitLogout}>Fermer la session</button>
    </div>

    <section class="card">
      <h2>Compte ByteBooks</h2>
      {#if account?.activated}
        <p>Appareil activé{#if account.username} pour {account.username}{/if}.</p>
        <p class="hint">Le mot de passe n'est pas enregistré. Ne supprimez pas le volume Docker : il contient l'unique activation.</p>
      {:else}
        <p class="hint">Saisissez l'identifiant ByteBooks, le même que celui utilisé pour autoriser la Kobo dans Adobe Digital Editions.</p>
        <form on:submit|preventDefault={submitActivate}>
          <label>
            Identifiant
            <input type="text" bind:value={bytebooksUser} autocomplete="username" />
          </label>
          <label>
            Mot de passe
            <input type="password" bind:value={bytebooksPassword} autocomplete="current-password" />
          </label>
          <button type="submit" disabled={busy}>Activer</button>
        </form>
      {/if}
    </section>

    <section class="card">
      <h2>Liseuse</h2>
      <button type="button" on:click={pickKobo} disabled={!browserOk || busy}>Sélectionner ma liseuse</button>
      {#if kobo?.isKobo}
        <p><strong>{kobo.modelName}</strong>{#if kobo.firmware} · firmware {kobo.firmware}{/if}</p>
        <p>{kobo.bookCount} livre{kobo.bookCount === 1 ? "" : "s"} repéré{kobo.bookCount === 1 ? "" : "s"} sur le volume.</p>
        {#if kobo.books.length}
          <ul class="books">
            {#each kobo.books.slice(0, 30) as book}
              <li>{book.relativePath}</li>
            {/each}
          </ul>
          {#if kobo.books.length > 30}
            <p class="hint">et {kobo.books.length - 30} autres</p>
          {/if}
        {/if}
        {#if !kobo.authorized}
          <p class="error">Kobo non autorisée : faites l'étape Adobe Digital Editions avec le même compte ByteBooks.</p>
        {/if}
      {:else if kobo?.error}
        <p class="error">{kobo.error}</p>
      {/if}
    </section>

    <section class="card">
      <h2>Ajouter un livre</h2>
      <div
        class="drop"
        class:ready={Boolean(kobo?.isKobo)}
        on:dragover|preventDefault
        on:drop={onDrop}
        role="region"
        aria-label="Dépôt de fichier"
      >
        <p>Déposez un fichier .acsm (prêt PNB) ou un EPUB.</p>
        <input type="file" accept=".acsm,.epub,application/epub+zip" on:change={onFile} />
      </div>
      {#if preview}
        <p>
          <strong>{preview.title || "Sans titre"}</strong>
          {#if preview.creator} — {preview.creator}{/if}
        </p>
        <p class="meta">
          {preview.fulfillmentType || "fichier"} · {preview.operatorURL}
          {#if preview.expiration} · jeton jusqu'au {preview.expiration}{/if}
          {#if preview.displayUntil} · prêt jusqu'au {preview.displayUntil}{/if}
        </p>
      {/if}
      {#if epubNote}
        <p class="hint">{epubNote.message}</p>
      {/if}
    </section>
  {/if}
</main>
