import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Form, Input, Button, Card, Typography, message, Space } from "antd";
import { UserOutlined, LockOutlined } from "@ant-design/icons";
import { useAuth } from "../context/AuthContext";
import type { ApiError } from "../api";

const { Title } = Typography;

export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [loading, setLoading] = useState(false);

  // Already logged in
  if (user) {
    const from = (location.state as { from?: { pathname: string } })?.from;
    navigate(from?.pathname || "/dashboard", { replace: true });
    return null;
  }

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      await login(values.username, values.password);
      message.success("登录成功");
      const from = (location.state as { from?: { pathname: string } })?.from;
      navigate(from?.pathname || "/dashboard", { replace: true });
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      message.error(apiErr?.detail || "登录失败，请检查用户名和密码");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
      }}
    >
      <Card style={{ width: 400, boxShadow: "0 8px 24px rgba(0,0,0,0.15)" }}>
        <Space direction="vertical" size="large" style={{ width: "100%" }}>
          <div style={{ textAlign: "center" }}>
            <Title level={3} style={{ marginBottom: 4 }}>
              合同管理系统
            </Title>
            <span style={{ color: "#999" }}>Contract Hub v0.0.1</span>
          </div>
          <Form
            name="login"
            onFinish={onFinish}
            size="large"
            initialValues={{ username: "admin", password: "admin123" }}
          >
            <Form.Item
              name="username"
              rules={[{ required: true, message: "请输入用户名" }]}
            >
              <Input prefix={<UserOutlined />} placeholder="用户名" />
            </Form.Item>
            <Form.Item
              name="password"
              rules={[{ required: true, message: "请输入密码" }]}
            >
              <Input.Password prefix={<LockOutlined />} placeholder="密码" />
            </Form.Item>
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                loading={loading}
                block
              >
                登录
              </Button>
            </Form.Item>
          </Form>
          <div style={{ textAlign: "center", color: "#999", fontSize: 12 }}>
            演示账号：admin/admin123 · user/user123
          </div>
        </Space>
      </Card>
    </div>
  );
}
