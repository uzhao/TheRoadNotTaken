import { useEffect, useRef, useState } from 'react'

import {
  fetchLecture,
  startLecture,
  subscribeJob,
  type JobError,
  type JobEvent,
  type LecturePage,
} from '../api'

/** 步骤条的一格：进行中或已完成。 */
export interface Step {
  key: string
  label: string
  done: boolean
}

export interface LectureState {
  page: LecturePage | null
  /** 生成中已流出的正文（讲义缓存后改用 `page.lecture.markdown`） */
  streamed: string
  steps: Step[]
  /** 生成中已画好的插图：名（不含扩展名）→ 第几次画好，用作地址的版本号 */
  drawn: Record<string, number>
  /** 排队位次，未排队为 null */
  queued: number | null
  failure: JobError | null
  error: string | null
  generating: boolean
  /** 重新开始（失败后「重试」） */
  restart: () => void
}

const FLUSH_MS = 100 // 流式时约每 100 ms 重渲染一次

/** 工具步要点里的插图名：`python3 figures/secant.py` → `secant`。 */
function figureName(detail: string): string | null {
  const m = /figures\/([\w.-]+?)\.(py|svg|png)\b/.exec(detail)
  return m ? m[1] : null
}

/** 开始学习并跟随讲义任务：正文增量节流渲染，工具步与重试转为步骤条。 */
export function useLecture(topicId: string): LectureState {
  const [page, setPage] = useState<LecturePage | null>(null)
  const [streamed, setStreamed] = useState('')
  const [steps, setSteps] = useState<Step[]>([])
  const [drawn, setDrawn] = useState<Record<string, number>>({})
  const [queued, setQueued] = useState<number | null>(null)
  const [failure, setFailure] = useState<JobError | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)
  const [round, setRound] = useState(0)
  const buffer = useRef('')

  useEffect(() => {
    let cancelled = false
    let unsubscribe = () => {}
    let timer: ReturnType<typeof setTimeout> | null = null
    let attempt = 1
    buffer.current = ''

    const flush = () => {
      timer = null
      if (!cancelled) setStreamed(buffer.current)
    }
    const suffix = () => (attempt > 1 ? `（第 ${attempt} 次尝试）` : '')
    const addStep = (key: string, label: string) =>
      setSteps((prev) =>
        prev.some((s) => s.key === key) ? prev : [...prev, { key, label, done: false }],
      )
    const finishStep = (key: string) =>
      setSteps((prev) => prev.map((s) => (s.key === key ? { ...s, done: true } : s)))

    const onEvent = (e: JobEvent) => {
      if (cancelled) return
      switch (e.event) {
        case 'queued':
          setQueued(e.data.position)
          break
        case 'started':
          setQueued(null)
          break
        case 'delta':
          if (buffer.current === '') addStep(`text-${attempt}`, `生成正文${suffix()}`)
          buffer.current += e.data.text
          timer ??= setTimeout(flush, FLUSH_MS)
          break
        case 'tool': {
          const name = figureName(e.data.detail)
          if (name === null) break
          const key = `fig-${attempt}-${e.data.step_index}`
          if (e.data.state === 'ACTIVE') addStep(key, `画图 ${name}${suffix()}`)
          else {
            finishStep(key)
            setDrawn((prev) => ({ ...prev, [name]: (prev[name] ?? 0) + 1 }))
          }
          break
        }
        case 'retry':
          // 重试时 agent 从头重写整份讲义
          attempt = e.data.attempt
          setSteps((prev) => [
            ...prev.map((s) => ({ ...s, done: true })),
            { key: `retry-${attempt}`, label: `校验未通过，正在修正${suffix()}`, done: true },
          ])
          buffer.current = ''
          flush()
          break
        case 'done':
          setGenerating(false)
          flush()
          setSteps((prev) => prev.map((s) => ({ ...s, done: true })))
          if (e.data.status === 'succeeded') {
            addStep('cached', '讲义已缓存')
            finishStep('cached')
            fetchLecture(topicId)
              .then((p) => !cancelled && setPage(p))
              .catch((err: unknown) => !cancelled && setError(String(err)))
          } else if (e.data.status === 'failed') {
            setFailure(e.data.error ?? { kind: 'exit', message: '生成失败' })
          }
          break
      }
    }

    startLecture(topicId)
      .then((p) => {
        if (cancelled) return
        setPage(p)
        if (p.job) {
          setGenerating(true)
          setQueued(p.job.position)
          unsubscribe = subscribeJob(p.job.id, onEvent)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })

    return () => {
      cancelled = true
      unsubscribe()
      if (timer !== null) clearTimeout(timer)
    }
  }, [topicId, round])

  const restart = () => {
    setPage(null)
    setStreamed('')
    setSteps([])
    setDrawn({})
    setQueued(null)
    setFailure(null)
    setError(null)
    setRound((r) => r + 1)
  }

  return { page, streamed, steps, drawn, queued, failure, error, generating, restart }
}
