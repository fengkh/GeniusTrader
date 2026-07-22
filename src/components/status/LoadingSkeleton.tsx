export function LoadingSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="h-4 w-32 animate-pulse rounded bg-slate-200" />
      <div className="mt-4 space-y-3">
        {Array.from({ length: lines }).map((_, index) => (
          <div key={index} className="h-3 animate-pulse rounded bg-slate-100" />
        ))}
      </div>
    </div>
  );
}
