import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Tabs, Alert, message, Table, Statistic, Row, Col } from 'antd'
import { RobotOutlined, SaveOutlined, LeftOutlined, RightOutlined, UnorderedListOutlined, EditOutlined, EyeOutlined, FileTextOutlined } from '@ant-design/icons'
import { Tag } from 'antd'
import { useNovelStore } from '../stores/novelStore'
import { useConfigStore } from '../stores/configStore'
import ReactMarkdown from 'react-markdown'

interface ChapterEntry {
  number: number
  title: string
  function: string[]
  core_events: string
  foreshadowing: string[]
  ending_hook: string
}

export const Outlines: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [volume, setVolume] = useState(1)
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('edit')
  const [parsedChapters, setParsedChapters] = useState<ChapterEntry[]>([])
  const [volumeName, setVolumeName] = useState('')
  const [isYaml, setIsYaml] = useState(false)

  const volStr = `vol-${String(volume).padStart(2, '0')}`

  const load = async (vol?: number) => {
    const v = vol ?? volume
    const vs = `vol-${String(v).padStart(2, '0')}`
    if (!currentNovel) return
    setContent('')
    setParsedChapters([])
    setVolumeName('')
    try {
      const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel)}/outline/${vs}`)
      const data = await resp.json()
      const c = data.content || ''
      setContent(c)
      const parsed = parseChapters(c)
      setParsedChapters(parsed.chapters)
      setVolumeName(parsed.volumeName)
      setIsYaml(parsed.isYaml)
    } catch {
      setContent(''); setParsedChapters([])
    }
  }

  useEffect(() => { load() }, [currentNovel, volume])

  const parseChapters = (text: string): { chapters: ChapterEntry[]; volumeName: string; isYaml: boolean } => {
    // Try YAML first
    if (text.trim().startsWith('#') && text.includes('chapters:') || text.includes('volume:')) {
      try {
        // Extract YAML section (skip comment lines starting with # at top level)
        const yamlText = text.replace(/^#.*\n/gm, '')
        // Simple YAML-like parsing for our known schema
        const chapters: ChapterEntry[] = []
        let volName = ''

        // Parse volume_name
        const vnMatch = yamlText.match(/volume_name:\s*"(.+)"/)
        if (vnMatch) volName = vnMatch[1]

        // Parse chapters array
        const chBlocks = yamlText.split(/\n  - number:/).slice(1)
        for (const block of chBlocks) {
          const numMatch = block.match(/^(\d+)/)
          const titleMatch = block.match(/title:\s*"(.+)"/)
          const funcMatch = block.match(/function:\s*\[(.+?)\]/)
          const eventsMatch = block.match(/core_events:\s*"(.+)"/)
          const fsMatch = block.match(/foreshadowing:\s*\[(.+?)\]/)
          const hookMatch = block.match(/ending_hook:\s*"(.+)"/)

          if (numMatch) {
            chapters.push({
              number: parseInt(numMatch[1]),
              title: titleMatch?.[1] || '',
              function: funcMatch ? funcMatch[1].split(',').map(s => s.trim().replace(/['"]/g, '')) : [],
              core_events: eventsMatch?.[1] || '',
              foreshadowing: fsMatch ? fsMatch[1].split(',').map(s => s.trim().replace(/['"]/g, '')).filter(Boolean) : [],
              ending_hook: hookMatch?.[1] || '',
            })
          }
        }
        if (chapters.length > 0) return { chapters, volumeName: volName, isYaml: true }
      } catch { /* fall through to Markdown */ }
    }

    // Fallback: Markdown table parsing
    const chapters: ChapterEntry[] = []
    const lines = text.split('\n')
    let volName = ''
    for (const line of lines) {
      if (line.startsWith('#') && line.includes('卷') && !line.startsWith('##')) {
        volName = line.replace(/^#+\s*/, '').trim()
      }
      if (line.startsWith('|') && !line.includes('---') && !line.includes('章节')) {
        const cells = line.replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim())
        if (cells.length >= 4 && /^\d+$/.test(cells[0])) {
          chapters.push({
            number: parseInt(cells[0]),
            title: cells[1] || '',
            function: cells[3] ? cells[3].split(/[、,]/).map(s => s.trim()) : [],
            core_events: cells[2] || '',
            foreshadowing: cells[4] ? cells[4].split(/[、,]/).map(s => s.trim()).filter(s => s && s !== '—') : [],
            ending_hook: cells[5] || '',
          })
        }
      }
    }
    return { chapters, volumeName: volName, isYaml: false }
  }

  const toYaml = (chapters: ChapterEntry[], volName: string): string => {
    const dangerScenes: number[] = []
    const majorCrises: number[] = []
    chapters.forEach(ch => {
      const funcs = ch.function.join('')
      if (funcs.includes('危机') || funcs.includes('哭点') || funcs.includes('对决')) dangerScenes.push(ch.number)
      if (funcs.includes('大反转') || funcs.includes('重大危机')) majorCrises.push(ch.number)
    })

    let yaml = `# 第${volume}卷章节规划\n`
    yaml += `volume: ${volume}\n`
    yaml += `volume_name: "${volName}"\n\n`
    yaml += `rhythm_rules:\n`
    yaml += `  danger_scenes: ${JSON.stringify(dangerScenes)}\n`
    yaml += `  major_crises: ${JSON.stringify(majorCrises)}\n\n`
    yaml += `chapters:\n`
    for (const ch of chapters) {
      yaml += `  - number: ${ch.number}\n`
      yaml += `    title: "${ch.title}"\n`
      yaml += `    function: ${JSON.stringify(ch.function)}\n`
      yaml += `    core_events: "${ch.core_events}"\n`
      yaml += `    foreshadowing: ${JSON.stringify(ch.foreshadowing)}\n`
      yaml += `    ending_hook: "${ch.ending_hook || ''}"\n`
    }
    return yaml
  }

  const handleSave = async () => {
    if (!currentNovel) return
    setSaving(true)
    // Auto-convert to YAML if chapters were parsed
    const saveContent = parsedChapters.length > 0
      ? toYaml(parsedChapters, volumeName)
      : content
    try {
      const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel)}/outline/${volStr}/edit`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: saveContent }),
      })
      const data = await resp.json()
      if (data.success) {
        setContent(saveContent)
        setIsYaml(true)
        message.success('大纲已保存 (YAML格式)')
      } else {
        message.error(data.error || '保存失败')
      }
    } catch {
      message.error('保存失败')
    } finally { setSaving(false) }
  }

  // Strip AI preamble/conversational text before YAML
  const _stripAiPreamble = (text: string): string => {
    // Find where the actual YAML starts — look for "volume:" at line start
    const lines = text.split('\n')
    const yamlStart = lines.findIndex(l => /^volume:\s*\d/.test(l.trim()))
    if (yamlStart > 0) {
      return lines.slice(yamlStart).join('\n')
    }
    // If no "volume:" found, try "chapters:" or "# " comment line starting with YAML
    const chStart = lines.findIndex(l => /^chapters:/.test(l.trim()))
    if (chStart > 0) return lines.slice(chStart).join('\n')
    return text
  }

  const handleAIGenerate = async () => {
    if (!currentNovel) return
    setAiLoading(true)
    try {
      const resp = await fetch('/api/ai/chat', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system: `你是一个专业的网文大纲策划师。请为第${volume}卷生成详细章节大纲。

