import React, { useState, useEffect } from 'react'
import { Card, Steps, Button, Space, Tag, Alert } from 'antd'
import {
  CheckCircleOutlined, ClockCircleOutlined, PlayCircleOutlined,
  FileTextOutlined, BookOutlined, TeamOutlined,
  EnvironmentOutlined, OrderedListOutlined, EditOutlined,
} from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'
import { useNavigate } from 'react-router-dom'

const ONBOARDING_STEPS = [
  {
    title: '项目信息',
    description: '创建 project.md — 作品名、类型、卖点、篇幅目标',
    icon: <FileTextOutlined />,
    file: 'project.md',
  },
  {
    title: '类型规则',
    description: '创建 genre_bible.md — 类型承诺、桥段、禁用写法',
    icon: <BookOutlined />,
    file: 'genre_bible.md',
  },
  {
    title: '世界观',
    description: '创建 world_bible.md — 力量体系、地图、组织、规则',
    icon: <EnvironmentOutlined />,
    file: 'world_bible.md',
  },
  {
    title: '人物档案',
    description: '创建 characters.md — 主角、配角、反派、关系',
    icon: <TeamOutlined />,
    file: 'characters.md',
  },
  {
    title: '章纲规划',
    description: '创建第一卷章纲 — 章节标题、功能、节奏',
    icon: <OrderedListOutlined />,
    file: 'outline/vol-01-chapters.md',
  },
  {
    title: '写第一章',
    description: '生成第一章正文 — 用写作台AI生成',
    icon: <EditOutlined />,
    file: 'manuscript/vol-01/ch-0001.md',
  },
]

export const Onboarding: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const navigate = useNavigate()
  const [completedSteps, setCompletedSteps] = useState<number[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (currentNovel) {
      checkProgress()
    }
  }, [currentNovel])

  const checkProgress = async () => {
    setLoading(true)
    try {
      const resp = await fetch(`/api/novels/${encodeURIComponent(currentNovel!)}/files`)
      const data = await resp.json()
      const existingFiles: string[] = data.files?.map((f: any) => f.path) || []

      const completed: number[] = []
      ONBOARDING_STEPS.forEach((step, idx) => {
        if (existingFiles.some((f: string) => f.includes(step.file.replace(/^.*\//, '')))) {
          completed.push(idx)
        }
      })
      setCompletedSteps(completed)
    } catch {
      // Graceful fallback
    }
    setLoading(false)
  }

  const currentStep = completedSteps.length

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <h2>📖 新书引导</h2>

      {!currentNovel && (
        <Alert
          type="info"
          message="请先在首页选择或创建一本小说"
          style={{ marginBottom: 16 }}
        />
      )}

      <Card style={{ marginBottom: 16 }}>
        <p>
          欢迎使用 novel-agent！通过以下6个步骤，完成新书的初始设定。
          每完成一步，系统会自动检测并标记完成。
        </p>

        <Steps
          direction="vertical"
          current={currentStep}
          items={ONBOARDING_STEPS.map((step, idx) => ({
            title: (
              <Space>
                {step.icon}
                <span>{step.title}</span>
                {completedSteps.includes(idx) ? (
                  <Tag color="success" icon={<CheckCircleOutlined />}>已完成</Tag>
                ) : idx === currentStep ? (
                  <Tag color="processing" icon={<PlayCircleOutlined />}>进行中</Tag>
                ) : (
                  <Tag icon={<ClockCircleOutlined />}>待完成</Tag>
                )}
              </Space>
            ),
            description: (
              <div>
                <p>{step.description}</p>
                <p style={{ color: '#888', fontSize: 12 }}>
                  目标文件: <code>{step.file}</code>
                </p>
              </div>
            ),
          }))}
        />
      </Card>

      {currentNovel && (
        <Space>
          {currentStep < ONBOARDING_STEPS.length && (
            <Button
              type="primary"
              onClick={() => {
                if (currentStep === 5) {
                  navigate('/writing')
                } else if (currentStep === 4) {
                  navigate('/outlines')
                } else if (currentStep === 3) {
                  navigate('/characters')
                } else if (currentStep === 2) {
                  navigate('/world')
                } else {
                  navigate('/novels/new')
                }
              }}
            >
              继续第{currentStep + 1}步：{ONBOARDING_STEPS[currentStep].title}
            </Button>
          )}
          <Button onClick={checkProgress} loading={loading}>
            刷新进度
          </Button>
          {currentStep >= ONBOARDING_STEPS.length && (
            <Button type="primary" onClick={() => navigate('/writing')}>
              🎉 全部完成！开始写作
            </Button>
          )}
        </Space>
      )}
    </div>
  )
}
