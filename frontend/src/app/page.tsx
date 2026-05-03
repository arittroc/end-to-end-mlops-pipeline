'use client'

import { useState, useEffect, useRef } from 'react'
import {
  motion,
  AnimatePresence,
  useMotionValue,
  useSpring,
} from 'framer-motion'
import { Home, Maximize2, Layers, CalendarDays, Sparkles, AlertCircle, MapPin } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Design tokens from UI UX PRO MAX (Modern Dark Cinema) ────────────────
const EXPO_OUT = [0.16, 1, 0.3, 1] as const
const SPRING_CARD = { type: 'spring', damping: 22, stiffness: 90 } as const
const SPRING_RESULT = { type: 'spring', damping: 18, stiffness: 70 } as const

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8085/api/v1/predict'

// ── Types ─────────────────────────────────────────────────────────────────
interface FormState {
  Location: string
  OverallQual: string
  GrLivArea: string
  TotalBsmtSF: string
  YearBuilt: string
}

interface PredictResponse {
  predicted_price_usd: number
  predicted_price_formatted: string
  model_uri: string | null
}

// ── Ambient orbs (UI UX PRO MAX §4 — glassmorphism animated blobs) ────────
function AmbientOrbs() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden" aria-hidden>
      {/* Primary indigo orb — top-left */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: 700,
          height: 700,
          top: '-20%',
          left: '-15%',
          background:
            'radial-gradient(circle, rgba(99,102,241,0.18) 0%, rgba(79,70,229,0.10) 40%, transparent 70%)',
          filter: 'blur(80px)',
        }}
        animate={{ x: [-40, 50], y: [-30, 45] }}
        transition={{
          duration: 14,
          repeat: Infinity,
          repeatType: 'mirror',
          ease: 'easeInOut',
        }}
      />
      {/* Deep purple orb — bottom-right */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: 600,
          height: 600,
          bottom: '-18%',
          right: '-12%',
          background:
            'radial-gradient(circle, rgba(124,58,237,0.16) 0%, rgba(109,40,217,0.08) 45%, transparent 70%)',
          filter: 'blur(90px)',
        }}
        animate={{ x: [30, -50], y: [20, -40] }}
        transition={{
          duration: 18,
          repeat: Infinity,
          repeatType: 'mirror',
          ease: 'easeInOut',
          delay: 2,
        }}
      />
      {/* Accent indigo orb — center-right */}
      <motion.div
        className="absolute rounded-full"
        style={{
          width: 400,
          height: 400,
          top: '40%',
          right: '5%',
          background:
            'radial-gradient(circle, rgba(56,82,230,0.12) 0%, rgba(67,56,202,0.06) 50%, transparent 70%)',
          filter: 'blur(70px)',
        }}
        animate={{ x: [-20, 30], y: [-25, 35] }}
        transition={{
          duration: 22,
          repeat: Infinity,
          repeatType: 'mirror',
          ease: 'easeInOut',
          delay: 5,
        }}
      />
    </div>
  )
}

// ── Field icon map ────────────────────────────────────────────────────────
const FIELD_ICONS = {
  OverallQual: Sparkles,
  GrLivArea: Maximize2,
  TotalBsmtSF: Layers,
  YearBuilt: CalendarDays,
} as const

type NumericFieldKey = Exclude<keyof FormState, 'Location'>

// ── Single form field ─────────────────────────────────────────────────────
interface FieldProps {
  id: NumericFieldKey
  label: string
  placeholder: string
  hint: string
  min: number
  max: number
  value: string
  onChange: (id: keyof FormState, v: string) => void
  index: number
  error?: string
}

