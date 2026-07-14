'use client';

import { useState } from 'react';
import type { SectionComponentProps } from '../types';

export interface MemberItem {
  name: string;
  instrument: string;
  photo: string;
  instagram?: string;
}

interface MembersGridProps extends SectionComponentProps {
  members?: MemberItem[];
  heading?: string;
}

function MemberCard({ member }: { member: MemberItem }) {
  const [flipped, setFlipped] = useState(false);

  return (
    <div
      className="group perspective-1000 cursor-pointer"
      onClick={() => setFlipped(!flipped)}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setFlipped(!flipped); } }}
      tabIndex={0}
      role="button"
      aria-label={`${member.name} - ${member.instrument}`}
    >
      <div className={`relative w-full aspect-[3/4] transition-transform duration-500 transform-style-3d ${flipped ? 'rotate-y-180' : ''}`}>
        {/* Front — photo */}
        <div className="absolute inset-0 backface-hidden rounded-xl overflow-hidden">
          <img
            src={member.photo}
            alt={member.name}
            className="w-full h-full object-cover"
            loading="lazy"
            decoding="async"
          />
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/70 to-transparent p-4">
            <p className="text-white font-semibold text-sm">{member.name}</p>
          </div>
        </div>
        {/* Back — info */}
        <div className="absolute inset-0 backface-hidden rotate-y-180 rounded-xl bg-[color:var(--brand-primary)] flex flex-col items-center justify-center p-6 text-white text-center">
          <h3 className="text-xl font-bold mb-2">{member.name}</h3>
          <p className="text-white/80 mb-4">{member.instrument}</p>
          {member.instagram && (
            <a
              href={`https://instagram.com/${member.instagram}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/20 hover:bg-white/30 transition-colors text-sm"
              onClick={(e) => e.stopPropagation()}
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/>
              </svg>
              @{member.instagram}
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export function MembersGrid({ members = [], heading }: MembersGridProps) {
  if (members.length === 0) return null;

  return (
    <section className="py-16 px-4 md:px-8">
      {heading && (
        <h2 className="text-2xl md:text-3xl font-bold text-foreground text-center mb-10">
          {heading}
        </h2>
      )}
      <div className="mx-auto max-w-6xl grid grid-cols-2 md:grid-cols-3 gap-6">
        {members.map((member) => (
          <MemberCard key={member.name} member={member} />
        ))}
      </div>
    </section>
  );
}
