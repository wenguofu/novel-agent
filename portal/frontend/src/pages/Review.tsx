import React, { useState } from 'react'
import { Card, InputNumber, Button, Space, Tag, Alert, Progress, Divider } from 'antd'
import { AuditOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

interface ReviewResult {
  success: boolean
  wc_ok?: boolean
  compliance_ok?: boolean
  forbidden_ok?: boolean
  ai_review?: string
  script_detail?: string
  bcontrast_count?: number
  tell_count?: number
}

export const Review: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [volume, setVolume] = useState(1)
  const [chapter, setChapter] = useState(1)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<ReviewResult | null>(null)
  const [stage, setStage] = useState<'idle' | 'scripts' | 'ai' | 'done'>('idle')
  const [elapsed, setElapsed] = useState(0)

  const padNum = (n: number) => String(n).padStart(3, '0')

  const handleReview = async () => {
    if (!currentNovel) return

    setRunning(true)
    setStage('scripts')
    setResult(null)
    setElapsed(0)

    const start = Date.now()
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)

    try {
      const chRef = `vol-${String(volume).padStart(2, '0')}-ch-${padNum(chapter)}`

      // Stage 1: scripts
      await new Promise((r) => setTimeout(r, 600))

      // Stage 2: AI review
      setStage('ai')
      const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel)}/review-chapter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chapter_ref: chRef,
          volume: `vol-${String(volume).padStart(2, '0')}`,
          chapter_num: chapter,
        }),
      })
      const data = await resp.json()
      setResult(data)
      setStage('done')
    } catch (err: any) {
      setResult({ success: false, ai_review: err.message })
      setStage('done')
    } finally {
      setRunning(false)
      clearInterval(timer)
    }
  }

  const allScriptsOk = result?.wc_ok && result?.compliance_ok && result?.forbidden_ok
  const issueList: string[] = []
  if (result && !result.wc_ok) issueList.push('字数不达标')
  if (result && !result.compliance_ok) issueList.push('合规检查未通过')
  if (result && !result.forbidden_ok) issueList.push('禁用模式超标')
  if (result && (result.bcontrast_count || 0) > 2) issueList.push(`二元对比超标(${result.bcontrast_count})`)
  if (result && (result.tell_count || 0) > 5) issueList.push(`叙述模式超标(${result.tell_count})`)

  return (
    <div>
      <h2>审稿台</h2>

      <Card title="章节审稿" style={{ marginBottom: 16 }}>
        <Space style={{ width: '100%' }} size="middle">
          <Space wrap>
            <span>卷：</span>
            <InputNumber min={1} value={volume} onChange={(v) => setVolume(v || 1)} />
            <span>章：</span>
            <InputNumber min={1} value={chapter} onChange={(v) => setChapter(v || 1)} />
          </Space>

          <Space>
            <Button type="primary" icon={<AuditOutlined />} onClick={handleReview} loading={running} disabled={!currentNovel}>
              运行审稿
            </Button>
            {running && (
              <Tag color="processing">
                审稿中 · {Math.floor(elapsed / 60)}分{elapsed % 60}秒
              </Tag>
            )}
          </Space>
        </Space>
      </Card>

      {running && (
        <Card title="审稿进度" style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div>
              <Progress percent={stage === 'scripts' ? 30 : stage === 'ai' ? 60 : 0} status="active" />
            </div>
            <Tag color={stage === 'scripts' ? 'processing' : stage === 'done' ? 'success' : 'default'}>
              {stage === 'scripts' ? '🔵 运行脚本检查...' : stage === 'done' ? '✅ 脚本检查完成' : '⚪ 等待脚本检查'}
            </Tag>
            <Tag color={stage === 'ai' ? 'processing' : stage === 'done' ? 'success' : 'default'}>
              {stage === 'ai' ? '🤖 AI 深度审稿分析...' : stage === 'done' ? '✅ AI 审稿完成' : '⚪ 等待AI审稿'}
            </Tag>
          </Space>
        </Card>
      )}

      {result && (
        <Card title="审稿结果" style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space>
              <Tag color={result.wc_ok ? 'success' : 'error'}>
                {result.wc_ok ? '✅' : '❌'} 字数
              </Tag>
              <Tag color={result.compliance_ok ? 'success' : 'error'}>
                {result.compliance_ok ? '✅' : '❌'} 合规
              </Tag>
              <Tag color={result.forbidden_ok ? 'success' : 'error'}>
                {result.forbidden_ok ? '✅' : '❌'} 禁用模式
              </Tag>
            </Space>

            {issueList.length > 0 && (
              <Alert
                type="warning"
                message={`仍有 ${issueList.length} 个问题: ${issueList.join(', ')}`}
                showIcon
              />
            )}

            {allScriptsOk && !issueList.length && (
              <Alert type="success" message="全部通过" showIcon icon={<CheckCircleOutlined />} />
            )}

            <Divider />

            {result.ai_review && (
              <div style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 6 }}>
                {result.ai_review}
              </div>
            )}

            {result.script_detail && (
              <>
                <Divider>脚本详情</Divider>
                <div style={{ whiteSpace: 'pre-wrap', fontSize: 12, color: '#666' }}>
                  {result.script_detail}
                </div>
              </>
            )}
          </Space>
        </Card>
      )}
    </div>
  )
}
