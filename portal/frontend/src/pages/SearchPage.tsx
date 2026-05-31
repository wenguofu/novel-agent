import React, { useState } from 'react'
import { Card, Select, Input, Space, List, Tag } from 'antd'
import { useNovelStore } from '../stores/novelStore'
import { useNovels } from '../api/client'

interface SearchResult { type: string; title: string; snippet: string; novel_name?: string; volume?: string }

export const SearchPage: React.FC = () => {
  const { data: novels = [] } = useNovels()
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const setCurrentNovel = useNovelStore((s) => s.setCurrentNovel)

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const params = new URLSearchParams({ q: query })
      if (currentNovel) params.set('novel', currentNovel)
      params.set('limit', '50')
      const resp = await fetch(`/api/content/search?${params}`)
      const data = await resp.json()
      const items: SearchResult[] = []
      if (data.chapters) items.push(...data.chapters.map((c: any) => ({ ...c, type: '章节' })))
      if (data.outlines) items.push(...data.outlines.map((o: any) => ({ ...o, type: '大纲' })))
      if (data.reviews) items.push(...data.reviews.map((r: any) => ({ ...r, type: '审稿' })))
      setResults(items)
    } finally { setLoading(false) }
  }

  return (
    <div>
      <h2>全文搜索</h2>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Select style={{ width: 180 }} value={currentNovel || undefined} allowClear
            placeholder="所有小说" onChange={v => setCurrentNovel(v || null)}
            options={novels.map(n => ({ value: n.name, label: n.title || n.name }))} />
          <Input.Search placeholder="输入关键词搜索..." value={query}
            onChange={e => setQuery(e.target.value)} onSearch={handleSearch}
            style={{ width: 400 }} enterButton />
        </Space>

        <List loading={loading} dataSource={results}
          locale={{ emptyText: query ? '未找到结果' : '输入关键词开始搜索' }}
          renderItem={(item) => (
            <List.Item>
              <List.Item.Meta
                title={<Space><Tag color="blue">{item.type}</Tag>{item.title}</Space>}
                description={<span>{item.snippet || ''}</span>}
              />
            </List.Item>
          )} />
      </Card>
    </div>
  )
}
