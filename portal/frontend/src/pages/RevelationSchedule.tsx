import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Select, Table, Tag, Modal, Input, InputNumber, message, Switch } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface Rev { id: number; name: string; info_type: string; reveal_volume: number; reveal_chapter: number; content?: string; audience_knows?: boolean; protagonist_knows?: boolean }

const INFO_COLORS: Record<string, string> = { '角色秘密': 'magenta', '伏笔揭示': 'orange', '世界观': 'purple', '剧情转折': 'red' }

export const RevelationSchedule: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const [items, setItems] = useState<Rev[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Rev | null>(null)
  const [form, setForm] = useState({ name: '', info_type: '角色秘密', reveal_volume: 1, reveal_chapter: 1, content: '', audience_knows: false, protagonist_knows: false })

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/revelation/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.revelation) ? data.revelation : Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []
      setItems(list)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [currentNovel])

  const handleSave = async () => {
    const url = editing
      ? `/api/revelation/${encodeURIComponent(currentNovel!)}/${editing.id}`
      : `/api/revelation/${encodeURIComponent(currentNovel!)}`
    await fetch(url, { method: editing ? 'PUT' : 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(form) })
    message.success(editing ? '已更新' : '已添加')
    setModalOpen(false); setEditing(null); load()
  }

  const handleDelete = async (id: number) => {
    await fetch(`/api/revelation/${encodeURIComponent(currentNovel!)}/${id}`, { method: 'DELETE' })
    message.success('已删除'); load()
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '类型', dataIndex: 'info_type', key: 'type', render: (t: string) => <Tag color={INFO_COLORS[t] || 'default'}>{t}</Tag> },
    { title: '揭示位置', key: 'pos', render: (_:any, r:Rev) => `vol-${r.reveal_volume} ch-${r.reveal_chapter}` },
    { title: '读者已知', dataIndex: 'audience_knows', key: 'aud', render: (v: boolean) => v ? <Tag color="green">是</Tag> : <Tag>否</Tag> },
    { title: '主角已知', dataIndex: 'protagonist_knows', key: 'prot', render: (v: boolean) => v ? <Tag color="green">是</Tag> : <Tag>否</Tag> },
    { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
    { title: '操作', key: 'act', render: (_:any, r:Rev) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => { setEditing(r); setForm({ name: r.name, info_type: r.info_type, reveal_volume: r.reveal_volume, reveal_chapter: r.reveal_chapter, content: r.content||'', audience_knows: !!r.audience_knows, protagonist_knows: !!r.protagonist_knows }); setModalOpen(true) }} />
        <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)} />
      </Space>
    )},
  ]

  return (
    <div>
      <h2>信息释放</h2>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setForm({ name:'', info_type:'角色秘密', reveal_volume:1, reveal_chapter:1, content:'', audience_knows:false, protagonist_knows:false }); setModalOpen(true) }}>添加释放点</Button>
        </Space>
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>
      <Modal title={editing ? '编辑释放点' : '添加释放点'} open={modalOpen} onOk={handleSave} onCancel={() => setModalOpen(false)} width={500}>
        <Space style={{ width: '100%' }}>
          <Input placeholder="名称" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
          <Select value={form.info_type} onChange={v => setForm({...form, info_type: v})}
            options={['角色秘密','伏笔揭示','世界观','剧情转折'].map(t => ({ value: t, label: t }))} style={{ width: '100%' }} />
          <Space><span>揭示卷:</span><InputNumber min={1} value={form.reveal_volume} onChange={v => setForm({...form, reveal_volume: v||1})} />
            <span>章:</span><InputNumber min={1} value={form.reveal_chapter} onChange={v => setForm({...form, reveal_chapter: v||1})} /></Space>
          <Input.TextArea placeholder="内容" value={form.content} onChange={e => setForm({...form, content: e.target.value})} rows={3} />
          <Space>
            <span>读者已知:</span><Switch checked={form.audience_knows} onChange={v => setForm({...form, audience_knows: v})} />
            <span>主角已知:</span><Switch checked={form.protagonist_knows} onChange={v => setForm({...form, protagonist_knows: v})} />
          </Space>
        </Space>
      </Modal>
    </div>
  )
}
