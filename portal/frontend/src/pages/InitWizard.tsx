import React, { useState } from 'react'
import { Card, Button, Space, message, Alert, Tag } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

const TABLE_NAMES: Record<string, string> = {
  world_building: '世界观', plot_arcs: '剧情弧线', pacing: '节奏控制', revelation: '信息释放',
  characters: '人物', foreshadowing: '伏笔', genre_rules: '类型规则', story_volumes: '故事卷',
  volume_plans: '卷计划', alias_names: '别名', project_meta: '项目元数据',
}

export const InitWizard: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<Record<string, number> | null>(null)

  const handleInit = async () => {
    if (!currentNovel) return
    setLoading(true); setResult(null)
    try {
      const resp = await fetch(`/api/init/full/${encodeURIComponent(currentNovel)}`, { method: 'POST' })
      const data = await resp.json()
      if (data.success) {
        setResult(data.results || data.tables || data)
        const total = Object.values(data.results || data.tables || data).reduce((a: number, b: any) => a + (typeof b === 'number' ? b : (b.created || 0)), 0)
        message.success(`初始化完成，共导入 ${total} 条数据`)
      }
    } catch { message.error('初始化失败') }
    finally { setLoading(false) }
  }

  return (
    <div>
      <h2>初始化向导</h2>
      <Card>
        <Space style={{ width: '100%' }} size="middle">
          <Space>
            <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleInit} loading={loading} size="large">
              一键初始化
            </Button>
          </Space>

          <Alert message="从项目文件（project.md、characters.md、world_bible.md等）批量导入数据到数据库，包括世界观、人物、伏笔、节奏等信息。" type="info" showIcon />

          {result && (
            <Card title="初始化结果" size="small">
              <Space wrap>
                {Object.entries(result).map(([key, val]) => (
                  <Tag key={key} color={val > 0 ? 'success' : 'default'}>
                    {TABLE_NAMES[key] || key}: {typeof val === 'number' ? val : (val as any).created || 0}
                  </Tag>
                ))}
              </Space>
            </Card>
          )}
        </Space>
      </Card>
    </div>
  )
}
