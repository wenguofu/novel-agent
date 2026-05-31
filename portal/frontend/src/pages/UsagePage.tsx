import React, { useState, useEffect, useCallback } from 'react'
import { Card, Row, Col, Statistic, Table, Segmented, Spin, Alert } from 'antd'
import {
  ThunderboltOutlined,
  DollarOutlined,
  SwapOutlined,
  RiseOutlined,
  ReloadOutlined,
} from '@ant-design/icons'

interface DailyRow {
  date: string
  calls: number
  prompt_tokens: number
  completion_tokens: number
  tokens: number
  cost: number
  by_operation: Record<string, { calls: number; tokens: number; cost: number }>
  by_model: Record<string, { calls: number; tokens: number; cost: number }>
  updated_at: string
}

interface OpRow {
  key: string
  name: string
  calls: number
  tokens: number
  cost: number
}

interface StatsData {
  daily: DailyRow[]
  totals: { calls: number; tokens: number; cost: number }
  by_operation: Record<string, { calls: number; tokens: number; cost: number }>
  by_model: Record<string, { calls: number; tokens: number; cost: number }>
  days: number
}

const DAY_OPTIONS = { '7天': 7, '30天': 30, '90天': 90 }

function fmtNum(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return String(n)
}

function fmtCost(n: number): string {
  if (n >= 1) return `$${n.toFixed(2)}`
  if (n >= 0.01) return `$${n.toFixed(4)}`
  return `$${n.toFixed(6)}`
}

