import { useState, useEffect, useRef } from 'react'

const A11Y_STORAGE_KEY = 'weathergpt_accessibility_settings'
const A11Y_AUTO_SPEAK_KEY = 'weathergpt_auto_speak_alerts'

export default function AccessibilityMenu() {
  const [isOpen, setIsOpen] = useState(false)
  const [textSize, setTextSize] = useState('normal') // 'normal' | 'large' | 'xlarge'
  const [highContrast, setHighContrast] = useState(false)
  const [autoSpeak, setAutoSpeak] = useState(false)
  
  const containerRef = useRef(null)
  const triggerRef = useRef(null)

  // Load settings on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(A11Y_STORAGE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw)
        if (parsed.textSize) {
          setTextSize(parsed.textSize)
          applyTextSize(parsed.textSize)
        }
        if (typeof parsed.highContrast === 'boolean') {
          setHighContrast(parsed.highContrast)
          applyHighContrast(parsed.highContrast)
        }
        if (typeof parsed.autoSpeak === 'boolean') {
          setAutoSpeak(parsed.autoSpeak)
        }
      }
      const separateAutoSpeak = localStorage.getItem(A11Y_AUTO_SPEAK_KEY)
      if (separateAutoSpeak !== null) {
        setAutoSpeak(separateAutoSpeak === 'true')
      }
    } catch (e) {
      console.warn('Could not load a11y settings from localStorage:', e)
    }
  }, [])

  const saveSettings = (newSize, newContrast, newSpeak) => {
    try {
      localStorage.setItem(
        A11Y_STORAGE_KEY,
        JSON.stringify({
          textSize: newSize,
          highContrast: newContrast,
          autoSpeak: newSpeak,
        })
      )
      localStorage.setItem(A11Y_AUTO_SPEAK_KEY, newSpeak ? 'true' : 'false')
    } catch (e) {
      console.warn('Could not save a11y settings:', e)
    }
  }

  const applyTextSize = (size) => {
    const root = document.documentElement
    const body = document.body
    root.classList.remove('text-scale-large', 'text-scale-xlarge')
    body.classList.remove('text-scale-large', 'text-scale-xlarge')
    if (size === 'large') {
      root.classList.add('text-scale-large')
      body.classList.add('text-scale-large')
    } else if (size === 'xlarge') {
      root.classList.add('text-scale-xlarge')
      body.classList.add('text-scale-xlarge')
    }
  }

  const applyHighContrast = (enabled) => {
    const root = document.documentElement
    const body = document.body
    if (enabled) {
      body.classList.add('high-contrast')
      root.classList.add('high-contrast')
      root.setAttribute('data-high-contrast', 'true')
    } else {
      body.classList.remove('high-contrast')
      root.classList.remove('high-contrast')
      root.removeAttribute('data-high-contrast')
    }
  }

  const handleTextSizeChange = (size) => {
    setTextSize(size)
    applyTextSize(size)
    saveSettings(size, highContrast, autoSpeak)
  }

  const handleHighContrastChange = (e) => {
    const checked = e.target.checked
    setHighContrast(checked)
    applyHighContrast(checked)
    saveSettings(textSize, checked, autoSpeak)
  }

  const handleAutoSpeakChange = (e) => {
    const checked = e.target.checked
    setAutoSpeak(checked)
    saveSettings(textSize, highContrast, checked)
    if (typeof window.applyAutoSpeak === 'function') {
      window.applyAutoSpeak(checked)
    } else {
      if (checked && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
        const utterance = new SpeechSynthesisUtterance('Voice assist enabled. Critical alerts will be spoken automatically.')
        utterance.rate = 0.95
        window.speechSynthesis.speak(utterance)
      } else if (!checked) {
        if (typeof window.stopAlertSpeech === 'function') {
          window.stopAlertSpeech()
        }
        if ('speechSynthesis' in window) {
          window.speechSynthesis.cancel()
        }
      }
    }
  }

  // Keyboard accessibility and click outside
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false)
        triggerRef.current?.focus()
      }
    }

    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  return (
    <div className="relative inline-flex items-center" ref={containerRef}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        aria-controls="reactA11yPopover"
        aria-label="Accessibility Control Center"
        className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-semibold rounded-lg border transition-all select-none ${
          isOpen
            ? 'bg-[#161b22] border-[#8b5cf6] text-[#c4b5fd] shadow-[0_0_12px_rgba(139,92,246,0.35)]'
            : 'bg-[#21262d] border-[#30363d] text-[#e6edf3] hover:border-[#8b5cf6] hover:text-white'
        }`}
      >
        <span className="text-[#a78bfa] text-sm leading-none" aria-hidden="true">♿</span>
        <span>Accessibility</span>
        <span className={`text-[8px] text-[#7d8590] transition-transform duration-200 ${isOpen ? 'rotate-180 text-[#c4b5fd]' : ''}`}>
          ▼
        </span>
      </button>

      {isOpen && (
        <div
          id="reactA11yPopover"
          role="dialog"
          aria-labelledby="reactA11yTitle"
          className="absolute top-[calc(100%+8px)] right-0 w-80 bg-[#161b22] border border-[#8b5cf6]/40 rounded-xl shadow-2xl z-[10000] p-4 flex flex-col gap-3.5 backdrop-blur-md animate-in fade-in zoom-in-95 duration-150"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-[#30363d] pb-2.5">
            <div className="flex items-center gap-2">
              <span className="text-base text-[#a78bfa]" aria-hidden="true">♿</span>
              <h3 id="reactA11yTitle" className="text-sm font-bold text-[#e6edf3] m-0 tracking-tight">
                Accessibility
              </h3>
            </div>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false)
                triggerRef.current?.focus()
              }}
              aria-label="Close Accessibility Menu"
              className="text-[#7d8590] hover:text-white hover:bg-[#21262d] px-1.5 py-0.5 rounded text-xs transition-colors"
            >
              &#10005;
            </button>
          </div>

          {/* Body */}
          <div className="flex flex-col gap-3.5">
            {/* Feature 1: Text Sizing */}
            <div className="flex flex-col gap-2">
              <div>
                <span className="text-xs font-semibold text-[#e6edf3] block">Text Size</span>
                <span className="text-[10.5px] text-[#7d8590] block">Adjust UI and text font scaling</span>
              </div>
              <div className="grid grid-cols-3 gap-1 bg-[#21262d] p-1 rounded-lg border border-[#30363d]">
                <button
                  type="button"
                  onClick={() => handleTextSizeChange('normal')}
                  aria-pressed={textSize === 'normal'}
                  className={`text-xs py-1.5 px-1 rounded font-medium transition-all ${
                    textSize === 'normal'
                      ? 'bg-[#7c3aed] text-white font-bold shadow-sm'
                      : 'text-[#7d8590] hover:text-white hover:bg-white/5'
                  }`}
                >
                  Normal
                </button>
                <button
                  type="button"
                  onClick={() => handleTextSizeChange('large')}
                  aria-pressed={textSize === 'large'}
                  className={`text-xs py-1.5 px-1 rounded font-medium transition-all ${
                    textSize === 'large'
                      ? 'bg-[#7c3aed] text-white font-bold shadow-sm'
                      : 'text-[#7d8590] hover:text-white hover:bg-white/5'
                  }`}
                >
                  Large
                </button>
                <button
                  type="button"
                  onClick={() => handleTextSizeChange('xlarge')}
                  aria-pressed={textSize === 'xlarge'}
                  className={`text-xs py-1.5 px-1 rounded font-medium transition-all ${
                    textSize === 'xlarge'
                      ? 'bg-[#7c3aed] text-white font-bold shadow-sm'
                      : 'text-[#7d8590] hover:text-white hover:bg-white/5'
                  }`}
                >
                  Extra Large
                </button>
              </div>
            </div>

            {/* Feature 2: High Contrast */}
            <div className="flex items-center justify-between gap-3">
              <div>
                <span className="text-xs font-semibold text-[#e6edf3] block">High Contrast</span>
                <span className="text-[10.5px] text-[#7d8590] block">Deep black, white text & solid borders</span>
              </div>
              <label className="relative inline-block w-10 h-5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={highContrast}
                  onChange={handleHighContrastChange}
                  role="switch"
                  aria-checked={highContrast}
                  className="sr-only peer"
                />
                <div className="w-10 h-5 bg-[#21262d] border border-[#30363d] peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-[#a78bfa] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-[#7d8590] after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#7c3aed] peer-checked:after:bg-white"></div>
              </label>
            </div>

            {/* Feature 3: Auto-Speak Alerts */}
            <div className="flex items-center justify-between gap-3">
              <div>
                <span className="text-xs font-semibold text-[#e6edf3] block">Auto-Speak Alerts</span>
                <span className="text-[10.5px] text-[#7d8590] block">Announce critical alerts with voice engine</span>
              </div>
              <label className="relative inline-block w-10 h-5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoSpeak}
                  onChange={handleAutoSpeakChange}
                  role="switch"
                  aria-checked={autoSpeak}
                  className="sr-only peer"
                />
                <div className="w-10 h-5 bg-[#21262d] border border-[#30363d] peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-[#a78bfa] rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-[#7d8590] after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#7c3aed] peer-checked:after:bg-white"></div>
              </label>
            </div>
          </div>

          {/* Footer note */}
          <div className="border-t border-[#30363d] pt-2.5">
            <p className="m-0 text-[10px] text-[#7d8590] text-center italic">
              Designed for elderly users and limited digital literacy
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
