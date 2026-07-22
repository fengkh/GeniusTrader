import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

export default function ReviewsPage() {
  return (
    <PlaceholderPage
      eyebrow="复盘历史"
      title="复盘历史"
      description="本轮只展示入口。完整历史复盘列表、版本对比和观察条件回看将在下一阶段实现。"
      items={[
        "按日期查看单股每日复盘与整体复盘",
        "按股票查看历史复盘摘要",
        "区分AI原始版本和人工修订版本",
        "查看历史观察条件及其后续验证状态"
      ]}
    />
  );
}