function FormField({
  id, label, placeholder, hint, min, max, value, onChange, index, error,
}: FieldProps) {
  const Icon = FIELD_ICONS[id]

  return (
    <motion.div
      initial={{ opacity: 0, y: 22 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ ...SPRING_CARD, delay: 0.35 + index * 0.05 }}
      className="flex flex-col gap-2"
    >
      <label htmlFor={id} className="field-label flex items-center gap-2">
        <Icon size={11} className="text-indigo-400" aria-hidden />
        {label}
      </label>

      <input
        id={id}
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(id, e.target.value)}
        aria-describedby={`${id}-hint`}
        aria-invalid={!!error}
        className={cn(
          'glass-input',
          error && 'border-red-500/50 focus:border-red-500/70'
        )}
      />

      <AnimatePresence mode="wait">
        {error ? (
          <motion.p
            key="error"
            id={`${id}-hint`}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.2 }}
            className="flex items-center gap-1.5 text-[11px] text-red-400 font-medium"
            role="alert"
          >
            <AlertCircle size={11} aria-hidden />
            {error}
          </motion.p>
        ) : (
          <motion.p
            key="hint"
            id={`${id}-hint`}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="text-[11px] tracking-wide"
            style={{ color: '#8a8f98' }}
          >
            {hint}
          </motion.p>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

// ── Loading ring ──────────────────────────────────────────────────────────
function LoadingRing() {
  return (
    <motion.div
      className="relative flex items-center justify-center"
      style={{ width: 72, height: 72 }}
      initial={{ opacity: 0, scale: 0.7 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.7 }}
      transition={{ duration: 0.25, ease: EXPO_OUT }}
    >
      {/* Outer glow */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background: 'radial-gradient(circle, rgba(99,102,241,0.35) 0%, transparent 70%)',
          filter: 'blur(12px)',
        }}
        animate={{ scale: [1, 1.25, 1], opacity: [0.5, 0.9, 0.5] }}
        transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
      />
      {/* Rotating conic ring */}
      <motion.div
        className="absolute inset-0 rounded-full"
        style={{
          background:
            'conic-gradient(from 0deg, transparent 0%, #6366f1 45%, #818cf8 55%, transparent 100%)',
        }}
        animate={{ rotate: 360 }}
        transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      />
      {/* Inner mask */}
      <div
        className="absolute rounded-full"
        style={{ inset: 5, background: '#050505' }}
      />
      {/* Center dot */}
      <motion.div
        className="relative w-2 h-2 rounded-full"
        style={{ background: '#818cf8' }}
        animate={{ scale: [1, 1.4, 1], opacity: [0.7, 1, 0.7] }}
        transition={{ duration: 1.2, repeat: Infinity, ease: 'easeInOut' }}
      />
    </motion.div>
  )
}

// ── Price counter hook ────────────────────────────────────────────────────
function usePriceCounter(targetPrice: number) {
  const raw = useMotionValue(0)
  const spring = useSpring(raw, { damping: 28, stiffness: 55 })
  const [display, setDisplay] = useState('$0')

  useEffect(() => {
    const unsub = spring.on('change', (v) => {
      setDisplay(
        new Intl.NumberFormat('en-US', {
          style: 'currency',
          currency: 'USD',
          maximumFractionDigits: 0,
        }).format(v)
      )
    })
    return unsub
  }, [spring])

  useEffect(() => {
    raw.set(targetPrice)
  }, [targetPrice, raw])

  return display
}

// ── Result display ────────────────────────────────────────────────────────
function PriceResult({ data }: { data: PredictResponse }) {
  const displayPrice = usePriceCounter(data.predicted_price_usd)

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9, y: 16 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95, y: 8 }}
      transition={SPRING_RESULT}
      className="relative mt-2 rounded-2xl overflow-hidden"
      style={{
        background: 'rgba(99,102,241,0.06)',
        border: '1px solid rgba(99,102,241,0.2)',
      }}
    >
      {/* Background glow */}
      <div
        className="glow-orb absolute inset-0 rounded-2xl pointer-events-none"
        style={{
          background:
            'radial-gradient(ellipse at 50% 0%, rgba(99,102,241,0.25) 0%, transparent 65%)',
        }}
        aria-hidden
      />

      <div className="relative px-6 py-6 text-center">
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.14em] mb-3"
          style={{ color: 'rgba(129,140,248,0.8)' }}
        >
          Predicted Market Value
        </p>

        <p
          className="text-4xl font-bold tracking-tight"
          style={{
            fontFamily: 'var(--font-cinzel)',
            color: '#ededef',
            textShadow: '0 0 40px rgba(99,102,241,0.6), 0 0 80px rgba(99,102,241,0.3)',
          }}
          aria-live="polite"
          aria-label={`Predicted price: ${displayPrice}`}
        >
          {displayPrice}
        </p>

        {data.model_uri && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.6 }}
            className="mt-3 text-[11px] tracking-wide"
            style={{ color: 'rgba(138,143,152,0.55)', fontFamily: 'monospace' }}
          >
            {data.model_uri.replace('models:/', '').replace('runs:/', 'run/')}
          </motion.p>
        )}
      </div>
    </motion.div>
  )
}

