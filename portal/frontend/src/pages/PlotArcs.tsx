import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Table, Tag, Modal, Input, InputNumber, message, Progress, Select } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface Arc {
  id: number; name: string; type: string
  volume_start?: number; chapter_start?: number
  volume_end?: number; chapter_end?: number
  summary?: string; status: string; milestones?: string; priority?: string
}

const TYPE_COLORS: Record<string, string> = { '主线': 'red', '支线': 'blue', '感情线': 'magenta', '成长线': 'green' }
const TYPE_OPTIONS = ['主线', '支线', '感情线', '成长线']

export const PlotArcs: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const [items, setItems] = useState<Arc[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Arc | null>(null)
  const [form, setForm] = useState({
    name: '', type: '支线', volume_start: 1, chapter_start: 1,
    volume_end: 3, chapter_end: 1, summary: '', status: 'active', priority: 'normal', milestones: '',
  })

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/plot_arcs/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.plot_arcs) ? data.plot_arcs :
                   Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []
      setItems(list)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [currentNovel])

  const handleSave = async () => {
    const url = editing
      ? `/api/plot_arcs/${encodeURIComponent(currentNovel!)}/${editing.id}`
      : `/api/plot_arcs/${encodeURIComponent(currentNovel!)}`
    const resp = await fetch(url, {
      method: editing ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    const data = await resp.json()
    if (data.success) {
      message.success(editing ? '已更新' : '已添加')
      setModalOpen(false); setEditing(null)
      load()
    } else {
      message.error(data.error || '保存失败')
    }
  }

  const handleDelete = async (id: number) => {
    await fetch(`/api/plot_arcs/${encodeURIComponent(currentNovel!)}/${id}`, { method: 'DELETE' })
    message.success('已删除'); load()
  }

  // Get max volume for progress calculation
  const maxVol = Math.max(...items.map(i => i.volume_end || 1), 1)

  const columns = [
    {
      title: '弧线', dataIndex: 'name', key: 'name', width: 140,
      render: (t: string, r: Arc) => (
        <Space direction="vertical" size={0}>
          <strong>{t}</strong>
          {r.priority === 'high' && <Tag color="red" style={{ fontSize: 10 }}>高优先</Tag>}
        </Space>
      ),
    },
    {
      title: '类型', dataIndex: 'type', key: 'type', width: 70,
      render: (t: string) => <Tag color={TYPE_COLORS[t] || 'default'}>{t}</Tag>,
    },
    {
      title: '进度', key: 'progress', width: 200,
      render: (_: any, r: Arc) => {
        const start = r.volume_start || 1
        const end = r.volume_end || start
        const totalVols = Math.max(1, end - start + 1)
        const doneVols = r.status === 'completed' ? totalVols : 0
        const pct = Math.round((doneVols / totalVols) * 100)
        return (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
              <span>第{start}卷</span>
              <span>第{end}卷</span>
            </div>
            <Progress percent={pct} size="small"
              status={r.status === 'completed' ? 'success' : 'active'}
              style={{ margin: 0 }} />
          </div>
        )
      },
    },
    {
      title: '状态', dataIndex: 'status', key: 'st', width: 80,
      render: (s: string) => (
        <Tag color={s === 'completed' ? 'success' : s === 'active' ? 'processing' : 'default'}>
          {s === 'completed' ? '完成' : s === 'active' ? '进行中' : s}
        </Tag>
      ),
    },
    {
      title: '摘要', dataIndex: 'summary', key: 'summary', ellipsis: true,
    },
    {
      title: '操作', key: 'act', width: 120,
      render: (_: any, r: Arc) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => {
            setEditing(r)
            setForm({
              name: r.name, type: r.type,
              volume_start: r.volume_start || 1, chapter_start: r.chapter_start || 1,
              volume_end: r.volume_end || 1, chapter_end: r.chapter_end || 1,
              summary: r.summary || '', status: r.status, priority: r.priority || 'normal',
              milestones: r.milestones || '',
            })
            setModalOpen(true)
          }} />
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)} />
        </Space>
      ),
    },
  ]

  // Vol timeline visualization
  const timelineData: { vol: number; arcs: string[] }[] = []
  if (items.length > 0) {
    for (let v = 1; v <= maxVol; v++) {
      const arcsHere = items
        .filter(a => (a.volume_start || 1) <= v && (a.volume_end || a.volume_start || 1) >= v)
        .map(a => a.name)
      timelineData.push({ vol: v, arcs: arcsHere })
    }
  }

  return (
    <div>
      <h2>剧情弧线</h2>

      {/* Volume timeline */}
      {timelineData.length > 0 && (
        <Card title="卷级弧线分布" size="small" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', gap: 4, overflowX: 'auto', padding: '8px 0' }}>
            {timelineData.map(({ vol, arcs }) => (
              <TooltipContent key={vol} vol={vol} arcs={arcs} />
            ))}
          </div>
        </Card>
      )}

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => {
            setEditing(null)
            setForm({
              name: '', type: '支线', volume_start: 1, chapter_start: 1,
              volume_end: 3, chapter_end: 1, summary: '', status: 'active',
              priority: 'normal', milestones: '',
            })
            setModalOpen(true)
          }}>
            添加弧线
          </Button>
        </Space>
        <Table dataSource={items} columns={columns} rowKey="id"
          loading={loading} size="small" pagination={{ pageSize: 50 }} />
      </Card>

      <Modal title={editing ? '编辑弧线' : '添加弧线'} open={modalOpen}
        onOk={handleSave} onCancel={() => setModalOpen(false)} width={560} okText="保存">
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Input placeholder="名称 *" value={form.name}
            onChange={e => setForm({ ...form, name: e.target.value })} />
          <Space wrap>
            <span>类型:</span>
            <Select value={form.type} onChange={v => setForm({ ...form, type: v })}
              style={{ width: 100 }}
              options={TYPE_OPTIONS.map(t => ({ value: t, label: t }))} />
            <span>优先级:</span>
            <Select value={form.priority} onChange={v => setForm({ ...form, priority: v })}
              style={{ width: 80 }}
              options={[
                { value: 'high', label: '高' }, { value: 'normal', label: '中' },
                { value: 'low', label: '低' },
              ]} />
            <span>状态:</span>
            <Select value={form.status} onChange={v => setForm({ ...form, status: v })}
              style={{ width: 100 }}
              options={[
                { value: 'active', label: '进行中' }, { value: 'completed', label: '已完成' },
                { value: 'planned', label: '规划中' },
              ]} />
          </Space>
          <Space>
            <span>起始:</span>
            <span>卷</span><InputNumber size="small" min={1} value={form.volume_start}
              onChange={v => setForm({ ...form, volume_start: v || 1 })} style={{ width: 60 }} />
            <span>章</span><InputNumber size="small" min={1} value={form.chapter_start}
              onChange={v => setForm({ ...form, chapter_start: v || 1 })} style={{ width: 60 }} />
            <span>→ 结束:</span>
            <span>卷</span><InputNumber size="small" min={1} value={form.volume_end}
              onChange={v => setForm({ ...form, volume_end: v || 1 })} style={{ width: 60 }} />
            <span>章</span><InputNumber size="small" min={1} value={form.chapter_end}
              onChange={v => setForm({ ...form, chapter_end: v || 1 })} style={{ width: 60 }} />
          </Space>
          <Input.TextArea placeholder="摘要" value={form.summary}
            onChange={e => setForm({ ...form, summary: e.target.value })} rows={2} />
          <Input.TextArea placeholder="里程碑 (JSON数组)" value={form.milestones}
            onChange={e => setForm({ ...form, milestones: e.target.value })} rows={2} />
        </Space>
      </Modal>
    </div>
  )
}

const TooltipContent: React.FC<{ vol: number; arcs: string[] }> = ({ vol, arcs }) => {
  const color = arcs.length >= 3 ? '#ff4d4f' : arcs.length >= 2 ? '#faad14' : '#1677ff'
  return (
    <div style={{
      minWidth: 36, textAlign: 'center', cursor: 'pointer',
      padding: '6px 4px', borderRadius: 4, background: arcs.length > 0 ? color : '#f5f5f5',
      color: arcs.length > 0 ? '#fff' : '#999', fontSize: 11, transition: 'all 0.2s',
    }} title={`第${vol}卷: ${arcs.join(', ') || '无弧线'}`}>
      <div style={{ fontWeight: 600 }}>{vol}</div>
      {arcs.length > 0 && <div style={{ fontSize: 9 }}>{arcs.length}条</div>}
    </div>
  )
}
