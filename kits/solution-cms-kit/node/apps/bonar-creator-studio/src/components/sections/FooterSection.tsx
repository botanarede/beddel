export function FooterSection() {
  return (
    <footer className="border-t py-8">
      <div className="mx-auto flex max-w-4xl flex-col items-center gap-3 px-6 text-xs text-muted-foreground md:flex-row md:justify-between">
        <span>© {new Date().getFullYear()} Your Brand</span>
        <div className="flex gap-4">
          <a href="/radar" className="hover:text-foreground">
            Radar Prana
          </a>
          <a href="/politica-de-privacidade" className="hover:text-foreground">
            Política de Privacidade
          </a>
          <a href="mailto:demo@example.com" className="hover:text-foreground">
            demo@example.com
          </a>
        </div>
      </div>
    </footer>
  )
}
