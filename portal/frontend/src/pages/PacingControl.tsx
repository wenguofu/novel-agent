import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Select, Table, Tag, Modal, Input, InputNumber, message, Progress } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface Pace { id: number; volume: number; chapter_start: number; chapter_end: number; pace_type: string; intensity: number; emotion_target?: string }

const PACE_COLORS: Record<string, string> = { '高潮': 'red', '过渡': 'blue', '铺垫': 'orange', '释缓': 'green' }

export const PacingControl: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const [items, setItems] = useState<Pace[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Pace | null>(null)
  const [form, setForm] = useState({ volume: 1, chapter_start: 1, chapter_end: 5, pace_type: '过渡', intensity: 5, emotion_target: '' })

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/pacing/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.pacing) ? data.pacing : Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []
      setItems(list)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [currentNovel])

  const handleSave = async () => {
    const url = editing
      ? `/api/pacing/${encodeURIComponent(currentNovel!)}/${editing.id}`
      : `/api/pacing/${encodeURIComponent(currentNovel!)}`
    await fetch(url, { method: editing ? 'PUT' : 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(form) })
    message.success(editing ? '已更新' : '已添加')
    setModalOpen(false); setEditing(null); load()
  }

  const handleDelete = async (id: number) => {
    await fetch(`/api/pacing/${encodeURIComponent(currentNovel!)}/${id}`, { method: 'DELETE' })
    message.success('已删除'); load()
  }

  const columns = [
    { title: '卷', dataIndex: 'volume', key: 'vol', width: 60 },
    { title: '章节', key: 'range', render: (_:any, r:Pace) => `${r.chapter_start}-${r.chapter_end}` },
    { title: '节奏', dataIndex: 'pace_type', key: 'type', render: (t: string) => <Tag color={PACE_COLORS[t] || 'default'}>{t}</Tag> },
    { title: '强度', dataIndex: 'intensity', key: 'int', render: (v: number) => <Progress percent={v * 10} size="small" style={{ width: 80 }} /> },
    { title: '情绪', dataIndex: 'emotion_target', key: 'emo', ellipsis: true },
    { title: '操作', key: 'act', render: (_:any, r:Pace) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => { setEditing(r); setForm({ volume: r.volume, chapter_start: r.chapter_start, chapter_end: r.chapter_end, pace_type: r.pace_type, intensity: r.intensity, emotion_target: r.emotion_target||'' }); setModalOpen(true) }} />
        <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)} />
      </Space>
    )},
  ]

  return (
    <div>
      <h2>节奏控制</h2>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setForm({ volume:1, chapter_start:1, chapter_end:5, pace_type:'过渡', intensity:5, emotion_target:'' }); setModalOpen(true) }}>添加节奏</Button>
        </Space>
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>
      <Modal title={editing ? '编辑节奏' : '添加节奏'} open={modalOpen} onOk={handleSave} onCancel={() => setModalOpen(false)}>
        <Space style={{ width: '100%' }}>
          <Space><span>卷:</span><InputNumber min={1} value={form.volume} onChange={v => setForm({...form, volume: v||1})} />
            <span>起:</span><InputNumber min={1} value={form.chapter_start} onChange={v => setForm({...form, chapter_start: v||1})} />
            <span>止:</span><InputNumber min={1} value={form.chapter_end} onChange={v => setForm({...form, chapter_end: v||1})} /></Space>
          <Select value={form.pace_type} onChange={v => setForm({...form, pace_type: v})}
            options={['高潮','过渡','铺垫','释缓'].map(p => ({ value: p, label: p }))} style={{ width: '100%' }} />
          <span>强度 (1-10):</span><InputNumber min={1} max={10} value={form.intensity} onChange={v => setForm({...form, intensity: v||5})} />
          <Input placeholder="情绪目标" value={form.emotion_target} onChange={e => setForm({...form, emotion_target: e.target.value})} />
        </Space>
      </Modal>
    </div>
  )
}
