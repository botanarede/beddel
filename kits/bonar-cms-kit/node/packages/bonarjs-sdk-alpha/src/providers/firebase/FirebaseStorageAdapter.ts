import {
  deleteObject,
  getDownloadURL as firebaseGetDownloadURL,
  ref,
  uploadString,
  type FirebaseStorage,
} from 'firebase/storage'

import type { IStorageAdapter } from '../../core/interfaces/IStorageAdapter'
import type { StorageMetadata } from '../../core/types'

/** Configuration for {@link FirebaseStorageAdapter}. */
export interface FirebaseStorageAdapterConfig {
  storage: FirebaseStorage
}

/** IStorageAdapter implementation backed by `firebase/storage`. */
export class FirebaseStorageAdapter implements IStorageAdapter {
  private readonly storage: FirebaseStorage

  constructor(config: FirebaseStorageAdapterConfig) {
    this.storage = config.storage
  }

  async uploadJSON(
    path: string,
    data: unknown,
    metadata?: StorageMetadata,
  ): Promise<void> {
    const storageRef = ref(this.storage, path)
    await uploadString(storageRef, JSON.stringify(data), 'raw', {
      contentType: metadata?.contentType ?? 'application/json',
      cacheControl: metadata?.cacheControl,
      customMetadata: metadata?.customMetadata,
    })
  }

  async getDownloadURL(path: string): Promise<string> {
    const storageRef = ref(this.storage, path)
    return firebaseGetDownloadURL(storageRef)
  }

  async deleteObject(path: string): Promise<void> {
    const storageRef = ref(this.storage, path)
    try {
      await deleteObject(storageRef)
    } catch (err) {
      // Firebase throws when the object does not exist — treat as idempotent.
      const code = (err as { code?: string } | undefined)?.code
      if (code && code === 'storage/object-not-found') return
      throw err
    }
  }
}
