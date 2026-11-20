import { Fragment, type ReactNode } from 'react'

/** Convierte `**texto**` en <strong> sin usar HTML crudo. */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    const key = `${keyPrefix}-${index}`
    if (part.length > 4 && part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={key} className="font-semibold text-white">
          {part.slice(2, -2)}
        </strong>
      )
    }
    return <Fragment key={key}>{part}</Fragment>
  })
}

const LIST_ITEM = /^\s*[-*]\s+/

interface AssistantMarkdownProps {
  text: string
}

/** Markdown mínimo del asistente: párrafos, **negritas** y listas con "- ". */
export default function AssistantMarkdown({ text }: AssistantMarkdownProps) {
  const blocks: ReactNode[] = []
  let listItems: string[] = []

  const flushList = () => {
    if (listItems.length === 0) {
      return
    }
    const index = blocks.length
    blocks.push(
      <ul key={`ul-${index}`} className="list-disc space-y-1 pl-5">
        {listItems.map((item, i) => (
          <li key={i}>{renderInline(item, `li-${index}-${i}`)}</li>
        ))}
      </ul>
    )
    listItems = []
  }

  for (const line of text.split('\n')) {
    if (LIST_ITEM.test(line)) {
      listItems.push(line.replace(LIST_ITEM, ''))
      continue
    }
    flushList()
    if (line.trim()) {
      const index = blocks.length
      blocks.push(<p key={`p-${index}`}>{renderInline(line, `p-${index}`)}</p>)
    }
  }
  flushList()

  return <div className="space-y-2 break-words">{blocks}</div>
}
