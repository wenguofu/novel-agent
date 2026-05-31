import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Card, Spin, Empty, Button, Space, Tooltip, Typography, Segmented } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'

const { Text } = Typography

interface TopologyNode {
  id: string
  label: string
  role: string
  group: string
  identity: string
  status: string
  relationCount: number
  value: number
}

interface TopologyEdge {
  from: string
  to: string
  label: string
  title?: string
  color?: { color: string }
  dashes?: boolean
}

interface CharacterTopologyProps {
  novelName: string | null
  onNodeClick?: (characterId: string, characterName: string) => void
}

const GROUP_COLORS: Record<string, string> = {
  protagonist: '#ff4d4f',
  heroine: '#eb2f96',
  antagonist: '#fa8c16',
  supporting: '#1677ff',
}

const ROLE_LABELS: Record<string, string> = {
  protagonist: '主角', heroine: '女主', antagonist: '反派', supporting: '配角',
}

// Simple force-directed layout
function layoutNodes(
  nodes: TopologyNode[],
  edges: TopologyEdge[],
  width: number,
  height: number,
) {
  const positions: Record<string, { x: number; y: number }> = {}

  // Initialize random positions
  nodes.forEach((n) => {
    positions[n.id] = {
      x: width / 2 + (Math.random() - 0.5) * 200,
      y: height / 2 + (Math.random() - 0.5) * 200,
    }
  })

  // Simple force simulation
  const iterations = 80
  const repulsion = 5000
  const attraction = 0.005
  const damping = 0.6

  for (let iter = 0; iter < iterations; iter++) {
    const forces: Record<string, { fx: number; fy: number }> = {}
    nodes.forEach((n) => {
      forces[n.id] = { fx: 0, fy: 0 }
    })

    // Repulsion between all pairs
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i]
        const b = nodes[j]
        const dx = positions[b.id].x - positions[a.id].x
        const dy = positions[b.id].y - positions[a.id].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = repulsion / (dist * dist)
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        forces[a.id].fx -= fx
        forces[a.id].fy -= fy
        forces[b.id].fx += fx
        forces[b.id].fy += fy
      }
    }

    // Attraction along edges
    edges.forEach((e) => {
      const a = e.from
      const b = e.to
      if (!positions[a] || !positions[b]) return
      const dx = positions[b].x - positions[a].x
      const dy = positions[b].y - positions[a].y
      const dist = Math.sqrt(dx * dx + dy * dy) || 1
      const force = dist * attraction
      const fx = (dx / dist) * force
      const fy = (dy / dist) * force
      forces[a].fx += fx
      forces[a].fy += fy
      forces[b].fx -= fx
      forces[b].fy -= fy
    })

    // Center gravity
    nodes.forEach((n) => {
      const dx = width / 2 - positions[n.id].x
      const dy = height / 2 - positions[n.id].y
      forces[n.id].fx += dx * 0.001
      forces[n.id].fy += dy * 0.001
    })

    // Apply forces with damping
    nodes.forEach((n) => {
      positions[n.id].x += forces[n.id].fx * damping
      positions[n.id].y += forces[n.id].fy * damping
      positions[n.id].x = Math.max(30, Math.min(width - 30, positions[n.id].x))
      positions[n.id].y = Math.max(30, Math.min(height - 30, positions[n.id].y))
    })
  }

  return positions
}