// ── Field definitions ─────────────────────────────────────────────────────
const FIELDS: Omit<FieldProps, 'value' | 'onChange' | 'index' | 'error'>[] = [
  {
    id: 'OverallQual',
    label: 'Overall Quality',
    placeholder: '7',
    hint: 'Material & finish quality · 1 (poor) → 10 (excellent)',
    min: 1,
    max: 10,
  },
  {
    id: 'GrLivArea',
    label: 'Ground Living Area',
    placeholder: '1500',
    hint: 'Above-grade living area in square feet',
    min: 100,
    max: 10000,
  },
  {
    id: 'TotalBsmtSF',
    label: 'Total Basement SF',
    placeholder: '856',
    hint: 'Total basement area in sq ft · 0 if none',
    min: 0,
    max: 6000,
  },
  {
    id: 'YearBuilt',
    label: 'Year Built',
    placeholder: '2003',
    hint: 'Original year of construction',
    min: 1800,
    max: new Date().getFullYear(),
  },
]

// ── Validation ────────────────────────────────────────────────────────────
function validate(form: FormState): Partial<Record<keyof FormState, string>> {
  const errors: Partial<Record<keyof FormState, string>> = {}

  if (!form.Location) errors.Location = 'Required'

  const qual = parseInt(form.OverallQual)
  if (!form.OverallQual) errors.OverallQual = 'Required'
  else if (isNaN(qual) || qual < 1 || qual > 10) errors.OverallQual = 'Must be 1–10'

  const area = parseInt(form.GrLivArea)
  if (!form.GrLivArea) errors.GrLivArea = 'Required'
  else if (isNaN(area) || area <= 0) errors.GrLivArea = 'Must be > 0 sq ft'

  if (form.TotalBsmtSF) {
    const bsmt = parseFloat(form.TotalBsmtSF)
    if (isNaN(bsmt) || bsmt < 0) errors.TotalBsmtSF = 'Must be ≥ 0'
  }

  if (form.YearBuilt) {
    const year = parseInt(form.YearBuilt)
    if (isNaN(year) || year < 1800 || year > new Date().getFullYear())
      errors.YearBuilt = `Must be 1800–${new Date().getFullYear()}`
  }

  return errors
}

