/**
 * Generates a complete set of CSS custom properties from tenant config.
 *
 * Converts hex colors to HSL space-separated values for Tailwind compatibility
 * (e.g., #0a0a0a → "0 0% 4%") and produces both raw hex brand vars and
 * HSL-based Tailwind vars (--background, --foreground, --primary, etc.).
 */

import type { RuntimeSiteConfig } from '@/config/tenant-types'

/**
 * Convert a hex color (#rrggbb or #rgb) to HSL space-separated string: "H S% L%"
 */
export function hexToHSL(hex: string): string {
  // Normalize
  let h = hex.replace('#', '')
  if (h.length === 3) {
    h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2]
  }

  const r = parseInt(h.substring(0, 2), 16) / 255
  const g = parseInt(h.substring(2, 4), 16) / 255
  const b = parseInt(h.substring(4, 6), 16) / 255

  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2

  if (max === min) {
    // Achromatic
    return `0 0% ${Math.round(l * 100)}%`
  }

  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max - min)

  let hue: number
  switch (max) {
    case r:
      hue = ((g - b) / d + (g < b ? 6 : 0)) * 60
      break
    case g:
      hue = ((b - r) / d + 2) * 60
      break
    default:
      hue = ((r - g) / d + 4) * 60
      break
  }

  return `${Math.round(hue)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`
}

/**
 * Lightens or darkens a hex color by a given amount (-100 to 100).
 * Positive = lighter, negative = darker.
 */
function adjustLightness(hex: string, amount: number): string {
  let h = hex.replace('#', '')
  if (h.length === 3) {
    h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2]
  }

  const r = parseInt(h.substring(0, 2), 16) / 255
  const g = parseInt(h.substring(2, 4), 16) / 255
  const b = parseInt(h.substring(4, 6), 16) / 255

  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  let l = (max + min) / 2
  let s = 0
  let hue = 0

  if (max !== min) {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max - min)
    switch (max) {
      case r:
        hue = ((g - b) / d + (g < b ? 6 : 0)) * 60
        break
      case g:
        hue = ((b - r) / d + 2) * 60
        break
      default:
        hue = ((r - g) / d + 4) * 60
        break
    }
  }

  l = Math.min(1, Math.max(0, l + amount / 100))

  return `${Math.round(hue)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`
}

/**
 * Generates the full :root CSS block with all theme variables.
 * Reads designTokens colors + branding from siteConfig.
 */
export function generateThemeVars(
  siteConfig: RuntimeSiteConfig,
  designTokens: { colors?: Record<string, string | Record<string, string>>; typography?: { fontFamilies?: Record<string, string> }; backgroundImage?: string },
): string {
  const rawColors = designTokens.colors ?? {}

  // Extract only flat string color values (ignore nested shade maps)
  const colors: Record<string, string> = {}
  for (const [key, value] of Object.entries(rawColors)) {
    if (typeof value === 'string') {
      colors[key] = value
    }
  }

  // Resolve colors with fallbacks
  const background = colors['background'] ?? '#ffffff'
  const foreground = colors['foreground'] ?? '#1b4332'
  const primary = colors['primary'] ?? siteConfig.branding.primaryColor
  const accent = colors['accent'] ?? siteConfig.branding.accentColor
  const tertiary = colors['tertiary'] ?? ''

  // Font families
  const fontHeading = siteConfig.branding.fontHeading ?? 'Inter'
  const fontBody = siteConfig.branding.fontBody ?? 'Inter'

  // Determine if dark theme (lightness of background < 20%)
  const bgLightness = parseInt(hexToHSL(background).split('%')[0].split(' ').pop() ?? '50')
  const isDark = bgLightness < 20

  // Muted: slightly shifted from background
  const muted = isDark ? adjustLightness(background, 8) : adjustLightness(background, -4)
  // Muted foreground: dimmed version of foreground
  const mutedForeground = isDark ? adjustLightness(foreground, -20) : adjustLightness(foreground, 20)
  // Border: subtle
  const border = isDark ? adjustLightness(background, 12) : adjustLightness(background, -10)

  // Background image (optional)
  const backgroundImage = designTokens.backgroundImage ?? ''

  const lines: string[] = [
    ':root {',
    `  --brand-primary: ${primary};`,
    `  --brand-accent: ${accent};`,
    `  --brand-background: ${background};`,
    `  --brand-foreground: ${foreground};`,
  ]

  if (tertiary) {
    lines.push(`  --brand-tertiary: ${tertiary};`)
  }

  if (backgroundImage) {
    lines.push(`  --brand-background-image: url('${backgroundImage}');`)
  }

  lines.push(
    `  --font-heading: '${fontHeading}', sans-serif;`,
    `  --font-body: '${fontBody}', sans-serif;`,
    `  --background: ${hexToHSL(background)};`,
    `  --foreground: ${hexToHSL(foreground)};`,
    `  --primary: ${hexToHSL(primary)};`,
    `  --primary-foreground: ${isDark ? '0 0% 100%' : '0 0% 100%'};`,
    `  --secondary: ${muted};`,
    `  --secondary-foreground: ${hexToHSL(foreground)};`,
    `  --accent: ${hexToHSL(accent)};`,
    `  --accent-foreground: ${hexToHSL(foreground)};`,
    `  --muted: ${muted};`,
    `  --muted-foreground: ${mutedForeground};`,
    `  --card: ${hexToHSL(background)};`,
    `  --card-foreground: ${hexToHSL(foreground)};`,
    `  --popover: ${hexToHSL(background)};`,
    `  --popover-foreground: ${hexToHSL(foreground)};`,
    `  --border: ${border};`,
    `  --input: ${border};`,
    `  --ring: ${hexToHSL(primary)};`,
    `  --destructive: 0 84% 60%;`,
    `  --destructive-foreground: 0 0% 100%;`,
    `  --radius: 0.5rem;`,
    '}',
  )

  return lines.join('\n')
}
