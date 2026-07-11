const verticals = [
  'Yoga & Meditação',
  'Fitness & Treino Funcional',
  'Nutrição & Alimentação Consciente',
  'Saúde Mental & Mindfulness',
  'Terapias Integrativas',
]

export function ServicesSection() {
  return (
    <section id="segmentos" className="border-y bg-muted/30 py-24">
      <div className="mx-auto max-w-3xl px-6">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-[var(--brand-primary)]">
          Verticais
        </p>
        <h2 className="mt-3 font-heading text-3xl font-bold md:text-4xl">
          Cinco mercados. Uma visão.
        </h2>
        <p className="mt-4 text-muted-foreground">
          Atuamos exclusivamente no ecossistema de bem-estar brasileiro.
        </p>
        <div className="mt-12 space-y-4">
          {verticals.map((v, i) => (
            <div key={v} className="flex items-center gap-4 border-b pb-4 last:border-0">
              <span className="text-xs font-medium text-[var(--brand-primary)]">0{i + 1}</span>
              <span className="text-base">{v}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
