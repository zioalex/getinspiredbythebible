/**
 * API client for Bible Chat backend
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export interface Message {
  role: 'user' | 'assistant'
  content: string
}

export interface Verse {
  reference: string
  text: string
  book: string
  chapter: number
  verse: number
  similarity?: number
}

export interface Passage {
  title: string
  reference: string
  text: string
  topics?: string[]
  similarity?: number
}

export interface ScriptureContext {
  query: string
  verses: Verse[]
  passages: Passage[]
}

export interface ChatResponse {
  message: string
  scripture_context?: ScriptureContext
  provider: string
  model: string
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy'
  providers: {
    llm: { provider: string; healthy: boolean }
    embedding: { provider: string; healthy: boolean }
  }
}

/**
 * Send a chat message and get a response
 */
export async function sendMessage(
  message: string,
  history: Message[] = []
): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/api/v1/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      conversation_history: history,
      include_search: true,
    }),
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  return response.json()
}

/**
 * Stream a chat response
 */
export async function* streamMessage(
  message: string,
  history: Message[] = []
): AsyncGenerator<string> {
  const response = await fetch(`${API_URL}/api/v1/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      message,
      conversation_history: history,
      include_search: true,
    }),
  })

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    const chunk = decoder.decode(value)
    const lines = chunk.split('\n')

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        if (data === '[DONE]') return

        try {
          const parsed = JSON.parse(data)
          if (parsed.content) {
            yield parsed.content
          }
        } catch {
          // Skip invalid JSON
        }
      }
    }
  }
}

/**
 * Search scripture
 */
export async function searchScripture(
  query: string,
  maxVerses: number = 5
): Promise<ScriptureContext> {
  const params = new URLSearchParams({
    q: query,
    max_verses: maxVerses.toString(),
  })

  const response = await fetch(`${API_URL}/api/v1/scripture/search?${params}`)

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  return response.json()
}

/**
 * Get a specific verse
 */
export async function getVerse(
  book: string,
  chapter: number,
  verse: number
): Promise<Verse> {
  const response = await fetch(
    `${API_URL}/api/v1/scripture/verse/${encodeURIComponent(book)}/${chapter}/${verse}`
  )

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  return response.json()
}

/**
 * Get all verses in a chapter
 */
export async function getChapter(
  book: string,
  chapter: number
): Promise<{ book: string; chapter: number; verses: Verse[] }> {
  const response = await fetch(
    `${API_URL}/api/v1/scripture/chapter/${encodeURIComponent(book)}/${chapter}`
  )

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  return response.json()
}

/**
 * Get verse with context
 */
export async function getVerseContext(
  book: string,
  chapter: number,
  verse: number
): Promise<{ target_verse: number; verses: Verse[] }> {
  const response = await fetch(
    `${API_URL}/api/v1/chat/verse/${encodeURIComponent(book)}/${chapter}/${verse}`
  )

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  return response.json()
}

/**
 * Check API health
 */
export async function checkHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_URL}/health`)

  if (!response.ok) {
    throw new Error(`API error: ${response.status}`)
  }

  return response.json()
}
