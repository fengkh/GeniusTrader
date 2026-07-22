import { PlaceholderPage } from "@/components/layout/PlaceholderPage";

export default function InformationPage() {
  return (
    <PlaceholderPage
      eyebrow="信息中心"
      title="信息中心"
      description="本轮只建立导航可点击的占位页，完整公告资讯、舆情收件箱、博主关注和待核实信息将在下一阶段完善。"
      items={[
        "公告与资讯 Tab：来源、发布时间、采集时间和原始链接",
        "舆情收件箱 Tab：链接录入、用户补充文本和待解析状态",
        "博主关注 Tab：平台、博主ID、主页链接和用户备注",
        "待核实信息 Tab：未经证实传闻、平台观点和事实分开展示"
      ]}
    />
  );
}
