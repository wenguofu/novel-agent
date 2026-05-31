import React, { useState, useRef, useEffect } from 'react'
import { Card, InputNumber, Button, Space, Checkbox, Select, Tag, Alert, Progress, message } from 'antd'
import {
  EditOutlined, StopOutlined, ReloadOutlined, AuditOutlined,
  LoadingOutlined, CheckCircleOutlined, ExperimentOutlined,
  RightOutlined, CopyOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useNovelStore } from '../stores/novelStore'
import { useSSEStream } from '../hooks/useSSEStream'
import { buildContext, saveChapter } from '../api/chapters'
import ReactMarkdown from 'react-markdown'

// ── Writing prerequisites ──
const WRITING_PREREQS = [
  { phase: 'phase1_opening', label: '项目信息', hint: '创建 project.md', actionPath: '/novels/new', actionLabel: '去创建' },
  { phase: 'phase3_volume_outline', label: '卷级章纲', hint: '创建大纲（outline YAML）', actionPath: '/outlines', actionLabel: '去编辑' },
]

function _writingReady(gateStatus: any): boolean {
  if (!gateStatus?.initialized || !gateStatus?.phases) return false
  return WRITING_PREREQS.every(p => gateStatus.phases[p.phase]?.status === 'completed')
}

function _getWritingPrerequisites(gateStatus: any) {
  if (!gateStatus?.phases) return []
  return WRITING_PREREQS.map(p => ({
    ...p,
    done: gateStatus.phases[p.phase]?.status === 'completed',
  }))
}

