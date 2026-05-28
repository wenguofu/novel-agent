import React, { useState, useEffect } from 'react'
import { Card, InputNumber, Button, Space, Tabs, Alert, message, Input } from 'antd'
import { RobotOutlined, SaveOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'
import ReactMarkdown from 'react-markdown'

export const Outlines: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [volume, setVolume] = useState(1)
  const [content, setContent] = useState('')
  const [, setLoading] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('edit')

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const vol = `vol-${String(volume).padStart(2, '0')}`
      const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel)}/outline/${vol}`)
      const data = await resp.json()
      setContent(data.content || data.outline || '')
    } catch { setContent('') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [currentNovel, volume])

  const handleSave = async () => {
    const vol = `vol-${String(volume).padStart(2, '0')}`
    await fetch(`/api/novels/${encodeURIComponent(currentNovel!)}/outline/${vol}`, {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ content })
    })
    message.success('保存成功')
  }

  const handleAIGenerate = async () => {
    setAiLoading(true)
    try {
      const resp = await fetch('/api/ai/chat', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          system: '你是一个专业的网文大纲策划师。请为小说生成详细的大纲。',
          user: `请为第${volume}卷生成详细章节大纲。`,
          model: 'deepseek-chat',
        })
      })
      const data = await resp.json()
      if (data.content) setContent(data.content)
      message.success('大纲生成完成')
    } catch { message.error('生成失败') }
    finally { setAiLoading(false) }
  }

  return (
    <div>
      <h2>大纲管理</h2>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <span>卷：</span>
          <InputNumber min={1} value={volume} onChange={v => { setVolume(v || 1); setActiveTab('edit') }} />
          <Button icon={<SaveOutlined />} onClick={handleSave} disabled={!currentNovel}>保存</Button>
          <Button icon={<RobotOutlined />} onClick={handleAIGenerate} loading={aiLoading} disabled={!currentNovel}>
            AI 生成本卷大纲
          </Button>
        </Space>

        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          {
            key: 'edit', label: '✏️ 编辑',
            children: <Input.TextArea value={content} onChange={e => setContent(e.target.value)}
              rows={20} style={{ fontFamily: 'monospace' }} placeholder="编写或粘贴大纲内容..." />,
          },
          {
            key: 'preview', label: '📐 预览',
            children: content
              ? <div className="markdown-body" style={{ padding: 16, maxHeight: '60vh', overflow: 'auto' }}>
                  <ReactMarkdown>{content}</ReactMarkdown>
                </div>
              : <Alert message="暂无内容" type="info" showIcon />,
          },
        ]} />
      </Card>
    </div>
  )
}
