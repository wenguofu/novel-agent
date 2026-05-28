import React, { useState, useRef } from 'react'
import { Card, InputNumber, Button, Space, Checkbox, Input, Tag, Alert } from 'antd'
import {
  EditOutlined, StopOutlined, ReloadOutlined, AuditOutlined,
} from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'
import { useSSEStream } from '../hooks/useSSEStream'
import { buildContext, saveChapter } from '../api/chapters'
import ReactMarkdown from 'react-markdown'

export const Writing: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [volume, setVolume] = useState(1)
  const [chapter, setChapter] = useState(1)
  const [autoReview, setAutoReview] = useState(true)
  const [style, setStyle] = useState('')
  const [autoLoop, setAutoLoop] = useState(false)
  const [loopChapters, setLoopChapters] = useState(5)
  const [statusMsg, setStatusMsg] = useState('')
  const [savedRef, setSavedRef] = useState('')

  const loopRef = useRef(false)
  const loopCountRef = useRef(0)

  const { streaming, content, wordCount, elapsed, startStream, stopStream } = useSSEStream()

  const padNum = (n: number) => String(n).padStart(3, '0')

  const doGenerate = async (vol: number, ch: number) => {
    if (!currentNovel) return

    setSavedRef('')
    const chRef = `vol-${String(vol).padStart(2, '0')}-ch-${padNum(ch)}`

    setStatusMsg(`✍️ 正在生成 ${chRef}...`)

    try {
      const systemPrompt = await buildContext({
        novel_name: currentNovel,
        volume: `vol-${String(vol).padStart(2, '0')}`,
        chapter: ch,
        style: style || undefined,
      })

      const userMsg = `请撰写第${vol}卷第${ch}章的内容。`

      await startStream(systemPrompt, userMsg, 'deepseek-chat', {
        onDone: async (fullText) => {
          setStatusMsg(`✅ 完成 · ${fullText.replace(/\s/g, '').length}字`)
          setSavedRef(chRef)

          // Auto-save
          try {
            await saveChapter(currentNovel, chRef, fullText, `vol-${String(vol).padStart(2, '0')}`, ch)
            setStatusMsg((s) => s + ' · 已保存')

            // Auto-review if enabled
            if (autoReview) {
              setStatusMsg((s) => s + ' · 自动审稿中...')
              try {
                const revResp = await fetch(`/api/novels/${encodeURIComponent(currentNovel)}/review-chapter`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ chapter_ref: chRef, volume: `vol-${String(vol).padStart(2, '0')}`, chapter_num: ch }),
                })
                const revData = await revResp.json()
                if (revData.success) {
                  setStatusMsg((s) => s.replace('自动审稿中...', '审稿完成'))
                }
              } catch {
                setStatusMsg((s) => s.replace('自动审稿中...', '审稿失败'))
              }
            }
          } catch {
            setStatusMsg((s) => s + ' · 保存失败')
          }
        },
        onError: (err) => {
          setStatusMsg(`❌ 生成失败: ${err.message}`)
        },
      })
    } catch (err: any) {
      setStatusMsg(`❌ 失败: ${err.message}`)
    }
  }

  const handleGenerate = () => doGenerate(volume, chapter)

  const handleAutoLoop = async () => {
    if (autoLoop) {
      loopRef.current = false
      setAutoLoop(false)
      return
    }

    setAutoLoop(true)
    loopRef.current = true
    loopCountRef.current = 0

    let v = volume
    let c = chapter

    while (loopRef.current && loopCountRef.current < loopChapters) {
      await doGenerate(v, c)
      loopCountRef.current++
      c++
      setChapter(c)
      if (!loopRef.current) break
      // brief pause between chapters
      await new Promise((r) => setTimeout(r, 2000))
    }

    setAutoLoop(false)
    loopRef.current = false
  }

  const handleRewrite = async () => {
    if (!currentNovel || !savedRef) return
    setStatusMsg('🔄 重写中...')
    await doGenerate(volume, chapter)
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

            <Input
              placeholder="风格（可选，如：金庸风）"
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              style={{ width: 200 }}
            />
          </Space>

          <Space wrap>
            <Button type="primary" icon={<EditOutlined />} onClick={handleGenerate} disabled={streaming || !currentNovel}>
              生成单章
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
                <Button icon={<AuditOutlined />} onClick={() => {/* navigate to review */}}>
                  审稿验证
                </Button>
              </>
            )}

            <Checkbox checked={autoReview} onChange={(e) => setAutoReview(e.target.checked)}>
              生成后自动审稿优化
            </Checkbox>

            <Space>
              <Checkbox checked={autoLoop} onChange={handleAutoLoop}>
                自动续写
              </Checkbox>
              {autoLoop && (
                <InputNumber
                  min={1}
                  max={50}
                  value={loopChapters}
                  onChange={(v) => setLoopChapters(v || 5)}
                  style={{ width: 60 }}
                  size="small"
                />
              )}
              {autoLoop && <Tag color="processing">运行中 {loopCountRef.current}/{loopChapters}</Tag>}
            </Space>
          </Space>
        </Space>
      </Card>

      {statusMsg && (
        <Alert
          message={statusMsg}
          type={statusMsg.startsWith('❌') ? 'error' : statusMsg.startsWith('✅') ? 'success' : 'info'}
          style={{ marginBottom: 16 }}
          showIcon
        />
      )}

      <Card
        title={
          <Space>
            <span>生成内容</span>
            {streaming && (
              <Tag color="blue">
                {Math.floor(elapsed / 60)}分{elapsed % 60}秒 · {wordCount}字
              </Tag>
            )}
          </Space>
        }
        style={{ minHeight: 400 }}
      >
        {content ? (
          <div className="markdown-body" style={{ maxHeight: '60vh', overflow: 'auto', padding: 8 }}>
            <ReactMarkdown>{content}</ReactMarkdown>
            {streaming && <span className="stream-cursor">▊</span>}
          </div>
        ) : (
          <div style={{ color: '#999', textAlign: 'center', padding: 60 }}>
            {streaming ? '生成中...' : '选择一个小说，点击「生成单章」开始写作'}
          </div>
        )}
      </Card>
    </div>
  )
}
