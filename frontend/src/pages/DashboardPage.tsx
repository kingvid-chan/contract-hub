import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Typography } from "antd";
import {
  FileTextOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  StopOutlined,
} from "@ant-design/icons";
import { getContracts, ContractInfo } from "../api";

const { Title } = Typography;

const STATUS_CONFIG: Record<
  string,
  { color: string; icon: React.ReactNode; label: string }
> = {
  draft: { color: "#faad14", icon: <FileTextOutlined />, label: "草稿" },
  pending_review: {
    color: "#1890ff",
    icon: <ClockCircleOutlined />,
    label: "待审核",
  },
  active: {
    color: "#52c41a",
    icon: <CheckCircleOutlined />,
    label: "生效中",
  },
  expired: { color: "#d9d9d9", icon: <StopOutlined />, label: "已过期" },
  terminated: { color: "#ff4d4f", icon: <StopOutlined />, label: "已终止" },
};

export default function DashboardPage() {
  const [contracts, setContracts] = useState<ContractInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getContracts(1, 100)
      .then((res) => setContracts(res.items))
      .finally(() => setLoading(false));
  }, []);

  const statusCounts: Record<string, number> = {};
  contracts.forEach((c) => {
    statusCounts[c.status] = (statusCounts[c.status] || 0) + 1;
  });

  return (
    <div>
      <Title level={4}>仪表盘</Title>
      <Row gutter={[16, 16]}>
        {Object.entries(STATUS_CONFIG).map(([status, cfg]) => (
          <Col xs={24} sm={12} lg={4} xl={4} key={status}>
            <Card loading={loading}>
              <Statistic
                title={cfg.label}
                value={statusCounts[status] || 0}
                valueStyle={{ color: cfg.color }}
                prefix={cfg.icon}
              />
            </Card>
          </Col>
        ))}
      </Row>
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col span={24}>
          <Card>
            <Statistic
              title="合同总数"
              value={contracts.length}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
}
