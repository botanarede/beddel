export function CTASection() {
  return (
    <section id="contato" className="py-24">
      <div className="mx-auto max-w-2xl px-6 text-center">
        <h2 className="font-heading text-3xl font-bold md:text-4xl">
          Vamos conversar.
        </h2>
        <p className="mt-4 text-muted-foreground">
          Se você atua no mercado de bem-estar e quer entender melhor quem é seu público, fale com a gente.
        </p>
        <a
          href="mailto:demo@example.com?subject=Contact"
          className="mt-8 inline-block rounded-full bg-[var(--brand-primary)] px-8 py-3 text-sm font-semibold text-white transition hover:opacity-90"
        >
          demo@example.com
        </a>
      </div>
    </section>
  )
}
