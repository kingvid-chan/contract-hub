import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Card,
  Descriptions,
  Button,
  Space,
  Tag,
  message,
  Typography,
  Divider,
  Upload,
  List,
  Popconfirm,
  Spin,
  Form,
  Input,
  Modal,
} from "antd";
import {
  ArrowLeftOutlined,
  EditOutlined,
  SaveOutlined,
  CloseOutlined,
  SendOutlined,
  CheckOutlined,
  RollbackOutlined,
  StopOutlined,
  UploadOutlined,
  DownloadOutlined,
  DeleteOutlined,
} from "@ant-design/icons";
import { useAuth } from "../context/AuthContext";
import {
  getContract,
  updateContract,
  deleteContract,
  submitContract,
  approveContract,
  rejectContract,
  terminateContract,
  uploadAttachment,
  deleteAttachment,
  downloadAttachment,
  ContractInfo,
  AttachmentInfo,
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

const ALLOWED_EXTS = [".pdf", ".doc", ".docx"];

export default function ContractDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [contract, setContract] = useState<ContractInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [form] = Form.useForm();

  const fetchContract = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const c = await getContract(Number(id));
      setContract(c);
    } catch {
      navigate("/contracts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContract();
  }, [id]);

  const handleSave = async () => {
    if (!contract) return;
    try {
      const values = await form.validateFields();
      setSaving(true);
      const updated = await updateContract(contract.id, values);
      setContract(updated);
      setEditing(false);
      message.success("合同已更新");
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      if (apiErr?.detail) message.error(apiErr.detail);
    } finally {
      setSaving(false);
    }
  };

  const handleAction = async (
    action: string,
    fn: (id: number) => Promise<ContractInfo>
  ) => {
    if (!contract) return;
    setActionLoading(action);
    try {
      const updated = await fn(contract.id);
      setContract(updated);
      message.success("操作成功");
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      message.error(apiErr?.detail || "操作失败");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async () => {
    if (!contract) return;
    try {
      await deleteContract(contract.id);
      message.success("合同已删除");
      navigate("/contracts");
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      message.error(apiErr?.detail || "删除失败");
    }
  };

  const handleUpload = async (file: File) => {
    if (!contract) return false;
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      message.error(`不支持的文件类型：${ext}。仅支持 PDF、DOC、DOCX`);
      return false;
    }
    setUploading(true);
    try {
      await uploadAttachment(contract.id, file);
      message.success("附件上传成功");
      await fetchContract();
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      message.error(apiErr?.detail || "上传失败");
    } finally {
      setUploading(false);
    }
    return false; // Prevent default upload behavior
  };

  const handleDeleteAttachment = async (attId: number) => {
    try {
      await deleteAttachment(attId);
      message.success("附件已删除");
      fetchContract();
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      message.error(apiErr?.detail || "删除失败");
    }
  };

  const handleDownload = async (att: AttachmentInfo) => {
    try {
      await downloadAttachment(att.id, att.original_name);
    } catch (err: unknown) {
      const apiErr = err as { detail?: string };
      message.error(apiErr?.detail || "下载失败");
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 100 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!contract) return null;

  const isDraft = contract.status === "draft";
  const isPendingReview = contract.status === "pending_review";
  const isActive = contract.status === "active";
  const isAdmin = user?.role === "admin";
  const isOwner = user?.id === contract.creator_id;
  const canEdit = isDraft && (isAdmin || isOwner);
  const statusCfg = STATUS_MAP[contract.status] || {
    color: "default",
    label: contract.status,
  };

  return (
    <div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <Space>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate("/contracts")}
          >
            返回
          </Button>
          <Title level={4} style={{ margin: 0 }}>
            {contract.title}
          </Title>
          <Tag color={statusCfg.color}>{statusCfg.label}</Tag>
        </Space>
        <Space>
          {isDraft && (isAdmin || isOwner) && (
            <>
              {!editing && (
                <Button
                  icon={<EditOutlined />}
                  onClick={() => {
                    form.setFieldsValue({
                      title: contract.title,
                      description: contract.description,
                    });
                    setEditing(true);
                  }}
                >
                  编辑
                </Button>
              )}
              <Popconfirm title="确定删除？" onConfirm={handleDelete}>
                <Button danger icon={<DeleteOutlined />}>
                  删除
                </Button>
              </Popconfirm>
            </>
          )}
        </Space>
      </div>

      {editing ? (
        <Card style={{ marginBottom: 16 }}>
          <Form form={form} layout="vertical">
            <Form.Item
              name="title"
              label="合同标题"
              rules={[{ required: true, message: "请输入合同标题" }]}
            >
              <Input maxLength={200} />
            </Form.Item>
            <Form.Item name="description" label="合同描述">
              <Input.TextArea rows={6} />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  loading={saving}
                  onClick={handleSave}
                >
                  保存
                </Button>
                <Button
                  icon={<CloseOutlined />}
                  onClick={() => setEditing(false)}
                >
                  取消
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      ) : (
        <Card style={{ marginBottom: 16 }}>
          <Descriptions column={2}>
            <Descriptions.Item label="合同编号">{contract.id}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={statusCfg.color}>{statusCfg.label}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建者">
              {contract.creator?.username || "-"}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {new Date(contract.created_at).toLocaleString("zh-CN")}
            </Descriptions.Item>
            <Descriptions.Item label="更新时间">
              {new Date(contract.updated_at).toLocaleString("zh-CN")}
            </Descriptions.Item>
          </Descriptions>
          <Divider />
          <div style={{ whiteSpace: "pre-wrap" }}>
            {contract.description || "暂无描述"}
          </div>
        </Card>
      )}

      {/* Status transition actions */}
      <Card style={{ marginBottom: 16 }} title="合同操作">
        <Space>
          {isDraft && (isAdmin || isOwner) && (
            <Button
              type="primary"
              icon={<SendOutlined />}
              loading={actionLoading === "submit"}
              onClick={() => handleAction("submit", submitContract)}
            >
              提交审核
            </Button>
          )}
          {isPendingReview && isAdmin && (
            <>
              <Button
                type="primary"
                icon={<CheckOutlined />}
                loading={actionLoading === "approve"}
                onClick={() => handleAction("approve", approveContract)}
                style={{ background: "#52c41a", borderColor: "#52c41a" }}
              >
                审批通过
              </Button>
              <Button
                danger
                icon={<RollbackOutlined />}
                loading={actionLoading === "reject"}
                onClick={() => handleAction("reject", rejectContract)}
              >
                驳回
              </Button>
            </>
          )}
          {isActive && isAdmin && (
            <Button
              danger
              icon={<StopOutlined />}
              loading={actionLoading === "terminate"}
              onClick={() => handleAction("terminate", terminateContract)}
            >
              终止合同
            </Button>
          )}
        </Space>
      </Card>

      {/* Attachments */}
      <Card
        title="附件"
        extra={
          <Upload
            beforeUpload={(file) => {
              handleUpload(file);
              return false;
            }}
            showUploadList={false}
            accept=".pdf,.doc,.docx"
          >
            <Button
              icon={<UploadOutlined />}
              loading={uploading}
              disabled={isDraft === false && !isAdmin}
            >
              上传附件
            </Button>
          </Upload>
        }
      >
        {contract.attachments && contract.attachments.length > 0 ? (
          <List
            dataSource={contract.attachments}
            renderItem={(att: AttachmentInfo) => (
              <List.Item
                actions={[
                  <Button
                    type="link"
                    icon={<DownloadOutlined />}
                    onClick={() => handleDownload(att)}
                    key="download"
                  >
                    下载
                  </Button>,
                  (isAdmin || att.uploader_id === user?.id) && (
                    <Popconfirm
                      title="确定删除该附件？"
                      onConfirm={() => handleDeleteAttachment(att.id)}
                      key="delete"
                    >
                      <Button type="link" danger icon={<DeleteOutlined />}>
                        删除
                      </Button>
                    </Popconfirm>
                  ),
                ].filter(Boolean)}
              >
                <List.Item.Meta
                  title={att.original_name}
                  description={`${(att.file_size / 1024).toFixed(1)} KB · ${att.content_type} · ${new Date(att.created_at).toLocaleString("zh-CN")}`}
                />
              </List.Item>
            )}
          />
        ) : (
          <div style={{ color: "#999", textAlign: "center", padding: 24 }}>
            暂无附件
          </div>
        )}
      </Card>
    </div>
  );
}
