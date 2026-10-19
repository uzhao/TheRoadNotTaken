import { useEffect, useState } from 'react'

import { fetchFields, type FieldsResponse } from '../api'

/** 顶层数据：领域列表与已掌握计数，供顶栏与知识网页共用；`version` 变化时重取。 */
export function useFields(version: number) {
  const [data, setData] = useState<FieldsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    fetchFields()
      .then((body) => {
        if (!cancelled) setData(body)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(String(err))
      })
    return () => {
      cancelled = true
    }
  }, [version])

  return { data, error }
}
