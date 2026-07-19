// web-test storage/storage v1.0 — Playwright WebStorage helpers.

import { page, ensureConnected } from '../core/state.mjs';

function normalizeKind(kind = 'local') {
  if (kind !== 'local' && kind !== 'session') {
    throw new Error("storage kind must be 'local' or 'session'");
  }
  return kind;
}

function storageFor(kind = 'local') {
  ensureConnected();
  const normalized = normalizeKind(kind);
  const store = normalized === 'session' ? page.sessionStorage : page.localStorage;
  if (!store) {
    throw new Error('Playwright WebStorage API is unavailable; install Playwright 1.61 or newer.');
  }
  return store;
}

function readArgs(keyOrOptions, options) {
  if (
    options === undefined
    && keyOrOptions
    && typeof keyOrOptions === 'object'
    && !Array.isArray(keyOrOptions)
  ) {
    return { key: undefined, options: keyOrOptions };
  }
  return { key: keyOrOptions, options: options || {} };
}

export async function getStorage(keyOrOptions, options) {
  const { key, options: opts } = readArgs(keyOrOptions, options);
  const store = storageFor(opts.kind);
  if (key === undefined) return await store.items();
  return await store.getItem(String(key));
}

export async function setStorage(key, value, options = {}) {
  if (key === undefined) throw new Error('setStorage requires a key');
  const kind = normalizeKind(options.kind);
  const store = storageFor(kind);
  await store.setItem(String(key), String(value));
  return { kind, key: String(key), value: await store.getItem(String(key)) };
}

export async function removeStorage(key, options = {}) {
  if (key === undefined) throw new Error('removeStorage requires a key');
  const kind = normalizeKind(options.kind);
  const store = storageFor(kind);
  await store.removeItem(String(key));
  return { kind, key: String(key), removed: true };
}

export async function clearStorage(options = {}) {
  const kind = normalizeKind(options.kind);
  const store = storageFor(kind);
  await store.clear();
  return { kind, cleared: true };
}
