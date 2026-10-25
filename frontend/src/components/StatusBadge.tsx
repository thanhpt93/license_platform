import React from 'react';

export function StatusBadge({ status }: { status: string }) {
  const normalized = (status || '').toUpperCase();
  const styles: Record<string, string> = {
    ACTIVE: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    EXPIRED: 'bg-amber-50 text-amber-800 border-amber-200',
    SUSPENDED: 'bg-orange-50 text-orange-800 border-orange-200',
    REVOKED: 'bg-red-50 text-red-700 border-red-200',
    REPLACED: 'bg-slate-100 text-slate-700 border-slate-300',
    INACTIVE: 'bg-slate-100 text-slate-600 border-slate-300',
    RETIRED: 'bg-slate-100 text-slate-600 border-slate-300',
    SUCCESS: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    FAILURE: 'bg-red-50 text-red-700 border-red-200',
    DENIED: 'bg-amber-50 text-amber-800 border-amber-200',
    SUBSCRIPTION: 'bg-blue-50 text-blue-700 border-blue-200',
    PERPETUAL: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  };

  const cls = styles[normalized] || 'bg-slate-100 text-slate-700 border-slate-200';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold border ${cls}`}>
      {status}
    </span>
  );
}

export function formatLimitValue(val: number): string {
  if (val === -1) return 'Unlimited (-1)';
  if (val === 0) return 'Disabled (0)';
  return String(val);
}

export function formatDateTime(iso?: string | null): string {
  if (!iso) return 'Never (Perpetual)';
  try {
    return new Date(iso).toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
  } catch {
    return iso;
  }
}
