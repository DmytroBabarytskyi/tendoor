import { PlusOutlined } from '@ant-design/icons'
import { App, Button, Form, Input, Modal, Select, Space, Switch, Table, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useEffect, useState } from 'react'
import { api, ROLE_NAMES, type Role, type User } from '../api/client'
import { useAuth } from '../auth/context'

const roleOptions = (Object.keys(ROLE_NAMES) as Role[]).map((r) => ({ value: r, label: ROLE_NAMES[r] }))
const PASSWORD_RULES = [
  { required: true, message: 'Вкажіть пароль' },
  { min: 10, message: 'Щонайменше 10 символів' },
]

type CreateValues = { email: string; full_name: string; role: Role; password: string }

export default function UsersPage() {
  const { user: me } = useAuth()
  const { message } = App.useApp()
  const [users, setUsers] = useState<User[] | null>(null)
  const [reloadKey, setReloadKey] = useState(0)
  const [creating, setCreating] = useState(false)
  const [resetFor, setResetFor] = useState<User | null>(null)
  const [createForm] = Form.useForm<CreateValues>()
  const [resetForm] = Form.useForm<{ password: string }>()

  useEffect(() => {
    let alive = true
    api<User[]>('/users').then(
      (list) => alive && setUsers(list),
      (e: Error) => message.error(e.message),
    )
    return () => {
      alive = false
    }
  }, [reloadKey, message])

  const patch = async (id: number, body: Partial<User> & { password?: string }) => {
    try {
      const updated = await api<User>(`/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) })
      setUsers((list) => list?.map((u) => (u.id === id ? updated : u)) ?? null)
      message.success('Збережено')
      return true
    } catch (e) {
      message.error((e as Error).message)
      return false
    }
  }

  const create = async (values: CreateValues) => {
    try {
      await api<User>('/users', { method: 'POST', body: JSON.stringify(values) })
      message.success('Користувача створено')
      setCreating(false)
      createForm.resetFields()
      setReloadKey((k) => k + 1)
    } catch (e) {
      message.error((e as Error).message)
    }
  }

  return (
    <>
      <Space style={{ width: '100%', justifyContent: 'space-between' }}>
        <Typography.Title level={3}>Користувачі</Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreating(true)}>
          Новий користувач
        </Button>
      </Space>
      <Table<User>
        rowKey="id"
        loading={users === null}
        dataSource={users ?? []}
        pagination={false}
        scroll={{ x: 800 }}
        columns={[
          { title: 'ПІБ', dataIndex: 'full_name' },
          { title: 'Email', dataIndex: 'email' },
          {
            title: 'Роль',
            dataIndex: 'role',
            render: (role: Role, u) => (
              <Select
                value={role}
                options={roleOptions}
                style={{ width: 170 }}
                disabled={u.id === me?.id}
                onChange={(r) => patch(u.id, { role: r })}
              />
            ),
          },
          {
            title: 'Активний',
            dataIndex: 'is_active',
            render: (active: boolean, u) => (
              <Switch checked={active} disabled={u.id === me?.id} onChange={(v) => patch(u.id, { is_active: v })} />
            ),
          },
          {
            title: 'Останній вхід',
            dataIndex: 'last_login_at',
            render: (d: string | null) => (d ? dayjs(d).format('DD.MM.YYYY HH:mm') : <Tag>ще не входив</Tag>),
          },
          {
            title: '',
            key: 'actions',
            render: (_, u) => (
              <Button size="small" onClick={() => setResetFor(u)}>
                Змінити пароль
              </Button>
            ),
          },
        ]}
      />

      <Modal
        title="Новий користувач"
        open={creating}
        onCancel={() => setCreating(false)}
        onOk={() => createForm.submit()}
        okText="Створити"
        cancelText="Скасувати"
        destroyOnHidden
      >
        <Form form={createForm} layout="vertical" onFinish={create} initialValues={{ role: 'auditor' }}>
          <Form.Item name="full_name" label="ПІБ" rules={[{ required: true, min: 2 }]}>
            <Input />
          </Form.Item>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email' }]}>
            <Input autoComplete="off" />
          </Form.Item>
          <Form.Item name="role" label="Роль" rules={[{ required: true }]}>
            <Select options={roleOptions} />
          </Form.Item>
          <Form.Item name="password" label="Початковий пароль" rules={PASSWORD_RULES}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`Новий пароль: ${resetFor?.email ?? ''}`}
        open={!!resetFor}
        onCancel={() => setResetFor(null)}
        onOk={() => resetForm.submit()}
        okText="Зберегти"
        cancelText="Скасувати"
        destroyOnHidden
      >
        <Typography.Paragraph type="secondary">Усі активні сесії користувача буде завершено.</Typography.Paragraph>
        <Form
          form={resetForm}
          layout="vertical"
          onFinish={async ({ password }) => {
            if (resetFor && (await patch(resetFor.id, { password }))) {
              setResetFor(null)
              resetForm.resetFields()
            }
          }}
        >
          <Form.Item name="password" label="Пароль" rules={PASSWORD_RULES}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
