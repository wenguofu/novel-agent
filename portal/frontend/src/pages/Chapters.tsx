import React, { useState, useEffect } from 'react'
import { Card, Input, List, Tag, Space } from 'antd'
import { BookOutlined, ReadOutlined, SearchOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface ChapterItem {
  name: string
  words: number
}

interface VolumeGroup {
  name: string
  chapters: ChapterItem[]
  total_words?: number
}

export const Chapters: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [volumes, setVolumes] = useState<VolumeGroup[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [selectedChapter, setSelectedChapter] = useState<string | null>(null)
  const [chapterContent, setChapterContent] = useState('')

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const novel = data?.novel || data || {}
      setVolumes(Array.isArray(novel.volumes) ? novel.volumes : [])
    } catch {
      setVolumes([])
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [currentNovel])

  const handleRead = async (volName: string, chName: string) => {
    const ref = `${volName}/${chName}`
    setSelectedChapter(ref)
    setChapterContent('加载中...')
    try {
      const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel!)}/chapters/${ref}`)
      const data = await resp.json()
      setChapterContent(data.content || '(空)')
    } catch {
      setChapterContent('加载失败')
    }
  }

  const extractChNum = (name: string) => {
    const m = name.match(/ch-(\d+)/)
    return m ? parseInt(m[1], 10) : 0
  }

  const filteredVolumes = volumes.map((vol) => ({
    ...vol,
    chapters: (vol.chapters || []).filter((ch) => {
      if (!search) return true
      const q = search.toLowerCase()
      return ch.name.toLowerCase().includes(q) || `第${extractChNum(ch.name)}章`.includes(q)
    }),
  })).filter((vol) => vol.chapters.length > 0)

  return (
    <div>
      <h2>章节浏览</h2>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Input
            placeholder="搜索章节..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: 250 }}
            allowClear
          />
        </Space>
      </Card>

      <div style={{ display: 'flex', gap: 16 }}>
        <Card title="章节列表" style={{ flex: '0 0 380px' }} loading={loading}
          styles={{ body: { maxHeight: '60vh', overflow: 'auto' } }}>
          {filteredVolumes.map((vol) => (
            <div key={vol.name} style={{ marginBottom: 16 }}>
              <Tag color="blue" style={{ marginBottom: 8 }}>
                {vol.name} ({vol.chapters.length}章)
              </Tag>
              <List
                size="small"
                dataSource={vol.chapters}
                renderItem={(ch) => {
                  const ref = `${vol.name}/${ch.name}`
                  return (
                    <List.Item
                      style={{
                        cursor: 'pointer',
                        background: selectedChapter === ref ? '#e6f4ff' : undefined,
                      }}
                      onClick={() => handleRead(vol.name, ch.name)}
                    >
                      <Space>
                        <BookOutlined />
                        <span>第{extractChNum(ch.name)}章</span>
                        <Tag>{ch.words?.toLocaleString() || 0}字</Tag>
                      </Space>
                    </List.Item>
                  )
                }}
              />
            </div>
          ))}
          {filteredVolumes.length === 0 && !loading && (
            <div style={{ color: '#999', textAlign: 'center', padding: 20 }}>暂无章节</div>
          )}
        </Card>

        <Card
          title={selectedChapter ? `阅读: ${selectedChapter}` : '章节内容'}
          style={{ flex: 1 }}
          styles={{ body: { maxHeight: '60vh', overflow: 'auto' } }}
        >
          {chapterContent ? (
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: 15 }}>
              {chapterContent}
            </div>
          ) : (
            <div style={{ color: '#999', textAlign: 'center', padding: 60 }}>
              <ReadOutlined style={{ fontSize: 48 }} />
              <p>选择小说后点击章节查看内容</p>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
