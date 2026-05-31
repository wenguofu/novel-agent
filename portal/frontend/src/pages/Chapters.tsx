import React, { useState, useEffect, useMemo } from 'react'
import { Card, Input, List, Tag, Space, Button, message, Popconfirm } from 'antd'
import { BookOutlined, ReadOutlined, SearchOutlined, CopyOutlined, DeleteOutlined } from '@ant-design/icons'
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
  const [deleting, setDeleting] = useState(false)

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

  const extractChNum = (name: string) => {
    const m = name.match(/ch-(\d+)/)
    return m ? parseInt(m[1], 10) : 0
  }

  // ── Find the latest chapter (for delete restriction) ──
  const latestRef = useMemo(() => {
    let latest: { vol: string; chNum: number; ref: string } | null = null
    for (const vol of volumes) {
      for (const ch of vol.chapters || []) {
        const cn = extractChNum(ch.name)
        if (!latest || cn > latest.chNum) {
          latest = { vol: vol.name, chNum: cn, ref: `${vol.name}/${ch.name}` }
        }
      }
    }
    return latest
  }, [volumes])

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

  const handleDelete = async (volName: string, chName: string) => {
    if (!currentNovel) return
    const ref = `${volName}/${chName}`
    setDeleting(true)
    try {
      const resp = await fetch(
        `/api/novels/${encodeURIComponent(currentNovel)}/chapters/${ref}`,
        { method: 'DELETE' }
      )
      const data = await resp.json()
      if (data.success) {
        message.success(data.message || '已删除')
        if (selectedChapter === ref) {
          setSelectedChapter(null)
          setChapterContent('')
        }
        // Show rollback details
        if (data.rollback_log?.length) {
          data.rollback_log.forEach((log: string) => message.info(log))
        }
        load() // refresh list
      } else {
        message.error(data.error || '删除失败')
      }
    } catch {
      message.error('删除请求失败')
    } finally { setDeleting(false) }
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
          {latestRef && (
            <Tag color="green">最新: 第{latestRef.chNum}章</Tag>
          )}
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
                  const chNum = extractChNum(ch.name)
                  const isLatest = latestRef?.ref === ref
                  const isSelected = selectedChapter === ref
                  return (
                    <List.Item
                      style={{
                        cursor: 'pointer',
                        background: isSelected ? '#e6f4ff' : undefined,
                      }}
                      onClick={() => handleRead(vol.name, ch.name)}
                      actions={[
                        isLatest ? (
                          <Popconfirm
                            key="del"
                            title="确认删除"
                            description={`删除第${chNum}章将回滚伏笔、角色状态和阶段进度。此操作不可撤销。`}
                            onConfirm={(e) => {
                              e?.stopPropagation()
                              handleDelete(vol.name, ch.name)
                            }}
                            onCancel={(e) => e?.stopPropagation()}
                            okText="确认删除"
                            cancelText="取消"
                            okButtonProps={{ danger: true }}
                          >
                            <Button
                              size="small"
                              danger
                              icon={<DeleteOutlined />}
                              loading={deleting}
                              onClick={(e) => e.stopPropagation()}
                            />
                          </Popconfirm>
                        ) : (
                          <Button
                            key="del-disabled"
                            size="small"
                            disabled
                            icon={<DeleteOutlined />}
                            title="只能从最新章节开始往前删除"
                            onClick={(e) => e.stopPropagation()}
                          />
                        ),
                      ]}
                    >
                      <Space>
                        <BookOutlined />
                        <span>第{chNum}章</span>
                        <Tag>{ch.words?.toLocaleString() || 0}字</Tag>
                        {isLatest && <Tag color="green">最新</Tag>}
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
          extra={
            chapterContent ? (
              <Space>
                {selectedChapter && latestRef?.ref === selectedChapter && (
                  <Popconfirm
                    title="确认删除"
                    description="删除当前章节将回滚伏笔、角色状态和阶段进度。"
                    onConfirm={() => {
                      if (selectedChapter) {
                        const [vol, ch] = selectedChapter.split('/')
                        handleDelete(vol, ch)
                      }
                    }}
                    okText="确认删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button size="small" danger icon={<DeleteOutlined />} loading={deleting}>
                      删除本章
                    </Button>
                  </Popconfirm>
                )}
                <Button
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => {
                    navigator.clipboard.writeText(chapterContent).then(() => {
                      message.success('已复制章节内容')
                    }).catch(() => {
                      message.error('复制失败')
                    })
                  }}
                >
                  复制
                </Button>
              </Space>
            ) : null
          }
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
