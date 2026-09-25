import { LockOutlined, MailOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'
import { useAuth } from '../auth/context'

type Values = { email: string; password: string }

export default function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (user) return <Navigate to={from} replace />

  const onFinish = async ({ email, password }: Values) => {
    setLoading(true)
    setError(null)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 16 }}>
      <Card style={{ width: '100%', maxWidth: 380 }}>
        <Typography.Title level={3} style={{ marginBottom: 4 }}>
          Tendoor
        </Typography.Title>
        <Typography.Paragraph type="secondary">Аналітика цінових аномалій публічних закупівель</Typography.Paragraph>
        {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
        <Form<Values> layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item name="email" label="Email" rules={[{ required: true, type: 'email', message: 'Вкажіть email' }]}>
            <Input prefix={<MailOutlined />} autoComplete="username" autoFocus />
          </Form.Item>
          <Form.Item name="password" label="Пароль" rules={[{ required: true, message: 'Вкажіть пароль' }]}>
            <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            Увійти
          </Button>
        </Form>
      </Card>
    </div>
  )
}
