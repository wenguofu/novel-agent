import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Select, Table, Tag, Modal, Input, message } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface WBItem {
  id: number; domain: string; name: string; content: string; tags?: string
}

const DOMAIN_COLORS: Record<string, string> = {
  '地理': 'green', '势力': 'red', '魔法': 'purple', '科技': 'blue',
  '历史': 'orange', '种族': 'cyan', '文化': 'magenta', '其他': 'default',
}

export const WorldBuilding: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [items, setItems] = useState<WBItem[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<WBItem | null>(null)
  const [form, setForm] = useState({ domain: '其他', name: '', content: '', tags: '' })

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/world_building/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.world_building) ? data.world_building : Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []
      setItems(list)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [currentNovel])

  const handleSave = async () => {
    const url = editing
      ? `/api/world_building/${encodeURIComponent(currentNovel!)}/${editing.id}`
      : `/api/world_building/${encodeURIComponent(currentNovel!)}`
    const method = editing ? 'PUT' : 'POST'
    await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) })
    message.success(editing ? '已更新' : '已添加')
    setModalOpen(false); setEditing(null); load()
  }

  const handleDelete = async (id: number) => {
    await fetch(`/api/world_building/${encodeURIComponent(currentNovel!)}/${id}`, { method: 'DELETE' })
    message.success('已删除'); load()
  }

  const openEdit = (item: WBItem) => {
    setEditing(item)
    setForm({ domain: item.domain, name: item.name, content: item.content, tags: item.tags || '' })
    setModalOpen(true)
  }

  const columns = [
    { title: '领域', dataIndex: 'domain', key: 'domain', width: 80, render: (d: string) => <Tag color={DOMAIN_COLORS[d] || 'default'}>{d}</Tag> },
    { title: '名称', dataIndex: 'name', key: 'name', width: 120 },
    { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
    { title: '标签', dataIndex: 'tags', key: 'tags', width: 150, render: (t: string) => t ? t.split(',').map((tag: string) => <Tag key={tag}>{tag.trim()}</Tag>) : null },
    {
      title: '操作', key: 'actions', width: 120,
      render: (_: any, r: WBItem) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)} />
        </Space>
      ),
    },
  ]

  return (
    <div>
      <h2>世界观管理</h2>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setForm({ domain: '其他', name: '', content: '', tags: '' }); setModalOpen(true) }}>添加条目</Button>
        </Space>
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>

      <Modal title={editing ? '编辑条目' : '添加条目'} open={modalOpen} onOk={handleSave} onCancel={() => setModalOpen(false)} width={600}>
        <Space style={{ width: '100%' }}>
          <Select value={form.domain} onChange={v => setForm({ ...form, domain: v })}
            options={['地理', '势力', '魔法', '科技', '历史', '种族', '文化', '其他'].map(d => ({ value: d, label: d }))}
            style={{ width: '100%' }} />
          <Input placeholder="名称" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
          <Input.TextArea placeholder="内容描述" value={form.content} onChange={e => setForm({ ...form, content: e.target.value })} rows={4} />
          <Input placeholder="标签（逗号分隔）" value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} />
        </Space>
      </Modal>
    </div>
  )
}
