import React, { useEffect, useState } from 'react';
import {
  ShieldCheck,
  Users,
  KeyRound,
  AlertTriangle,
  Clock,
  Ban,
  PlusCircle,
  FileSpreadsheet,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { apiRequest, DashboardSummary, LicenseRecord } from '../api';
import { StatusBadge, formatDateTime } from '../components/StatusBadge';

interface DashboardViewProps {
  onNavigate: (tab: string) => void;
  onQuickCreateCustomer: () => void;
  onQuickIssueLicense: () => void;
  onSelectLicense: (lic: LicenseRecord) => void;
}

export function DashboardView({
  onNavigate,
  onQuickCreateCustomer,
  onQuickIssueLicense,
  onSelectLicense,
}: DashboardViewProps) {
  const [data, setData] = useState<DashboardSummary | null>(null);
  const [periodDays, setPeriodDays] = useState<number>(30);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = async (days: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiRequest<DashboardSummary>(`/api/dashboard?period_days=${days}&expiring_within_days=30`);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard(periodDays);
  }, [periodDays]);

  if (loading && !data) {
    return (
      <div className="p-8 flex items-center justify-center text-slate-500">
        <RefreshCw className="w-5 h-5 animate-spin mr-2" />
        Loading real-time licensing telemetry...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-lg text-red-700">
        <p className="font-semibold">Error loading dashboard statistics</p>
        <p className="text-sm mt-1">{error}</p>
        <button
          onClick={() => loadDashboard(periodDays)}
          className="mt-3 px-3 py-1.5 bg-red-600 text-white rounded text-xs font-medium"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-6">
      {/* Top Banner & Quick Actions */}
      <div className="bg-white border border-slate-200 rounded-lg p-5 flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Licensing & Cryptographic Operations Overview</h2>
          <div className="flex items-center gap-3 mt-1 text-sm text-slate-600">
            <span className="inline-flex items-center gap-1.5">
              <ShieldCheck className={`w-4 h-4 ${data.signing_engine_ready ? 'text-emerald-600' : 'text-red-600'}`} />
              Signing Authority:{' '}
              <strong className={data.signing_engine_ready ? 'text-emerald-700' : 'text-red-700'}>
                {data.signing_engine_ready ? `Ed25519 Ready (${data.active_key_id})` : 'Unavailable / Check Key Config'}
              </strong>
            </span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-slate-600 mr-2">
            <span>Issuance Period:</span>
            <select
              value={periodDays}
              onChange={(e) => setPeriodDays(Number(e.target.value))}
              className="border border-slate-300 rounded-md px-2.5 py-1.5 text-sm bg-white"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={365}>Last 365 days</option>
            </select>
          </div>
          <button
            onClick={onQuickCreateCustomer}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 rounded-md text-sm font-medium transition"
          >
            <PlusCircle className="w-4 h-4 text-blue-600" />
            New Customer
          </button>
          <button
            onClick={onQuickIssueLicense}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium shadow-sm transition"
          >
            <KeyRound className="w-4 h-4" />
            Issue License
          </button>
        </div>
      </div>

      {/* 6 Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase">
            <span>Total Customers</span>
            <Users className="w-4 h-4 text-blue-600" />
          </div>
          <p className="text-2xl font-bold text-slate-900 mt-2">{data.total_customers}</p>
          <p className="text-xs text-slate-500 mt-1">{data.active_customers} active accounts</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase">
            <span>Active Licenses</span>
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <p className="text-2xl font-bold text-emerald-700 mt-2">{data.active_licenses}</p>
          <p className="text-xs text-slate-500 mt-1">Valid & verified</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase">
            <span>Expiring Soon</span>
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <p className="text-2xl font-bold text-amber-700 mt-2">{data.expiring_soon_licenses}</p>
          <p className="text-xs text-slate-500 mt-1">Within next 30 days</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase">
            <span>Expired</span>
            <Clock className="w-4 h-4 text-slate-500" />
          </div>
          <p className="text-2xl font-bold text-slate-800 mt-2">{data.expired_licenses}</p>
          <p className="text-xs text-slate-500 mt-1">Past validity date</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase">
            <span>Revoked / Susp.</span>
            <Ban className="w-4 h-4 text-red-600" />
          </div>
          <p className="text-2xl font-bold text-red-700 mt-2">{data.revoked_or_suspended_licenses}</p>
          <p className="text-xs text-slate-500 mt-1">Administratively halted</p>
        </div>

        <div className="bg-white border border-slate-200 rounded-lg p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500 text-xs font-medium uppercase">
            <span>Issued ({data.period_days}d)</span>
            <FileSpreadsheet className="w-4 h-4 text-indigo-600" />
          </div>
          <p className="text-2xl font-bold text-indigo-700 mt-2">{data.issued_in_period}</p>
          <p className="text-xs text-slate-500 mt-1">New & renewed</p>
        </div>
      </div>

      {/* Main Content Grids: Recent Issuance & Expiring Soon */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent License Issuance Activity */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-sm flex flex-col">
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900 text-sm">Recent License Issuance Activity</h3>
            <button
              onClick={() => onNavigate('licenses')}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium inline-flex items-center gap-1"
            >
              View All <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
          <div className="overflow-x-auto">
            {data.recent_licenses.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No licenses have been issued yet. Use "Issue License" to sign your first license artifact.
              </div>
            ) : (
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase">
                    <th className="py-2.5 px-4">License #</th>
                    <th className="py-2.5 px-4">Customer</th>
                    <th className="py-2.5 px-4">Type</th>
                    <th className="py-2.5 px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {data.recent_licenses.map((lic) => (
                    <tr
                      key={lic.id}
                      onClick={() => onSelectLicense(lic)}
                      className="hover:bg-slate-50 cursor-pointer"
                    >
                      <td className="py-2.5 px-4 font-mono text-xs font-medium text-blue-600">
                        {lic.license_number}
                      </td>
                      <td className="py-2.5 px-4 text-slate-800">{lic.customer_name || lic.customer_code}</td>
                      <td className="py-2.5 px-4">
                        <StatusBadge status={lic.license_type} />
                      </td>
                      <td className="py-2.5 px-4">
                        <StatusBadge status={lic.effective_status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Licenses Approaching Expiration */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-sm flex flex-col">
          <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
            <h3 className="font-semibold text-slate-900 text-sm">Subscriptions Approaching Expiration (Next 30 Days)</h3>
            <span className="text-xs text-slate-500">{data.expiring_soon_list.length} listed</span>
          </div>
          <div className="overflow-x-auto">
            {data.expiring_soon_list.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-500">
                No active subscriptions are expiring within the next 30 days.
              </div>
            ) : (
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase">
                    <th className="py-2.5 px-4">License #</th>
                    <th className="py-2.5 px-4">Customer</th>
                    <th className="py-2.5 px-4">Expires At (UTC)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {data.expiring_soon_list.map((lic) => (
                    <tr
                      key={lic.id}
                      onClick={() => onSelectLicense(lic)}
                      className="hover:bg-slate-50 cursor-pointer"
                    >
                      <td className="py-2.5 px-4 font-mono text-xs font-medium text-blue-600">
                        {lic.license_number}
                      </td>
                      <td className="py-2.5 px-4 text-slate-800">{lic.customer_name}</td>
                      <td className="py-2.5 px-4 text-xs text-amber-700 font-medium">
                        {formatDateTime(lic.expires_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      {/* Recent Administrative Audit Actions */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 className="font-semibold text-slate-900 text-sm">Recent Administrative Actions</h3>
          <button
            onClick={() => onNavigate('audit')}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium inline-flex items-center gap-1"
          >
            Full Audit Log <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="overflow-x-auto">
          {data.recent_audit_logs.length === 0 ? (
            <div className="p-6 text-center text-sm text-slate-500">No administrative actions logged yet.</div>
          ) : (
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase">
                  <th className="py-2.5 px-4">Timestamp (UTC)</th>
                  <th className="py-2.5 px-4">Actor</th>
                  <th className="py-2.5 px-4">Action</th>
                  <th className="py-2.5 px-4">Entity</th>
                  <th className="py-2.5 px-4">Outcome</th>
                  <th className="py-2.5 px-4">Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {data.recent_audit_logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50">
                    <td className="py-2.5 px-4 font-mono text-xs text-slate-600">
                      {formatDateTime(log.timestamp)}
                    </td>
                    <td className="py-2.5 px-4 font-medium text-slate-800">
                      {log.actor_username || 'system'}
                    </td>
                    <td className="py-2.5 px-4 font-mono text-xs text-slate-800">{log.action}</td>
                    <td className="py-2.5 px-4 text-xs text-slate-600">{log.entity_type}</td>
                    <td className="py-2.5 px-4">
                      <StatusBadge status={log.outcome} />
                    </td>
                    <td className="py-2.5 px-4 text-slate-600 text-xs">{log.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
