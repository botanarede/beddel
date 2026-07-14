/**
 * PublicLayout — responsive header + main content + footer.
 *
 * Navigation clicks dispatch via BehaviorContract actions.
 * All content comes from props — no hardcoded strings.
 */

'use client';

import { useState } from 'react';
import type { BehaviorContract, BehaviorDispatcher } from '@botanarede/core';

export interface NavItem {
  label: string;
  type: 'route' | 'external';
  route?: string;
  href?: string;
}

export interface PublicLayoutProps {
  children: React.ReactNode;
  navigation: { items: NavItem[] };
  siteConfig: {
    name: string;
    logo: string;
    logoWhite?: string;
    phone?: string;
    email?: string;
    social?: Record<string, string | undefined>;
  };
  tenantId?: string;
  onBehavior?: BehaviorDispatcher;
}

export function PublicLayout({
  children,
  navigation,
  siteConfig,
  onBehavior,
}: PublicLayoutProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navItems = navigation.items;

  const handleNavClick = (item: NavItem) => {
    setMobileMenuOpen(false);
    if (!onBehavior) return;

    if (item.type === 'route' && item.route) {
      const behavior: BehaviorContract = { type: 'route-navigate', route: item.route };
      onBehavior(behavior);
    } else if (item.type === 'external' && item.href) {
      const behavior: BehaviorContract = { type: 'external-link', href: item.href, target: '_blank' };
      onBehavior(behavior);
    }
  };

  return (
    <>
      {/* Header */}
      <header className="sticky top-0 z-50 border-b bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 md:h-20 md:px-8">
          {/* Logo */}
          <a href="/" aria-label={siteConfig.name}>
            <img
              src={siteConfig.logo}
              alt={siteConfig.name}
              className="h-10 w-auto md:h-14"
            />
          </a>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-6" aria-label="Main navigation">
            {navItems.map((item) => (
              <button
                key={item.route ?? item.href ?? item.label}
                type="button"
                onClick={() => handleNavClick(item)}
                className="text-sm font-medium text-gray-700 transition-colors hover:text-green-700"
              >
                {item.label}
              </button>
            ))}
          </nav>

          {/* Mobile Hamburger */}
          <button
            type="button"
            className="md:hidden p-2 rounded-md text-gray-700 hover:bg-gray-100"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileMenuOpen}
          >
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Menu */}
        {mobileMenuOpen && (
          <nav className="md:hidden border-t bg-white px-4 py-4" aria-label="Mobile navigation">
            <ul className="space-y-2">
              {navItems.map((item) => (
                <li key={item.route ?? item.href ?? item.label}>
                  <button
                    type="button"
                    onClick={() => handleNavClick(item)}
                    className="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-700 hover:bg-gray-100 hover:text-green-700"
                  >
                    {item.label}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </header>

      {/* Main Content */}
      <main>{children}</main>

      {/* Footer */}
      <footer className="border-t bg-gray-900 text-white py-10">
        <div className="mx-auto max-w-6xl px-4 md:px-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Brand */}
            <div className="flex flex-col items-center md:items-start gap-3">
              {siteConfig.logoWhite && (
                <img
                  src={siteConfig.logoWhite}
                  alt={siteConfig.name}
                  className="h-16 w-auto"
                />
              )}
              <p className="text-sm text-gray-400">{siteConfig.name}</p>
            </div>

            {/* Contact */}
            <div className="flex flex-col items-center md:items-start gap-2 text-sm text-gray-300">
              {siteConfig.email && (
                <a href={`mailto:${siteConfig.email}`} className="hover:text-white">
                  {siteConfig.email}
                </a>
              )}
              {siteConfig.phone && (
                <a href={`tel:${siteConfig.phone}`} className="hover:text-white">
                  {siteConfig.phone}
                </a>
              )}
            </div>

            {/* Social Links */}
            <div className="flex items-center justify-center md:justify-end gap-4">
              {siteConfig.social &&
                Object.entries(siteConfig.social).map(([platform, url]) =>
                  url ? (
                    <a
                      key={platform}
                      href={url}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={platform}
                      className="text-gray-400 hover:text-white transition-colors"
                    >
                      <span className="capitalize text-sm">{platform}</span>
                    </a>
                  ) : null,
                )}
            </div>
          </div>

          {/* Copyright */}
          <div className="mt-8 pt-6 border-t border-gray-800 text-center text-xs text-gray-500">
            © {new Date().getFullYear()} {siteConfig.name}. All rights reserved.
          </div>
        </div>
      </footer>
    </>
  );
}
