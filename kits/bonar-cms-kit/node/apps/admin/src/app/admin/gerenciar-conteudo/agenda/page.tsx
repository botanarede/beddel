'use client'

import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useDynamicTable } from '@botanarede/bonarjs-sdk-alpha/react'

import { useTenant } from '@/lib/tenant-context'
import { toDate } from '@/lib/timestamp'

interface AgendaEvent {
  id?: string
  title: string
  description?: string
  date: number
  time?: string
  image?: string
  link?: string
  location?: string
  slug?: string
  archived?: boolean
  tags?: string[]
}

function slugify(title: string): string {
  return title
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

interface EditorState {
  id?: string
  title: string
  description: string
  date: string
  time: string
  location: string
  link: string
  image: string
}

const BLANK_EDITOR: EditorState = {
  title: '',
  description: '',
  date: '',
  time: '19:00',
  location: '',
  link: '',
  image: '',
}

export default function AdminAgenda() {
  const { getItems, setItem, deleteItemById } = useDynamicTable()
  const { tenantConfig } = useTenant()
  const [events, setEvents] = useState<AgendaEvent[]>([])
  const [loading, setLoading] = useState(true)
  const [editor, setEditor] = useState<EditorState | null>(null)

  const tenantName = tenantConfig?.metadata?.name ?? 'Tenant'

  const load = useCallback(() => {
    setLoading(true)
    getItems<AgendaEvent>('agenda', {
      orderBy: { field: 'date', direction: 'asc' },
    })
      .then((items) => setEvents(items.filter((e) => !e.archived)))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }, [getItems])

  useEffect(() => {
    load()
  }, [load])

  const openNew = () => setEditor({ ...BLANK_EDITOR })

  const openEdit = (ev: AgendaEvent) => {
    const d = toDate(ev.date)
    setEditor({
      id: ev.id,
      title: ev.title,
      description: ev.description ?? '',
      date: d ? d.toISOString().slice(0, 10) : '',
      time: ev.time ?? '19:00',
      location: ev.location ?? '',
      link: ev.link ?? '',
      image: ev.image ?? '',
    })
  }

  const save = async () => {
    if (!editor) return
    const dateMs = editor.date
      ? new Date(editor.date + 'T00:00:00').getTime()
      : Date.now()
    await setItem<AgendaEvent>(
      'agenda',
      {
        title: editor.title,
        description: editor.description,
        date: dateMs,
        time: editor.time,
        location: editor.location,
        link: editor.link,
        image: editor.image,
        slug: slugify(editor.title),
        archived: false,
      },
      editor.id,
      'NONE',
    )
    setEditor(null)
    load()
  }

  const confirmDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this item?')) return
    await deleteItemById('agenda', id)
    load()
  }

  return (
    <div className="mx-auto max-w-5xl">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Events</h1>
          <p className="text-sm text-muted-foreground">{tenantName}</p>
        </div>
        <button
          type="button"
          onClick={openNew}
          className="inline-flex items-center gap-2 rounded-md bg-[color:var(--brand-primary)] px-4 py-2 text-sm font-medium text-white"
        >
          <Plus size={16} />
          Create Event
        </button>
      </header>

      {loading ? (
        <p className="mt-8 text-sm text-muted-foreground">Loading...</p>
      ) : events.length === 0 ? (
        <p className="mt-8 text-sm text-muted-foreground">
          No upcoming events at the moment.
        </p>
      ) : (
        <ul className="mt-8 divide-y rounded-lg border bg-background">
          {events.map((ev) => (
            <li
              key={ev.id ?? ev.title}
              className="flex items-center justify-between px-4 py-3"
            >
              <div>
                <p className="font-medium">{ev.title}</p>
                <p className="text-xs text-muted-foreground">
                  {toDate(ev.date)?.toLocaleDateString('en-US') ?? ''}{' '}
                  {ev.time ? `• ${ev.time}` : ''}{' '}
                  {ev.location ? `• ${ev.location}` : ''}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => openEdit(ev)}
                  className="rounded-md border p-2"
                  aria-label="Edit"
                >
                  <Pencil size={16} />
                </button>
                <button
                  type="button"
                  onClick={() => ev.id && confirmDelete(ev.id)}
                  className="rounded-md border p-2 text-red-600"
                  aria-label="Delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {editor ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-lg rounded-lg border bg-background p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-semibold">
              {editor.id ? 'Edit Event' : 'Create Event'}
            </h2>
            <div className="grid gap-3 text-sm">
              <label className="flex flex-col gap-1">
                <span className="font-medium">Link</span>
                <input
                  value={editor.link}
                  onChange={(e) =>
                    setEditor({ ...editor, link: e.target.value })
                  }
                  className="rounded-md border px-3 py-2"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="font-medium">Title</span>
                <input
                  value={editor.title}
                  onChange={(e) =>
                    setEditor({ ...editor, title: e.target.value })
                  }
                  className="rounded-md border px-3 py-2"
                />
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex flex-col gap-1">
                  <span className="font-medium">Date</span>
                  <input
                    type="date"
                    value={editor.date}
                    onChange={(e) =>
                      setEditor({ ...editor, date: e.target.value })
                    }
                    className="rounded-md border px-3 py-2"
                  />
                </label>
                <label className="flex flex-col gap-1">
                  <span className="font-medium">Time</span>
                  <input
                    value={editor.time}
                    onChange={(e) =>
                      setEditor({ ...editor, time: e.target.value })
                    }
                    className="rounded-md border px-3 py-2"
                  />
                </label>
              </div>
              <label className="flex flex-col gap-1">
                <span className="font-medium">Location</span>
                <input
                  value={editor.location}
                  onChange={(e) =>
                    setEditor({ ...editor, location: e.target.value })
                  }
                  className="rounded-md border px-3 py-2"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="font-medium">Description</span>
                <textarea
                  rows={3}
                  value={editor.description}
                  onChange={(e) =>
                    setEditor({ ...editor, description: e.target.value })
                  }
                  className="rounded-md border px-3 py-2"
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="font-medium">Image URL</span>
                <input
                  value={editor.image}
                  onChange={(e) =>
                    setEditor({ ...editor, image: e.target.value })
                  }
                  className="rounded-md border px-3 py-2"
                />
              </label>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditor(null)}
                className="rounded-md border px-4 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={save}
                className="rounded-md bg-[color:var(--brand-primary)] px-4 py-2 text-sm font-medium text-white"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
