import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Bot, User } from 'lucide-react'
import { sendChat, getChatHistory } from '../lib/api'
import { AgentCouncil } from '../components/AgentCouncil'
import { StreamingText } from '../components/StreamingText'

interface Message {
  role: 'user' | 'assistant'
  content: string
  tickers?: string[]
  streaming?: boolean
}

const COUNCIL_RE = /^(?:council|agent|analyze)\s+([A-Z]{1,5})$/i

export default function Chat() {
  const [messages, setMessages]     = useState<Message[]>([])
  const [input, setInput]           = useState('')
  const [loading, setLoading]       = useState(false)
  const [councilTicker, setCouncilTicker] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    getChatHistory().then((hist: Array<{ role: string; content: string }>) => {
      if (hist?.length) {
        setMessages(hist.map(h => ({ role: h.role as 'user' | 'assistant', content: h.content })))
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function submit() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')

    const councilMatch = text.match(COUNCIL_RE)
    if (councilMatch) {
      setCouncilTicker(councilMatch[1].toUpperCase())
      return
    }

    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)
    try {
      const { response, tickers_fetched } = await sendChat(text)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: response, tickers: tickers_fetched, streaming: true },
      ])
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: 'Sorry, something went wrong. Is the backend running?' },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5 pb-36 md:pb-6">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-20">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center mb-4 shadow-xl shadow-blue-500/20">
              <Bot size={24} className="text-white" />
            </div>
            <p className="text-white font-semibold mb-1">AI Investment Advisor</p>
            <p className="text-slate-500 text-sm max-w-xs">
              Ask about any stock, e.g. "Is NVDA a buy?"<br />
              Type <span className="text-blue-400 font-mono">council TSLA</span> for the Agent Council debate.
            </p>
          </div>
        )}

        <AnimatePresence>
          {messages.map((m, i) => (
            <motion.div key={i}
              initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
              className={`flex gap-3 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {m.role === 'assistant' && (
                <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot size={13} className="text-white" />
                </div>
              )}
              <div className={`max-w-2xl rounded-2xl px-4 py-3 text-sm leading-relaxed
                ${m.role === 'user'
                  ? 'bg-blue-600/20 border border-blue-500/30 text-white'
                  : 'bg-card border border-white/5 text-slate-200'}`}
              >
                {m.role === 'assistant' && m.streaming && i === messages.length - 1
                  ? <StreamingText text={m.content} speed={18} />
                  : <p className="whitespace-pre-wrap">{m.content}</p>
                }
                {m.tickers && m.tickers.length > 0 && (
                  <div className="flex gap-1.5 flex-wrap mt-2 pt-2 border-t border-white/5">
                    <span className="text-xs text-slate-600">Data fetched:</span>
                    {m.tickers.map(t => (
                      <span key={t} className="text-xs px-2 py-0.5 rounded-full bg-white/5 text-slate-400">{t}</span>
                    ))}
                  </div>
                )}
              </div>
              {m.role === 'user' && (
                <div className="w-7 h-7 rounded-lg bg-white/10 flex items-center justify-center shrink-0 mt-0.5">
                  <User size={13} className="text-white" />
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {loading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shrink-0">
              <Bot size={13} className="text-white" />
            </div>
            <div className="bg-card border border-white/5 rounded-2xl px-4 py-3">
              <div className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <span key={i} className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="sticky bottom-0 md:relative border-t border-white/5 bg-navy px-4 py-4 mb-14 md:mb-0">
        <div className="flex gap-3 max-w-3xl mx-auto">
          <input
            value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() } }}
            placeholder='Ask about a stock, or type "council TSLA"…'
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/60 transition-colors"
          />
          <button onClick={submit} disabled={!input.trim() || loading}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 text-white disabled:opacity-40 hover:opacity-90 transition-opacity"
          >
            <Send size={15} />
          </button>
        </div>
      </div>

      {/* Agent Council modal */}
      {councilTicker && (
        <AgentCouncil
          ticker={councilTicker}
          onClose={() => setCouncilTicker(null)}
        />
      )}
    </div>
  )
}
