'use client'

import { useState, useId } from 'react'
import type { SectionComponentProps } from '../types'

interface FormField {
  name: string
  label: string
  type: 'text' | 'email' | 'tel' | 'textarea'
  required?: boolean
  placeholder?: string
}

interface ContactSectionProps extends SectionComponentProps {
  heading?: string
  email?: string
  whatsapp?: string
  whatsappDisplay?: string
  location?: string
  fields?: FormField[]
  submitLabel?: string
  onSubmit?: (values: Record<string, string>) => Promise<void>
  submittingLabel?: string
}

/**
 * ContactSection — Two-column layout with contact info cards and a dynamic form.
 */
export function ContactSection({
  heading = 'Contato',
  email,
  whatsapp,
  whatsappDisplay,
  location,
  fields = [],
  submitLabel = 'Enviar Mensagem',
  onSubmit,
  submittingLabel = 'Enviando...',
}: ContactSectionProps) {
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const formId = useId()

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setErrorMsg(null)
    const form = e.currentTarget
    const data = new FormData(form)

    // Honeypot check
    if (data.get('company')) {
      form.reset()
      return
    }

    const values: Record<string, string> = {}
    for (const field of fields) {
      values[field.name] = (data.get(field.name) as string) ?? ''
    }

    if (onSubmit) {
      setSubmitting(true)
      try {
        await onSubmit(values)
        setSubmitted(true)
        form.reset()
        setTimeout(() => setSubmitted(false), 4000)
      } catch {
        setErrorMsg('Erro ao enviar mensagem. Tente novamente.')
      } finally {
        setSubmitting(false)
      }
    } else {
      setSubmitted(true)
      form.reset()
      setTimeout(() => setSubmitted(false), 4000)
    }
  }

  const whatsappDigits = whatsapp?.replace(/\D/g, '') ?? ''

  return (
    <section className="w-full py-16 px-4 md:px-8">
      {heading && (
        <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">
          {heading}
        </h2>
      )}

      <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-10">
        {/* Left column — info cards */}
        <div className="flex flex-col gap-4">
          {email && (
            <div className="rounded-xl bg-white/5 border border-white/10 p-5 flex items-center gap-4">
              <EnvelopeIcon />
              <a
                href={`mailto:${email}`}
                className="text-foreground hover:underline break-all"
              >
                {email}
              </a>
            </div>
          )}

          {whatsapp && (
            <div className="rounded-xl bg-white/5 border border-white/10 p-5 flex items-center gap-4">
              <PhoneIcon />
              <a
                href={`https://wa.me/${whatsappDigits}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-foreground hover:underline"
              >
                {whatsappDisplay || whatsapp}
              </a>
            </div>
          )}

          {location && (
            <div className="rounded-xl bg-white/5 border border-white/10 p-5 flex items-center gap-4">
              <MapPinIcon />
              <span className="text-foreground">{location}</span>
            </div>
          )}
        </div>

        {/* Right column — form */}
        <form
          role="form"
          aria-label="Formulário de contato"
          onSubmit={handleSubmit}
          className="flex flex-col gap-4"
        >
          {/* Honeypot */}
          <div className="hidden" aria-hidden="true">
            <input type="text" name="company" tabIndex={-1} autoComplete="off" />
          </div>

          {fields.map((field) => {
            const fieldId = `${formId}-${field.name}`
            return (
              <div key={field.name} className="flex flex-col gap-1">
                <label htmlFor={fieldId} className="text-sm font-medium text-foreground/70">
                  {field.label}
                  {field.required && <span className="text-red-400 ml-1">*</span>}
                </label>
                {field.type === 'textarea' ? (
                  <textarea
                    id={fieldId}
                    name={field.name}
                    required={field.required}
                    aria-required={field.required}
                    placeholder={field.placeholder}
                    rows={4}
                    className="bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-foreground placeholder:text-foreground/40 focus:border-[color:var(--brand-primary)] focus:outline-none resize-y"
                  />
                ) : (
                  <input
                    id={fieldId}
                    type={field.type}
                    name={field.name}
                    required={field.required}
                    aria-required={field.required}
                    placeholder={field.placeholder}
                    className="bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-foreground placeholder:text-foreground/40 focus:border-[color:var(--brand-primary)] focus:outline-none"
                  />
                )}
              </div>
            )
          })}

          <button
            type="submit"
            disabled={submitting}
            className="bg-[color:var(--brand-primary)] hover:opacity-90 text-white font-semibold rounded-lg px-6 py-3 mt-2 transition-opacity disabled:opacity-60"
          >
            {submitting ? submittingLabel : submitLabel}
          </button>

          {submitted && (
            <p className="text-green-400 text-sm font-medium mt-2" role="status">
              Mensagem enviada!
            </p>
          )}

          {errorMsg && (
            <p className="text-red-400 text-sm font-medium mt-2" role="alert">
              {errorMsg}
            </p>
          )}
        </form>
      </div>
    </section>
  )
}

/* ─── Inline SVG Icons ─── */

function EnvelopeIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="w-5 h-5 text-foreground/60 shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M21.75 6.75v10.5a2.25 2.25 0 0 1-2.25 2.25h-15a2.25 2.25 0 0 1-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0 0 19.5 4.5h-15a2.25 2.25 0 0 0-2.25 2.25m19.5 0v.243a2.25 2.25 0 0 1-1.07 1.916l-7.5 4.615a2.25 2.25 0 0 1-2.36 0L3.32 8.91a2.25 2.25 0 0 1-1.07-1.916V6.75"
      />
    </svg>
  )
}

function PhoneIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="w-5 h-5 text-foreground/60 shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 0 0 2.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 0 1-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 0 0-1.091-.852H4.5A2.25 2.25 0 0 0 2.25 4.5v2.25Z"
      />
    </svg>
  )
}

function MapPinIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      className="w-5 h-5 text-foreground/60 shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z"
      />
    </svg>
  )
}
