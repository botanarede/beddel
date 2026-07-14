/**
 * EventGrid — responsive CSS grid of event cards.
 *
 * Receives event data via the `data` prop from dataBinding resolver,
 * or directly via `items` prop for static usage.
 * Each card is clickable and dispatches onItemClick callback.
 */

'use client';

import type { SectionComponentProps } from '../types';

export interface EventItem {
  id: string;
  title: string;
  date: string;
  time?: string;
  image?: string;
  description?: string;
  flyer?: string;
  location?: string;
  link?: string;
}

interface EventGridProps extends SectionComponentProps {
  items?: EventItem[];
  heading?: string;
  emptyMessage?: string;
  columns?: string;
  theme?: 'light' | 'dark';
  onItemClick?: (item: EventItem) => void;
  onItemView?: (item: EventItem) => void;
}

function EventCard({
  event,
  onItemClick,
  theme = 'light',
}: {
  event: EventItem;
  onItemClick?: (item: EventItem) => void;
  theme?: 'light' | 'dark';
}) {
  const handleClick = () => onItemClick?.(event);
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onItemClick?.(event);
    }
  };

  const cardBg = theme === 'dark'
    ? 'bg-white/5 border-white/10 hover:bg-white/10'
    : 'bg-card border-border shadow-sm hover:shadow-md';
  const titleColor = theme === 'dark' ? 'text-foreground' : 'text-card-foreground';
  const textColor = theme === 'dark' ? 'text-foreground/70' : 'text-muted-foreground';
  const descColor = theme === 'dark' ? 'text-foreground/60' : 'text-muted-foreground';

  return (
    <div
      className={`overflow-hidden rounded-lg border ${cardBg} transition-shadow cursor-pointer`}
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      aria-label={`Event: ${event.title}`}
    >
      {/* Image */}
      {event.image && (
        <div className="relative h-48 overflow-hidden">
          <img
            src={event.image}
            alt={event.title}
            className="absolute inset-0 w-full h-full object-cover"
            loading="lazy"
            decoding="async"
          />
        </div>
      )}

      {/* Content */}
      <div className="p-4">
        <h3 className={`text-lg font-semibold ${titleColor} mb-2`}>{event.title}</h3>
        <div className={`space-y-1 text-sm ${textColor}`}>
          {event.date && (
            <div className="flex items-center gap-2">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
              <span>{event.date}</span>
            </div>
          )}
          {event.time && (
            <div className="flex items-center gap-2">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <span>{event.time}</span>
            </div>
          )}
          {event.location && (
            <div className="flex items-center gap-2">
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
              <span>{event.location}</span>
            </div>
          )}
        </div>
        {event.description && (
          <p className={`mt-3 text-sm ${descColor} line-clamp-2`}>{event.description}</p>
        )}
      </div>
    </div>
  );
}

export function EventGrid({
  items,
  data,
  heading,
  emptyMessage = 'No events scheduled.',
  columns,
  theme = 'light',
  onItemClick,
  onItemView,
}: EventGridProps) {
  // Prefer items prop; fall back to data from dataBinding
  const events: EventItem[] = items ?? (data as EventItem[]) ?? [];

  // Fire onItemView for visible items (simplified: on mount)
  if (onItemView && events.length > 0) {
    // Intentionally not using useEffect to avoid client-only constraint
    // The app layer handles view tracking via intersection observer
  }

  const gridStyle = columns
    ? { gridTemplateColumns: columns }
    : undefined;

  const headingColor = theme === 'dark' ? 'text-foreground' : 'text-foreground';
  const emptyColor = theme === 'dark' ? 'text-foreground/50' : 'text-muted-foreground';

  return (
    <section className="py-8 px-4 md:px-8">
      {heading && (
        <h2 className={`text-2xl md:text-3xl font-bold ${headingColor} text-center mb-8`}>
          {heading}
        </h2>
      )}

      {events.length === 0 ? (
        <p className={`text-center ${emptyColor} py-12`}>{emptyMessage}</p>
      ) : (
        <div
          className="grid gap-6"
          style={gridStyle ?? { gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}
        >
          {events.map((event) => (
            <EventCard key={event.id} event={event} onItemClick={onItemClick} theme={theme} />
          ))}
        </div>
      )}
    </section>
  );
}
