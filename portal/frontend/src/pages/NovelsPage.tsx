import React from 'react'
import { Card, List, Tag, Space, Button } from 'antd'
import { BookOutlined, EditOutlined, ReadOutlined } from '@ant-design/icons'
import { useNovelStore } from '../stores/novelStore'
import { useNavigate } from 'react-router-dom'

export const NovelsPage: React.FC = () => {
  const novels = useNovelStore((s) => s.novels)
  const setCurrentNovel = useNovelStore((s) => s.setCurrentNovel)
  const navigate = useNavigate()

  const handleAction = (name: string, path: string) => {
    setCurrentNovel(name); navigate(path)
  }

  return (
    <div>
      <h2>小说列表</h2>
      <Card>
        <List dataSource={novels}
          locale={{ emptyText: '暂无小说' }}
          renderItem={(n) => (
            <List.Item actions={[
              <Button icon={<EditOutlined />} onClick={() => handleAction(n.name, '/writing')}>写作</Button>,
              <Button icon={<ReadOutlined />} onClick={() => handleAction(n.name, '/chapters')}>浏览</Button>,
            ]}>
              <List.Item.Meta
                avatar={<BookOutlined style={{ fontSize: 24 }} />}
                title={n.title || n.name}
                description={<Space>{n.genre && <Tag>{n.genre}</Tag>}{n.total_chapters}章 · {(n.total_words||0).toLocaleString()}字</Space>}
              />
            </List.Item>
          )} />
      </Card>
    </div>
  )
}
