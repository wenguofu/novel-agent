import React from 'react'
import { Card, Row, Col, Statistic, List, Tag, Button, Space } from 'antd'
import {
  BookOutlined,
  FileTextOutlined,
  EditOutlined,
  SettingOutlined,
  ReadOutlined,
  AppstoreOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { useNovelStore } from '../stores/novelStore'
import { useNovels } from '../api/client'
import { EmotionCurveChart } from '../components/EmotionCurveChart'

export const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const setCurrentNovel = useNovelStore((s) => s.setCurrentNovel)
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const { data: novels = [], isLoading } = useNovels()

  const totalChapters = novels.reduce((sum, n) => sum + n.total_chapters, 0)
  const totalWords = novels.reduce((sum, n) => sum + (n.total_words || 0), 0)

  const handleNovelAction = (name: string, action: string) => {
    setCurrentNovel(name)
    navigate(action)
  }

  const activeNovel = currentNovel || (novels.length > 0 ? novels[0].name : null)

  return (
    <div>
      <h2>控制台</h2>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="小说数量"
              value={novels.length}
              prefix={<BookOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="总章节"
              value={totalChapters}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="总字数"
              value={totalWords}
              prefix={<EditOutlined />}
              formatter={(v) =>
                typeof v === 'number'
                  ? v >= 10000
                    ? `${(v / 10000).toFixed(1)} 万`
                    : v.toLocaleString()
                  : String(v)
              }
            />
          </Card>
        </Col>
      </Row>

      {activeNovel && (
        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={24}>
            <EmotionCurveChart novelName={activeNovel} compact />
          </Col>
        </Row>
      )}

      <Card title="欢迎使用 NovelForge" loading={isLoading}>
        <p style={{ color: '#666', marginBottom: 16 }}>
          选择一个小说开始写作，或创建新的小说项目。
        </p>

        <List
          dataSource={novels}
          locale={{ emptyText: '暂无小说，点击上方「新建小说」开始' }}
          renderItem={(novel) => (
            <List.Item
              actions={[
                <Button
                  size="small"
                  icon={<AppstoreOutlined />}
                  onClick={() => setCurrentNovel(novel.name)}
                >
                  内容管理
                </Button>,
                <Button
                  type="primary"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => handleNovelAction(novel.name, '/writing')}
                >
                  写作
                </Button>,
                <Button
                  size="small"
                  icon={<ReadOutlined />}
                  onClick={() => handleNovelAction(novel.name, '/chapters')}
                >
                  浏览
                </Button>,
                <Button
                  size="small"
                  icon={<SettingOutlined />}
                  onClick={() => handleNovelAction(novel.name, '/config')}
                >
                  设置
                </Button>,
              ]}
            >
              <List.Item.Meta
                title={
                  <Space>
                    <BookOutlined />
                    {novel.title || novel.name}
                    {novel.genre && <Tag>{novel.genre}</Tag>}
                  </Space>
                }
                description={`${novel.total_chapters} 章 · ${(novel.total_words || 0).toLocaleString()} 字${novel.last_chapter ? ` · 最近: ${novel.last_chapter}` : ''}`}
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  )
}
