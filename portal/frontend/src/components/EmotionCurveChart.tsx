import React from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from 'recharts'
import { Card, Spin, Empty, Button, Typography } from 'antd'
import { BarChartOutlined } from '@ant-design/icons'

const { Text } = Typography

interface PacingEntry {
  chapter_start: number
  chapter_end: number
  pace_type: string
  intensity: number
  emotion_target: string
}

interface EmotionCurveProps {
  novelName: string | null
  volume?: number
  compact?: boolean
}

const PACE_COLORS: Record<string, string> = {
  '高潮': '#f5222d',
  '铺垫': '#faad14',
  '过渡': '#1890ff',
  '释缓': '#52c41a',
}

export const EmotionCurveChart: React.FC<EmotionCurveProps> = ({
  novelName, compact = false,
}) => {
  const [data, setData] = React.useState<any[]>([])
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  const fetchPacingData = React.useCallback(async () => {
    if (!novelName) return
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(`/api/novels/${encodeURIComponent(novelName)}/file?path=outline/vol-01-chapters.md`)
      if (!resp.ok) {
        setError('暂无节奏数据')
        return
      }
      const result = await resp.json()
      if (!result.success || !result.content) {
        setError('暂无节奏数据')
        return
      }

      // Parse rhythm table from outline content
      const content = result.content
      const entries: PacingEntry[] = []

      // Match table rows: | 042-045 | pace | ... | emotion | ...
      const rowRegex = /^\|\s*(\d{3})\s*[-–]\s*(\d{3})\s*\|\s*([^|]+?)\s*\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|/gm
      let match
      while ((match = rowRegex.exec(content)) !== null) {
        const chStart = parseInt(match[1])
        const chEnd = parseInt(match[2])
        const paceLabel = match[3].trim()
        const emotionText = match[4].trim()

        let paceType = '过渡'
        let intensity = 5
        if (['高潮', '高压', '危机'].some(kw => paceLabel.includes(kw))) {
          paceType = '高潮'; intensity = 9
        } else if (['铺垫', '伏笔'].some(kw => paceLabel.includes(kw))) {
          paceType = '铺垫'; intensity = 4
        } else if (['释缓', '放松', '日常'].some(kw => paceLabel.includes(kw))) {
          paceType = '释缓'; intensity = 3
        }

        let emotion = ''
        for (const kw of ['爽', '虐', '悬', '燃', '暖', '惧', '压抑', '期待', '惊喜', '好奇']) {
          if (emotionText.includes(kw)) { emotion = kw; break }
        }

        entries.push({ chapter_start: chStart, chapter_end: chEnd, pace_type: paceType, intensity, emotion_target: emotion })
      }

      // Convert to chart data points (one per entry)
      const chartData = entries.map(e => ({
        chapter: `${e.chapter_start}-${e.chapter_end}`,
        chapterNum: e.chapter_start,
        intensity: e.intensity,
        pace: e.pace_type,
        emotion: e.emotion_target,
        label: `${e.pace_type}${e.emotion_target ? ' · ' + e.emotion_target : ''}`,
      }))

      setData(chartData)
    } catch {
      setError('加载节奏数据失败')
    } finally {
      setLoading(false)
    }
  }, [novelName])

  React.useEffect(() => {
    fetchPacingData()
  }, [fetchPacingData])

  if (!novelName) {
    return (
      <Card size="small">
        <Empty description="请先选择小说" />
      </Card>
    )
  }

  if (loading) {
    return (
      <Card size="small" style={{ textAlign: 'center', padding: 40 }}>
        <Spin />
        <div style={{ marginTop: 8 }}>
          <Text type="secondary">加载情绪曲线...</Text>
        </div>
      </Card>
    )
  }

  if (error || data.length === 0) {
    return (
      <Card
        size="small"
        title={<><BarChartOutlined /> 情绪曲线</>}
      >
        <Empty description={error || "暂无节奏数据，请先初始化卷纲节奏表"}>
          <Button size="small" onClick={fetchPacingData}>重新加载</Button>
        </Empty>
      </Card>
    )
  }

  const height = compact ? 200 : 300

  return (
    <Card
      size="small"
      title={<><BarChartOutlined /> 章季节奏 / 情绪曲线</>}
      extra={<Text type="secondary" style={{ fontSize: 12 }}>{data.length} 个数据点</Text>}
    >
      <ResponsiveContainer width="100%" height={height}>
        <LineChart
          data={data}
          margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="chapter"
            tick={{ fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis domain={[0, 10]} tick={{ fontSize: 11 }} />
          <Tooltip
            formatter={(value: any, name: any) => {
              if (name === 'intensity') return [`${value}/10`, '强度']
              return [value, name]
            }}
            labelFormatter={(label: any) => {
              return `章节 ${label}`
            }}
          />
          <Legend />
          <ReferenceLine y={5} stroke="#d9d9d9" strokeDasharray="5 5" />
          <Line
            type="monotone"
            dataKey="intensity"
            stroke="#1677ff"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 6 }}
            name="强度"
          />
        </LineChart>
      </ResponsiveContainer>
      <div style={{ marginTop: 8, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {Object.entries(PACE_COLORS).map(([type, color]) => (
          <Text key={type} style={{ fontSize: 11 }}>
            <span style={{
              display: 'inline-block', width: 10, height: 10,
              backgroundColor: color, borderRadius: 2, marginRight: 4,
            }} />
            {type}
          </Text>
        ))}
      </div>
    </Card>
  )
}