export const CharacterTopology: React.FC<CharacterTopologyProps> = ({
  novelName, onNodeClick,
}) => {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<{ nodes: TopologyNode[]; edges: TopologyEdge[] } | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [layout, setLayout] = useState<'force' | 'radial'>('force')
  const svgRef = useRef<SVGSVGElement>(null)

  const fetchTopology = useCallback(async () => {
    if (!novelName) return
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(`/api/characters/${encodeURIComponent(novelName)}/topology`)
      const result = await resp.json()
      if (result.success) {
        setData({ nodes: result.nodes, edges: result.edges })
      } else {
        setError(result.error || '加载失败')
      }
    } catch (e: any) {
      setError(e.message || '网络错误')
    } finally {
      setLoading(false)
    }
  }, [novelName])

  useEffect(() => {
    fetchTopology()
  }, [fetchTopology])

  const W = 900
  const H = 500

  // Compute positions
  const positions = React.useMemo(() => {
    if (!data || data.nodes.length === 0) return {}
    if (layout === 'force') {
      return layoutNodes(data.nodes, data.edges, W, H)
    }
    // Radial layout
    const poss: Record<string, { x: number; y: number }> = {}
    const cx = W / 2
    const cy = H / 2
    const radius = Math.min(W, H) / 2 - 60
    data.nodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / data.nodes.length - Math.PI / 2
      poss[n.id] = {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle),
      }
    })
    return poss
  }, [data, layout, W, H])

  const nodeRadius = (node: TopologyNode) => {
    if (node.group === 'protagonist' || node.group === 'heroine') return 18
    if (node.group === 'antagonist') return 15
    return Math.max(10, 12 + node.relationCount * 2)
  }

  if (loading) {
    return (
      <Card size="small" style={{ textAlign: 'center', padding: 60 }}>
        <Spin size="large" />
        <div style={{ marginTop: 12 }}>
          <Text type="secondary">加载人物关系拓扑...</Text>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card size="small">
        <Empty description={error}>
          <Button icon={<ReloadOutlined />} onClick={fetchTopology}>重新加载</Button>
        </Empty>
      </Card>
    )
  }

  if (!data || data.nodes.length === 0) {
    return (
      <Card size="small">
        <Empty description="暂无人物数据">
          <Text type="secondary" style={{ fontSize: 12 }}>
            添加人物并在 relationship_map 字段中定义人物关系后，此处将显示关系拓扑图
          </Text>
        </Empty>
      </Card>
    )
  }

  return (
    <Card
      size="small"
      title={
        <Space>
          <span>人物关系拓扑</span>
          <Text type="secondary" style={{ fontSize: 12, fontWeight: 'normal' }}>
            {data.nodes.length} 人 · {data.edges.length} 条关系
          </Text>
        </Space>
      }
      extra={
        <Space size={8}>
          {Object.entries(GROUP_COLORS).map(([group, color]) => (
            <Tooltip key={group} title={ROLE_LABELS[group] || group}>
              <span style={{
                display: 'inline-block', width: 10, height: 10,
                backgroundColor: color, borderRadius: '50%',
                border: '1px solid rgba(0,0,0,0.15)',
                cursor: 'default',
              }} />
            </Tooltip>
          ))}
          <Segmented
            size="small"
            value={layout}
            onChange={(v) => setLayout(v as 'force' | 'radial')}
            options={[
              { value: 'force', label: '力导向' },
              { value: 'radial', label: '环形' },
            ]}
          />
          <Button size="small" icon={<ReloadOutlined />} onClick={fetchTopology} />
        </Space>
      }
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        style={{
          width: '100%', height: 500,
          border: '1px solid #f0f0f0', borderRadius: 8,
          background: '#fafafa', cursor: 'grab',
        }}
      >
        {/* Edge arrows def */}
        <defs>
          <marker id="arrowhead" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="6" markerHeight="4" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#999" />
          </marker>
          <marker id="arrowhead-red" viewBox="0 0 10 7" refX="10" refY="3.5" markerWidth="6" markerHeight="4" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#ff4d4f" />
          </marker>
        </defs>

        {/* Edges */}
        {data.edges.map((edge, i) => {
          const from = positions[edge.from]
          const to = positions[edge.to]
          if (!from || !to) return null
          const edgeColor = edge.color?.color || '#1677ff'
          const isDashed = edge.dashes
          const midX = (from.x + to.x) / 2
          const midY = (from.y + to.y) / 2

          return (
            <g key={`edge-${i}`}>
              <line
                x1={from.x} y1={from.y} x2={to.x} y2={to.y}
                stroke={edgeColor} strokeWidth={1.5}
                strokeDasharray={isDashed ? '6,3' : undefined}
                markerEnd={edgeColor === '#ff4d4f' ? 'url(#arrowhead-red)' : 'url(#arrowhead)'}
                opacity={0.6}
              />
              {edge.label && (
                <text
                  x={midX} y={midY - 4}
                  textAnchor="middle"
                  fontSize={9}
                  fill="#666"
                  style={{ pointerEvents: 'none' }}
                >
                  {edge.label}
                </text>
              )}
            </g>
          )
        })}

        {/* Nodes */}
        {data.nodes.map((node) => {
          const pos = positions[node.id]
          if (!pos) return null
          const r = nodeRadius(node)
          const color = GROUP_COLORS[node.group] || GROUP_COLORS.supporting
          const isHovered = hoveredNode === node.id
          const showDetail = isHovered && (node.identity || node.status)

          return (
            <g
              key={`node-${node.id}`}
              transform={`translate(${pos.x}, ${pos.y})`}
              onMouseEnter={() => setHoveredNode(node.id)}
              onMouseLeave={() => setHoveredNode(null)}
              onClick={() => onNodeClick?.(node.id, node.label)}
              style={{ cursor: 'pointer' }}
            >
              {/* Glow for protagonist/heroine */}
              {(node.group === 'protagonist' || node.group === 'heroine') && (
                <circle r={r + 6} fill={color} opacity={0.15} />
              )}
              {/* Node circle */}
              <circle
                r={r}
                fill={color}
                stroke="#fff"
                strokeWidth={isHovered ? 3 : 1.5}
                opacity={isHovered ? 1 : 0.9}
              />
              {/* Label */}
              <text
                y={r + 14}
                textAnchor="middle"
                fontSize={12}
                fontWeight={node.group === 'protagonist' || node.group === 'heroine' ? 600 : 400}
                fill="#333"
              >
                {node.label}
              </text>
              {/* Role badge */}
              <text
                y={r + 27}
                textAnchor="middle"
                fontSize={9}
                fill="#888"
              >
                {ROLE_LABELS[node.group] || node.role}
              </text>

              {/* Tooltip on hover */}
              {showDetail && (
                <g transform={`translate(${r + 10}, -20)`}>
                  <rect
                    x={0} y={0}
                    width={Math.max(100, (node.identity?.length || 0) * 8 + 20)}
                    height={node.status ? 40 : 24}
                    rx={4}
                    fill="white"
                    stroke="#d9d9d9"
                    opacity={0.95}
                  />
                  <text x={8} y={14} fontSize={11} fill="#333">
                    {node.identity || ''}
                  </text>
                  {node.status && (
                    <text x={8} y={30} fontSize={10} fill="#888">
                      📌 {node.status.slice(0, 20)}
                    </text>
                  )}
                </g>
              )}
            </g>
          )
        })}
      </svg>
    </Card>
  )
}
