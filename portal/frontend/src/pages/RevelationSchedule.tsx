import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Table, Tag, Modal, Input, InputNumber, message, Switch, Select, Timeline, Tooltip } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, EyeInvisibleOutlined, ClockCircleOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface Rev {
  id: number; name: string; info_type: string
  reveal_volume: number; reveal_chapter: number
  content?: string; audience_knows?: boolean; protagonist_knows?: boolean; priority?: string
}

const INFO_COLORS: Record<string, string> = {
  '角色秘密': 'magenta', '伏笔揭示': 'orange', '世界观': 'purple', '剧情转折': 'red',
}

export const RevelationSchedule: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const [items, setItems] = useState<Rev[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Rev | null>(null)
  const [viewMode, setViewMode] = useState<'table' | 'timeline'>('table')
  const [detailItem, setDetailItem] = useState<Rev | null>(null)
  const [form, setForm] = useState({
    name: '', info_type: '角色秘密', reveal_volume: 1, reveal_chapter: 1,
    content: '', audience_knows: false, protagonist_knows: false, priority: 'normal',
  })

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/revelation/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.revelation) ? data.revelation :
                   Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []
      setItems(list)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [currentNovel])

  const handleSave = async () => {
    const url = editing
      ? `/api/revelation/${encodeURIComponent(currentNovel!)}/${editing.id}`
      : `/api/revelation/${encodeURIComponent(currentNovel!)}`
    const resp = await fetch(url, {
      method: editing ? 'PUT' : 'POST',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form),
    })
    const data = await resp.json()
    if (data.success) { message.success(editing ? '已更新' : '已添加'); setModalOpen(false); setEditing(null); load() }
    else { message.error(data.error || '保存失败') }
  }

  const handleDelete = async (id: number) => {
    await fetch(`/api/revelation/${encodeURIComponent(currentNovel!)}/${id}`, { method: 'DELETE' })
    message.success('已删除'); load()
  }

  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '类型', dataIndex: 'info_type', key: 'type', width: 90,
      render: (t: string) => <Tag color={INFO_COLORS[t] || 'default'}>{t}</Tag> },
    { title: '揭示位置', key: 'pos', width: 130,
      render: (_: any, r: Rev) => <span><ClockCircleOutlined style={{ fontSize: 11, color: '#999', marginRight: 4 }} />第{r.reveal_volume}卷第{r.reveal_chapter}章</span> },
    { title: '信息差', key: 'asym', width: 110,
      render: (_: any, r: Rev) => {
        const aud = !!r.audience_knows; const prot = !!r.protagonist_knows
        if (!aud && !prot) return <Tag>双方未知</Tag>
        if (aud && !prot) return <Tooltip title="读者知道，主角不知道 — 制造期待"><Tag color="orange"><EyeOutlined /> 读者独知</Tag></Tooltip>
        if (aud && prot) return <Tag color="green">双方已知</Tag>
        if (!aud && prot) return <Tag color="blue"><EyeInvisibleOutlined /> 主角独知</Tag>
        return null
      }},
    { title: '内容', dataIndex: 'content', key: 'content', ellipsis: true },
    { title: '操作', key: 'act', width: 100,
      render: (_: any, r: Rev) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => { setEditing(r); setForm({ name: r.name, info_type: r.info_type, reveal_volume: r.reveal_volume, reveal_chapter: r.reveal_chapter, content: r.content||'', audience_knows: !!r.audience_knows, protagonist_knows: !!r.protagonist_knows, priority: r.priority||'normal' }); setModalOpen(true) }} />
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)} />
        </Space>
      )},
  ]

  const timelineByVol: Record<number, Rev[]> = {}
  items.forEach(item => { const v = item.reveal_volume || 0; if (!timelineByVol[v]) timelineByVol[v] = []; timelineByVol[v].push(item) })
  const sortedVols = Object.keys(timelineByVol).map(Number).sort((a, b) => a - b)

  return (
    <div>
      <h2>信息释放</h2>
      <Card>
        <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setForm({ name:'', info_type:'角色秘密', reveal_volume:1, reveal_chapter:1, content:'', audience_knows:false, protagonist_knows:false, priority:'normal' }); setModalOpen(true) }}>添加释放点</Button>
          <Select size="small" value={viewMode} onChange={setViewMode} style={{ width: 120 }}
            options={[{ value: 'table', label: '表格视图' }, { value: 'timeline', label: '时间线视图' }]} />
        </Space>
        {viewMode === 'table' ? (
          <Table dataSource={items} columns={columns} rowKey="id" loading={loading} size="small" />
        ) : (
          <Card size="small" title="信息释放时间线">
            {sortedVols.length > 0 ? (
              <Timeline items={sortedVols.map(vol => ({
                children: (
                  <div>
                    <h4>第 {vol} 卷</h4>
                    <Space wrap>
                      {(timelineByVol[vol] || []).map((r, i) => (
                        <Tag key={i} color={INFO_COLORS[r.info_type] || 'default'}
                          style={{ cursor: 'pointer' }}
                          onClick={() => setDetailItem(r)}>
                          {r.name}
                          <span style={{ fontSize: 10, marginLeft: 4 }}>
                            {!!r.audience_knows && '👁'} {!!r.protagonist_knows && '🧑'}
                          </span>
                        </Tag>
                      ))}
                    </Space>
                  </div>
                ),
              }))} />
            ) : <div style={{ color: '#999', textAlign: 'center', padding: 30 }}>暂无数据</div>}
          </Card>
        )}
      </Card>
      <Modal title={editing ? '编辑释放点' : '添加释放点'} open={modalOpen} onOk={handleSave} onCancel={() => setModalOpen(false)} width={520} okText="保存">
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Input placeholder="名称 *" value={form.name} onChange={e => setForm({...form, name: e.target.value})} />
          <Select value={form.info_type} onChange={v => setForm({...form, info_type: v})} style={{ width:'100%' }}
            options={['角色秘密','伏笔揭示','世界观','剧情转折'].map(t => ({ value: t, label: t }))} />
          <Space><span>揭示于 卷</span><InputNumber min={1} value={form.reveal_volume} onChange={v => setForm({...form, reveal_volume: v||1})} /><span>章</span><InputNumber min={1} value={form.reveal_chapter} onChange={v => setForm({...form, reveal_chapter: v||1})} /></Space>
          <Input.TextArea placeholder="内容描述" value={form.content} onChange={e => setForm({...form, content: e.target.value})} rows={3} />
          <Space><label>读者已知:</label><Switch checked={form.audience_knows} onChange={v => setForm({...form, audience_knows: v})} /><label>主角已知:</label><Switch checked={form.protagonist_knows} onChange={v => setForm({...form, protagonist_knows: v})} /></Space>
        </Space>
      </Modal>
      <Modal title={detailItem?.name || ''} open={!!detailItem} onCancel={() => setDetailItem(null)} footer={null} width={400}>
        {detailItem && <div><Tag color={INFO_COLORS[detailItem.info_type]||'default'}>{detailItem.info_type}</Tag><p style={{marginTop:8}}>{detailItem.content||'(无描述)'}</p><p><small>揭示: 第{detailItem.reveal_volume}卷第{detailItem.reveal_chapter}章</small></p><p>读者: {detailItem.audience_knows?'已知':'未知'} | 主角: {detailItem.protagonist_knows?'已知':'未知'}</p></div>}
      </Modal>
    </div>
  )
}
