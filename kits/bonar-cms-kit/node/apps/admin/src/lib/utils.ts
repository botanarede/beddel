import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Concatenate Tailwind class names while resolving conflicts. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
