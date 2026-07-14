import type { IAuthAdapter } from '../../src/core/interfaces/IAuthAdapter'
import type { ICacheAdapter } from '../../src/core/interfaces/ICacheAdapter'
import type { IDatabaseAdapter } from '../../src/core/interfaces/IDatabaseAdapter'
import type { IStorageAdapter } from '../../src/core/interfaces/IStorageAdapter'
import type { IMailAdapter } from '../../src/core/interfaces/IMailAdapter'
import type { User } from '../../src/core/entities/User'
import type {
  EventType,
  LoginResult,
  MailPayload,
  OAuthProvider,
  OAuthSignInOptions,
  QueryOptions,
  StorageMetadata,
  CacheVariant,
} from '../../src/core/types'
import { LoginStatus } from '../../src/core/types'

export interface FakeDatabaseOptions {
  seed?: Record<string, Record<string, unknown>[]>
}

export class FakeDatabase implements IDatabaseAdapter {
  readonly tables: Record<string, Record<string, unknown>[]>
  public calls: {
    getItems: Array<{ table: string; options?: QueryOptions }>
    getItemById: Array<{ table: string; id: string }>
    setItem: Array<{ table: string; data: object; id?: string; events?: EventType }>
    deleteItemById: Array<{ table: string; id: string }>
    getItemChildById: Array<{
      table: string
      itemId: string
      childName: string
      childId: string
    }>
  } = {
    getItems: [],
    getItemById: [],
    setItem: [],
    deleteItemById: [],
    getItemChildById: [],
  }

  constructor(options: FakeDatabaseOptions = {}) {
    this.tables = JSON.parse(JSON.stringify(options.seed ?? {}))
  }

  async getItems<T>(table: string, options?: QueryOptions): Promise<T[]> {
    this.calls.getItems.push({ table, options })
    return (this.tables[table] ?? []) as T[]
  }
  async getItemById<T>(table: string, id: string): Promise<T | null> {
    this.calls.getItemById.push({ table, id })
    const list = this.tables[table] ?? []
    return (list.find((x) => (x as { id?: string }).id === id) as T | undefined) ?? null
  }
  async setItem<T>(
    table: string,
    data: object,
    id?: string,
    events?: EventType,
  ): Promise<T> {
    this.calls.setItem.push({ table, data, id, events })
    this.tables[table] ??= []
    const newId = id ?? `id-${this.tables[table]!.length + 1}`
    const item = { id: newId, ...(data as object) } as Record<string, unknown>
    const existing = this.tables[table]!.findIndex(
      (x) => (x as { id?: string }).id === newId,
    )
    if (existing >= 0) this.tables[table]![existing] = item
    else this.tables[table]!.push(item)
    return item as T
  }
  async deleteItemById(
    table: string,
    id: string,
  ): Promise<{ success: true }> {
    this.calls.deleteItemById.push({ table, id })
    if (this.tables[table]) {
      this.tables[table] = this.tables[table]!.filter(
        (x) => (x as { id?: string }).id !== id,
      )
    }
    return { success: true }
  }
  async getItemChildById<T>(
    table: string,
    itemId: string,
    childName: string,
    childId: string,
  ): Promise<T | null> {
    this.calls.getItemChildById.push({ table, itemId, childName, childId })
    return null
  }
}

export class FakeCache implements ICacheAdapter {
  readonly writes: Array<{ table: string; items: unknown[] }> = []
  readonly invalidations: string[] = []
  readonly reads: Array<{ table: string; variant?: CacheVariant }> = []
  readonly backing = new Map<string, unknown[]>()

  async getCachedItems<T>(table: string, variant?: CacheVariant): Promise<T[] | null> {
    this.reads.push({ table, variant })
    const key = variant ? `${table}-${variant}` : table
    return (this.backing.get(key) as T[]) ?? null
  }
  async updateCache(table: string, items: unknown[]): Promise<void> {
    this.writes.push({ table, items })
    this.backing.set(table, items)
  }
  invalidate(table: string): void {
    this.invalidations.push(table)
    this.backing.delete(table)
  }
}

export class FakeStorage implements IStorageAdapter {
  readonly uploads: Array<{
    path: string
    data: unknown
    metadata?: StorageMetadata
  }> = []
  readonly deletes: string[] = []

  async uploadJSON(
    path: string,
    data: unknown,
    metadata?: StorageMetadata,
  ): Promise<void> {
    this.uploads.push({ path, data, metadata })
  }
  async getDownloadURL(path: string): Promise<string> {
    return `https://fake.example/${path}`
  }
  async deleteObject(path: string): Promise<void> {
    this.deletes.push(path)
  }
}

export class FakeAuth implements IAuthAdapter {
  public currentUser: User | null = null
  private listeners: Array<(u: User | null) => void> = []

  async signInWithEmailPassword(
    email: string,
    _password: string,
  ): Promise<LoginResult> {
    this.currentUser = { email }
    this.emit()
    return { message: LoginStatus.SUCCESS, user: this.currentUser }
  }
  async signInWithEmailCode(
    email: string,
    code?: number,
  ): Promise<LoginResult> {
    if (code === undefined) return { message: LoginStatus.EMAIL_SENT }
    if (code === 1234) {
      this.currentUser = { email }
      this.emit()
      return { message: LoginStatus.SUCCESS, user: this.currentUser }
    }
    return { message: LoginStatus.INVALID_CODE }
  }
  async signInWithOAuth(
    _provider: OAuthProvider,
    _options?: OAuthSignInOptions,
  ): Promise<LoginResult> {
    this.currentUser = { email: 'oauth@example.com' }
    this.emit()
    return { message: LoginStatus.SUCCESS, user: this.currentUser }
  }
  async signOut(): Promise<void> {
    this.currentUser = null
    this.emit()
  }
  async getCurrentUser(): Promise<User | null> {
    return this.currentUser
  }
  onAuthStateChanged(listener: (u: User | null) => void): () => void {
    this.listeners.push(listener)
    listener(this.currentUser)
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener)
    }
  }
  async getIdToken(): Promise<string | null> {
    return this.currentUser ? 'fake-id-token' : null
  }

  private emit(): void {
    for (const l of this.listeners) l(this.currentUser)
  }
}

export class FakeMail implements IMailAdapter {
  readonly sent: MailPayload[] = []
  async send(payload: MailPayload): Promise<void> {
    this.sent.push(payload)
  }
}
