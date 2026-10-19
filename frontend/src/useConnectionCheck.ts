import { useEffect, useState } from 'react'

import { cancelJob, createPingJob, type Job, type JobEvent, subscribeJob } from './api'

/** 「重试连接」任务的状态：顶栏放按钮，主区列事件流，二者共用。 */
export function useConnectionCheck() {
  const [job, setJob] = useState<Job | null>(null)
  const [events, setEvents] = useState<JobEvent[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (job === null) return
    return subscribeJob(job.id, (event) => setEvents((prev) => [...prev, event]))
  }, [job])

  const running = job !== null && events.at(-1)?.event !== 'done'

  const start = () => {
    setEvents([])
    setError(null)
    createPingJob()
      .then(setJob)
      .catch((e: Error) => setError(e.message))
  }
  const cancel = () => {
    if (job) void cancelJob(job.id)
  }

  return { job, events, error, running, start, cancel }
}