export const UsagePage: React.FC = () => {
  const [days, setDays] = useState(30)
  const [data, setData] = useState<StatsData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const resp = await fetch(`/api/usage/daily?days=${days}`)
      const json = await resp.json()
      if (json.success) {
        setData(json)
      } else {
        setError(json.error || '获取数据失败')
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Auto-refresh every 60s while the page is open
  useEffect(() => {
    const timer = setInterval(fetchData, 60_000)
    return () => clearInterval(timer)
  }, [fetchData])

  // Build operation and model tables from aggregate data
  const opTableData: OpRow[] = data
    ? Object.entries(data.by_operation)
        .map(([name, info]) => ({
          key: name,
          name,
          calls: info.calls,
          tokens: info.tokens,
          cost: info.cost,
        }))
        .sort((a, b) => b.tokens - a.tokens)
    : []

  const modelTableData: OpRow[] = data
    ? Object.entries(data.by_model)
        .map(([name, info]) => ({
          key: name,
          name,
          calls: info.calls,
          tokens: info.tokens,
          cost: info.cost,
        }))
        .sort((a, b) => b.tokens - a.tokens)
    : []

  const dailyColumns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
    { title: '调用', dataIndex: 'calls', key: 'calls', width: 80, align: 'right' as const },
    {
      title: '总Token',
      dataIndex: 'tokens',
      key: 'tokens',
      width: 130,
      align: 'right' as const,
      render: (v: number) => fmtNum(v),
      sorter: (a: DailyRow, b: DailyRow) => a.tokens - b.tokens,
    },
    {
      title: '输入',
      dataIndex: 'prompt_tokens',
      key: 'prompt_tokens',
      width: 130,
      align: 'right' as const,
      render: (v: number) => fmtNum(v),
    },
    {
      title: '输出',
      dataIndex: 'completion_tokens',
      key: 'completion_tokens',
      width: 130,
      align: 'right' as const,
      render: (v: number) => fmtNum(v),
    },
    {
      title: '费用',
      dataIndex: 'cost',
      key: 'cost',
      width: 130,
      align: 'right' as const,
      render: (v: number) => fmtCost(v),
      sorter: (a: DailyRow, b: DailyRow) => a.cost - b.cost,
    },
  ]

  const breakdownColumns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '调用次数', dataIndex: 'calls', key: 'calls', align: 'right' as const },
    {
      title: 'Token',
      dataIndex: 'tokens',
      key: 'tokens',
      align: 'right' as const,
      render: (v: number) => fmtNum(v),
      sorter: (a: OpRow, b: OpRow) => a.tokens - b.tokens,
      defaultSortOrder: 'descend' as const,
    },
    {
      title: '费用',
      dataIndex: 'cost',
      key: 'cost',
      align: 'right' as const,
      render: (v: number) => fmtCost(v),
      sorter: (a: OpRow, b: OpRow) => a.cost - b.cost,
    },
  ]

  return (
    <div>
      <h2>Token 用量统计</h2>

      {/* Controls */}
      <Card style={{ marginBottom: 16 }}>
        <Row justify="space-between" align="middle">
          <Col>
            <Segmented
              value={days}
              options={Object.entries(DAY_OPTIONS).map(([label, v]) => ({
                label,
                value: v,
              }))}
              onChange={(v) => setDays(v as number)}
            />
          </Col>
          <Col>
            <ReloadOutlined
              onClick={fetchData}
              style={{ fontSize: 18, cursor: 'pointer', color: '#1677ff' }}
              spin={loading}
            />
          </Col>
        </Row>
      </Card>

      {error && (
        <Alert message={error} type="error" style={{ marginBottom: 16 }} closable />
      )}

      <Spin spinning={loading && !data}>
        {/* Summary Cards */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={6}>
            <Card>
              <Statistic
                title="总调用次数"
                value={data?.totals.calls ?? 0}
                valueStyle={{ color: '#1677ff' }}
                prefix={<SwapOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="总 Token"
                value={data ? fmtNum(data.totals.tokens) : '0'}
                valueStyle={{ color: '#52c41a' }}
                prefix={<ThunderboltOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="总费用"
                value={data ? fmtCost(data.totals.cost) : '$0'}
                valueStyle={{ color: '#fa8c16' }}
                prefix={<DollarOutlined />}
              />
            </Card>
          </Col>
          <Col span={6}>
            <Card>
              <Statistic
                title="日均 Token"
                value={
                  data && data.daily.length > 0
                    ? fmtNum(Math.round(data.totals.tokens / data.daily.length))
                    : '0'
                }
                valueStyle={{ color: '#722ed1' }}
                prefix={<RiseOutlined />}
              />
            </Card>
          </Col>
        </Row>

        {/* Daily Trend Table */}
        <Card title="每日趋势" style={{ marginBottom: 16 }}>
          <Table
            dataSource={data?.daily ?? []}
            columns={dailyColumns}
            pagination={false}
            size="small"
            rowKey="date"
            scroll={{ y: 400 }}
            locale={{ emptyText: '暂无数据' }}
            summary={() => {
              if (!data?.daily.length) return null
              const totalCalls = data.daily.reduce((s, d) => s + d.calls, 0)
              const totalPrompt = data.daily.reduce((s, d) => s + d.prompt_tokens, 0)
              const totalComp = data.daily.reduce((s, d) => s + d.completion_tokens, 0)
              const totalTok = data.daily.reduce((s, d) => s + d.tokens, 0)
              const totalCost = data.daily.reduce((s, d) => s + d.cost, 0)
              return (
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0}>
                    <strong>合计</strong>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={1} align="right">
                    <strong>{totalCalls}</strong>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={2} align="right">
                    <strong>{fmtNum(totalTok)}</strong>
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={3} align="right">
                    {fmtNum(totalPrompt)}
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={4} align="right">
                    {fmtNum(totalComp)}
                  </Table.Summary.Cell>
                  <Table.Summary.Cell index={5} align="right">
                    <strong>{fmtCost(totalCost)}</strong>
                  </Table.Summary.Cell>
                </Table.Summary.Row>
              )
            }}
          />
        </Card>

        {/* Breakdowns */}
        <Row gutter={16}>
          <Col span={12}>
            <Card title="按操作类型">
              <Table
                dataSource={opTableData}
                columns={breakdownColumns}
                pagination={false}
                size="small"
                rowKey="name"
                locale={{ emptyText: '暂无数据' }}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card title="按模型">
              <Table
                dataSource={modelTableData}
                columns={breakdownColumns}
                pagination={false}
                size="small"
                rowKey="name"
                locale={{ emptyText: '暂无数据' }}
              />
            </Card>
          </Col>
        </Row>
      </Spin>
    </div>
  )
}