// ── Main page ─────────────────────────────────────────────────────────────
export default function HomePage() {
  const [form, setForm] = useState<FormState>({
    Location: '',
    OverallQual: '',
    GrLivArea: '',
    TotalBsmtSF: '',
    YearBuilt: '',
  })
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({})
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PredictResponse | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  function handleChange(id: keyof FormState, v: string) {
    setForm((f) => ({ ...f, [id]: v }))
    if (errors[id]) setErrors((e) => ({ ...e, [id]: undefined }))
    if (apiError) setApiError(null)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const errs = validate(form)
    if (Object.keys(errs).length) {
      setErrors(errs)
      return
    }

    setLoading(true)
    setResult(null)
    setApiError(null)

    const payload: Record<string, string | number> = {
      Location: form.Location,
      OverallQual: parseInt(form.OverallQual),
      GrLivArea: parseInt(form.GrLivArea),
    }
    if (form.TotalBsmtSF) payload.TotalBsmtSF = parseFloat(form.TotalBsmtSF)
    if (form.YearBuilt) payload.YearBuilt = parseInt(form.YearBuilt)

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail ?? `HTTP ${res.status}`)
      }

      const data: PredictResponse = await res.json()
      setResult(data)

      setTimeout(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      }, 100)
    } catch (err) {
      setApiError(
        err instanceof Error ? err.message : 'Prediction failed. Check the API server.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="relative min-h-dvh flex items-center justify-center p-4 sm:p-8">
      <AmbientOrbs />

      {/* ── Glass card ── */}
      <motion.div
        className="glass-card w-full max-w-lg relative z-10"
        initial={{ opacity: 0, y: 32, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ ...SPRING_CARD, delay: 0.05 }}
      >
        {/* ── Header ── */}
        <motion.div
          className="px-8 pt-8 pb-6 text-center"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...SPRING_CARD, delay: 0.18 }}
        >
          <div
            className="inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-5"
            style={{
              background:
                'linear-gradient(135deg, rgba(99,102,241,0.25) 0%, rgba(124,58,237,0.2) 100%)',
              border: '1px solid rgba(99,102,241,0.3)',
              boxShadow: '0 0 24px rgba(99,102,241,0.2)',
            }}
            aria-hidden
          >
            <Home size={24} style={{ color: '#a5b4fc' }} />
          </div>

          <h1
            className="text-2xl font-semibold tracking-wide mb-2"
            style={{ fontFamily: 'var(--font-cinzel)', color: '#ededef' }}
          >
            House Price Oracle
          </h1>
          <p
            className="text-[13px] tracking-[0.04em]"
            style={{ color: '#8a8f98' }}
          >
            End-to-End MLOps · Indian Tech Hub Markets
          </p>
        </motion.div>

        {/* Divider */}
        <div style={{ height: 1, background: 'rgba(255,255,255,0.06)' }} />

        {/* ── Form ── */}
        <form onSubmit={handleSubmit} noValidate className="px-8 py-6">
          {/* Location selector */}
          <motion.div
            initial={{ opacity: 0, y: 22 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...SPRING_CARD, delay: 0.3 }}
            className="flex flex-col gap-2 mb-5"
          >
            <label htmlFor="Location" className="field-label flex items-center gap-2">
              <MapPin size={11} className="text-indigo-400" aria-hidden />
              City Market
            </label>
            <select
              id="Location"
              value={form.Location}
              onChange={(e) => handleChange('Location', e.target.value)}
              aria-invalid={!!errors.Location}
              className={cn(
                'glass-input',
                errors.Location && 'border-red-500/50 focus:border-red-500/70'
              )}
              style={{ color: form.Location ? 'inherit' : '#8a8f98' }}
            >
              <option value="">Select a city...</option>
              <option value="Gurgaon">Gurgaon (Delhi NCR)</option>
              <option value="Bangalore">Bangalore</option>
              <option value="Kolkata">Kolkata</option>
            </select>
            <AnimatePresence mode="wait">
              {errors.Location && (
                <motion.p
                  key="loc-error"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.2 }}
                  className="flex items-center gap-1.5 text-[11px] text-red-400 font-medium"
                  role="alert"
                >
                  <AlertCircle size={11} aria-hidden />
                  {errors.Location}
                </motion.p>
              )}
            </AnimatePresence>
          </motion.div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-6">
            {FIELDS.map((field, i) => (
              <FormField
                key={field.id}
                {...field}
                value={form[field.id]}
                onChange={handleChange}
                index={i}
                error={errors[field.id]}
              />
            ))}
          </div>

          {/* API error banner */}
          <AnimatePresence>
            {apiError && (
              <motion.div
                initial={{ opacity: 0, y: -8, height: 0 }}
                animate={{ opacity: 1, y: 0, height: 'auto' }}
                exit={{ opacity: 0, y: -8, height: 0 }}
                transition={{ duration: 0.22, ease: EXPO_OUT }}
                className="mb-5 overflow-hidden"
              >
                <div
                  className="flex items-start gap-2.5 px-4 py-3 rounded-xl text-[12px] tracking-wide"
                  style={{
                    background: 'rgba(239,68,68,0.08)',
                    border: '1px solid rgba(239,68,68,0.2)',
                    color: '#fca5a5',
                  }}
                  role="alert"
                >
                  <AlertCircle size={14} className="mt-0.5 shrink-0" aria-hidden />
                  {apiError}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Predict button */}
          <motion.button
            type="submit"
            disabled={loading}
            className="predict-btn"
            whileTap={{ scale: 0.97 }}
            transition={{ type: 'spring', damping: 20, stiffness: 400 }}
            aria-label="Predict house price"
          >
            <AnimatePresence mode="wait">
              {loading ? (
                <motion.span
                  key="loading"
                  className="flex items-center justify-center gap-3"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.18 }}
                >
                  <motion.span
                    className="w-4 h-4 rounded-full"
                    style={{
                      border: '2px solid rgba(255,255,255,0.3)',
                      borderTopColor: '#fff',
                      display: 'inline-block',
                    }}
                    animate={{ rotate: 360 }}
                    transition={{ duration: 0.8, repeat: Infinity, ease: 'linear' }}
                    aria-hidden
                  />
                  Predicting…
                </motion.span>
              ) : (
                <motion.span
                  key="idle"
                  className="flex items-center justify-center gap-2"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.18 }}
                >
                  <Sparkles size={14} aria-hidden />
                  Predict Price
                </motion.span>
              )}
            </AnimatePresence>
          </motion.button>
        </form>

        {/* ── Loading ring + Result ── */}
        <div className="px-8 pb-8" ref={resultRef}>
          <AnimatePresence mode="wait">
            {loading && !result && (
              <motion.div
                key="ring"
                className="flex flex-col items-center gap-4 py-2"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              >
                <LoadingRing />
                <p
                  className="text-[12px] tracking-[0.08em] uppercase"
                  style={{ color: 'rgba(129,140,248,0.7)' }}
                >
                  Running inference…
                </p>
              </motion.div>
            )}

            {result && !loading && <PriceResult key="result" data={result} />}
          </AnimatePresence>
        </div>
      </motion.div>

      {/* Footer label */}
      <motion.p
        className="absolute bottom-6 text-[11px] tracking-[0.06em] uppercase"
        style={{ color: 'rgba(138,143,152,0.3)' }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.2, duration: 1 }}
        aria-hidden
      >
        Day 3 · End-to-End MLOps Pipeline
      </motion.p>
    </main>
  )
}
