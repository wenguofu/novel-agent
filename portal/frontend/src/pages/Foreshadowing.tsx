import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Table, Tag, Modal, Input, message, Statistic, Row, Col, Select, Badge, Progress, Tooltip } from 'antd'
import { PlusOutlined, CheckCircleOutlined, EyeOutlined, WarningOutlined, FilterOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface Foreshadow {
  id: number; name: string; description?: string; category: string
  status: string; introduced_vol?: number; introduced_ch?: number
  target_vol?: number; target_ch?: number; priority: string
  resolved_vol?: number; resolved_ch?: number; resolution_note?: string
  hint_method?: string; reveal_method?: string; is_dark?: boolean
}

const CAT_COLORS: Record<string, string> = {
  '剧情': 'blue', '角色': 'green', '世界观': 'purple',
  '身份': 'orange', '能力': 'red', '感情': 'magenta',
}
const CAT_OPTIONS = ['全部', '剧情', '角色', '世界观', '身份', '能力', '感情']
const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待填坑' },
  { value: 'pending_confirmation', label: '待确认' },
  { value: 'resolved', label: '已填坑' },
  { value: 'abandoned', label: '已放弃' },
]

export const Foreshadowing: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [items, setItems] = useState<Foreshadow[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Foreshadow | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [selectedItem, setSelectedItem] = useState<Foreshadow | null>(null)
  const [filterCat, setFilterCat] = useState('全部')
  const [filterStatus, setFilterStatus] = useState('')
  const [form, setForm] = useState({
    name: '', description: '', category: '剧情',
    priority: 'normal', target_vol: 1, target_ch: 1,
    hint_method: '', reveal_method: '', is_dark: false,
  })

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/foreshadowing/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.foreshadowing) ? data.foreshadowing :
                   Array.isArray(data) ? data : []
      setItems(list)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [currentNovel])

  const handleSave = async () => {
    const url = editing
      ? `/api/foreshadowing/${encodeURIComponent(currentNovel!)}/${editing.id}`
      : `/api/foreshadowing/${encodeURIComponent(currentNovel!)}`
    const method = editing ? 'PUT' : 'POST'
    const resp = await fetch(url, {
      method, headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    const data = await resp.json()
    if (data.success) {
      message.success(editing ? '已更新' : '已添加')
      setModalOpen(false); setEditing(null); load()
    } else {
      message.error(data.error || '保存失败')
    }
  }

  const handleResolve = async (id: number) => {
    await fetch(`/api/foreshadowing/${encodeURIComponent(currentNovel!)}/resolve/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ vol: 1, ch: 1, note: '手动标记已填坑' }),
    })
    message.success('已填坑'); load()
  }

  const handleBatchResolve = async () => {
    const pending = items.filter(i => i.status === 'pending' || i.status === 'pending_confirmation')
    if (pending.length === 0) { message.info('没有待处理的伏笔'); return }
    for (const item of pending.slice(0, 10)) {
      await fetch(`/api/foreshadowing/${encodeURIComponent(currentNovel!)}/resolve/${item.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vol: item.target_vol || 1, ch: item.target_ch || 1, note: '批量标记' }),
      })
    }
    message.success(`已处理 ${pending.length} 条伏笔`); load()
  }

  const handleDelete = async (id: number) => {
    await fetch(`/api/foreshadowing/${encodeURIComponent(currentNovel!)}/${id}`, { method: 'DELETE' })
    message.success('已删除'); load()
  }

  // Stats
  const filtered = items.filter(i => {
    if (filterCat !== '全部' && i.category !== filterCat) return false
    if (filterStatus && i.status !== filterStatus) return false
    return true
  })
  const resolved = items.filter(i => i.status === 'resolved').length
  const pending = items.filter(i => i.status === 'pending' || i.status === 'pending_confirmation').length
  const pct = items.length > 0 ? Math.round((resolved / items.length) * 100) : 0

  const columns = [
    {
      title: '名称', dataIndex: 'name', key: 'name', width: 180,
      render: (t: string, r: Foreshadow) => (
        <Space size={4}>
          {r.priority === 'high' && <Tooltip title="高优先级"><WarningOutlined style={{ color: '#ff4d4f', fontSize: 12 }} /></Tooltip>}
          <a onClick={() => { setSelectedItem(r); setDetailOpen(true) }}>{t}</a>
          {r.is_dark && <Tag color="default" style={{ fontSize: 10 }}>暗线</Tag>}
        </Space>
      ),
    },
    { title: '分类', dataIndex: 'category', key: 'cat', width: 80,
      render: (c: string) => <Tag color={CAT_COLORS[c] || 'default'}>{c}</Tag> },
    {
      title: '状态', dataIndex: 'status', key: 'st', width: 80,
      render: (s: string, r: Foreshadow) => {
        if (s === 'resolved') return <Tag color="success">已填坑</Tag>
        if (s === 'abandoned') return <Tag color="default">已放弃</Tag>
        if (s === 'pending_confirmation') return <Tag color="warning">待确认</Tag>
        // Check if target chapter has passed
        const passed = r.target_vol && r.target_vol > 0 && r.target_ch && r.target_ch > 0
        if (passed) {
          return <Tooltip title={`目标: 第${r.target_vol}卷第${r.target_ch}章`}>
            <Tag color="processing">待填坑 <Badge status="warning" /></Tag>
          </Tooltip>
        }
        return <Tag color="processing">待填坑</Tag>
      },
    },
    {
      title: '引入 → 目标', key: 'pos', width: 130,
      render: (_: any, r: Foreshadow) => (
        <Space size={2}>
          {r.introduced_vol ? <span style={{ fontSize: 11, color: '#999' }}>v{r.introduced_vol}c{r.introduced_ch}</span> : '-'}
          <span style={{ color: '#999' }}>→</span>
          {r.target_vol ? <span style={{ fontSize: 11, fontWeight: 500 }}>v{r.target_vol}c{r.target_ch}</span> : '-'}
        </Space>
      ),
    },
    {
      title: '操作', key: 'act', width: 160,
      render: (_: any, r: Foreshadow) => (
        <Space size="small">
          {r.status !== 'resolved' && (
            <Button size="small" type="primary" icon={<CheckCircleOutlined />} onClick={() => handleResolve(r.id)}>
              填坑
            </Button>
          )}
          <Button size="small" icon={<EyeOutlined />}
            onClick={() => { setSelectedItem(r); setDetailOpen(true) }}>
            详情
          </Button>
          <Button size="small" danger onClick={() => handleDelete(r.id)}>删</Button>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <h2>伏笔管理</h2>

      {/* Stats overview */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={5}>
          <Card size="small">
            <Statistic title="总伏笔" value={items.length} suffix="条" />
          </Card>
        </Col>
        <Col span={5}>
          <Card size="small">
            <Statistic title="待填坑" value={pending} suffix="条"
              valueStyle={{ color: pending > 3 ? '#faad14' : undefined }} />
          </Card>
        </Col>
        <Col span={5}>
          <Card size="small">
            <Statistic title="已填坑" value={resolved} suffix="条"
              valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={9}>
          <Card size="small">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 12, color: '#666' }}>完成率</span>
              <Progress percent={pct} size="small" style={{ flex: 1, margin: 0 }}
                status={pct > 80 ? 'success' : pct > 40 ? 'active' : 'normal'} />
            </div>
          </Card>
        </Col>
      </Row>

      <Card>
        <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Button type="primary" icon={<PlusOutlined />}
              onClick={() => {
                setEditing(null)
                setForm({ name: '', description: '', category: '剧情', priority: 'normal',
                  target_vol: 1, target_ch: 1, hint_method: '', reveal_method: '', is_dark: false })
                setModalOpen(true)
              }}>
              添加伏笔
            </Button>
            <Button onClick={handleBatchResolve} disabled={pending === 0}>批量填坑</Button>
          </Space>

          <Space>
            <FilterOutlined />
            <Select size="small" value={filterCat}
              onChange={v => setFilterCat(v)} style={{ width: 100 }}
              options={CAT_OPTIONS.map(c => ({ value: c, label: c }))} />
            <Select size="small" value={filterStatus}
              onChange={v => setFilterStatus(v)} style={{ width: 110 }}
              options={STATUS_OPTIONS} />
          </Space>
        </Space>

        <Table dataSource={filtered} columns={columns} rowKey="id"
          loading={loading} size="small" pagination={{ pageSize: 30 }}
          scroll={{ x: 700 }} />
      </Card>

      {/* Add/Edit Modal */}
      <Modal
        title={editing ? '编辑伏笔' : '添加伏笔'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        width={560}
        okText="保存"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Input placeholder="名称 *" value={form.name}
            onChange={e => setForm({ ...form, name: e.target.value })} />
          <Input.TextArea placeholder="描述" value={form.description}
            onChange={e => setForm({ ...form, description: e.target.value })} rows={3} />
          <Space wrap>
            <span>分类:</span>
            <Select size="small" value={form.category}
              onChange={v => setForm({ ...form, category: v })} style={{ width: 100 }}
              options={CAT_OPTIONS.filter(c => c !== '全部').map(c => ({ value: c, label: c }))} />
            <span>优先级:</span>
            <Select size="small" value={form.priority}
              onChange={v => setForm({ ...form, priority: v })} style={{ width: 80 }}
              options={[{ value: 'high', label: '高' }, { value: 'normal', label: '中' }, { value: 'low', label: '低' }]} />
          </Space>
          <Space wrap>
            <span>目标卷:</span>
            <Input type="number" min={1} value={form.target_vol}
              onChange={e => setForm({ ...form, target_vol: parseInt(e.target.value) || 1 })}
              style={{ width: 70 }} />
            <span>目标章:</span>
            <Input type="number" min={1} value={form.target_ch}
              onChange={e => setForm({ ...form, target_ch: parseInt(e.target.value) || 1 })}
              style={{ width: 70 }} />
          </Space>
          <Input placeholder="埋设手法 (hint_method)" value={form.hint_method}
            onChange={e => setForm({ ...form, hint_method: e.target.value })} />
          <Input placeholder="揭示手法 (reveal_method)" value={form.reveal_method}
            onChange={e => setForm({ ...form, reveal_method: e.target.value })} />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={form.is_dark}
              onChange={e => setForm({ ...form, is_dark: e.target.checked })} />
            暗线伏笔（读者不易察觉）
          </label>
        </Space>
      </Modal>

      {/* Detail Modal */}
      <Modal
        title={selectedItem ? `伏笔详情 — ${selectedItem.name}` : ''}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={500}
      >
        {selectedItem && (
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <div>
              <Tag color={CAT_COLORS[selectedItem.category] || 'default'}>{selectedItem.category}</Tag>
              <Tag color={selectedItem.priority === 'high' ? 'red' : selectedItem.priority === 'normal' ? 'orange' : 'default'}>
                {selectedItem.priority === 'high' ? '高优先级' : selectedItem.priority === 'normal' ? '中优先级' : '低优先级'}
              </Tag>
              <Tag color={selectedItem.status === 'resolved' ? 'success' : selectedItem.status === 'abandoned' ? 'default' : 'processing'}>
                {selectedItem.status === 'resolved' ? '已填坑' : selectedItem.status === 'abandoned' ? '已放弃' : selectedItem.status === 'pending_confirmation' ? '待确认' : '待填坑'}
              </Tag>
              {selectedItem.is_dark && <Tag color="default">暗线</Tag>}
            </div>
            <p><strong>描述:</strong> {selectedItem.description || '(无)'}</p>
            {selectedItem.introduced_vol && selectedItem.introduced_vol > 0 && (
              <p>引入: 第{selectedItem.introduced_vol}卷第{selectedItem.introduced_ch}章</p>
            )}
            {selectedItem.target_vol && selectedItem.target_vol > 0 && (
              <p>计划填坑: 第{selectedItem.target_vol}卷第{selectedItem.target_ch}章</p>
            )}
            {selectedItem.resolved_vol && selectedItem.resolved_vol > 0 && (
              <p>已填坑: 第{selectedItem.resolved_vol}卷第{selectedItem.resolved_ch}章</p>
            )}
            {selectedItem.resolution_note && (
              <p><strong>填坑说明:</strong> {selectedItem.resolution_note}</p>
            )}
            {selectedItem.hint_method && (
              <p><strong>埋设手法:</strong> {selectedItem.hint_method}</p>
            )}
            {selectedItem.reveal_method && (
              <p><strong>揭示手法:</strong> {selectedItem.reveal_method}</p>
            )}
          </Space>
        )}
      </Modal>
    </div>
  )
}
