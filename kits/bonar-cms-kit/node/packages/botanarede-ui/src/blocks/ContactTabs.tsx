/**
 * ContactTabs — horizontal tab list with content panels.
 *
 * All content comes from props (no hardcoded strings).
 * Tab switch dispatches onTabChange callback.
 */

'use client';

import { useState, type ReactNode } from 'react';
import type { SectionComponentProps } from '../types';

export interface TabDefinition {
  id: string;
  label: string;
  content: ReactNode;
}

interface ContactTabsProps extends SectionComponentProps {
  tabs?: TabDefinition[];
  defaultTab?: string;
  onTabChange?: (tabId: string) => void;
}

export function ContactTabs({
  tabs = [],
  defaultTab,
  onTabChange,
}: ContactTabsProps) {
  const [activeTab, setActiveTab] = useState(defaultTab ?? tabs[0]?.id ?? '');

  if (tabs.length === 0) {
    return null;
  }

  const handleTabChange = (tabId: string) => {
    setActiveTab(tabId);
    onTabChange?.(tabId);
  };

  const activePanel = tabs.find((t) => t.id === activeTab);

  return (
    <section className="py-8 px-4 md:px-8">
      {/* Tab List */}
      <div
        className="flex border-b overflow-x-auto"
        role="tablist"
        aria-label="Contact sections"
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            onClick={() => handleTabChange(tab.id)}
            className={`px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors border-b-2 -mb-px ${
              activeTab === tab.id
                ? 'border-green-700 text-green-700 font-bold'
                : 'border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Panel */}
      {activePanel && (
        <div
          role="tabpanel"
          id={`panel-${activePanel.id}`}
          aria-labelledby={`tab-${activePanel.id}`}
          className="py-6"
        >
          {activePanel.content}
        </div>
      )}
    </section>
  );
}
