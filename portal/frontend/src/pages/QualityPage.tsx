import React, { useState, useEffect } from 'react'
import { Card, Statistic, Row, Col, Progress, Tag, Space } from 'antd'
import { BarChartOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'

export const QualityPage: React.FC = () => {
  const currentNovel = useNovelStore((s) => s.currentNovel)

  const [report, setReport] = useState<any>(null)
  const [, setLoading] = useState(false)

  const load = async () => {
    if (!currentNovel) return
    setLoading(true)
    try {
      const resp = await fetch(`/api/content/quality-report/${encodeURIComponent(currentNovel)}`)
      const data = await resp.json()
      setReport(data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [currentNovel])

  const wcRate = report?.wc_pass_rate ? parseFloat(String(report.wc_pass_rate)) : 0
  const compRate = report?.compliance_pass_rate ? parseFloat(String(report.compliance_pass_rate)) : 0

  return (
    <div>
      <h2>质量报告</h2>
      <Card>
        {report ? (
          <>
            <Row gutter={16} style={{ marginBottom: 24 }}>
              <Col span={6}><Card><Statistic title="总章节" value={report.total_chapters || 0} /></Card></Col>
              <Col span={6}><Card><Statistic title="总审稿" value={report.total_reviews || 0} /></Card></Col>
              <Col span={6}><Card><Progress type="circle" percent={Math.round(wcRate)} size={80} format={() => `${Math.round(wcRate)}%`} /><div style={{ textAlign: 'center', marginTop: 8 }}>字数通过率</div></Card></Col>
              <Col span={6}><Card><Progress type="circle" percent={Math.round(compRate)} size={80} format={() => `${Math.round(compRate)}%`} /><div style={{ textAlign: 'center', marginTop: 8 }}>合规通过率</div></Card></Col>
            </Row>

            {report.alerts?.length > 0 && (
              <Card title="⚠️ 警告" size="small" style={{ marginBottom: 16 }}>
                {report.alerts.map((a: string, i: number) => <Tag color="orange" key={i}>{a}</Tag>)}
              </Card>
            )}
          </>
        ) : (
          <div style={{ color: '#999', textAlign: 'center', padding: 40 }}>
            <BarChartOutlined style={{ fontSize: 48 }} /><p>选择小说查看质量报告</p>
          </div>
        )}
      </Card>
    </div>
  )
}
