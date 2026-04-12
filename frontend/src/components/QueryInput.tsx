import { useState, useRef, KeyboardEvent, useImperativeHandle, forwardRef } from 'react'
import { Search } from 'lucide-react'

interface Props {
  onSubmit: (q: string) => void
  loading: boolean
  disabled: boolean
}

export interface QueryInputRef {
  setValue: (v: string) => void
}

export const QueryInput = forwardRef<QueryInputRef, Props>(
  function QueryInput({ onSubmit, loading, disabled }, ref) {
    const [value, setValue] = useState('')
    const textRef = useRef<HTMLTextAreaElement>(null)

    useImperativeHandle(ref, () => ({
      setValue(v: string) {
        setValue(v)
        textRef.current?.focus()
      },
    }))

    const submit = () => {
      const q = value.trim()
      if (!q || loading || disabled) return
      setValue('')
      onSubmit(q)
    }

    const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
    }

    return (
      <div className="glass input-area flex items-end gap-3 p-3"
        style={{ border: '1px solid var(--border)' }}>
        <textarea
          ref={textRef}
          rows={2}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={onKey}
          placeholder="Ask a question about your data… (Enter to submit, Shift+Enter for new line)"
          disabled={disabled || loading}
          style={{
            flex: 1,
            background: 'transparent',
            resize: 'none',
            outline: 'none',
            color: 'var(--text-primary)',
            lineHeight: 1.6,
            fontFamily: 'Inter, system-ui, sans-serif',
            fontSize: 14,
            border: 'none',
          }}
        />
        <button
          className="btn-primary flex-shrink-0 gap-1.5"
          style={{ padding: '9px 18px', fontSize: 13 }}
          onClick={submit}
          disabled={!value.trim() || loading || disabled}>
          {loading
            ? <><div className="spinner" style={{ width: 14, height: 14 }} />&nbsp;Analysing…</>
            : <><Search size={14} /> Analyse</>
          }
        </button>
      </div>
    )
  }
)
