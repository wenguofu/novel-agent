import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Table, Tag, Modal, Input, message, Row, Col, Statistic, Select } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, FilterOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface WBItem {
  id: number; domain: string; name: string; content: string; tags?: string; related_vol?: number
}

const DOMAIN_COLORS: Record<string, string> = {
  '地理': 'green', '势力': 'red', '魔法': 'purple', '科技': 'blue',
  '历史': 'orange', '种族': 'cyan', '文化': 'magenta', '规则': 'geekblue',
  '物品': 'gold', '组织': 'volcano', '其他': 'default',
}
const DOMAINS = ['全部', '地理', '势力', '魔法', '科技', '历史', '种族', '文化', '规则', '物品', '组织', '其他']

export const WorldBuilding: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const [items, setItems] = useState<WBItem[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<WBItem | null>(null)
  const [filterDomain, setFilterDomain] = useState('全部')
  const [form, setForm] = useState({ domain: '其他', name: '', content: '', tags: '' })

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/world_building/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.world_building) ? data.world_building :
                   Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []
      setItems(list)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [currentNovel])

  const handleSave = async () => {
    const url = editing
      ? `/api/world_building/${encodeURIComponent(currentNovel!)}/${editing.id}`
      : `/api/world_building/${encodeURIComponent(currentNovel!)}`
    const resp = await fetch(url, {
      method: editing ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
    const data = await resp.json()
    if (data.success) { message.success(editing ? '已更新' : '已添加'); setModalOpen(false); setEditing(null); load() }
    else { message.error(data.error || '保存失败') }
  }

  const handleDelete = async (id: number) => {
    await fetch(`/api/world_building/${encodeURIComponent(currentNovel!)}/${id}`, { method: 'DELETE' })
    message.success('已删除'); load()
  }

  const filtered = filterDomain === '全部' ? items : items.filter(i => i.domain === filterDomain)

  // Domain stats
  const domainCounts: Record<string, number> = {}
  items.forEach(i => { domainCounts[i.domain] = (domainCounts[i.domain] || 0) + 1 })

  const columns = [
    { title: '领域', dataIndex: 'domain', key: 'domain', width: 80,
      render: (d: string) => <Tag color={DOMAIN_COLORS[d] || 'default'}>{d}</Tag> },
    { title: '名称', dataIndex: 'name', key: 'name', width: 130 },
    { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
    { title: '标签', dataIndex: 'tags', key: 'tags', width: 180,
      render: (t: string) => t ? t.split(',').map((tag: string) => <Tag key={tag.trim()} style={{ fontSize: 11 }}>{tag.trim()}</Tag>) : null },
    { title: '关联卷', dataIndex: 'related_vol', key: 'rel', width: 80,
      render: (v: number) => v ? `第${v}卷` : '-' },
    { title: '操作', key: 'actions', width: 100,
      render: (_: any, r: WBItem) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => { setEditing(r); setForm({ domain: r.domain, name: r.name, content: r.content, tags: r.tags || '' }); setModalOpen(true) }} />
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)} />
        </Space>
      )},
  ]

  return (
    <div>
      <h2>世界观管理</h2>

      {/* Domain overview */}
      {Object.keys(domainCounts).length > 0 && (
        <Row gutter={8} style={{ marginBottom: 16 }}>
          {Object.entries(domainCounts).slice(0, 8).map(([domain, count]) => (
            <Col key={domain} span={3}>
              <Card size="small" hoverable
                style={{ textAlign: 'center', background: filterDomain === domain ? '#e6f4ff' : undefined }}
                onClick={() => setFilterDomain(filterDomain === domain ? '全部' : domain)}>
                <Statistic title={<Tag color={DOMAIN_COLORS[domain] || 'default'}>{domain}</Tag>} value={count} suffix="条" valueStyle={{ fontSize: 18 }} />
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <Card>
        <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setForm({ domain: '其他', name: '', content: '', tags: '' }); setModalOpen(true) }}>
            添加条目
          </Button>
          <Space>
            <FilterOutlined />
            <Select size="small" value={filterDomain}
              onChange={v => setFilterDomain(v)} style={{ width: 100 }}
              options={DOMAINS.map(d => ({ value: d, label: d }))} />
          </Space>
        </Space>
        <Table dataSource={filtered} columns={columns} rowKey="id"
          loading={loading} size="small" pagination={{ pageSize: 30 }} />
      </Card>

      <Modal title={editing ? '编辑条目' : '添加条目'} open={modalOpen}
        onOk={handleSave} onCancel={() => setModalOpen(false)} width={560} okText="保存">
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <span>领域:</span>
          <Select value={form.domain} onChange={v => setForm({ ...form, domain: v })} style={{ width: '100%' }}
            options={DOMAINS.filter(d => d !== '全部').map(d => ({ value: d, label: d }))} />
          <Input placeholder="名称 *" value={form.name}
            onChange={e => setForm({ ...form, name: e.target.value })} />
          <Input.TextArea placeholder="内容描述" value={form.content}
            onChange={e => setForm({ ...form, content: e.target.value })} rows={5} />
          <Input placeholder="标签（逗号分隔）" value={form.tags}
            onChange={e => setForm({ ...form, tags: e.target.value })} />
        </Space>
      </Modal>
    </div>
  )
}