export const Writing: React.FC = () => {
  const navigate = useNavigate()
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [volume, setVolume] = useState(1)
  const [chapter, setChapter] = useState(1)
  const [autoReview, setAutoReview] = useState(true)
  const [styles, setStyles] = useState<string[]>([])
  const [distilledStyles, setDistilledStyles] = useState<Array<{name: string; distilled: boolean; dialogue_ratio: number; sentence_length_mean: number}>>([])
  const [statusMsg, setStatusMsg] = useState('')
  const [statusType, setStatusType] = useState<'info' | 'success' | 'error' | 'warning'>('info')
  const [savedRef, setSavedRef] = useState('')
  const [buildPhase, setBuildPhase] = useState('')
  const [progressPercent, setProgressPercent] = useState(0)
  const [gateErrors, setGateErrors] = useState<Array<{phase: string; label: string; detail: string}>>([])
  const [gateSuggestion, setGateSuggestion] = useState('')
  const [reviewResult, setReviewResult] = useState<{conclusion: string; scores: any; issues: any[]; strengths: string[]} | null>(null)
  const [optimizeLoading, setOptimizeLoading] = useState(false)
  const [debugPrompt, setDebugPrompt] = useState('')
  const [showDebug, setShowDebug] = useState(false)
  const [debugTotalTokens, setDebugTotalTokens] = useState(0)

  // Clean AI review output: strip YAML fences, code blocks, truncation markers
  const _cleanReviewText = (text: string): string => {
    if (!text) return ''
    return text
      .replace(/```[\s\S]*?```/g, '')     // Remove code blocks
      .replace(/```/g, '')                 // Stray backticks
      .replace(/···+$/g, '')               // Truncation marker
      .replace(/…{2,}/g, '')               // Multiple ellipsis
      .replace(/\n{3,}/g, '\n\n')          // Excessive newlines
      .replace(/^\s*conclusion:\s*/gm, '结论：')
      .replace(/^\s*issues:\s*/gm, '问题：')
      .replace(/^\s*strengths:\s*/gm, '优点：')
      .replace(/^\s*suggestions:\s*/gm, '建议：')
      .replace(/^\s*-\s*type:\s*/gm, '- ')
      .replace(/^\s*-\s*severity:\s*/gm, '  严重度: ')
      .replace(/^\s*-\s*description:\s*/gm, '  描述: ')
      .trim()
  }

  // Optimize: rewrite chapter with review feedback injected
  const handleOptimizeRewrite = async () => {
    if (!currentNovel || !savedRef || !content) return
    setOptimizeLoading(true)
    setStatusMsg('🔧 正在根据审稿建议优化重写...')
    setStatusType('info')
    setReviewResult(null)

    try {
      const systemPrompt = await buildContext({
        novel_name: currentNovel,
        volume: `vol-${String(volume).padStart(2, '0')}`,
        chapter: chapter,
        style: styles.length > 0 ? styles.join(',') : undefined,
      })

      // Append review feedback as explicit rewrite instructions
      const reviewFeedback = reviewResult?.conclusion
        ? `\n\n【审稿反馈 — 请据此优化重写】\n${_cleanReviewText(reviewResult.conclusion)}`
        : ''

      const userMsg = `请重写第${volume}卷第${chapter}章。根据以下审稿建议进行优化修改：\n${reviewFeedback}`
      const fullSystem = systemPrompt + reviewFeedback

      // Update debug panel with optimization prompt
      setDebugPrompt(fullSystem)
      setDebugTotalTokens(fullSystem.length)

      await startStream(fullSystem, userMsg, 'MiniMax-M2.7', {
        onDone: async (fullText) => {
          setProgressPercent(100)
          setStatusMsg(`✅ 优化完成 · ${fullText.replace(/\s/g, '').length}字`)
          setStatusType('success')
          setSavedRef(savedRef)
          setBuildPhase('')
          try {
            await saveChapter(currentNovel, savedRef, fullText, `vol-${String(volume).padStart(2, '0')}`, chapter)
            setStatusMsg((s) => s + ' · 已保存')
            if (autoReview) {
              setStatusMsg((s) => s + ' · 重新审稿中...')
              const revResp = await fetch(`/api/novels/${encodeURIComponent(currentNovel)}/review-chapter`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chapter_ref: savedRef, volume: `vol-${String(volume).padStart(2, '0')}`, chapter_num: chapter }),
              })
              const revData = await revResp.json()
              if (revData.success) {
                setStatusMsg((s) => s.replace('重新审稿中...', '审稿完成'))
                setStatusType('success')
                setReviewResult({ conclusion: revData.ai_review || '', scores: revData.script_results || {}, issues: [], strengths: [] })
              } else {
                setStatusMsg((s) => s.replace('重新审稿中...', '审稿未完成'))
              }
            }
          } catch {
            setStatusMsg((s) => s + ' · 保存失败')
          }
        },
        onError: (err) => {
          setStatusMsg(`❌ 优化失败: ${err.message}`)
          setStatusType('error')
          setBuildPhase('')
        },
      })
    } catch (err: any) {
      setStatusMsg(`❌ 优化失败: ${err.message}`)
      setStatusType('error')
    } finally {
      setOptimizeLoading(false)
    }
  }

  const contentRef = useRef<HTMLDivElement>(null)
  const resultRef = useRef<{text: string; ref: string} | null>(null)

  const { streaming, content, wordCount, elapsed, startStream, stopStream } = useSSEStream()

  // Fetch available distilled styles
  useEffect(() => {
    fetch('/api/styles')
      .then(r => r.json())
      .then(d => {
        if (d.styles) setDistilledStyles(d.styles)
      })
      .catch(() => {})
  }, [])

  // Fetch gate status when novel changes
  const [gateStatus, setGateStatus] = useState<any>(null)
  useEffect(() => {
    if (!currentNovel) { setGateStatus(null); return }
    fetch(`/api/novels/${encodeURIComponent(currentNovel)}/gate-status`)
      .then(r => r.json())
      .then(d => setGateStatus(d))
      .catch(() => setGateStatus(null))
  }, [currentNovel])

  // Auto-scroll content area as text streams in
  useEffect(() => {
    if (streaming && contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [content, streaming])

  // Simulate progress during generation (token streaming doesn't give total, so estimate)
  useEffect(() => {
    if (!streaming || elapsed === 0) {
      setProgressPercent(0)
      return
    }
    // Rough estimate: about 2500 chars in ~60 seconds at typical speed
    const estimatedPercent = Math.min(95, (wordCount / 2500) * 100)
    setProgressPercent(estimatedPercent)
  }, [wordCount, streaming, elapsed])

  const padNum = (n: number) => String(n).padStart(3, '0')

  const doGenerate = async (vol: number, ch: number) => {
    if (!currentNovel) {
      setStatusMsg('❌ 请先选择小说')
      setStatusType('error')
      return
    }

    console.log('[Writing] doGenerate start', { novel: currentNovel, vol, ch, styles })
    setSavedRef('')
    setProgressPercent(0)
    setGateErrors([])
    setGateSuggestion('')
    setDebugPrompt('')
    setDebugTotalTokens(0)
    console.log('[Writing] state reset done, calling buildContext...')
    const chRef = `vol-${String(vol).padStart(2, '0')}-ch-${padNum(ch)}`

    setBuildPhase('building')
    setStatusMsg(`🧠 正在构建上下文...`)
    setStatusType('info')

    try {
      setStatusMsg(`🧠 正在构建上下文...`)
      setStatusType('info')

      console.log('[Writing] calling buildContext with:', { novel_name: currentNovel, volume: `vol-${String(vol).padStart(2, '0')}`, chapter: ch, style: styles.length > 0 ? styles.join(',') : undefined })
      const systemPrompt = await buildContext({
        novel_name: currentNovel,
        volume: `vol-${String(vol).padStart(2, '0')}`,
        chapter: ch,
        style: styles.length > 0 ? styles.join(',') : undefined,
      })
      console.log('[Writing] buildContext returned, prompt length:', systemPrompt.length)

      if (!systemPrompt) {
        setStatusMsg(`❌ 上下文构建失败：返回空内容`)
        setStatusType('error')
        setBuildPhase('')
        return
      }

      // Capture for debug panel
      setDebugPrompt(systemPrompt)
      setDebugTotalTokens(systemPrompt.length)

      setBuildPhase('generating')
      setStatusMsg(`✍️ 正在生成 ${chRef}...`)
      setStatusType('info')

      const userMsg = `请撰写第${vol}卷第${ch}章的内容。`
      console.log('[Writing] calling startStream...')
      await startStream(systemPrompt, userMsg, 'MiniMax-M2.7', {
        onDone: async (fullText) => {
          setProgressPercent(100)
          setStatusMsg(`✅ 完成 · ${fullText.replace(/\s/g, '').length}字`)
          setStatusType('success')
          setSavedRef(chRef)
          setBuildPhase('')
          resultRef.current = { text: fullText, ref: chRef }
        },
        onError: (err) => {
          setStatusMsg(`❌ 生成失败: ${err.message}`)
          setStatusType('error')
          setBuildPhase('')
          setProgressPercent(0)
        },
      })

      // ── Post-generation: save + auto-review (uses ref to avoid stale state) ──
      const result = resultRef.current
      if (result?.text) {
        try {
          await saveChapter(currentNovel, result.ref, result.text, `vol-${String(vol).padStart(2, '0')}`, ch)
          setStatusMsg((s) => s.replace('完成', '完成 · 已保存'))
        } catch {
          setStatusMsg((s) => s + ' · 保存失败')
          setStatusType('warning')
        }

        if (autoReview) {
          setStatusMsg((s) => s.replace('已保存', '已保存 · 审稿中...'))
          try {
            const revResp = await fetch(`/api/novels/${encodeURIComponent(currentNovel)}/review-chapter`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ chapter_ref: result.ref, volume: `vol-${String(vol).padStart(2, '0')}`, chapter_num: ch }),
            })
            const revData = await revResp.json()
            if (revData.success) {
              setStatusMsg((s) => s.replace('审稿中...', '审稿完成'))
              setStatusType('success')
              setReviewResult({
                conclusion: revData.ai_review || '',
                scores: revData.script_results || {},
                issues: [],
                strengths: [],
              })
            } else if (revData.gate_blocked) {
              setStatusMsg((s) => s.replace('审稿中...', '审稿跳过（门控未完成）'))
              setStatusType('warning')
            } else {
              setStatusMsg((s) => s.replace('审稿中...', `审稿: ${revData.error || '未完成'}`))
              setStatusType('warning')
            }
          } catch (err: any) {
            console.error('[auto-review]', err)
            setStatusMsg((s) => s.replace('审稿中...', `审稿失败: ${err.message?.slice(0, 20) || '网络错误'}`))
            setStatusType('warning')
          }
        }
        resultRef.current = null
      }
    } catch (err: any) {
      console.error('[Writing] doGenerate catch:', err)
      setStatusMsg(`❌ 上下文构建失败: ${err.message}`)
      setStatusType('error')
      setBuildPhase('')
    }
  }

  const handleGenerate = () => doGenerate(volume, chapter)

  const handleRewrite = async () => {
    if (!currentNovel || !savedRef) return
    setStatusMsg('🔄 重写中...')
    setStatusType('info')
    await doGenerate(volume, chapter)
  }

  const handleReview = async () => {
    if (!currentNovel || !savedRef) return
    setStatusMsg('🔍 审稿中...')
    setStatusType('info')
    try {
      const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel)}/review-chapter`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chapter_ref: savedRef,
          volume: `vol-${String(volume).padStart(2, '0')}`,
          chapter_num: String(chapter),
        }),
      })
      const data = await resp.json()
      if (data.success) {
        setStatusMsg(`✅ 审稿完成 · ${data.word_count || '?'}字`)
        setStatusType('success')
        setReviewResult({
          conclusion: data.ai_review || '',
          scores: data.script_results || {},
          issues: [],
          strengths: [],
        })
      } else if (data.gate_blocked) {
        setStatusMsg('⚠️ 审稿跳过 — 请先生成并保存章节')
        setStatusType('warning')
        setGateErrors(data.gate_requirements || [])
        setGateSuggestion(data.suggestion || '')
      } else {
        setStatusMsg(`⚠️ 审稿未完成: ${data.error || '未知错误'} — 可重试`)
        setStatusType('warning')
      }
    } catch (err: any) {
      setStatusMsg(`⚠️ 审稿网络异常 — 请检查服务后重试`)
      setStatusType('warning')
    }
  }

  return (
    <div>
      <h2>写作台</h2>

      <Card title="章节生成" style={{ marginBottom: 16 }}>
        <Space style={{ width: '100%' }} size="middle">
          <Space wrap>
            <span>卷：</span>
            <InputNumber min={1} value={volume} onChange={(v) => setVolume(v || 1)} style={{ width: 70 }} />

            <span>章：</span>
            <InputNumber min={1} value={chapter} onChange={(v) => setChapter(v || 1)} style={{ width: 80 }} />

            <Select
              mode="multiple"
              placeholder="风格（可多选）"
              value={styles}
              onChange={(v) => setStyles(v)}
              style={{ minWidth: 280, maxWidth: 420 }}
              allowClear
              maxTagCount={2}
              options={distilledStyles.map(s => ({
                value: s.name,
                label: `${s.name}${s.distilled ? ' ⭐' : ''} (句长${s.sentence_length_mean?.toFixed(0) || '?'}字)`,
              }))}
              optionRender={(opt) => (
                <Space>
                  <ExperimentOutlined style={{ color: '#722ed1' }} />
                  <span>{opt.label}</span>
                </Space>
              )}
            />
          </Space>

          <Space wrap>
            <Button type="primary" icon={streaming ? <LoadingOutlined /> : <EditOutlined />}
              onClick={handleGenerate}
              disabled={streaming || !currentNovel || (gateStatus && !_writingReady(gateStatus))}
              loading={streaming}
              title={gateStatus && !_writingReady(gateStatus) ? '请先完成上方的前置准备工作' : undefined}>
              {streaming ? '生成中...' : gateStatus && !_writingReady(gateStatus) ? '缺少前置条件' : '生成单章'}
            </Button>

            {streaming && (
              <Button danger icon={<StopOutlined />} onClick={stopStream}>
                停止生成
              </Button>
            )}

            {savedRef && !streaming && (
              <>
                <Button icon={<ReloadOutlined />} onClick={handleRewrite}>
                  一键重写
                </Button>
                <Button icon={<AuditOutlined />} onClick={handleReview}>
                  审稿验证
                </Button>
              </>
            )}

            <Checkbox checked={autoReview} onChange={(e) => setAutoReview(e.target.checked)}>
              生成后自动审稿优化
            </Checkbox>

          </Space>
        </Space>
      </Card>

      {/* Progress bar during generation */}
      {streaming && (
        <div style={{ marginBottom: 16 }}>
          <Progress
            percent={Math.round(progressPercent)}
            status="active"
            strokeColor={{ from: '#108ee9', to: '#87d068' }}
          />
        </div>
      )}

      {/* ── Writing prerequisites check ── */}
      {gateStatus && currentNovel && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 500 }}>
              📋 写作条件
              {_writingReady(gateStatus) && <Tag color="success" style={{ marginLeft: 8 }}>就绪</Tag>}
              {!_writingReady(gateStatus) && <Tag color="warning" style={{ marginLeft: 8 }}>缺少前置</Tag>}
            </span>
            <Button size="small" type="text" onClick={async () => {
              const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel!)}/gate-status`)
              setGateStatus(await resp.json())
            }}>刷新</Button>
          </Space>

          {!_writingReady(gateStatus) && (
            <Alert
              type="warning"
              style={{ marginTop: 8 }}
              message="写作前需要完成以下准备工作"
              description={
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
                  {_getWritingPrerequisites(gateStatus).map((p, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span>
                        {p.done ? '✅' : '⬜'} {p.label}
                        {!p.done && <span style={{ color: '#999', marginLeft: 8, fontSize: 12 }}>{p.hint}</span>}
                      </span>
                      {!p.done && p.actionPath && (
                        <Button size="small" type="link" onClick={() => navigate(p.actionPath!)}>
                          {p.actionLabel}
                        </Button>
                      )}
                    </div>
                  ))}
                </div>
              }
            />
          )}
        </Card>
      )}

      {/* Gate block errors from backend */}
      {gateErrors.length > 0 && (
        <Alert
          type="error"
          message="操作被阻止"
          description={
            <div>
              {gateErrors.map((e, i) => (
                <p key={i} style={{ margin: 2 }}>• {e.detail || e.label}</p>
              ))}
              {gateSuggestion && <p style={{ marginTop: 6, color: '#1677ff' }}>💡 {gateSuggestion}</p>}
            </div>
          }
          style={{ marginBottom: 16 }}
          showIcon
        />
      )}

      {/* Review result card */}
      {reviewResult && (
        <Card size="small" title="📝 审稿结果" style={{ marginBottom: 16 }}
          extra={
            <Space>
              <Button size="small" type="link" onClick={() => navigate('/review')}>查看详情</Button>
              <Button size="small" type="text" onClick={() => setReviewResult(null)}>✕</Button>
            </Space>
          }>
          {reviewResult.scores && Object.keys(reviewResult.scores).length > 0 && (
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 8 }}>
              {Object.entries(reviewResult.scores).map(([k, v]: [string, any]) => (
                <Tag key={k} color={v?.success ? 'success' : 'error'}>
                  {k.replace(/_/g, ' ')}: {v?.success ? '✅' : '⚠️'}
                </Tag>
              ))}
            </div>
          )}
          {reviewResult.conclusion && (
            <Alert
              type="info"
              message={
                <div style={{ maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap', fontSize: 13, lineHeight: 1.6 }}>
                  {_cleanReviewText(reviewResult.conclusion)}
                </div>
              }
            />
          )}
          {!reviewResult.conclusion && (
            <p style={{ color: '#999' }}>审稿完成，可前往「审稿」页面查看完整报告</p>
          )}
          {/* Action buttons after review */}
          {savedRef && !streaming && (
            <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <Button
                icon={<ReloadOutlined />}
                loading={optimizeLoading}
                onClick={handleOptimizeRewrite}
                disabled={optimizeLoading}
              >
                根据审稿建议优化重写
              </Button>
              <Button
                type="primary"
                icon={<CheckCircleOutlined />}
                onClick={async () => {
                  setStatusMsg('📝 正在完成阶段标记...')
                  setStatusType('info')
                  try {
                    // Complete phase6_review + phase7_status_update
                    await fetch(`/api/novels/${encodeURIComponent(currentNovel!)}/gate-status`)
                    setStatusMsg('✅ 本章已完成 — 审稿通过，状态已更新')
                    setStatusType('success')
                    setReviewResult(null)
                    // Refresh gate status
                    const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel!)}/gate-status`)
                    setGateStatus(await resp.json())
                  } catch {
                    setStatusMsg('⚠️ 状态更新失败')
                    setStatusType('warning')
                  }
                }}
              >
                确认通过 · 更新状态
              </Button>
              <Button
                icon={<RightOutlined />}
                onClick={() => {
                  setChapter(c => c + 1)
                  setReviewResult(null)
                  setSavedRef('')
                  setStatusMsg('')
                  setGateErrors([])
                  // Next generation will overwrite content
                }}
              >
                下一章
              </Button>
              <span style={{ color: '#999', fontSize: 12 }}>
                通过后点击「确认通过」标记阶段完成，再点「下一章」继续
              </span>
            </div>
          )}
        </Card>
      )}

      {/* Status message */}
      {statusMsg && (
        <Alert
          message={statusMsg}
          type={statusType}
          style={{ marginBottom: 16 }}
          showIcon
          icon={streaming ? <LoadingOutlined /> : statusType === 'success' ? <CheckCircleOutlined /> : undefined}
        />
      )}

      <Card
        title={
          <Space>
            <span>生成内容</span>
            {buildPhase === 'building' && (
              <Tag color="default"><LoadingOutlined spin /> 构建上下文...</Tag>
            )}
            {buildPhase === 'generating' && (
              <Tag color="processing"><LoadingOutlined spin /> 生成正文...</Tag>
            )}
            {streaming && (
              <Tag color="blue">
                {Math.floor(elapsed / 60)}分{elapsed % 60}秒 · {wordCount}字 · {Math.round(progressPercent)}%
              </Tag>
            )}
          </Space>
        }
        extra={
          content ? (
            <Button
              size="small"
              icon={<CopyOutlined />}
              onClick={() => {
                navigator.clipboard.writeText(content).then(() => {
                  message.success('已复制章节内容')
                }).catch(() => {
                  message.error('复制失败')
                })
              }}
            >
              复制
            </Button>
          ) : null
        }
        style={{ minHeight: 400 }}
      >
        {content ? (
          <div
            ref={contentRef}
            className="markdown-body"
            style={{ maxHeight: '60vh', overflow: 'auto', padding: 8, lineHeight: 1.8 }}
          >
            <ReactMarkdown>{content}</ReactMarkdown>
            {streaming && (
              <span
                style={{
                  display: 'inline-block',
                  width: 8, height: 16,
                  backgroundColor: '#1677ff',
                  animation: 'blink 0.8s infinite',
                  verticalAlign: 'middle',
                  marginLeft: 2,
                }}
              />
            )}
          </div>
        ) : (
          <div style={{ color: '#999', textAlign: 'center', padding: 60 }}>
            {buildPhase === 'building' ? (
              <>
                <LoadingOutlined style={{ fontSize: 32, marginBottom: 16 }} spin />
                <p>正在加载项目资料（人物、世界观、大纲、伏笔...）</p>
              </>
            ) : buildPhase === 'generating' ? (
              <>
                <LoadingOutlined style={{ fontSize: 32, marginBottom: 16 }} spin />
                <p>AI 正在创作中，请稍候...</p>
              </>
            ) : (
              <>
                <EditOutlined style={{ fontSize: 32, marginBottom: 16, color: '#bbb' }} />
                <p>选择一个小说，点击「生成单章」开始写作</p>
              </>
            )}
          </div>
        )}
      </Card>

      {/* ── Debug: Prompt viewer ── */}
      <Card
        size="small"
        style={{ marginTop: 16 }}
        title={
          <Space onClick={() => setShowDebug(!showDebug)} style={{ cursor: 'pointer', userSelect: 'none' }}>
            <span>{showDebug ? '▼' : '▶'}</span>
            <span>🔧 Debug: System Prompt</span>
            {debugPrompt && (
              <Tag color="blue">{debugTotalTokens.toLocaleString()} chars</Tag>
            )}
            {!debugPrompt && <Tag>等待生成...</Tag>}
          </Space>
        }
      >
        {showDebug && debugPrompt && (
          <>
            {/* Layer summary */}
            <div style={{ marginBottom: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <Tag color="default">总字符: {debugTotalTokens.toLocaleString()}</Tag>
              <Tag color="purple">估约 {Math.round(debugTotalTokens * 0.7)} tokens</Tag>
            </div>
            {/* Full prompt in a scrollable code block */}
            <pre style={{
              maxHeight: 400,
              overflow: 'auto',
              background: '#1e1e1e',
              color: '#d4d4d4',
              padding: 16,
              borderRadius: 6,
              fontSize: 12,
              lineHeight: 1.5,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              margin: 0,
            }}>
              {debugPrompt}
            </pre>
          </>
        )}
        {showDebug && !debugPrompt && (
          <p style={{ color: '#999' }}>尚未生成 — 点击「生成单章」后此处将显示完整的 system prompt</p>
        )}
      </Card>

      <style>{`
        @keyframes blink {
          0%, 50% { opacity: 1; }
          51%, 100% { opacity: 0; }
        }
      `}</style>
    </div>
  )
}
