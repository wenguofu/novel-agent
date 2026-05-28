import React from 'react'
import { Layout as AntLayout, Menu, Select, Divider } from 'antd'
import {
  DashboardOutlined,
  EditOutlined,
  BookOutlined,
  FileTextOutlined,
  AuditOutlined,
  UserOutlined,
  EyeOutlined,
  GlobalOutlined,
  NodeIndexOutlined,
  FieldTimeOutlined,
  UnlockOutlined,
  ThunderboltOutlined,
  BarChartOutlined,
  SearchOutlined,
  SettingOutlined,
  PlusOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation } from 'react-router-dom'
import { useNovelStore } from '../stores/novelStore'

const { Sider, Content } = AntLayout

interface LayoutProps {
  children: React.ReactNode
}

// ── Global (always visible) ──
const globalItems = [
  { key: '/', icon: <DashboardOutlined />, label: '控制台' },
  { key: '/novels/new', icon: <PlusOutlined />, label: '新建小说' },
]

// ── Novel workspace (visible when novel selected) ──
const novelGroups = [
  {
    key: 'write',
    label: '创作',
    children: [
      { key: '/writing', icon: <EditOutlined />, label: '写作' },
      { key: '/chapters', icon: <BookOutlined />, label: '章节' },
      { key: '/outlines', icon: <FileTextOutlined />, label: '大纲' },
      { key: '/review', icon: <AuditOutlined />, label: '审稿' },
    ],
  },
  {
    key: 'design',
    label: '设定',
    children: [
      { key: '/characters', icon: <UserOutlined />, label: '人物' },
      { key: '/foreshadowing', icon: <EyeOutlined />, label: '伏笔' },
      { key: '/world', icon: <GlobalOutlined />, label: '世界观' },
      { key: '/arcs', icon: <NodeIndexOutlined />, label: '弧线' },
      { key: '/pacing', icon: <FieldTimeOutlined />, label: '节奏' },
      { key: '/revelation', icon: <UnlockOutlined />, label: '释放' },
    ],
  },
  {
    key: 'tools',
    label: '工具',
    children: [
      { key: '/init', icon: <ThunderboltOutlined />, label: '初始化' },
      { key: '/workflow', icon: <AuditOutlined />, label: '工作流' },
      { key: '/quality', icon: <BarChartOutlined />, label: '质量' },
    ],
  },
]

// ── Always-visible extras below workspace ──
const extraItems = [
  { key: '/search', icon: <SearchOutlined />, label: '搜索' },
  { key: '/config', icon: <SettingOutlined />, label: '配置' },
]

// Flatten for selectedKey matching
const allItems = [
  ...globalItems,
  ...novelGroups.flatMap((g) => g.children),
  ...extraItems,
]

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const navigate = useNavigate()
  const location = useLocation()
  const novels = useNovelStore((s) => s.novels)
  const currentNovel = useNovelStore((s) => s.currentNovel)
  const setCurrentNovel = useNovelStore((s) => s.setCurrentNovel)

  const selectedKey = allItems.find(
    (item) => item.key !== '/' && location.pathname.startsWith(item.key)
  )?.key || (location.pathname === '/' ? '/' : undefined)

  // Build Ant Design Menu items with SubMenu groups
  const menuItems = [
    // Global
    ...globalItems.map((item) => ({ key: item.key, icon: item.icon, label: item.label })),
    { type: 'divider' as const },
  ]

  if (currentNovel) {
    // Novel workspace groups
    for (const group of novelGroups) {
      menuItems.push({
        key: group.key,
        label: group.label,
        type: 'group' as const,
        children: group.children.map((item) => ({
          key: item.key,
          icon: item.icon,
          label: item.label,
        })),
      })
    }
  } else {
    // No novel selected: show guide item
    menuItems.push({
      key: '_no_novel',
      label: '请先在控制台选择小说',
      icon: <BookOutlined />,
      disabled: true,
    })
  }

  menuItems.push(
    { type: 'divider' as const },
    ...extraItems.map((item) => ({ key: item.key, icon: item.icon, label: item.label })),
  )

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider width={210} theme="dark">
        {/* Header */}
        <div
          style={{
            padding: '12px 16px 8px',
            display: 'flex',
            flexDirection: 'column',
            gap: 8,
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          <div
            style={{
              color: '#fff',
              fontSize: 18,
              fontWeight: 'bold',
              textAlign: 'center',
            }}
          >
            NovelForge
          </div>

          {/* Novel Selector — always visible */}
          <Select
            style={{ width: '100%', color: '#fff' }}
            className="sidebar-novel-select"
            value={currentNovel || undefined}
            allowClear
            placeholder="选择小说..."
            onChange={(v) => {
              setCurrentNovel(v || null)
              if (v && location.pathname === '/') {
                navigate('/writing')
              }
            }}
            options={novels.map((n) => ({
              value: n.name,
              label: `${n.title || n.name}  ${n.total_chapters ? `(${n.total_chapters}章)` : ''}`,
            }))}
            dropdownStyle={{ minWidth: 200 }}
            variant="borderless"
            popupMatchSelectWidth={false}
          />
        </div>

        {/* Navigation */}
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={selectedKey ? [selectedKey] : []}
          items={menuItems}
          onClick={({ key }) => {
            if (key.startsWith('_')) return
            navigate(key)
          }}
          style={{ borderRight: 0 }}
        />
      </Sider>

      <Content style={{ padding: 24, overflow: 'auto' }}>
        {!currentNovel && !['/', '/novels/new', '/search', '/config'].includes(location.pathname) ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '60vh',
              color: '#999',
            }}
          >
            <BookOutlined style={{ fontSize: 64, marginBottom: 16 }} />
            <h3 style={{ color: '#666' }}>请先选择一部小说</h3>
            <p>在左侧边栏顶部的下拉框中选择小说，或在控制台选择。</p>
          </div>
        ) : (
          children
        )}
      </Content>
    </AntLayout>
  )
}
