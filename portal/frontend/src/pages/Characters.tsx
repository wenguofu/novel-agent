import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Table, Tag, Modal, Input, message, Tabs, Descriptions, Badge, Typography } from 'antd'
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  ApartmentOutlined, UnorderedListOutlined,
} from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'
import { CharacterTopology } from '../components/CharacterTopology'

const { Text, Paragraph } = Typography

interface Character {
  id: number
  name: string
  role: string
  gender?: string
  age?: string
  identity?: string
  personality?: string
  appearance?: string
  background?: string
  current_status?: string
  current_vol?: number
  current_ch?: number
  emotional_state?: string
  ability_level?: string
  relationship_map?: string
  arc?: string
  lifeline?: string
  desire?: string
  fear?: string
  lie?: string
  truth?: string
  dilemma?: string
  mirror?: string
  ending?: string
  notes?: string
}

interface CharacterEvent {
  id: number
  event_type: string
  description: string
  vol: number
  ch: number
  chapter_ref: string
  created_at: string
}

const ROLE_COLORS: Record<string, string> = {
  '主角': 'red', '女主': 'magenta', '反派': 'orange', '配角': 'blue',
}

const INITIAL_FORM = {
  name: '', role: '配角', gender: '', age: '', identity: '', personality: '',
  appearance: '', background: '', current_status: '', emotional_state: '',
  ability_level: '', relationship_map: '', arc: '', lifeline: '',
  desire: '', fear: '', lie: '', truth: '', dilemma: '', mirror: '',
  ending: '', notes: '',
}

