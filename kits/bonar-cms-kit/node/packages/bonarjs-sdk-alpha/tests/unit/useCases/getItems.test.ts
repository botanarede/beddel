import { describe, expect, it } from 'vitest'

import { GetItems } from '../../../src/core/useCases/dynamicTable/GetItems'
import { FakeDatabase } from '../../fixtures/fakeAdapters'

describe('useCases/GetItems', () => {
  it('filters out archived items', async () => {
    const db = new FakeDatabase({
      seed: {
        agenda: [
          { id: 'a', title: 'Active' },
          { id: 'b', title: 'Archived', archived: true },
          { id: 'c', title: 'Active 2', archived: false },
        ],
      },
    })
    const items = await new GetItems(db).execute('agenda')
    expect(items.map((i) => (i as { id: string }).id)).toEqual(['a', 'c'])
  })

  it('returns empty array for missing table', async () => {
    const db = new FakeDatabase()
    expect(await new GetItems(db).execute('empty')).toEqual([])
  })

  it('passes query options to the adapter', async () => {
    const db = new FakeDatabase({ seed: { agenda: [] } })
    const opts = { limit: 5 as const }
    await new GetItems(db).execute('agenda', opts)
    expect(db.calls.getItems[0]?.options).toEqual(opts)
  })
})
