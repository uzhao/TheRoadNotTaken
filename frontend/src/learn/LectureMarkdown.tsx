import Markdown, { type Components } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import remarkMath from 'remark-math'

import { figureUrl } from '../api'

interface Props {
  topicId: string
  markdown: string
  /** 讲义已缓存：插图可从静态路由取；否则插图位置显示占位框 */
  cached: boolean
  /** 生成中已画好的插图（名 → 版本号）：画好即从任务目录显示 */
  drawn: Record<string, number>
  streaming: boolean
}

const FIGURE_RE = /^figures\/([A-Za-z0-9][A-Za-z0-9._-]*\.(?:svg|png))$/

/**
 * 讲义正文：markdown + KaTeX（`throwOnError: false`）。不启用 rehype-raw，原始 HTML 不渲染；
 * 插图一律 `<img>` 引用后端静态路由，不内联 SVG，也不加载 `figures/` 以外的地址。
 */
export function LectureMarkdown({ topicId, markdown, cached, drawn, streaming }: Props) {
  const components: Components = {
    img: ({ src, alt }) => {
      const match = typeof src === 'string' ? FIGURE_RE.exec(src) : null
      const caption = alt ?? ''
      const version = match ? drawn[match[1].replace(/\.(svg|png)$/, '')] : undefined
      if (match && (cached || version !== undefined)) {
        const url = figureUrl(topicId, match[1])
        return (
          <span className="fig">
            <img src={cached ? url : `${url}?v=${version}`} alt={caption} />
            <span className="cap">{caption}</span>
          </span>
        )
      }
      return (
        <span className={`fig${streaming ? ' pending' : ''}`}>
          <span className="box">{match ? '插图绘制中…' : '插图不可用'}</span>
          <span className="cap">{caption}</span>
        </span>
      )
    },
  }
  return (
    <article className={`lecture${streaming ? ' streaming' : ''}`}>
      <Markdown
        remarkPlugins={[remarkMath]}
        rehypePlugins={[[rehypeKatex, { throwOnError: false }]]}
        components={components}
      >
        {markdown}
      </Markdown>
    </article>
  )
}
