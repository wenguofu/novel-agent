import React, { useState, useEffect } from 'react'
import { Card, Input, Button, Space, InputNumber, message, Form } from 'antd'
import { SaveOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useConfigStore } from '../stores/configStore'

export const ConfigPage: React.FC = () => {
  const config = useConfigStore((s) => s.deepseekConfig)
  const configured = useConfigStore((s) => s.configured)
  const fetchConfig = useConfigStore((s) => s.fetchConfig)
  const saveConfig = useConfigStore((s) => s.saveConfig)
  const testConfig = useConfigStore((s) => s.testConfig)

  const [form, setForm] = useState({ api_key: '', api_base: 'https://api.deepseek.com', model: 'deepseek-chat', temperature: 0.7, max_tokens: 8192, top_p: 0.9 })

  useEffect(() => { fetchConfig() }, [])
  useEffect(() => { if (config.api_key) setForm(prev => ({ ...prev, ...config })) }, [config])

  const handleSave = async () => { await saveConfig(form); message.success('保存成功') }
  const handleTest = async () => {
    const ok = await testConfig()
    message[ok ? 'success' : 'error'](ok ? '连接成功' : '连接失败')
  }

  return (
    <div>
      <h2>配置</h2>
      <Card title="DeepSeek API 设置" style={{ maxWidth: 600 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <div style={{ marginBottom: 4, fontWeight: 500 }}>API Key</div>
            <Input.Password
              value={form.api_key}
              onChange={e => setForm({...form, api_key: e.target.value})}
              placeholder="sk-..."
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <div style={{ marginBottom: 4, fontWeight: 500 }}>API Base</div>
            <Input
              value={form.api_base}
              onChange={e => setForm({...form, api_base: e.target.value})}
              style={{ width: '100%' }}
            />
          </div>

          <div>
            <div style={{ marginBottom: 4, fontWeight: 500 }}>Model</div>
            <Input
              value={form.model}
              onChange={e => setForm({...form, model: e.target.value})}
              style={{ width: '100%' }}
            />
          </div>

          <Space size="middle">
            <div>
              <div style={{ marginBottom: 4, fontWeight: 500 }}>Temperature</div>
              <InputNumber
                min={0} max={2} step={0.1}
                value={form.temperature}
                onChange={v => setForm({...form, temperature: v || 0.7})}
                style={{ width: 140 }}
              />
            </div>

            <div>
              <div style={{ marginBottom: 4, fontWeight: 500 }}>Max Tokens</div>
              <InputNumber
                min={100} max={65536}
                value={form.max_tokens}
                onChange={v => setForm({...form, max_tokens: v || 8192})}
                style={{ width: 140 }}
              />
            </div>

            <div>
              <div style={{ marginBottom: 4, fontWeight: 500 }}>Top P</div>
              <InputNumber
                min={0} max={1} step={0.05}
                value={form.top_p}
                onChange={v => setForm({...form, top_p: v || 0.9})}
                style={{ width: 120 }}
              />
            </div>
          </Space>

          <Space>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>保存</Button>
            <Button icon={<CheckCircleOutlined />} onClick={handleTest} disabled={!form.api_key}>测试连接</Button>
            {configured && <span style={{ color: '#52c41a' }}>✅ 已配置</span>}
          </Space>
        </Space>
      </Card>
    </div>
  )
}
