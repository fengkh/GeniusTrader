import type { ClassificationTag } from "@/mock/types";

const toneMap = {
  standard: "border-slate-300 bg-white text-slate-700",
  suggestion: "border-blue-200 bg-blue-50 text-blue-800",
  user: "border-emerald-200 bg-emerald-50 text-emerald-800"
};

const labelMap = {
  standard: "标准分类",
  suggestion: "系统建议",
  user: "用户标签"
};

export function ClassificationTagGroup({
  title,
  tags
}: {
  title: string;
  tags: ClassificationTag[];
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold text-slate-500">{title}</p>
      {tags.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {tags.map((tag) => (
            <span
              key={`${tag.kind}-${tag.label}`}
              className={`inline-flex items-center rounded-md border px-2 py-1 text-xs font-medium ${toneMap[tag.kind]}`}
              title={tag.detail}
            >
              {labelMap[tag.kind]}：{tag.label}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-sm text-slate-500">暂无{title}</p>
      )}
    </div>
  );
}
