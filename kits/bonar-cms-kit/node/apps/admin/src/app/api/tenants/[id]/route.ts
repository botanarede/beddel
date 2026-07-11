import { NextResponse } from 'next/server'
import { loadTenantConfig } from '@/lib/load-tenants'

export const dynamic = 'force-dynamic'

export async function GET(
  _request: Request,
  { params }: { params: { id: string } },
) {
  const config = await loadTenantConfig(params.id)
  if (!config) {
    return NextResponse.json({ error: 'Tenant not found' }, { status: 404 })
  }
  return NextResponse.json(config)
}
