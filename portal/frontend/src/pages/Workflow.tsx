import React, { useState } from 'react'
import { Card, InputNumber, Button, Space, Select, Steps, Tag, Alert, message } from 'antd'
import { PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface StepResult { step_id: string; name: string; ok: boolean; detail?: string; output?: string }

export const Workflow: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [volume, setVolume] = useState(1)
  const [chapter, setChapter] = useState(1)
  const [running, setRunning] = useState(false)
  const [mode, setMode] = useState<'pipeline' | 'preflight' | 'postflight'>('pipeline')
  const [results, setResults] = useState<StepResult[]>([])
  const [summary, setSummary] = useState('')

  const handleRun = async () => {
    if (!currentNovel) return
    setRunning(true); setResults([]); setSummary('')

    try {
      let url = ''
      if (mode === 'pipeline') {
        url = `/api/novels/${encodeURIComponent(currentNovel)}/enforce-pipeline`
      } else if (mode === 'preflight') {
        url = `/api/workflow/preflight/${encodeURIComponent(currentNovel)}`
      } else {
        url = `/api/workflow/postflight/${encodeURIComponent(currentNovel)}`
      }

      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ volume: `vol-${String(volume).padStart(2, '0')}`, chapter_num: chapter }),
      })
      const data = await resp.json()
      setResults(data.results || [])
      const passes = data.results?.filter((r: StepResult) => r.ok).length || 0
      const total = data.results?.length || 0
      setSummary(`通过 ${passes}/${total}`)
    } catch (err: any) {
      message.error('执行失败: ' + err.message)
    } finally { setRunning(false) }
  }

  const currentStep = results.length > 0
    ? results.findIndex(r => !r.ok)
    : -1

  return (
    <div>
      <h2>工作流检查</h2>

      <Card style={{ marginBottom: 16 }}>
        <Space style={{ width: '100%' }}>
          <Space wrap>
            <span>卷:</span><InputNumber min={1} value={volume} onChange={v => setVolume(v||1)} />
            <span>章:</span><InputNumber min={1} value={chapter} onChange={v => setChapter(v||1)} />
          </Space>

          <Space>
            <Select value={mode} onChange={v => setMode(v)} style={{ width: 150 }}
              options={[
                { value: 'pipeline', label: '▶️ 全管道' },
                { value: 'preflight', label: '⚙️ 门控' },
                { value: 'postflight', label: '📋 后置检查' },
              ]} />
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRun} loading={running} disabled={!currentNovel}>
              执行
            </Button>
          </Space>
        </Space>
      </Card>

      {summary && (
        <Alert
          message={summary}
          type={summary.startsWith(`通过 ${results.length}`) ? 'success' : 'warning'}
          style={{ marginBottom: 16 }}
          showIcon
        />
      )}

      {results.length > 0 && (
        <Card title="执行结果">
          <Steps
            direction="vertical"
            size="small"
            current={currentStep >= 0 ? currentStep : results.length}
            status={currentStep >= 0 ? 'error' : 'finish'}
            items={results.map((r) => ({
              title: (
                <Space>
                  <Tag color={r.ok ? 'success' : 'error'}>{r.ok ? <CheckCircleOutlined /> : <CloseCircleOutlined />}</Tag>
                  {r.name}
                </Space>
              ),
              description: r.detail || r.output,
            }))}
          />
        </Card>
      )}
    </div>
  )
}