**严格输出规则：**
- 直接输出YAML，不要任何开场白、解释、总结
- 第一行必须是 "# 第N卷章节规划"
- 第二行开始是YAML结构
- 禁止输出"好的"、"没问题"、"以下是"等对话文字

输出模板：
# 第${volume}卷章节规划
volume: ${volume}
volume_name: "卷名"
rhythm_rules:
  danger_scenes: [危机章节号]
  major_crises: [重大危机章节号]
chapters:
  - number: 1
    title: "章节标题"
    function: ["开篇", "悬念"]
    core_events: "核心事件描述"
    foreshadowing: ["伏笔关键词"]
    ending_hook: "结尾悬念"

要求：
- 卷共40-60章
- function必须是以下之一: 开篇/悬念/爽点/哭点/危机/对决/暧昧/温暖/笑点/过渡/反转/大反转
- 每章结尾牵引不能为空`,
          messages: [{ role: 'user', content: `直接输出第${volume}卷YAML大纲，不要开场白。` }],
          model: useConfigStore.getState().deepseekConfig?.deepseek_model || '',
        }),
      })
      const data = await resp.json()
      if (data.content) {
        const cleaned = _stripAiPreamble(data.content)
        setContent(cleaned)
        const parsed = parseChapters(cleaned)
        setParsedChapters(parsed.chapters)
        setVolumeName(parsed.volumeName)
        setIsYaml(parsed.isYaml)
        message.success(`大纲生成完成：${parsed.chapters.length}章`)
      } else {
        message.error('生成失败')
      }
    } catch { message.error('生成失败') }
    finally { setAiLoading(false) }
  }

  const chapterColumns = [
    { title: '章', dataIndex: 'number', key: 'num', width: 55 },
    { title: '标题', dataIndex: 'title', key: 'title', width: 120, ellipsis: true },
    {
      title: '功能', dataIndex: 'function', key: 'func', width: 160,
      render: (funcs: string[]) => funcs?.map((f: string) => {
        const colorMap: Record<string, string> = {
          '开篇': 'blue', '悬念': 'purple', '爽点': 'gold', '哭点': 'red',
          '危机': 'volcano', '对决': 'magenta', '暧昧': 'pink', '温暖': 'orange',
          '笑点': 'green', '过渡': 'default', '反转': 'geekblue', '大反转': 'red',
        }
        return <Tag key={f} color={colorMap[f] || 'default'} style={{ fontSize: 11 }}>{f}</Tag>
      }),
    },
    { title: '核心事件', dataIndex: 'core_events', key: 'events', ellipsis: true },
    {
      title: '伏笔', dataIndex: 'foreshadowing', key: 'fs', width: 120,
      render: (fs: string[]) => fs?.filter(Boolean).map((f: string) =>
        <Tag key={f} color="orange" style={{ fontSize: 10 }}>{f}</Tag>
      ),
    },
  ]

  const stats = {
    totalChapters: parsedChapters.length,
    dangerCount: parsedChapters.filter(c => c.function?.some(f => f.includes('危机') || f.includes('哭点'))).length,
    highCount: parsedChapters.filter(c => c.function?.some(f => f.includes('爽点') || f.includes('对决'))).length,
    hookCount: parsedChapters.filter(c => c.ending_hook).length,
  }

  return (
    <div>
      <h2>大纲管理</h2>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card size="small"><Statistic title="总章节" value={stats.totalChapters} suffix="章" /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="危机/哭点" value={stats.dangerCount} valueStyle={{ color: '#ff4d4f' }} suffix="处" /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="爽点/对决" value={stats.highCount} valueStyle={{ color: '#faad14' }} suffix="处" /></Card></Col>
        <Col span={6}><Card size="small"><Statistic title="结尾牵引" value={stats.hookCount} valueStyle={{ color: '#1890ff' }} suffix="章" /></Card></Col>
      </Row>

      <Card>
        <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Button size="small" icon={<LeftOutlined />}
              onClick={() => { const v = Math.max(1, volume - 1); setVolume(v); load(v) }}
              disabled={volume <= 1} />
            <span style={{ fontWeight: 500, fontSize: 14 }}>第 {volume} 卷</span>
            <Button size="small" icon={<RightOutlined />}
              onClick={() => { const v = volume + 1; setVolume(v); load(v) }} />
            <Button icon={<SaveOutlined />} onClick={handleSave} loading={saving} disabled={!currentNovel}>
              保存
            </Button>
            <Button icon={<RobotOutlined />} onClick={handleAIGenerate}
              loading={aiLoading} disabled={!currentNovel}>
              AI 生成本卷大纲
            </Button>
          </Space>
        </Space>

        <Tabs activeKey={activeTab} onChange={setActiveTab} items={[
          {
            key: 'edit',
            label: <><EditOutlined /> 编辑</>,
            children: (
              <div>
                {!isYaml && parsedChapters.length > 0 && (
                  <Alert
                    type="info"
                    message="检测到Markdown格式大纲，保存时将自动转为YAML格式"
                    style={{ marginBottom: 12 }}
                    showIcon
                  />
                )}
                {isYaml && (
                  <Tag color="green" style={{ marginBottom: 8 }}><FileTextOutlined /> YAML格式</Tag>
                )}
                <textarea
                  value={content}
                  onChange={e => {
                    setContent(e.target.value)
                    const parsed = parseChapters(e.target.value)
                    setParsedChapters(parsed.chapters)
                    setVolumeName(parsed.volumeName)
                    setIsYaml(parsed.isYaml)
                  }}
                  rows={20}
                  style={{
                    width: '100%', fontFamily: 'monospace', fontSize: 13,
                    border: '1px solid #d9d9d9', borderRadius: 6, padding: 12,
                    resize: 'vertical', lineHeight: 1.6,
                  }}
                  placeholder={`YAML格式大纲（可直接编辑）：\n\nvolume: ${volume}\nvolume_name: "卷名"\n\nrhythm_rules:\n  danger_scenes: []\n  major_crises: []\n\nchapters:\n  - number: 1\n    title: "章节标题"\n    function: ["开篇", "悬念"]\n    core_events: "核心事件描述"\n    foreshadowing: ["伏笔关键词"]\n    ending_hook: "结尾悬念"`}
                />
              </div>
            ),
          },
          {
            key: 'preview',
            label: <><EyeOutlined /> 预览</>,
            children: content
              ? <div className="markdown-body" style={{ padding: 16, maxHeight: '60vh', overflow: 'auto' }}>
                  <ReactMarkdown>{content}</ReactMarkdown>
                </div>
              : <Alert message="暂无内容，请编辑或生成大纲" type="info" showIcon />,
          },
          {
            key: 'chapters',
            label: <><UnorderedListOutlined /> 章节列表 ({parsedChapters.length})</>,
            children: parsedChapters.length > 0
              ? <Table dataSource={parsedChapters} columns={chapterColumns}
                  rowKey="number" size="small" pagination={false}
                  scroll={{ y: 400 }} />
              : <Alert message="未检测到章节结构" type="info"
                  description="请在编辑器中输入 '第001章' 格式的章节标题，系统会自动解析" showIcon />,
          },
        ]} />
      </Card>
    </div>
  )
}
