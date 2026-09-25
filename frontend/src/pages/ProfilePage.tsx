import { App, Button, Card, Descriptions, Form, Input, Typography } from 'antd'
import { changePassword, ROLE_NAMES } from '../api/client'
import { useAuth } from '../auth/context'

type Values = { old_password: string; new_password: string; confirm: string }

export default function ProfilePage() {
  const { user } = useAuth()
  const { message } = App.useApp()
  const [form] = Form.useForm<Values>()

  const submit = async ({ old_password, new_password }: Values) => {
    try {
      await changePassword(old_password, new_password)
      message.success('Пароль змінено. Інші сесії завершено.')
      form.resetFields()
    } catch (e) {
      message.error((e as Error).message)
    }
  }

  return (
    <>
      <Typography.Title level={3}>Профіль</Typography.Title>
      <Card style={{ maxWidth: 520, marginBottom: 16 }}>
        <Descriptions column={1} size="small">
          <Descriptions.Item label="ПІБ">{user?.full_name}</Descriptions.Item>
          <Descriptions.Item label="Email">{user?.email}</Descriptions.Item>
          <Descriptions.Item label="Роль">{user && ROLE_NAMES[user.role]}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title="Зміна пароля" style={{ maxWidth: 520 }}>
        <Form form={form} layout="vertical" onFinish={submit}>
          <Form.Item name="old_password" label="Поточний пароль" rules={[{ required: true }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="Новий пароль"
            rules={[{ required: true }, { min: 10, message: 'Щонайменше 10 символів' }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="Повторіть новий пароль"
            dependencies={['new_password']}
            rules={[
              { required: true },
              ({ getFieldValue }) => ({
                validator: (_, v) =>
                  !v || v === getFieldValue('new_password') ? Promise.resolve() : Promise.reject(new Error('Паролі не збігаються')),
              }),
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit">
            Змінити пароль
          </Button>
        </Form>
      </Card>
    </>
  )
}
