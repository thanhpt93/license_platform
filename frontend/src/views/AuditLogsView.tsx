import React, { useEffect, useState } from 'react';
import { Search, RefreshCw, Shield } from 'lucide-react';
import { apiRequest, AuditLogItem } from '../api';
import { StatusBadge, formatDateTime } from '../components/StatusBadge';

export function AuditLogsView() {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [entityType, setEntityType] = useState<string>('');
  const [outcome, setOutcome] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadLogs = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: '20',
      });
      if (search.trim()) params.set('search', search.trim());
      if (entityType) params.set('entity_type', entityType);
      if (outcome) params.set('outcome', outcome);

      const res = await apiRequest<{ items: AuditLogItem[]; total: number }>(`/api/audit-logs?${params.toString()}`);
      setLogs(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [page, entityType, outcome]);

  return (
    <div className="space-y-5">
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            loadLogs();
          }}
          className="flex flex-wrap items-center gap-3 flex-1"
        >
          <div className="relative w-72">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search action, actor, reason, ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 border border-slate-300 rounded-md text-sm"
            />
          </div>
          <select
            value={entityType}
            onChange={(e) => {
              setEntityType(e.target.value);
              setPage(1);
            }}
            className="border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white"
          >
            <option value="">All Entity Types</option>
            <option value="LICENSE">LICENSE</option>
            <option value="CUSTOMER">CUSTOMER</option>
            <option value="LICENSE_PLAN">LICENSE_PLAN</option>
            <option value="PRODUCT">PRODUCT</option>
            <option value="SIGNING_KEY">SIGNING_KEY</option>
            <option value="USER">USER</option>
            <option value="SECURITY">SECURITY</option>
          </select>
          <select
            value={outcome}
            onChange={(e) => {
              setOutcome(e.target.value);
              setPage(1);
            }}
            className="border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white"
          >
            <option value="">All Outcomes</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="FAILURE">FAILURE</option>
            <option value="DENIED">DENIED</option>
          </select>
          <button
            type="submit"
            className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-sm font-medium"
          >
            Search
          </button>
        </form>

        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Shield className="w-4 h-4 text-blue-600" />
          Append-only administrative audit log (secrets sanitized)
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 flex items-center justify-center text-slate-500 text-sm">
            <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading audit trail...
          </div>
        ) : logs.length === 0 ? (
          <div className="p-10 text-center text-slate-500 text-sm">No matching audit log records found.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase">
                  <th className="py-3 px-4">Timestamp (UTC)</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Entity Type / ID</th>
                  <th className="py-3 px-4">Outcome</th>
                  <th className="py-3 px-4">Summary / Reason</th>
                  <th className="py-3 px-4">Metadata</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50">
                    <td className="py-2.5 px-4 font-mono text-xs text-slate-600 whitespace-nowrap">
                      {formatDateTime(log.timestamp)}
                    </td>
                    <td className="py-2.5 px-4 font-medium text-slate-900 text-xs">
                      {log.actor_username || 'unauthenticated'}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-xs font-semibold text-slate-800">{log.action}</td>
                    <td className="py-2.5 px-4 text-xs">
                      <span className="font-semibold text-slate-700">{log.entity_type}</span>
                      {log.entity_id && (
                        <span className="block font-mono text-[11px] text-slate-500 truncate max-w-[160px]">
                          {log.entity_id}
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 px-4">
                      <StatusBadge status={log.outcome} />
                    </td>
                    <td className="py-2.5 px-4 text-xs text-slate-700">{log.reason || '—'}</td>
                    <td className="py-2.5 px-4 font-mono text-[11px] text-slate-500 max-w-xs truncate">
                      {log.metadata_json ? JSON.stringify(log.metadata_json) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="px-4 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-600">
          <span>
            Showing {logs.length} of {total} audit events
          </span>
          <div className="space-x-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="px-2.5 py-1 border border-slate-300 bg-white rounded disabled:opacity-50"
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              disabled={page * 20 >= total}
              onClick={() => setPage((p) => p + 1)}
              className="px-2.5 py-1 border border-slate-300 bg-white rounded disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
