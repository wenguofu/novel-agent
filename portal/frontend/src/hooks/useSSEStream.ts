import { useState, useRef, useCallback } from 'react'

interface UseSSEOptions {
  onToken?: (token: string) => void
  onDone?: (fullText: string) => void
  onError?: (error: Error) => void
}

export function useSSEStream() {
  const [streaming, setStreaming] = useState(false)
  const [content, setContent] = useState('')
  const [wordCount, setWordCount] = useState(0)
  const [elapsed, setElapsed] = useState(0)
  const abortRef = useRef<AbortController | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const startStream = useCallback(
    async (systemPrompt: string, userMessage: string, model: string, opts: UseSSEOptions = {}) => {
      setStreaming(true)
      setContent('')
      setWordCount(0)
      setElapsed(0)

      const controller = new AbortController()
      abortRef.current = controller

      const startTime = Date.now()
      timerRef.current = setInterval(() => {
        setElapsed(Math.floor((Date.now() - startTime) / 1000))
      }, 1000)

      let fullText = ''

      try {
        const resp = await fetch('/api/ai/stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            system: systemPrompt,
            user: userMessage,
            model,
          }),
          signal: controller.signal,
        })

        if (!resp.ok) {
          throw new Error(`HTTP ${resp.status}`)
        }

        const reader = resp.body?.getReader()
        if (!reader) throw new Error('No response body')

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6).trim()
              if (data === '[DONE]') continue

              try {
                const parsed = JSON.parse(data)
                if (parsed.type === 'token' && parsed.content) {
                  fullText += parsed.content
                  setContent(fullText)
                  setWordCount(fullText.replace(/\s/g, '').length)
                  opts.onToken?.(parsed.content)
                } else if (parsed.type === 'done') {
                  // done
                }
              } catch {
                // skip unparseable chunks
              }
            }
          }
        }

        opts.onDone?.(fullText)
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          opts.onError?.(err)
        }
      } finally {
        setStreaming(false)
        if (timerRef.current) {
          clearInterval(timerRef.current)
          timerRef.current = null
        }
        abortRef.current = null
      }
    },
    []
  )

  const stopStream = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  return { streaming, content, wordCount, elapsed, startStream, stopStream }
}
