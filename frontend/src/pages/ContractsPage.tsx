import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Button,
  Tag,
  Space,
  Modal,
  Form,
  Input,
  Select,
  message,
  Typography,
  Popconfirm,
} from "antd";
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import {
  getContracts,
  createContract,
  deleteContract,
  ContractInfo,
} from "../api";
import type { ApiError } from "../api";

const { Title } = Typography;

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  draft: { color: "gold", label: "草稿" },
  pending_review: { color: "blue", label: "待审核" },
  active: { color: "green", label: "生效中" },
  expired: { color: "default", label: "已过期" },
  terminated: { color: "red", label: "已终止" },
};

export default function ContractsPage() {
  const navigate = useNavigate();
  const [contracts, setContracts] = useState<ContractInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const fetchContracts = async (p = page, s = statusFilter) => {
    setLoading(true);
    try {
      const res = await getContracts(p, 20, s);
      setContracts(res.items);
      setTotal(res.total);
      setPage(p);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContracts();
  }, []);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      const created = await createContract(values);
      message.success("合同已创建");
      setModalOpen(false);
      navigate(`/contracts/${created.id}`);
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      if (apiErr?.detail) message.error(apiErr.detail);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteContract(id);
      message.success("合同已删除");
      fetchContracts();
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      message.error(apiErr?.detail || "删除失败");
    }
  };

  const columns = [
    { title: "ID", dataIndex: "id", key: "id", width: 60 },
    { title: "标题", dataIndex: "title", key: "title", ellipsis: true },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      width: 100,
      render: (status: string) => {
        const cfg = STATUS_MAP[status] || { color: "default", label: status };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: "创建者",
      key: "creator",
      width: 100,
      render: (_: unknown, r: ContractInfo) => r.creator?.username || "-",
    },
    {
      title: "更新时间",
      dataIndex: "updated_at",
      key: "updated_at",
      width: 180,
      render: (v: string) => new Date(v).toLocaleString("zh-CN"),
    },
    {
      title: "操作",
      key: "actions",
      width: 200,
      render: (_: unknown, record: ContractInfo) => (
        <Space>
          <Button
            type="link"
            icon={<EyeOutlined />}
            onClick={() => navigate(`/contracts/${record.id}`)}
          >
            查看
          </Button>
          {record.status === "draft" && (
            <>
              <Button
                type="link"
                icon={<EditOutlined />}
                onClick={() => navigate(`/contracts/${record.id}`)}
              >
                编辑
              </Button>
              <Popconfirm
                title="确定删除？"
                onConfirm={() => handleDelete(record.id)}
              >
                <Button type="link" danger icon={<DeleteOutlined />}>
                  删除
                </Button>
              </Popconfirm>
            </>
          )}
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
          合同管理
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            form.resetFields();
            setModalOpen(true);
          }}
        >
          新建合同
        </Button>
      </div>

      <div style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="按状态筛选"
          style={{ width: 150 }}
          value={statusFilter || undefined}
          onChange={(v) => {
            setStatusFilter(v || "");
            fetchContracts(1, v || "");
          }}
        >
          {Object.entries(STATUS_MAP).map(([k, v]) => (
            <Select.Option key={k} value={k}>
              {v.label}
            </Select.Option>
          ))}
        </Select>
      </div>

      <Table
        columns={columns}
        dataSource={contracts}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: (p) => fetchContracts(p),
        }}
        onRow={(record) => ({
          style: { cursor: "pointer" },
          onDoubleClick: () => navigate(`/contracts/${record.id}`),
        })}
      />

      <Modal
        title="新建合同"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="title"
            label="合同标题"
            rules={[{ required: true, message: "请输入合同标题" }]}
          >
            <Input placeholder="合同标题" maxLength={200} />
          </Form.Item>
          <Form.Item name="description" label="合同描述">
            <Input.TextArea rows={4} placeholder="合同描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
