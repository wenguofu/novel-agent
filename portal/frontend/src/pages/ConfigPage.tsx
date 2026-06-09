import React, { useState, useEffect } from 'react'
import { Card, Input, Button, Space, InputNumber, message, Select, Tag, Divider } from 'antd'
import { SaveOutlined, CheckCircleOutlined, KeyOutlined, ApiOutlined, RobotOutlined } from '@ant-design/icons'
import { useConfigStore } from '../stores/configStore'

const MODEL_OPTIONS = [
  { value: 'MiniMax-M3', label: 'MiniMax V3', desc: '旗舰级写作模型，最强创作能力' },
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro', desc: '旗舰模型，最强性能' },
  { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash', desc: '快速响应，高性价比' },
]

export const ConfigPage: React.FC = () => {
  const config = useConfigStore((s) => s.deepseekConfig)
  const configured = useConfigStore((s) => s.configured)
  const fetchConfig = useConfigStore((s) => s.fetchConfig)
  const saveConfig = useConfigStore((s) => s.saveConfig)
  const testConfig = useConfigStore((s) => s.testConfig)

  const [form, setForm] = useState({
    api_key: '', api_base: 'https://api.minimaxi.com/anthropic',
    model: 'MiniMax-M3', temperature: 0.7, max_tokens: 65536, top_p: 0.9,
  })
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  // Auto-fill from saved config on mount
  useEffect(() => {
    fetchConfig().then(() => {
      // fetchConfig updates the store, but we need to read from it
    })
  }, [])

  // When store config loads, populate form
  useEffect(() => {
    const s = useConfigStore.getState().deepseekConfig
    if (s.api_key || s.api_base || s.model) {
      setForm(prev => ({
        api_key: s.deepseek_key_saved ? s.deepseek_key_saved : prev.api_key,
        api_base: s.deepseek_saved_base || s.deepseek_api_base || prev.api_base,
        model: s.deepseek_saved_model || s.deepseek_model || prev.model,
        temperature: s.deepseek_temperature ?? prev.temperature,
        max_tokens: s.deepseek_max_tokens ?? prev.max_tokens,
        top_p: s.deepseek_top_p ?? prev.top_p,
      }))
    }
  }, [config])

  const handleSave = async () => {
    setSaving(true)
    try {
      await saveConfig(form)
      message.success('配置已保存到数据库')
    } catch {
      message.error('保存失败')
    } finally { setSaving(false) }
  }

  const handleTest = async () => {
    if (!form.api_key.trim()) {
      message.warning('请先填写 API Key')
      return
    }
    setTesting(true)
    try {
      const ok = await testConfig()
      message[ok ? 'success' : 'error'](ok ? 'API 连接成功' : '连接失败，请检查配置')
    } catch {
      message.error('测试失败')
    } finally { setTesting(false) }
  }

  const selectedModel = MODEL_OPTIONS.find(m => m.value === form.model)

  return (
    <div>
      <h2>系统配置</h2>

      <Card style={{ maxWidth: 640 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {/* API Key */}
          <div>
            <div style={{ marginBottom: 6, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
              <KeyOutlined /> API Key
              {configured && <Tag color="success" style={{ fontSize: 11 }}>已配置</Tag>}
            </div>
            <Input.Password
              value={form.api_key}
              onChange={e => setForm({ ...form, api_key: e.target.value })}
              placeholder="sk-..."
              style={{ width: '100%' }}
              visibilityToggle
            />
            <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
              密钥加密存储于本地数据库，不会上传
            </div>
          </div>

          <Divider style={{ margin: '4px 0' }} />

          {/* Model selector */}
          <div>
            <div style={{ marginBottom: 6, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
              <RobotOutlined /> 模型选择
            </div>
            <Select
              value={form.model}
              onChange={v => setForm({ ...form, model: v })}
              style={{ width: '100%' }}
              options={MODEL_OPTIONS.map(m => ({
                value: m.value,
                label: (
                  <div>
                    <div>{m.label}</div>
                    <div style={{ fontSize: 11, color: '#999' }}>{m.desc}</div>
                  </div>
                ),
              }))}
            />
            {selectedModel && (
              <div style={{ fontSize: 11, color: '#666', marginTop: 4 }}>
                {selectedModel.desc}
              </div>
            )}
          </div>

          {/* API Base */}
          <div>
            <div style={{ marginBottom: 6, fontWeight: 500, display: 'flex', alignItems: 'center', gap: 6 }}>
              <ApiOutlined /> API Base URL
            </div>
            <Select
              value={form.api_base}
              onChange={v => setForm({ ...form, api_base: v })}
              style={{ width: '100%' }}
              options={[
                { value: 'https://api.minimaxi.com/anthropic', label: 'MiniMax V3 (Anthropic兼容)' },
                { value: 'https://api.deepseek.com', label: 'DeepSeek 官方 (api.deepseek.com)' },
              ]}
            />
          </div>

          <Divider style={{ margin: '4px 0' }} />

          {/* Generation params */}
          <div style={{ fontWeight: 500 }}>生成参数</div>
          <Space size="middle" wrap>
            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: '#666' }}>Temperature</div>
              <InputNumber
                min={0} max={2} step={0.1}
                value={form.temperature}
                onChange={v => setForm({ ...form, temperature: v || 0.7 })}
                style={{ width: 120 }}
              />
            </div>

            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: '#666' }}>Max Tokens</div>
              <InputNumber
                min={100} max={65536} step={100}
                value={form.max_tokens}
                onChange={v => setForm({ ...form, max_tokens: v || 8192 })}
                style={{ width: 140 }}
              />
            </div>

            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: '#666' }}>Top P</div>
              <InputNumber
                min={0} max={1} step={0.05}
                value={form.top_p}
                onChange={v => setForm({ ...form, top_p: v || 0.9 })}
                style={{ width: 120 }}
              />
            </div>
          </Space>

          <Divider style={{ margin: '4px 0' }} />

          <Space>
            <Button type="primary" icon={<SaveOutlined />}
              onClick={handleSave} loading={saving}>
              保存到数据库
            </Button>
            <Button icon={<CheckCircleOutlined />}
              onClick={handleTest} loading={testing}
              disabled={!form.api_key.trim()}>
              测试连接
            </Button>
            {configured && (
              <Tag color="success" icon={<CheckCircleOutlined />}>已配置</Tag>
            )}
          </Space>
        </Space>
      </Card>
    </div>
  )
}
