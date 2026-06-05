import { useEffect, useState } from 'react'

interface Props {
  text: string
  speed?: number
  onDone?: () => void
}

export function StreamingText({ text, speed = 12, onDone }: Props) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)

  useEffect(() => {
    setDisplayed('')
    setDone(false)
    if (!text) return
    const words = text.split(' ')
    let i = 0
    const timer = setInterval(() => {
      if (i >= words.length) {
        clearInterval(timer)
        setDisplayed(text)
        setDone(true)
        onDone?.()
        return
      }
      setDisplayed(words.slice(0, i + 1).join(' '))
      i++
    }, speed)
    return () => clearInterval(timer)
  }, [text, speed, onDone])

  return (
    <span className="whitespace-pre-wrap">
      {displayed}
      {!done && (
        <span className="inline-block w-0.5 h-[1em] bg-blue-400 ml-0.5 align-middle animate-pulse" />
      )}
    </span>
  )
}
