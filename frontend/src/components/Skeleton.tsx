/** Simple skeleton placeholder for loading states. */
export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-zinc-700/80 ${className}`}
      aria-hidden
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="rounded-lg bg-zinc-900 border border-zinc-700 p-4 flex flex-col">
      <Skeleton className="h-3 w-20 mb-2" />
      <Skeleton className="h-8 w-24 mt-1" />
      <Skeleton className="h-3 w-32 mt-2" />
    </div>
  );
}

export function EventRowSkeleton() {
  return (
    <div className="flex items-center gap-4 p-3 rounded-lg bg-zinc-900 border border-zinc-700">
      <Skeleton className="h-4 w-36 shrink-0" />
      <Skeleton className="h-5 w-14 rounded" />
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-24 ml-auto rounded" />
    </div>
  );
}

export function TimelineRowSkeleton() {
  return (
    <div className="flex items-center gap-3 py-2.5 px-2 border-b border-zinc-800/80">
      <Skeleton className="h-4 w-44 shrink-0" />
      <Skeleton className="h-4 w-20 rounded" />
      <Skeleton className="h-4 w-16 rounded" />
      <Skeleton className="h-4 w-12" />
    </div>
  );
}
