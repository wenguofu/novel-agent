import React, { useState, useEffect, useMemo } from 'react'
import { Card, Button, Space, Tag, Alert, Progress, Divider, message, List, Select } from 'antd'
import { AuditOutlined, CheckCircleOutlined, ToolOutlined, HistoryOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'
import ReactMarkdown from 'react-markdown'

interface ReviewResult {
  success: boolean
  wc_ok?: boolean; compliance_ok?: boolean; forbidden_ok?: boolean
  ai_review?: string; script_detail?: string
  bcontrast_count?: number; tell_count?: number; word_count?: number
  gate_blocked?: boolean; gate_requirements?: any[]
}

interface ReviewHistoryItem {
  key: string; chapter: string; date: string; status: string; issues: number
}

interface ChapterOption {
  label: string; value: number; words: number
}

export const Review: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [volumes, setVolumes] = useState<Array<{ name: string; chNum: number; chapters: ChapterOption[] }>>([])
  const [volume, setVolume] = useState<number>(1)
  const [chapter, setChapter] = useState<number>(1)
  const [running, setRunning] = useState(false)
  const [optimizing, setOptimizing] = useState(false)
  const [result, setResult] = useState<ReviewResult | null>(null)
  const [stage, setStage] = useState<'idle' | 'scripts' | 'ai' | 'done'>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [history, setHistory] = useState<ReviewHistoryItem[]>([])
  const [optimizedContent, setOptimizedContent] = useState('')

  // ── Fetch available volumes and chapters ──
  useEffect(() => {
    if (!currentNovel) return
    fetch(`/api/novels/${encodeURIComponent(currentNovel)}`)
      .then(r => r.json())
      .then(data => {
        const novel = data?.novel || data || {}
        const rawVols = Array.isArray(novel.volumes) ? novel.volumes : []
        const parsed = rawVols.map((v: any) => ({
          name: v.name,
          chNum: parseInt((v.name || '').replace('vol-', '')) || 0,
          chapters: (v.chapters || []).map((ch: any) => ({
            label: `第${(ch.name.match(/ch-(\d+)/) || ['', '0'])[1].replace(/^0+/, '')}章 (${ch.words?.toLocaleString() || 0}字)`,
            value: parseInt((ch.name.match(/ch-(\d+)/) || ['', '0'])[1]),
            words: ch.words || 0,
          })).sort((a: ChapterOption, b: ChapterOption) => a.value - b.value),
        })).sort((a: any, b: any) => a.chNum - b.chNum)
        setVolumes(parsed)
        // Auto-select first volume and chapter if available
        if (parsed.length > 0) {
          setVolume(parsed[0].chNum)
          if (parsed[0].chapters.length > 0) {
            setChapter(parsed[0].chapters[0].value)
          }
        }
      })
      .catch(() => setVolumes([]))
  }, [currentNovel])

  // ── Derived: selected volume's chapters ──
  const currentVolume = useMemo(
    () => volumes.find(v => v.chNum === volume),
    [volumes, volume]
  )
  const chapterOptions = currentVolume?.chapters || []

  const padNum = (n: number) => String(n).padStart(3, '0')

  const handleReview = async () => {
    if (!currentNovel) return
    if (!chapter) { message.warning('请先选择章节'); return }
    setRunning(true); setStage('scripts'); setResult(null); setOptimizedContent('')
    setElapsed(0)
    const start = Date.now()
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)

    try {
      const chRef = `vol-${String(volume).padStart(2, '0')}-ch-${padNum(chapter)}`
      // Script stage
      await new Promise((r) => setTimeout(r, 400))
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

      // Add to history
      const issueCount = [data.wc_ok, data.compliance_ok, data.forbidden_ok].filter(v => !v).length
        + (data.bcontrast_count > 2 ? 1 : 0) + (data.tell_count > 5 ? 1 : 0)
      setHistory(prev => [{
        key: `${chRef}-${Date.now()}`,
        chapter: chRef,
        date: new Date().toLocaleTimeString(),
        status: data.gate_blocked ? '门控阻止' : data.success ? '完成' : '失败',
        issues: issueCount,
      }, ...prev].slice(0, 20))
    } catch (err: any) {
      setResult({ success: false, ai_review: err.message })
      setStage('done')
    } finally {
      setRunning(false); clearInterval(timer)
    }
  }

  const handleOptimize = async () => {
    if (!currentNovel || !result) return
    const chRef = `vol-${String(volume).padStart(2, '0')}-ch-${padNum(chapter)}`
    setOptimizing(true)
    try {
      const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel)}/optimize-chapter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chapter_ref: chRef,
          volume: `vol-${String(volume).padStart(2, '0')}`,
          chapter_num: chapter,
          review_text: result?.ai_review || '',
          script_issues: JSON.stringify({
            wc_ok: result?.wc_ok,
            compliance_ok: result?.compliance_ok,
            forbidden_ok: result?.forbidden_ok,
            bcontrast_count: result?.bcontrast_count,
            tell_count: result?.tell_count,
          }),
        }),
      })
      const data = await resp.json()
      if (data.success) {
        setOptimizedContent(data.content || '')
        message.success('优化完成')
      } else {
        message.error(data.error || '优化失败')
      }
    } catch {
      message.error('优化请求失败')
    } finally { setOptimizing(false) }
  }

  const allScriptsOk = result?.wc_ok && result?.compliance_ok && result?.forbidden_ok
  const issueList: string[] = []
  if (result && !result.wc_ok) issueList.push('字数不达标')
  if (result && !result.compliance_ok) issueList.push('合规检查未通过')
  if (result && !result.forbidden_ok) issueList.push('禁用模式超标')
  if (result && (result.bcontrast_count || 0) > 2) issueList.push(`二元对比超标(${result.bcontrast_count}次)`)
  if (result && (result.tell_count || 0) > 5) issueList.push(`叙述模式超标(${result.tell_count}次)`)

  return (
    <div>
      <h2>审稿台</h2>

      <Card title="章节审稿" style={{ marginBottom: 16 }}>
        <Space style={{ width: '100%' }} size="middle">
          <Space wrap>
            <span>卷:</span>
            <Select
              value={volume}
              onChange={(v) => { setVolume(v); setChapter(0) }}
              style={{ width: 140 }}
              options={volumes.map(v => ({
                label: `${v.name} (${v.chapters.length}章)`,
                value: v.chNum,
              }))}
              placeholder="选择卷"
            />
            <span>章:</span>
            <Select
              value={chapter || undefined}
              onChange={(v) => setChapter(v)}
              style={{ width: 220 }}
              options={chapterOptions.map(ch => ({
                label: ch.label,
                value: ch.value,
              }))}
              placeholder={chapterOptions.length ? '选择章节' : '暂无章节'}
              disabled={chapterOptions.length === 0}
              notFoundContent="该卷暂无章节"
            />
          </Space>

          <Space>
            <Button type="primary" icon={<AuditOutlined />} onClick={handleReview}
              loading={running} disabled={!currentNovel || !chapter}>
              {running ? '审稿中...' : '运行审稿'}
            </Button>
            {running && (
              <Tag color="processing">{stage === 'ai' ? 'AI 分析中' : '脚本检查中'} · {elapsed}秒</Tag>
            )}
          </Space>
        </Space>
      </Card>

      {/* Progress */}
      {running && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Progress
            percent={stage === 'scripts' ? 25 : stage === 'ai' ? 65 : 0}
            status="active"
            strokeColor={{ from: '#108ee9', to: '#87d068' }}
          />
          <div style={{ marginTop: 8 }}>
            <Tag color={stage === 'scripts' ? 'processing' : stage === 'done' ? 'success' : 'default'}>
              {stage === 'scripts' ? '分析字数/合规/禁用模式...' : stage === 'done' ? '脚本检查完成' : '等待'}
            </Tag>
            <Tag color={stage === 'ai' ? 'processing' : stage === 'done' ? 'success' : 'default'}>
              {stage === 'ai' ? 'AI 深度审稿...' : stage === 'done' ? 'AI 审稿完成' : '等待 AI'}
            </Tag>
          </div>
        </Card>
      )}

      {/* Results */}
      {result && (
        <Card title="审稿结果" style={{ marginBottom: 16 }}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Space wrap>
              <Tag color={result.wc_ok ? 'success' : 'error'}>
                {result.wc_ok ? '✅' : '❌'} 字数 {result.word_count ? `(${result.word_count}字)` : ''}
              </Tag>
              <Tag color={result.compliance_ok ? 'success' : 'error'}>
                {result.compliance_ok ? '✅' : '❌'} 合规
              </Tag>
              <Tag color={result.forbidden_ok ? 'success' : 'error'}>
                {result.forbidden_ok ? '✅' : '❌'} 禁用模式
              </Tag>
              {result.bcontrast_count !== undefined && (
                <Tag color={result.bcontrast_count <= 2 ? 'success' : 'warning'}>
                  二元对比: {result.bcontrast_count}/{2}
                </Tag>
              )}
              {result.tell_count !== undefined && (
                <Tag color={result.tell_count <= 5 ? 'success' : 'warning'}>
                  叙述模式: {result.tell_count}/5
                </Tag>
              )}
            </Space>

            {result.gate_blocked && (
              <Alert type="warning" message="门控未通过，请先完成前置阶段"
                description={result.gate_requirements?.map((r: any) => r.detail).join('; ')} showIcon />
            )}

            {!result.gate_blocked && issueList.length > 0 && (
              <Alert type="warning" message={`${issueList.length} 个问题: ${issueList.join('; ')}`}
                action={<Button size="small" icon={<ToolOutlined />} type="primary"
                  onClick={handleOptimize} loading={optimizing}>一键修复</Button>}
                showIcon />
            )}

            {allScriptsOk && !issueList.length && !result.gate_blocked && (
              <Alert type="success" message="全部通过" showIcon icon={<CheckCircleOutlined />} />
            )}

            <Divider />

            {result.ai_review && (
              <div style={{
                whiteSpace: 'pre-wrap', background: '#fafafa', padding: 16,
                borderRadius: 8, border: '1px solid #f0f0f0', maxHeight: 400,
                overflow: 'auto', fontSize: 13, lineHeight: 1.6,
              }}>
                <ReactMarkdown>{result.ai_review}</ReactMarkdown>
              </div>
            )}

            {result.script_detail && (
              <>
                <Divider>脚本检查详情</Divider>
                <pre style={{
                  fontSize: 11, color: '#888', background: '#f5f5f5',
                  padding: 12, borderRadius: 4, maxHeight: 200, overflow: 'auto',
                  whiteSpace: 'pre-wrap', margin: 0,
                }}>
                  {result.script_detail}
                </pre>
              </>
            )}

            {optimizedContent && (
              <>
                <Divider>优化后内容</Divider>
                <div style={{
                  whiteSpace: 'pre-wrap', background: '#f6ffed', padding: 16,
                  borderRadius: 8, border: '1px solid #b7eb8f', maxHeight: 300,
                  overflow: 'auto', fontSize: 13,
                }}>
                  {optimizedContent.slice(0, 2000)}
                  {optimizedContent.length > 2000 && <div style={{ color: '#999', marginTop: 8 }}>... (内容已截断，全文已保存)</div>}
                </div>
              </>
            )}
          </Space>
        </Card>
      )}

      {/* History */}
      {history.length > 0 && (
        <Card title={<><HistoryOutlined /> 审稿历史 ({history.length})</>} size="small">
          <List
            size="small"
            dataSource={history}
            renderItem={(item) => (
              <List.Item>
                <Space>
                  <Tag color={item.status === '完成' ? 'success' : item.status === '门控阻止' ? 'warning' : 'error'}>
                    {item.status}
                  </Tag>
                  <span>{item.chapter}</span>
                  <span style={{ color: '#999', fontSize: 12 }}>{item.date}</span>
                  {item.issues > 0 && <Tag color="warning">{item.issues} 问题</Tag>}
                </Space>
              </List.Item>
            )}
          />
        </Card>
      )}
    </div>
  )
}
