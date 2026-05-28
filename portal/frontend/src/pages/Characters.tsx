import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Select, Table, Tag, Modal, Input, message } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface Character {
  id: number
  name: string
  role: string
  identity?: string
  personality?: string
  current_status?: string
}

const ROLE_COLORS: Record<string, string> = {
  '主角': 'red', '女主': 'magenta', '反派': 'orange', '配角': 'blue',
}

export const Characters: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [chars, setChars] = useState<Character[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Character | null>(null)
  const [form, setForm] = useState({ name: '', role: '配角', identity: '', personality: '', current_status: '' })

  const loadChars = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/characters/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.characters) ? data.characters : Array.isArray(data) ? data : []
      setChars(list)
    } finally { setLoading(false) }
  }

  useEffect(() => { loadChars() }, [currentNovel])

  const handleSave = async () => {
    const url = editing
      ? `/api/characters/${encodeURIComponent(currentNovel!)}/${editing.id}`
      : `/api/characters/${encodeURIComponent(currentNovel!)}`
    const method = editing ? 'PUT' : 'POST'
    await fetch(url, { method, headers: {'Content-Type':'application/json'}, body: JSON.stringify(form) })
    message.success(editing ? '已更新' : '已添加')
    setModalOpen(false)
    setEditing(null)
    loadChars()
  }

  const handleDelete = async (id: number) => {
    await fetch(`/api/characters/${encodeURIComponent(currentNovel!)}/${id}`, { method: 'DELETE' })
    message.success('已删除')
    loadChars()
  }

  const openEdit = (c: Character) => {
    setEditing(c)
    setForm({ name: c.name, role: c.role, identity: c.identity || '', personality: c.personality || '', current_status: c.current_status || '' })
    setModalOpen(true)
  }

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name' },
    { title: '角色', dataIndex: 'role', key: 'role', render: (r: string) => <Tag color={ROLE_COLORS[r] || 'default'}>{r}</Tag> },
    { title: '身份', dataIndex: 'identity', key: 'identity' },
    { title: '当前状态', dataIndex: 'current_status', key: 'status' },
    { title: '操作', key: 'actions', render: (_: any, r: Character) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
        <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)}>删除</Button>
      </Space>
    )},
  ]

  return (
    <div>
      <h2>人物管理</h2>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setForm({ name: '', role: '配角', identity: '', personality: '', current_status: '' }); setModalOpen(true) }}>
            添加人物
          </Button>
        </Space>
        <Table dataSource={chars} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>

      <Modal title={editing ? '编辑人物' : '添加人物'} open={modalOpen} onOk={handleSave} onCancel={() => setModalOpen(false)}>
        <Space style={{ width: '100%' }}>
          <Input placeholder="姓名" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
          <Select value={form.role} onChange={v => setForm({...form, role: v})}
            options={['主角','女主','反派','配角'].map(r => ({ value: r, label: r }))} style={{ width: '100%' }} />
          <Input placeholder="身份" value={form.identity} onChange={e => setForm({...form, identity: e.target.value})} />
          <Input placeholder="性格" value={form.personality} onChange={e => setForm({...form, personality: e.target.value})} />
          <Input placeholder="当前状态" value={form.current_status} onChange={e => setForm({...form, current_status: e.target.value})} />
        </Space>
      </Modal>
    </div>
  )
}
