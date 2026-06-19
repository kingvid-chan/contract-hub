import { useEffect, useState } from "react";
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Space,
  Popconfirm,
  message,
  Typography,
} from "antd";
import { PlusOutlined, EditOutlined, DeleteOutlined } from "@ant-design/icons";
import { getUsers, createUser, updateUser, deleteUser, UserInfo } from "../api";
import type { ApiError } from "../api";

const { Title } = Typography;

export default function UsersPage() {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<UserInfo | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const fetchUsers = async (p = page) => {
    setLoading(true);
    try {
      const res = await getUsers(p);
      setUsers(res.items);
      setTotal(res.total);
      setPage(p);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const openCreate = () => {
    setEditingUser(null);
    form.resetFields();
    form.setFieldsValue({ role: "user" });
    setModalOpen(true);
  };

  const openEdit = (user: UserInfo) => {
    setEditingUser(user);
    form.setFieldsValue({ username: user.username, role: user.role });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      if (editingUser) {
        await updateUser(editingUser.id, values);
        message.success("用户已更新");
      } else {
        await createUser(values);
        message.success("用户已创建");
      }
      setModalOpen(false);
      fetchUsers();
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      if (apiErr?.detail) message.error(apiErr.detail);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteUser(id);
      message.success("用户已删除");
      fetchUsers();
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      message.error(apiErr?.detail || "删除失败");
    }
  };

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 60 },
    { title: "用户名", dataIndex: "username", key: "username" },
    {
      title: "角色",
      dataIndex: "role",
      key: "role",
      render: (role: string) => (role === "admin" ? "管理员" : "用户"),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (v: string) => new Date(v).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 180,
      render: (_: unknown, record: UserInfo) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => openEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该用户？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <Title level={4} style={{ margin: 0 }}>
          用户管理
        </Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建用户
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={users}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: (p) => fetchUsers(p),
        }}
      />

      <Modal
        title={editingUser ? "编辑用户" : "新建用户"}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: "请输入用户名" }]}
          >
            <Input placeholder="用户名" maxLength={50} />
          </Form.Item>
          <Form.Item
            name="password"
            label={editingUser ? "新密码（留空不修改）" : "密码"}
            rules={
              editingUser
                ? []
                : [
                    { required: true, message: "请输入密码" },
                    { min: 6, message: "密码至少6位" },
                  ]
            }
          >
            <Input.Password placeholder="密码" />
          </Form.Item>
          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: "请选择角色" }]}
          >
            <Select>
              <Select.Option value="user">用户</Select.Option>
              <Select.Option value="admin">管理员</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
