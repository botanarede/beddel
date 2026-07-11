import { NextResponse } from 'next/server'
import { listTenants } from '@/lib/load-tenants'

export const dynamic = 'force-dynamic'

export async function GET() {
  const tenants = await listTenants()
  return NextResponse.json(tenants)
}
