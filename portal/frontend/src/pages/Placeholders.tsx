import React from 'react'
import { Card } from 'antd'

const PlaceholderPage: React.FC<{ title: string }> = ({ title }) => (
  <Card title={title}>
    <p>🚧 {title}页面开发中...</p>
  </Card>
)

export const Settings: React.FC = () => <PlaceholderPage title="设置" />
