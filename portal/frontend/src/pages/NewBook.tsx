import React, { useState } from 'react'
import { Card, Steps, Input, Select, Button, Space, Tag, message, Alert } from 'antd'
import { BookOutlined, ThunderboltOutlined } from '@ant-design/icons'

const GENRES = ['玄幻', '仙侠', '都市', '科幻', '历史', '悬疑', '游戏', '军事', '武侠', '奇幻', '轻小说', '二次元', '体育']
const WORD_GOALS = [
  { label: '50万字 (短篇)', value: 500000 },
  { label: '100万字 (中篇)', value: 1000000 },
  { label: '200万字 (长篇)', value: 2000000 },
  { label: '300万字 (超长篇)', value: 3000000 },
]

export const NewBook: React.FC = () => {
  const [step, setStep] = useState(0)
  const [name, setName] = useState('')
  const [genre, setGenre] = useState('玄幻')
  const [subgenre, setSubgenre] = useState<string[]>([])
  const [wordGoal, setWordGoal] = useState(1000000)
  const [protagonist, setProtagonist] = useState('')
  const [sellingPoint, setSellingPoint] = useState('')
  const [worldSetting, setWorldSetting] = useState('')
  const [style, setStyle] = useState('')
  const [creating, setCreating] = useState(false)

  const handleCreate = async () => {
    if (!name.trim()) { message.warning('请输入小说名称'); return }
    setCreating(true)
    try {
      const resp = await fetch('/api/novels/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          genre, subgenre: subgenre.join(','),
          word_goal: wordGoal,
          protagonist, selling_point: sellingPoint,
          world_setting: worldSetting, style,
        }),
      })
      const data = await resp.json()
      if (data.success) {
        message.success(`小说「${name}」创建成功！`)
        setStep(7) // done
      } else {
        message.error(data.error || '创建失败')
      }
    } catch { message.error('创建失败') }
    finally { setCreating(false) }
  }

  const renderStep = () => {
    switch (step) {
      case 0: return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <h3>📖 输入小说名称</h3>
          <Input size="large" placeholder="请输入小说名称" value={name}
            onChange={e => setName(e.target.value)} maxLength={50} />
          {name && <Tag color="blue">{name}</Tag>}
        </Space>
      )
      case 1: return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <h3>🎭 选择类型</h3>
          <Select size="large" style={{ width: '100%' }} value={genre}
            onChange={v => { setGenre(v); setSubgenre([]) }}
            options={GENRES.map(g => ({ value: g, label: g }))} />
        </Space>
      )
      case 2: return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <h3>🏷️ 子类型 (可多选)</h3>
          <Select mode="multiple" size="large" style={{ width: '100%' }}
            value={subgenre} onChange={v => setSubgenre(v)}
            placeholder="选择子类型..."
            options={(genre === '玄幻' ? ['东方玄幻','异界大陆','高武世界'] :
              genre === '仙侠' ? ['古典仙侠','现代修真','洪荒流'] :
              genre === '都市' ? ['都市生活','商战','娱乐'] :
              ['传统','创新','混合']).map(s => ({ value: s, label: s }))} />
        </Space>
      )
      case 3: return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <h3>📏 目标字数</h3>
          <Select size="large" style={{ width: '100%' }} value={wordGoal}
            onChange={v => setWordGoal(v)}
            options={WORD_GOALS} />
        </Space>
      )
      case 4: return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <h3>🦸 主角设定</h3>
          <Input.TextArea rows={4} placeholder="描述主角的姓名、性格、背景..." value={protagonist}
            onChange={e => setProtagonist(e.target.value)} />
        </Space>
      )
      case 5: return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <h3>💡 卖点/核心创意</h3>
          <Input.TextArea rows={4} placeholder="小说的核心卖点是什么？金手指？穿越？重生？" value={sellingPoint}
            onChange={e => setSellingPoint(e.target.value)} />
        </Space>
      )
      case 6: return (
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <h3>🌍 世界观设定</h3>
          <Input.TextArea rows={4} placeholder="描述小说世界的背景、规则、势力分布..." value={worldSetting}
            onChange={e => setWorldSetting(e.target.value)} />
          <h3>🎨 写作风格</h3>
          <Input placeholder="如：金庸风、番茄风、辰东风..." value={style}
            onChange={e => setStyle(e.target.value)} />
          <Alert message="确认信息" description={`书名: ${name || '(未填)'} | 类型: ${genre} | 字数: ${(wordGoal/10000).toFixed(0)}万`} type="info" showIcon />
        </Space>
      )
      case 7: return (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <BookOutlined style={{ fontSize: 64, color: '#1677ff' }} />
          <h2>小说创建成功！</h2>
          <p>「{name}」已就绪，前往写作台开始创作吧。</p>
        </div>
      )
      default: return null
    }
  }

  return (
    <div>
      <h2>新建小说</h2>
      <Card>
        <Steps
          current={step}
          size="small"
          style={{ marginBottom: 32 }}
          items={[
            { title: '书名' }, { title: '类型' }, { title: '子类型' }, { title: '字数' },
            { title: '主角' }, { title: '卖点' }, { title: '设定' }, { title: '完成' },
          ]}
        />

        {renderStep()}

        <div style={{ marginTop: 32, display: 'flex', justifyContent: 'space-between' }}>
          <Button disabled={step === 0} onClick={() => setStep(s => s - 1)}>上一步</Button>
          {step < 6 ? (
            <Button type="primary" onClick={() => setStep(s => s + 1)}
              disabled={step === 0 && !name.trim()}>
              下一步
            </Button>
          ) : step === 6 ? (
            <Button type="primary" icon={<ThunderboltOutlined />}
              onClick={handleCreate} loading={creating} size="large">
              创建小说
            </Button>
          ) : null}
        </div>
      </Card>
    </div>
  )
}