export const Characters: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [chars, setChars] = useState<Character[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Character | null>(null)
  const [form, setForm] = useState({ ...INITIAL_FORM })
  const [activeTab, setActiveTab] = useState('table')
  const [selectedChar, setSelectedChar] = useState<Character | null>(null)
  const [charEvents, setCharEvents] = useState<CharacterEvent[]>([])
  const [detailOpen, setDetailOpen] = useState(false)

  const loadChars = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/characters/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      const list = Array.isArray(data.items) ? data.items : Array.isArray(data.characters) ? data.characters : Array.isArray(data) ? data : []
      setChars(list)
    } catch {
      setChars([])
    } finally { setLoading(false) }
  }

  useEffect(() => { loadChars() }, [currentNovel])

  const handleSave = async () => {
    if (!currentNovel) return
    const url = editing
      ? `/api/characters/${encodeURIComponent(currentNovel)}/${editing.id}`
      : `/api/characters/${encodeURIComponent(currentNovel)}`
    const method = editing ? 'PUT' : 'POST'
    try {
      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await resp.json()
      if (data.success) {
        message.success(editing ? '已更新' : '已添加')
        setModalOpen(false)
        setEditing(null)
        loadChars()
      } else {
        message.error(data.error || '保存失败')
      }
    } catch {
      message.error('网络错误')
    }
  }

  const handleDelete = async (id: number) => {
    if (!currentNovel) return
    await fetch(`/api/characters/${encodeURIComponent(currentNovel)}/${id}`, { method: 'DELETE' })
    message.success('已删除')
    loadChars()
  }

  const openEdit = (c: Character) => {
    setEditing(c)
    setForm({
      name: c.name || '', role: c.role || '配角', gender: c.gender || '',
      age: c.age || '', identity: c.identity || '', personality: c.personality || '',
      appearance: c.appearance || '', background: c.background || '',
      current_status: c.current_status || '', emotional_state: c.emotional_state || '',
      ability_level: c.ability_level || '', relationship_map: c.relationship_map || '',
      arc: c.arc || '', lifeline: c.lifeline || '',
      desire: c.desire || '', fear: c.fear || '', lie: c.lie || '',
      truth: c.truth || '', dilemma: c.dilemma || '', mirror: c.mirror || '',
      ending: c.ending || '', notes: c.notes || '',
    })
    setModalOpen(true)
  }

  const handleNodeClick = async (characterId: string, _name: string) => {
    const char = chars.find(c => String(c.id) === characterId)
    if (!char) return
    setSelectedChar(char)
    // Load events
    try {
      const resp = await fetch(`/api/characters/${encodeURIComponent(currentNovel!)}/${characterId}`)
      const data = await resp.json()
      setCharEvents(data.events || [])
    } catch {
      setCharEvents([])
    }
    setDetailOpen(true)
  }

  const parseRelationshipMap = (relMap: string) => {
    try {
      const parsed = JSON.parse(relMap)
      if (Array.isArray(parsed)) return parsed
      if (typeof parsed === 'object') return Object.entries(parsed).map(([k, v]) => ({ name: k, relation: v }))
    } catch {
      // Try markdown list fallback
      const items = relMap.split('\n').filter(l => l.trim().startsWith('-'))
      return items.map(l => {
        const cleaned = l.replace(/^[-*]\s*/, '')
        const [name, ...rest] = cleaned.split(/[：:]/)
        return { name: name?.trim(), relation: rest.join(':').trim() }
      })
    }
    return []
  }

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name', width: 100 },
    { title: '角色', dataIndex: 'role', key: 'role', width: 70,
      render: (r: string) => <Tag color={ROLE_COLORS[r] || 'default'}>{r}</Tag> },
    { title: '身份', dataIndex: 'identity', key: 'identity', ellipsis: true },
    { title: '性格', dataIndex: 'personality', key: 'personality', ellipsis: true, width: 150 },
    { title: '当前状态', dataIndex: 'current_status', key: 'status', ellipsis: true, width: 150 },
    { title: '关系数', key: 'relations', width: 70,
      render: (_: any, r: Character) => {
        const rels = parseRelationshipMap(r.relationship_map || '')
        return <Badge count={rels.length} showZero style={{ backgroundColor: '#1677ff' }} />
      }},
    { title: '操作', key: 'actions', width: 130,
      render: (_: any, r: Character) => (
        <Space size="small">
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>编辑</Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r.id)}>删除</Button>
        </Space>
      )},
  ]

  const tabItems = [
    {
      key: 'table',
      label: <span><UnorderedListOutlined /> 列表</span>,
      children: (
        <Table dataSource={chars} columns={columns} rowKey="id"
          loading={loading} size="small" pagination={{ pageSize: 50 }}
          scroll={{ x: 800 }}
          onRow={(record) => ({
            style: { cursor: 'pointer' },
            onClick: () => handleNodeClick(String(record.id), record.name),
          })}
        />
      ),
    },
    {
      key: 'topology',
      label: <span><ApartmentOutlined /> 关系拓扑</span>,
      children: <CharacterTopology novelName={currentNovel} onNodeClick={handleNodeClick} />,
    },
  ]

  return (
    <div>
      <h2>人物管理</h2>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button type="primary" icon={<PlusOutlined />}
            onClick={() => {
              setEditing(null)
              setForm({ ...INITIAL_FORM })
              setModalOpen(true)
            }}>
            添加人物
          </Button>
          <Tabs activeKey={activeTab} onChange={setActiveTab}
            items={tabItems}
            size="small"
          />
        </Space>
      </Card>

      {/* Add/Edit Modal */}
      <Modal
        title={editing ? `编辑人物 — ${editing.name}` : '添加人物'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        width={720}
        okText="保存"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: '100%' }} size="small">
          <Space wrap>
            <Input placeholder="姓名 *" value={form.name}
              onChange={e => setForm({...form, name: e.target.value})}
              style={{ width: 160 }} />
            <span>角色:</span>
            <select value={form.role}
              onChange={e => setForm({...form, role: e.target.value})}
              style={{
                padding: '4px 11px', border: '1px solid #d9d9d9', borderRadius: 6,
                fontSize: 14, outline: 'none', width: 120,
              }}>
              {['主角','女主','反派','配角'].map(r => <option key={r} value={r}>{r}</option>)}
            </select>
            <Input placeholder="性别" value={form.gender}
              onChange={e => setForm({...form, gender: e.target.value})} style={{ width: 80 }} />
            <Input placeholder="年龄" value={form.age}
              onChange={e => setForm({...form, age: e.target.value})} style={{ width: 80 }} />
          </Space>
          <Input placeholder="身份/职业" value={form.identity}
            onChange={e => setForm({...form, identity: e.target.value})} />
          <Input placeholder="性格特质" value={form.personality}
            onChange={e => setForm({...form, personality: e.target.value})} />
          <Input placeholder="外貌描述" value={form.appearance}
            onChange={e => setForm({...form, appearance: e.target.value})} />
          <Input placeholder="当前状态" value={form.current_status}
            onChange={e => setForm({...form, current_status: e.target.value})} />
          <Input placeholder="情感状态" value={form.emotional_state}
            onChange={e => setForm({...form, emotional_state: e.target.value})} />
          <Input placeholder="能力等级" value={form.ability_level}
            onChange={e => setForm({...form, ability_level: e.target.value})} />
          <Input placeholder="欲望/目标" value={form.desire}
            onChange={e => setForm({...form, desire: e.target.value})} />
          <Input placeholder="恐惧" value={form.fear}
            onChange={e => setForm({...form, fear: e.target.value})} />
          <Input placeholder="谎言/误解" value={form.lie}
            onChange={e => setForm({...form, lie: e.target.value})} />
          <Input placeholder="真相/领悟" value={form.truth}
            onChange={e => setForm({...form, truth: e.target.value})} />
          <Input placeholder="困境" value={form.dilemma}
            onChange={e => setForm({...form, dilemma: e.target.value})} />
          <Input placeholder="镜像角色" value={form.mirror}
            onChange={e => setForm({...form, mirror: e.target.value})} />
          <Input.TextArea placeholder="背景故事" value={form.background}
            onChange={e => setForm({...form, background: e.target.value})} rows={2} />
          <Input.TextArea placeholder={'关系图谱 (JSON: [{"target_id":2,"relation_type":"师徒"}])'}
            value={form.relationship_map}
            onChange={e => setForm({...form, relationship_map: e.target.value})} rows={3} />
          <Input.TextArea placeholder={'角色弧线 (JSON: [{"vol":1,"ch":10,"event":"遇到劲敌"}])'}
            value={form.arc}
            onChange={e => setForm({...form, arc: e.target.value})} rows={2} />
          <Input.TextArea placeholder="生命线" value={form.lifeline}
            onChange={e => setForm({...form, lifeline: e.target.value})} rows={2} />
          <Input placeholder="结局" value={form.ending}
            onChange={e => setForm({...form, ending: e.target.value})} />
          <Input.TextArea placeholder="备注" value={form.notes}
            onChange={e => setForm({...form, notes: e.target.value})} rows={2} />
        </Space>
      </Modal>

      {/* Character Detail Modal */}
      <Modal
        title={selectedChar ? `${selectedChar.name} — 人物详情` : ''}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={null}
        width={640}
      >
        {selectedChar && (
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="角色">
              <Tag color={ROLE_COLORS[selectedChar.role] || 'default'}>{selectedChar.role}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="性别">{selectedChar.gender || '—'}</Descriptions.Item>
            <Descriptions.Item label="身份" span={2}>{selectedChar.identity || '—'}</Descriptions.Item>
            <Descriptions.Item label="性格" span={2}>{selectedChar.personality || '—'}</Descriptions.Item>
            <Descriptions.Item label="当前状态" span={2}>{selectedChar.current_status || '—'}</Descriptions.Item>
            <Descriptions.Item label="情感状态">{selectedChar.emotional_state || '—'}</Descriptions.Item>
            <Descriptions.Item label="能力等级">{selectedChar.ability_level || '—'}</Descriptions.Item>
            <Descriptions.Item label="欲望">{selectedChar.desire || '—'}</Descriptions.Item>
            <Descriptions.Item label="恐惧">{selectedChar.fear || '—'}</Descriptions.Item>
            <Descriptions.Item label="谎言/误解">{selectedChar.lie || '—'}</Descriptions.Item>
            <Descriptions.Item label="真相/领悟">{selectedChar.truth || '—'}</Descriptions.Item>
            <Descriptions.Item label="困境" span={2}>{selectedChar.dilemma || '—'}</Descriptions.Item>
            <Descriptions.Item label="镜像" span={2}>{selectedChar.mirror || '—'}</Descriptions.Item>
            <Descriptions.Item label="结局" span={2}>{selectedChar.ending || '—'}</Descriptions.Item>

            {/* Relationships */}
            <Descriptions.Item label="关系拓扑" span={2}>
              {(() => {
                const rels = parseRelationshipMap(selectedChar.relationship_map || '')
                if (rels.length === 0) return <Text type="secondary">暂无关系数据</Text>
                return (
                  <Space wrap>
                    {rels.map((r: any, i: number) => (
                      <Tag key={i} color="blue">
                        {r.name || r.target_name || '?'}
                        {r.relation || r.relation_type ? ` — ${r.relation || r.relation_type}` : ''}
                      </Tag>
                    ))}
                  </Space>
                )
              })()}
            </Descriptions.Item>

            {/* Arc */}
            {selectedChar.arc && (
              <Descriptions.Item label="角色弧线" span={2}>
                <Paragraph ellipsis={{ rows: 3, expandable: true }} style={{ margin: 0 }}>
                  {selectedChar.arc}
                </Paragraph>
              </Descriptions.Item>
            )}

            {/* Events history */}
            {charEvents.length > 0 && (
              <Descriptions.Item label={`事件记录 (${charEvents.length})`} span={2}>
                <div style={{ maxHeight: 200, overflow: 'auto' }}>
                  {charEvents.slice(-15).reverse().map((e) => (
                    <div key={e.id} style={{
                      padding: '4px 0', borderBottom: '1px solid #f0f0f0',
                      fontSize: 12, display: 'flex', gap: 8,
                    }}>
                      <Tag style={{ fontSize: 10, margin: 0 }}>{e.event_type}</Tag>
                      <Text style={{ flex: 1, fontSize: 12 }}>{e.description}</Text>
                      {e.vol > 0 && (
                        <Text type="secondary" style={{ fontSize: 10, whiteSpace: 'nowrap' }}>
                          第{e.vol}卷第{e.ch}章
                        </Text>
                      )}
                    </div>
                  ))}
                </div>
              </Descriptions.Item>
            )}

            {/* Background & Notes */}
            {selectedChar.background && (
              <Descriptions.Item label="背景" span={2}>
                <Paragraph ellipsis={{ rows: 3, expandable: true }} style={{ margin: 0 }}>
                  {selectedChar.background}
                </Paragraph>
              </Descriptions.Item>
            )}
            {selectedChar.notes && (
              <Descriptions.Item label="备注" span={2}>{selectedChar.notes}</Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Modal>
    </div>
  )
}
