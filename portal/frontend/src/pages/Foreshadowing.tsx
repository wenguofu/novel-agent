import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Select, Table, Tag, Modal, Input, message } from 'antd'
import { PlusOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface Foreshadow {
  id: number; name: string; description?: string; category: string
  status: string; introduced_vol?: number; introduced_ch?: number
  target_vol?: number; target_ch?: number; priority: string
}

const CAT_COLORS: Record<string, string> = { '剧情': 'blue', '角色': 'green', '世界观': 'purple', '身份': 'orange', '能力': 'red' }
const PRI_COLORS: Record<string, string> = { 'high': 'red', 'normal': 'orange', 'low': 'default' }

export const Foreshadowing: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [items, setItems] = useState<Foreshadow[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [form, setForm] = useState({ name: '', description: '', category: '剧情', priority: 'normal', target_vol: 1, target_ch: 1 })

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/foreshadowing/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.foreshadowing) ? data.foreshadowing : Array.isArray(data) ? data : []
      setItems(list)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [currentNovel])

  const handleSave = async () => {
    await fetch(`/api/foreshadowing/${encodeURIComponent(currentNovel!)}`, {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(form)
    })
    message.success('已添加')
    setModalOpen(false)
    load()
  }

  const handleResolve = async (id: number) => {
    await fetch(`/api/foreshadowing/${encodeURIComponent(currentNovel!)}/resolve/${id}`, { method: 'POST' })
    message.success('已填坑')
    load()
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '分类', dataIndex: 'category', key: 'cat', render: (c: string) => <Tag color={CAT_COLORS[c] || 'default'}>{c}</Tag> },
    { title: '优先级', dataIndex: 'priority', key: 'pri', render: (p: string) => <Tag color={PRI_COLORS[p] || 'default'}>{p === 'high' ? '高' : p === 'normal' ? '中' : '低'}</Tag> },
    { title: '状态', dataIndex: 'status', key: 'st', render: (s: string) => <Tag color={s === 'resolved' ? 'success' : s === 'abandoned' ? 'default' : 'processing'}>{s === 'resolved' ? '已填' : s === 'abandoned' ? '放弃' : '待填'}</Tag> },
    { title: '目标', key: 'target', render: (_: any, r: Foreshadow) => r.target_vol ? `vol-${r.target_vol} ch-${r.target_ch}` : '-' },
    { title: '操作', key: 'act', render: (_: any, r: Foreshadow) => r.status === 'pending' ? (
      <Button size="small" type="primary" icon={<CheckCircleOutlined />} onClick={() => handleResolve(r.id)}>填坑</Button>
    ) : null },
  ]

  return (
    <div>
      <h2>伏笔管理</h2>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setForm({ name: '', description: '', category: '剧情', priority: 'normal', target_vol: 1, target_ch: 1 }); setModalOpen(true) }}>添加伏笔</Button>
        </Space>
        <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
      </Card>

      <Modal title="添加伏笔" open={modalOpen} onOk={handleSave} onCancel={() => setModalOpen(false)}>
        <Space style={{ width: '100%' }}>
          <Input placeholder="名称" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
          <Input.TextArea placeholder="描述" value={form.description} onChange={e => setForm({...form, description: e.target.value})} rows={3} />
          <Select value={form.category} onChange={v => setForm({...form, category: v})}
            options={['剧情','角色','世界观','身份','能力'].map(c => ({ value: c, label: c }))} style={{ width: '100%' }} />
          <Select value={form.priority} onChange={v => setForm({...form, priority: v})}
            options={[{value:'high',label:'高'},{value:'normal',label:'中'},{value:'low',label:'低'}]} style={{ width: '100%'}} />
        </Space>
      </Modal>
    </div>
  )
}
