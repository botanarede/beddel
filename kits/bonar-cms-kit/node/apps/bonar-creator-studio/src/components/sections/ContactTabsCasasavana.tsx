'use client'

import { useState } from 'react'
import { ContactTabs } from '@botanarede/ui-react'
import { useDynamicTable } from '@botanarede/bonarjs-sdk-alpha/react'
import type { SiteConfig } from '@/config/site-types'

interface TabDefinition {
  id: string
  label: string
  content: React.ReactNode
}

// ─── Tab Content Components ────────────────────────────────────────────────────

function ContactInfoTab({ siteConfig }: { siteConfig: SiteConfig }) {
  const { setItem } = useDynamicTable()
  const [isLoading, setIsLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !email || !message) return

    setIsLoading(true)
    try {
      const createdAt = Date.now()
      const messageData = {
        subject: 'Contato - Casa Savana',
        text: `Nome: ${name}\nEmail: ${email}\nMensagem: ${message}`,
        html: `Nome: ${name}<br/>Email: ${email}<br/>Mensagem: ${message}`,
      }
      await setItem(
        'emails',
        {
          to: ['demo@example.com'],
          from: 'Casa Savana <demo@example.com>',
          message: messageData,
          createdAt,
          type: 'simple_contact',
        },
        undefined,
        'EMAIL'
      )

      if (typeof window !== 'undefined') {
        ;(window as any).dataLayer = (window as any).dataLayer || []
        ;(window as any).dataLayer.push({
          event: 'form_submission',
          form_type: 'simple_contact',
          form_name: 'Contato Geral',
          lead_value: 50,
        })
      }

      setSent(true)
      setName('')
      setEmail('')
      setMessage('')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="grid grid-cols-1 gap-10 md:grid-cols-2">
        {/* Form */}
        <div className="order-2 md:order-1">
          <h2 className="mb-6 text-2xl font-bold text-green-800">Fale Conosco</h2>
          {sent ? (
            <div className="rounded-lg bg-green-50 p-6 text-center">
              <p className="text-lg font-medium text-green-800">Mensagem enviada!</p>
              <p className="mt-2 text-sm text-gray-600">Entraremos em contato em breve.</p>
              <button
                type="button"
                onClick={() => setSent(false)}
                className="mt-4 text-sm font-medium text-green-700 underline"
              >
                Enviar outra mensagem
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="contact-name" className="block text-sm font-medium text-gray-700">
                  Nome
                </label>
                <input
                  id="contact-name"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-green-500"
                />
              </div>
              <div>
                <label htmlFor="contact-email" className="block text-sm font-medium text-gray-700">
                  Email
                </label>
                <input
                  id="contact-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-green-500"
                />
              </div>
              <div>
                <label htmlFor="contact-message" className="block text-sm font-medium text-gray-700">
                  Mensagem
                </label>
                <textarea
                  id="contact-message"
                  required
                  rows={4}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-green-500"
                />
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full rounded-md bg-[#0a700a] px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#085f08] disabled:opacity-50 md:w-auto"
              >
                {isLoading ? 'Enviando...' : 'Enviar Mensagem'}
              </button>
            </form>
          )}
        </div>

        {/* Contact info sidebar */}
        <div className="order-1 space-y-8 md:order-2">
          <div>
            <h3 className="mb-4 text-xl font-semibold text-green-800">Informações de Contato</h3>
            <div className="space-y-4">
              <div className="flex items-start gap-3">
                <div className="rounded-full bg-green-100 p-2">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-green-700" aria-hidden="true">
                    <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                    <polyline points="22,6 12,13 2,6" />
                  </svg>
                </div>
                <div>
                  <p className="font-medium">Email</p>
                  <a href={`mailto:${siteConfig.email}`} className="text-gray-600 hover:text-green-700">
                    {siteConfig.email}
                  </a>
                </div>
              </div>
              {siteConfig.phone && (
                <div className="flex items-start gap-3">
                  <div className="rounded-full bg-green-100 p-2">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-green-700" aria-hidden="true">
                      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
                    </svg>
                  </div>
                  <div>
                    <p className="font-medium">Telefone / WhatsApp</p>
                    <a href={`tel:${siteConfig.phone}`} className="text-gray-600 hover:text-green-700">
                      {siteConfig.phone}
                    </a>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div>
            <h3 className="mb-4 text-xl font-semibold text-green-800">Horário de Funcionamento</h3>
            <div className="rounded-xl border border-gray-100 bg-green-50 p-5 shadow-sm">
              <ul className="space-y-2 text-sm text-gray-700">
                {siteConfig.openingHours.map((h, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="mt-1.5 h-2 w-2 rounded-full bg-green-700 shrink-0" />
                    <span>{h.description} — {h.opens} às {h.closes}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Static map */}
          <div>
            <h3 className="mb-4 text-xl font-semibold text-green-800">Localização</h3>
            <a
              href={`https://www.google.com/maps/search/?api=1&query=${siteConfig.address.googleMapsQuery}`}
              target="_blank"
              rel="noopener noreferrer"
              className="block overflow-hidden rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow"
            >
              <img
                src="/images/static-map-savana.webp"
                alt={`Mapa - ${siteConfig.address.street}, ${siteConfig.address.city}`}
                className="w-full h-48 object-cover"
                loading="lazy"
              />
            </a>
            <p className="mt-2 text-sm text-gray-600">
              {siteConfig.address.street}, {siteConfig.address.city} - {siteConfig.address.state}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

function BirthdayTab() {
  const instagramContactUrl = 'https://ig.me/m/example'

  return (
    <div className="max-w-4xl mx-auto text-center">
      <h2 className="mb-4 text-2xl font-bold text-green-800">Lista de Aniversário</h2>
      <p className="mb-8 text-gray-600">
        Comemore seu aniversário na Casa Savana! Entre em contato pelo Instagram para fazer sua reserva.
      </p>
      <a
        href={instagramContactUrl}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-3 rounded-full bg-gradient-to-r from-[#f09433] via-[#e6683c] to-[#dc2743] px-6 py-3 font-semibold text-white shadow-lg transition-transform hover:scale-[1.02]"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
          <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
          <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
        </svg>
        Solicitar pelo Instagram
      </a>
      <div className="mt-8 rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
        <p>Você receberá um link do Sympla com desconto para compartilhar com seus convidados.</p>
      </div>
    </div>
  )
}

function CorporateEventsTab() {
  const { setItem } = useDynamicTable()
  const [isLoading, setIsLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [company, setCompany] = useState('')
  const [contact, setContact] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [eventType, setEventType] = useState('')
  const [guests, setGuests] = useState('')
  const [message, setMessage] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    try {
      const createdAt = Date.now()
      const text = `Empresa: ${company}\nContato: ${contact}\nEmail: ${email}\nTelefone: ${phone}\nTipo: ${eventType}\nConvidados: ${guests}\nMensagem: ${message}`
      await setItem(
        'emails',
        {
          to: ['demo@example.com'],
          from: 'Casa Savana <demo@example.com>',
          message: {
            subject: 'Evento Corporativo - Casa Savana',
            text,
            html: text.replace(/\n/g, '<br/>'),
          },
          createdAt,
          type: 'corporate_event',
        },
        undefined,
        'EMAIL'
      )

      if (typeof window !== 'undefined') {
        ;(window as any).dataLayer = (window as any).dataLayer || []
        ;(window as any).dataLayer.push({
          event: 'form_submission',
          form_type: 'corporate_event',
          form_name: 'Eventos Corporativos',
          lead_value: 5000,
        })
      }

      setSent(true)
    } finally {
      setIsLoading(false)
    }
  }

  const differentials = [
    { title: 'Capacidade Flexível', description: 'Espaços adaptáveis para grupos de diferentes tamanhos' },
    { title: 'Horários Flexíveis', description: 'Disponibilidade em diversos horários, inclusive fora do horário comercial' },
    { title: 'Serviços Adicionais', description: 'Buffet personalizado e estacionamento em frente' },
  ]

  return (
    <div className="max-w-4xl mx-auto">
      <div className="mb-8 text-center">
        <h2 className="mb-4 text-2xl font-bold text-green-800">Eventos Corporativos</h2>
        <p className="text-gray-600">
          Planeje seu evento corporativo conosco. Oferecemos estrutura completa para reuniões,
          confraternizações e eventos empresariais.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-10 md:grid-cols-2">
        {/* Form */}
        <div>
          {sent ? (
            <div className="rounded-lg bg-green-50 p-6 text-center">
              <p className="text-lg font-medium text-green-800">Solicitação enviada!</p>
              <p className="mt-2 text-sm text-gray-600">Nossa equipe entrará em contato em até 24 horas.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="corp-company" className="block text-sm font-medium text-gray-700">Empresa</label>
                <input id="corp-company" type="text" required value={company} onChange={(e) => setCompany(e.target.value)} className="mt-1 block w-full rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-green-500" />
              </div>
              <div>
                <label htmlFor="corp-contact" className="block text-sm font-medium text-gray-700">Nome do contato</label>
                <input id="corp-contact" type="text" required value={contact} onChange={(e) => setContact(e.target.value)} className="mt-1 block w-full rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-green-500" />
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="corp-email" className="block text-sm font-medium text-gray-700">Email</label>
                  <input id="corp-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 block w-full rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-green-500" />
                </div>
                <div>
                  <label htmlFor="corp-phone" className="block text-sm font-medium text-gray-700">Telefone</label>
                  <input id="corp-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} className="mt-1 block w-full rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-green-500" />
                </div>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <label htmlFor="corp-type" className="block text-sm font-medium text-gray-700">Tipo de evento</label>
                  <select id="corp-type" value={eventType} onChange={(e) => setEventType(e.target.value)} className="mt-1 block w-full rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-green-500">
                    <option value="">Selecione</option>
                    <option value="confraternizacao">Confraternização</option>
                    <option value="reuniao">Reunião</option>
                    <option value="workshop">Workshop</option>
                    <option value="lancamento">Lançamento de produto</option>
                    <option value="outro">Outro</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="corp-guests" className="block text-sm font-medium text-gray-700">Número de convidados</label>
                  <input id="corp-guests" type="number" min="1" value={guests} onChange={(e) => setGuests(e.target.value)} className="mt-1 block w-full rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-green-500" />
                </div>
              </div>
              <div>
                <label htmlFor="corp-message" className="block text-sm font-medium text-gray-700">Detalhes do evento</label>
                <textarea id="corp-message" rows={3} value={message} onChange={(e) => setMessage(e.target.value)} className="mt-1 block w-full rounded-md border border-gray-300 px-4 py-2 text-sm shadow-sm focus:border-green-500 focus:ring-green-500" />
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full rounded-md bg-[#0a700a] px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#085f08] disabled:opacity-50"
              >
                {isLoading ? 'Enviando...' : 'Solicitar Orçamento'}
              </button>
            </form>
          )}
        </div>

        {/* Differentials */}
        <div className="space-y-6">
          <h3 className="text-lg font-semibold text-green-800">Diferenciais</h3>
          <div className="space-y-4">
            {differentials.map((d, i) => (
              <div key={i} className="rounded-lg border border-gray-100 bg-white p-4 shadow-sm">
                <h4 className="font-medium text-gray-900">{d.title}</h4>
                <p className="mt-1 text-sm text-gray-600">{d.description}</p>
              </div>
            ))}
          </div>
          <div>
            <h3 className="mb-3 text-lg font-semibold text-green-800">Processo de Reserva</h3>
            <ol className="space-y-2 text-sm text-gray-700">
              <li className="flex items-start gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-100 text-xs font-bold text-green-800">1</span>
                Preencha o formulário com os detalhes do evento
              </li>
              <li className="flex items-start gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-100 text-xs font-bold text-green-800">2</span>
                Nossa equipe entrará em contato em até 24 horas
              </li>
              <li className="flex items-start gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-100 text-xs font-bold text-green-800">3</span>
                Agendamento de visita técnica (se necessário)
              </li>
              <li className="flex items-start gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-100 text-xs font-bold text-green-800">4</span>
                Apresentação da proposta personalizada
              </li>
              <li className="flex items-start gap-2">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-100 text-xs font-bold text-green-800">5</span>
                Confirmação da reserva e pagamento do sinal
              </li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  )
}

function FAQTab({ siteConfig }: { siteConfig: SiteConfig }) {
  const faqItems = siteConfig.faq

  return (
    <div className="max-w-3xl mx-auto">
      <h2 className="mb-8 text-2xl font-bold text-center text-green-800">Dúvidas Frequentes</h2>
      <div className="space-y-4">
        {faqItems.map((item, index) => (
          <details
            key={index}
            className="group rounded-lg border border-gray-200 bg-white"
          >
            <summary className="flex cursor-pointer items-center justify-between p-5 text-left font-medium text-gray-900 hover:bg-gray-50">
              <span>{item.question}</span>
              <svg
                className="h-5 w-5 shrink-0 text-gray-500 transition-transform group-open:rotate-180"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </summary>
            <div className="border-t px-5 py-4 text-sm text-gray-600">
              {item.answer}
            </div>
          </details>
        ))}
      </div>
    </div>
  )
}

// ─── Main Connected Component ──────────────────────────────────────────────────

interface ContactTabsCasasavanaProps {
  defaultTab?: string
  siteConfig?: SiteConfig
  [key: string]: unknown
}

/**
 * Connected ContactTabs for casasavana tenant.
 * Provides 4 tabs with tenant-specific content and SDK integration.
 */
export function ContactTabsCasasavana({ defaultTab = 'contact', siteConfig, ...rest }: ContactTabsCasasavanaProps) {
  if (!siteConfig) return null

  const tabs: TabDefinition[] = [
    {
      id: 'contact',
      label: 'Contato Geral',
      content: <ContactInfoTab siteConfig={siteConfig} />,
    },
    {
      id: 'birthday',
      label: 'Aniversário',
      content: <BirthdayTab />,
    },
    {
      id: 'corporate',
      label: 'Eventos Corporativos',
      content: <CorporateEventsTab />,
    },
    {
      id: 'faq',
      label: 'Dúvidas Frequentes',
      content: <FAQTab siteConfig={siteConfig} />,
    },
  ]

  return <ContactTabs tabs={tabs} defaultTab={defaultTab} />
}
