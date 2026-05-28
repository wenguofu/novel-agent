import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Select, Table, Tag, Modal, Input, InputNumber, message } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface Arc { id: number; name: string; type: string; volume_start?: number; volume_end?: number; summary?: string; status: string }

const TYPE_COLORS: Record<string, string> = { '主线': 'red', '支线': 'blue', '感情线': 'magenta' }

export const PlotArcs: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const [items, setItems] = useState<Arc[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Arc | null>(null)
  const [form, setForm] = useState({ name: '', type: '支线', volume_start: 1, volume_end: 1, summary: '', status: 'active' })

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/plot_arcs/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.plot_arcs) ? data.plot_arcs : Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []
      setItems(list)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [currentNovel])

  const handleSave = async () => {
    const url = editing
      ? `/api/plot_arcs/${encodeURIComponent(currentNovel!)}/${editing.id}`
      : `/api/plot_arcs/${encodeURIComponent(currentNovel!)}`
    await fetch(url, { method: editing ? 'PUT' : 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(form) })
    message.success(editing ? '已更新' : '已添加')
    setModalOpen(false); setEditing(null); load()
  }

  const handleDelete = async (id: number) => {
    await fetch(`/api/plot_arcs/${encodeURIComponent(currentNovel!)}/${id}`, { method: 'DELETE' })
    message.success('已删除'); load()
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类型', dataIndex: 'type', key: 'type', render: (t: string) => <Tag color={TYPE_COLORS[t] || 'default'}>{t}</Tag> },
    { title: '卷范围', key: 'range', render: (_:any, r:Arc) => r.volume_start ? `vol-${r.volume_start} ~ vol-${r.volume_end || r.volume_start}` : '-' },
    { title: '状态', dataIndex: 'status', key: 'st', render: (s: string) => <Tag color={s === 'completed' ? 'success' : 'processing'}>{s === 'completed' ? '完成' : '进行中'}</Tag> },
    { title: '摘要', dataIndex: 'summary', key: 'summary', ellipsis: true },
    { title: '操作', key: 'act', render: (_:any, r:Arc) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => { setEditing(r); setForm({ name: r.name, type: r.type, volume_start: r.volume_start||1, volume_end: r.volume_end||1, summary: r.summary||'', status: r.status }); setModalOpen(true) }} />
        <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)} />
      </Space>
    )},
  ]

  return (
    <div>
      <h2>剧情弧线</h2>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setForm({ name:'', type:'支线', volume_start:1, volume_end:1, summary:'', status:'active' }); setModalOpen(true) }}>添加弧线</Button>
        </Space>
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>
      <Modal title={editing ? '编辑弧线' : '添加弧线'} open={modalOpen} onOk={handleSave} onCancel={() => setModalOpen(false)} width={500}>
        <Space style={{ width: '100%' }}>
          <Input placeholder="名称" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
          <Select value={form.type} onChange={v => setForm({...form, type: v})}
            options={['主线','支线','感情线'].map(t => ({ value: t, label: t }))} style={{ width: '100%' }} />
          <Space><span>起:</span><InputNumber min={1} value={form.volume_start} onChange={v => setForm({...form, volume_start: v||1})} /><span>止:</span><InputNumber min={1} value={form.volume_end} onChange={v => setForm({...form, volume_end: v||1})} /></Space>
          <Input.TextArea placeholder="摘要" value={form.summary} onChange={e => setForm({...form, summary: e.target.value})} rows={3} />
        </Space>
      </Modal>
    </div>
  )
}
