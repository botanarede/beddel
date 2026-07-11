import type { StorageMetadata } from '../types'

/**
 * Minimal object-storage surface required by the SDK. Only JSON uploads are
 * exercised today but `deleteObject`/`getDownloadURL` are kept symmetrical
 * for future uses (e.g. hosting user-uploaded images).
 */
export interface IStorageAdapter {
  /** Upload `data` as a JSON blob at `path`. Overwrites on conflict. */
  uploadJSON(
    path: string,
    data: unknown,
    metadata?: StorageMetadata,
  ): Promise<void>

  /** Return a browser-reachable download URL for the object at `path`. */
  getDownloadURL(path: string): Promise<string>

  /** Delete the object at `path`. No-op when the object does not exist. */
  deleteObject(path: string): Promise<void>
}
