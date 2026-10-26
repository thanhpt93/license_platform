import React, { useEffect, useState } from 'react';
import {
  Search,
  KeyRound,
  Download,
  ShieldCheck,
  ShieldAlert,
  RefreshCw,
  ArrowLeft,
  RotateCcw,
  Replace,
  PauseCircle,
  Ban,
  FileCode,
  CheckCircle2,
  X,
} from 'lucide-react';
import {
  ALL_SOFTWARE_FEATURES,
  apiRequest,
  Customer,
  downloadSignedLicenseFile,
  isAllFeatures,
  LicensePlan,
  LicenseRecord,
  Product,
  VerifyArtifactResponse,
} from '../api';
import { StatusBadge, formatDateTime, formatLimitValue } from '../components/StatusBadge';

interface LicensesViewProps {
  openIssueWizardSignal?: number;
  selectedLicenseSignal?: LicenseRecord | null;
  onClearSelectedLicenseSignal?: () => void;
  canWrite: boolean;
}

export function LicensesView({
  openIssueWizardSignal,
  selectedLicenseSignal,
  onClearSelectedLicenseSignal,
  canWrite,
}: LicensesViewProps) {
  const [licenses, setLicenses] = useState<LicenseRecord[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [editionFilter, setEditionFilter] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Detail View state
  const [activeLicense, setActiveLicense] = useState<LicenseRecord | null>(null);
  const [verificationResult, setVerificationResult] = useState<VerifyArtifactResponse | null>(null);
  const [showPayloadModal, setShowPayloadModal] = useState<boolean>(false);

  // Issue Wizard Modal state
  const [showIssueWizard, setShowIssueWizard] = useState<boolean>(false);
  const [wizardStep, setWizardStep] = useState<number>(1);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [plans, setPlans] = useState<LicensePlan[]>([]);

  const [selectedCustomerId, setSelectedCustomerId] = useState<string>('');
  const [selectedProductId, setSelectedProductId] = useState<string>('');
  const [selectedEdition, setSelectedEdition] = useState<'developer' | 'production'>('production');
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [customDurationDays, setCustomDurationDays] = useState<number>(365);
  const [customMaxDevices, setCustomMaxDevices] = useState<number>(1);
  const [customMaxConcurrent, setCustomMaxConcurrent] = useState<number>(4);
  const [customTotalQuota, setCustomTotalQuota] = useState<number>(-1);
  const [allFeaturesEnabled, setAllFeaturesEnabled] = useState<boolean>(true);
  const [issueNotes, setIssueNotes] = useState<string>('');
  const [wizardError, setWizardError] = useState<string | null>(null);
  const [issuing, setIssuing] = useState<boolean>(false);
  const [issuedResult, setIssuedResult] = useState<LicenseRecord | null>(null);

  // Lifecycle Action Modal (Renew / Replace / Suspend / Revoke)
  const [lifecycleAction, setLifecycleAction] = useState<'RENEW' | 'REPLACE' | 'SUSPEND' | 'REVOKE' | null>(null);
  const [actionReason, setActionReason] = useState<string>('');
  const [actionDurationDays, setActionDurationDays] = useState<number>(365);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSubmitting, setActionSubmitting] = useState<boolean>(false);

  // Standalone Artifact Verifier Modal
  const [showStandaloneVerifier, setShowStandaloneVerifier] = useState<boolean>(false);
  const [rawArtifactInput, setRawArtifactInput] = useState<string>('');
  const [standaloneVerifyRes, setStandaloneVerifyRes] = useState<VerifyArtifactResponse | null>(null);

  const loadLicenses = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: '15',
      });
      if (search.trim()) params.set('search', search.trim());
      if (statusFilter) params.set('status', statusFilter);
      if (editionFilter) params.set('edition', editionFilter);

      const res = await apiRequest<{ items: LicenseRecord[]; total: number }>(`/api/licenses?${params.toString()}`);
      setLicenses(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load licenses');
    } finally {
      setLoading(false);
    }
  };

  const loadLicenseDetail = async (id: string) => {
    try {
      const detail = await apiRequest<LicenseRecord>(`/api/licenses/${id}`);
      setActiveLicense(detail);
      setVerificationResult(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to load license details');
    }
  };

  useEffect(() => {
    loadLicenses();
  }, [page, statusFilter, editionFilter]);

  useEffect(() => {
    if (selectedLicenseSignal) {
      loadLicenseDetail(selectedLicenseSignal.id);
      if (onClearSelectedLicenseSignal) onClearSelectedLicenseSignal();
    }
  }, [selectedLicenseSignal]);

  useEffect(() => {
    if (openIssueWizardSignal && openIssueWizardSignal > 0 && canWrite) {
      openWizard();
    }
  }, [openIssueWizardSignal]);

  const openWizard = async () => {
    setWizardError(null);
    setIssuedResult(null);
    setWizardStep(1);
    setAllFeaturesEnabled(true);
    setShowIssueWizard(true);
    try {
      const [custRes, prodRes, planRes] = await Promise.all([
        apiRequest<{ items: Customer[] }>('/api/customers?status=ACTIVE&page_size=100'),
        apiRequest<Product[]>('/api/products'),
        apiRequest<LicensePlan[]>('/api/license-plans?status=ACTIVE'),
      ]);
      setCustomers(custRes.items);
      setProducts(prodRes);
      setPlans(planRes);

      if (custRes.items.length > 0) setSelectedCustomerId(custRes.items[0].id);
      if (prodRes.length > 0) setSelectedProductId(prodRes[0].id);
      const matchingPlans = planRes.filter((p) => p.edition === 'production');
      if (matchingPlans.length > 0) {
        selectPlanInWizard(matchingPlans[0]);
      } else if (planRes.length > 0) {
        setSelectedEdition(planRes[0].edition);
        selectPlanInWizard(planRes[0]);
      }
    } catch (err) {
      setWizardError(err instanceof Error ? err.message : 'Failed to load wizard prerequisites');
    }
  };

  const selectPlanInWizard = (p: LicensePlan) => {
    setSelectedPlanId(p.id);
    setCustomDurationDays(p.default_duration_days || 365);
    setCustomMaxDevices(p.max_devices);
    setCustomMaxConcurrent(p.max_concurrent_inspections);
    setCustomTotalQuota(p.total_inspection_quota);
  };

  const handleEditionChangeInWizard = (ed: 'developer' | 'production') => {
    setSelectedEdition(ed);
    const matching = plans.filter((p) => p.product_id === selectedProductId && p.edition === ed);
    if (matching.length > 0) {
      selectPlanInWizard(matching[0]);
    } else {
      setSelectedPlanId('');
    }
  };

  const currentWizardPlan = plans.find((p) => p.id === selectedPlanId);
  const currentWizardCustomer = customers.find((c) => c.id === selectedCustomerId);
  const currentWizardProduct = products.find((p) => p.id === selectedProductId);

  const handleConfirmIssue = async () => {
    if (!currentWizardPlan || !selectedCustomerId) return;
    setIssuing(true);
    setWizardError(null);
    try {
      const payload: Record<string, unknown> = {
        customer_id: selectedCustomerId,
        plan_id: selectedPlanId,
        notes: issueNotes || null,
      };
      if (allFeaturesEnabled) {
        payload.custom_features = ALL_SOFTWARE_FEATURES;
      }
      if (currentWizardPlan.license_type === 'SUBSCRIPTION') {
        payload.duration_days = Number(customDurationDays);
      }
      if (currentWizardPlan.allow_custom_limits) {
        payload.custom_limits = {
          max_devices: Number(customMaxDevices),
          max_concurrent_inspections: Number(customMaxConcurrent),
          total_inspection_quota: Number(customTotalQuota),
        };
      }
      const created = await apiRequest<LicenseRecord>('/api/licenses', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      setIssuedResult(created);
      setWizardStep(3);
      await loadLicenses();
    } catch (err) {
      setWizardError(err instanceof Error ? err.message : 'License issuance failed');
    } finally {
      setIssuing(false);
    }
  };

  const handleVerifySignature = async (licId: string) => {
    try {
      const res = await apiRequest<VerifyArtifactResponse>(`/api/licenses/${licId}/verify`, {
        method: 'POST',
      });
      setVerificationResult(res);
      await loadLicenseDetail(licId);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Verification failed');
    }
  };

  const handleExecuteLifecycleAction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeLicense || !lifecycleAction) return;
    setActionSubmitting(true);
    setActionError(null);

    try {
      let updatedOrNew: LicenseRecord;
      if (lifecycleAction === 'RENEW') {
        updatedOrNew = await apiRequest<LicenseRecord>(`/api/licenses/${activeLicense.id}/renew`, {
          method: 'POST',
          body: JSON.stringify({
            duration_days: Number(actionDurationDays),
            reason: actionReason,
          }),
        });
      } else if (lifecycleAction === 'REPLACE') {
        updatedOrNew = await apiRequest<LicenseRecord>(`/api/licenses/${activeLicense.id}/replace`, {
          method: 'POST',
          body: JSON.stringify({
            reason: actionReason,
          }),
        });
      } else if (lifecycleAction === 'SUSPEND') {
        updatedOrNew = await apiRequest<LicenseRecord>(`/api/licenses/${activeLicense.id}/suspend`, {
          method: 'POST',
          body: JSON.stringify({ reason: actionReason }),
        });
      } else {
        updatedOrNew = await apiRequest<LicenseRecord>(`/api/licenses/${activeLicense.id}/revoke`, {
          method: 'POST',
          body: JSON.stringify({ reason: actionReason }),
        });
      }

      setLifecycleAction(null);
      setActionReason('');
      await loadLicenses();
      await loadLicenseDetail(updatedOrNew.id);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setActionSubmitting(false);
    }
  };

  const handleVerifyStandaloneJson = async (e: React.FormEvent) => {
    e.preventDefault();
    setStandaloneVerifyRes(null);
    try {
      const parsed = JSON.parse(rawArtifactInput);
      const res = await apiRequest<VerifyArtifactResponse>('/api/licenses/verify-artifact', {
        method: 'POST',
        body: JSON.stringify({ artifact: parsed }),
      });
      setStandaloneVerifyRes(res);
    } catch (err) {
      setStandaloneVerifyRes({
        valid: false,
        reason: err instanceof Error ? err.message : 'Invalid JSON artifact format',
        verified_at: new Date().toISOString(),
      });
    }
  };

  // =====================================================================
  // ISSUED LICENSE DETAIL VIEW
  // =====================================================================
  if (activeLicense) {
    const canModifyState =
      canWrite && activeLicense.effective_status !== 'REVOKED' && activeLicense.effective_status !== 'REPLACED';

    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <button
            onClick={() => setActiveLicense(null)}
            className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 font-medium"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Licenses List
          </button>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setShowPayloadModal(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 rounded-md text-xs font-medium"
            >
              <FileCode className="w-4 h-4" /> View Canonical Payload & Artifact
            </button>
            <button
              onClick={() => handleVerifySignature(activeLicense.id)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-emerald-300 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 rounded-md text-xs font-medium"
            >
              <ShieldCheck className="w-4 h-4" /> Verify Signature Now
            </button>
            <button
              onClick={() => downloadSignedLicenseFile(activeLicense.id, activeLicense.license_number)}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-medium shadow-sm"
            >
              <Download className="w-4 h-4" /> Download Signed License (.novalic.json)
            </button>
          </div>
        </div>

        {verificationResult && (
          <div
            className={`p-4 rounded-lg border flex items-center justify-between ${
              verificationResult.valid
                ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                : 'bg-red-50 border-red-200 text-red-900'
            }`}
          >
            <div className="flex items-center gap-3">
              {verificationResult.valid ? (
                <ShieldCheck className="w-6 h-6 text-emerald-600" />
              ) : (
                <ShieldAlert className="w-6 h-6 text-red-600" />
              )}
              <div className="text-sm">
                <div className="font-semibold">
                  {verificationResult.valid
                    ? 'Ed25519 Cryptographic Signature Verified'
                    : 'Cryptographic Signature Verification Failed'}
                </div>
                <div className="text-xs opacity-90">{verificationResult.reason}</div>
              </div>
            </div>
            <span className="text-xs font-mono">{formatDateTime(verificationResult.verified_at)}</span>
          </div>
        )}

        {/* Main Detail Card */}
        <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-bold font-mono text-slate-900">{activeLicense.license_number}</h2>
                <StatusBadge status={activeLicense.effective_status} />
                <StatusBadge status={activeLicense.license_type} />
              </div>
              <p className="text-xs text-slate-500 mt-1 font-mono">License UUID: {activeLicense.id}</p>
            </div>

            {canModifyState && (
              <div className="flex items-center gap-2">
                {activeLicense.license_type === 'SUBSCRIPTION' && (
                  <button
                    onClick={() => {
                      setLifecycleAction('RENEW');
                      setActionDurationDays(365);
                      setActionReason('');
                      setActionError(null);
                    }}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded text-xs font-medium"
                  >
                    <RotateCcw className="w-3.5 h-3.5" /> Issue Renewal
                  </button>
                )}
                <button
                  onClick={() => {
                    setLifecycleAction('REPLACE');
                    setActionReason('');
                    setActionError(null);
                  }}
                  className="inline-flex items-center gap-1 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-300 rounded text-xs font-medium"
                >
                  <Replace className="w-3.5 h-3.5" /> Issue Replacement
                </button>
                {activeLicense.effective_status !== 'SUSPENDED' && (
                  <button
                    onClick={() => {
                      setLifecycleAction('SUSPEND');
                      setActionReason('');
                      setActionError(null);
                    }}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded text-xs font-medium"
                  >
                    <PauseCircle className="w-3.5 h-3.5" /> Suspend
                  </button>
                )}
                <button
                  onClick={() => {
                    setLifecycleAction('REVOKE');
                    setActionReason('');
                    setActionError(null);
                  }}
                  className="inline-flex items-center gap-1 px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 rounded text-xs font-medium"
                >
                  <Ban className="w-3.5 h-3.5" /> Revoke
                </button>
              </div>
            )}
          </div>

          <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
            {/* Column 1: Customer & Product */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Customer & Product</h4>
              <div>
                <span className="text-xs text-slate-500 block">Customer</span>
                <span className="font-semibold text-slate-900">{activeLicense.customer_name}</span>
                <span className="ml-2 font-mono text-xs text-blue-700">({activeLicense.customer_code})</span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Product & Edition</span>
                <span className="font-mono font-semibold text-slate-800">{activeLicense.product_code_snapshot}</span>
                <span className="ml-2 px-2 py-0.5 bg-slate-100 rounded font-mono text-xs">{activeLicense.edition}</span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Commercial Plan Snapshot</span>
                <span className="font-medium text-slate-800">{activeLicense.plan_name_snapshot}</span>
                <span className="block font-mono text-xs text-slate-500">{activeLicense.plan_code_snapshot}</span>
              </div>
            </div>

            {/* Column 2: Validity & Dates */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Validity & Timestamps</h4>
              <div>
                <span className="text-xs text-slate-500 block">Issued Date (UTC)</span>
                <span className="font-mono text-xs text-slate-800">{formatDateTime(activeLicense.issued_at)}</span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Valid-From Date (not_before)</span>
                <span className="font-mono text-xs text-slate-800">{formatDateTime(activeLicense.not_before)}</span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Expiration Date (expires_at)</span>
                <span className="font-mono text-xs font-semibold text-slate-900">
                  {formatDateTime(activeLicense.expires_at)}
                </span>
              </div>
              {activeLicense.status_reason && (
                <div>
                  <span className="text-xs text-slate-500 block">Status Change Reason</span>
                  <span className="text-xs text-amber-800 bg-amber-50 px-2 py-1 rounded border border-amber-200 inline-block mt-0.5">
                    {activeLicense.status_reason}
                  </span>
                </div>
              )}
            </div>

            {/* Column 3: Cryptographic Signature */}
            <div className="space-y-3">
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Cryptographic Proof</h4>
              <div>
                <span className="text-xs text-slate-500 block">Signature Verification Status</span>
                {activeLicense.signature_verified ? (
                  <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold text-xs mt-0.5">
                    <ShieldCheck className="w-4 h-4" /> Verified Valid (Ed25519)
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-red-700 font-semibold text-xs mt-0.5">
                    <ShieldAlert className="w-4 h-4" /> Verification Failed
                  </span>
                )}
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Signing Key ID</span>
                <span className="font-mono text-xs font-semibold text-slate-800">{activeLicense.key_id}</span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Ed25519 Signature (Base64)</span>
                <div className="font-mono text-[11px] text-slate-600 bg-slate-50 p-2 rounded border border-slate-200 break-all">
                  {activeLicense.signature_b64}
                </div>
              </div>
            </div>
          </div>

          {/* Entitlements: Features & Limits */}
          <div className="px-6 py-4 border-t border-slate-200 bg-slate-50/60 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <h4 className="text-xs font-semibold text-slate-500 uppercase">Signed Feature Entitlements</h4>
                {isAllFeatures(activeLicense.features_snapshot) && (
                  <span className="px-2 py-0.5 bg-emerald-50 text-emerald-800 border border-emerald-300 rounded text-[11px] font-semibold">
                    ★ All Software Features (*)
                  </span>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {activeLicense.features_snapshot.map((f) => (
                  <span
                    key={f}
                    className="px-2.5 py-1 bg-white border border-blue-200 text-blue-800 rounded text-xs font-mono font-medium"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>
            <div>
              <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">Signed Runtime Limits</h4>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div className="bg-white p-2.5 rounded border border-slate-200">
                  <span className="text-slate-500 block">Max Activated Devices</span>
                  <span className="font-mono font-semibold text-slate-900 mt-0.5 block">
                    {formatLimitValue(activeLicense.limits_snapshot.max_devices)}
                  </span>
                </div>
                <div className="bg-white p-2.5 rounded border border-slate-200">
                  <span className="text-slate-500 block">Max Concurrent Insp.</span>
                  <span className="font-mono font-semibold text-slate-900 mt-0.5 block">
                    {formatLimitValue(activeLicense.limits_snapshot.max_concurrent_inspections)}
                  </span>
                </div>
                <div className="bg-white p-2.5 rounded border border-slate-200">
                  <span className="text-slate-500 block">Total Insp. Quota</span>
                  <span className="font-mono font-semibold text-slate-900 mt-0.5 block">
                    {formatLimitValue(activeLicense.limits_snapshot.total_inspection_quota)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Issuance, Renewal & Replacement Lineage History */}
          <div className="px-6 py-4 border-t border-slate-200">
            <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">
              Issuance, Renewal & Replacement History
            </h4>
            {activeLicense.lineage_previous.length === 0 && activeLicense.lineage_next.length === 0 ? (
              <p className="text-xs text-slate-500">
                Original standalone license issuance. No prior or successor linked licenses.
              </p>
            ) : (
              <div className="space-y-2 text-xs">
                {activeLicense.lineage_previous.map((rel) => (
                  <div
                    key={rel.id}
                    className="flex items-center justify-between p-2.5 bg-slate-50 rounded border border-slate-200"
                  >
                    <div>
                      <span className="font-semibold text-slate-700">{rel.relationship_type} FROM: </span>
                      <button
                        onClick={() => loadLicenseDetail(rel.previous_license_id)}
                        className="font-mono text-blue-600 hover:underline font-medium"
                      >
                        {rel.previous_license_number || rel.previous_license_id}
                      </button>
                      <span className="text-slate-500 ml-2">— {rel.reason}</span>
                    </div>
                    <span className="font-mono text-slate-500">{formatDateTime(rel.created_at)}</span>
                  </div>
                ))}
                {activeLicense.lineage_next.map((rel) => (
                  <div
                    key={rel.id}
                    className="flex items-center justify-between p-2.5 bg-blue-50/50 rounded border border-blue-200"
                  >
                    <div>
                      <span className="font-semibold text-blue-900">{rel.relationship_type} TO: </span>
                      <button
                        onClick={() => loadLicenseDetail(rel.new_license_id)}
                        className="font-mono text-blue-600 hover:underline font-medium"
                      >
                        {rel.new_license_number || rel.new_license_id}
                      </button>
                      <span className="text-slate-600 ml-2">— {rel.reason}</span>
                    </div>
                    <span className="font-mono text-slate-500">{formatDateTime(rel.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* View Canonical Payload Modal */}
        {showPayloadModal && (
          <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full overflow-hidden max-h-[90vh] flex flex-col">
              <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                <h3 className="font-semibold text-slate-900 text-sm">
                  Signed License Artifact Envelope ({activeLicense.license_number})
                </h3>
                <button onClick={() => setShowPayloadModal(false)} className="text-slate-400 hover:text-slate-600">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="p-6 overflow-y-auto">
                <pre className="bg-slate-900 text-slate-100 p-4 rounded-md font-mono text-xs overflow-x-auto">
                  {JSON.stringify(activeLicense.signed_artifact_json, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        )}

        {/* Lifecycle Action Modal */}
        {lifecycleAction && (
          <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg shadow-xl max-w-md w-full overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
                <h3 className="font-semibold text-slate-900">
                  {lifecycleAction === 'RENEW' && `Renew License (${activeLicense.license_number})`}
                  {lifecycleAction === 'REPLACE' && `Replace License (${activeLicense.license_number})`}
                  {lifecycleAction === 'SUSPEND' && `Suspend License (${activeLicense.license_number})`}
                  {lifecycleAction === 'REVOKE' && `Revoke License (${activeLicense.license_number})`}
                </h3>
                <button onClick={() => setLifecycleAction(null)} className="text-slate-400 hover:text-slate-600">
                  <X className="w-5 h-5" />
                </button>
              </div>
              <form onSubmit={handleExecuteLifecycleAction} className="p-6 space-y-4 text-sm">
                {actionError && (
                  <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">{actionError}</div>
                )}

                {lifecycleAction === 'RENEW' && (
                  <>
                    <p className="text-slate-600 text-xs">
                      Renewal issues a brand-new cryptographically signed license artifact linked to{' '}
                      <strong>{activeLicense.license_number}</strong> while preserving the previous record untouched.
                    </p>
                    <div>
                      <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                        Renewal Duration (Days) *
                      </label>
                      <input
                        type="number"
                        min={1}
                        required
                        value={actionDurationDays}
                        onChange={(e) => setActionDurationDays(Number(e.target.value))}
                        className="w-full border border-slate-300 rounded px-3 py-2 font-mono"
                      />
                    </div>
                  </>
                )}

                {lifecycleAction === 'REPLACE' && (
                  <p className="text-slate-600 text-xs">
                    Replacement issues a new signed license artifact and marks{' '}
                    <strong>{activeLicense.license_number}</strong> as <code>REPLACED</code>.
                  </p>
                )}

                {(lifecycleAction === 'SUSPEND' || lifecycleAction === 'REVOKE') && (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded text-xs text-amber-900">
                    <strong>Operational Notice:</strong> Changing status to {lifecycleAction} updates internal server
                    records immediately. Offline customer PCs will not learn of this change until online/offline
                    revocation synchronization is executed.
                  </div>
                )}

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Audit Reason / Justification *
                  </label>
                  <textarea
                    required
                    minLength={3}
                    rows={3}
                    placeholder="Enter an auditable administrative reason..."
                    value={actionReason}
                    onChange={(e) => setActionReason(e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                  />
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setLifecycleAction(null)}
                    className="px-4 py-2 border border-slate-300 rounded text-slate-700"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionSubmitting}
                    className={`px-4 py-2 text-white rounded font-medium ${
                      lifecycleAction === 'REVOKE'
                        ? 'bg-red-600 hover:bg-red-700'
                        : lifecycleAction === 'SUSPEND'
                        ? 'bg-amber-600 hover:bg-amber-700'
                        : 'bg-blue-600 hover:bg-blue-700'
                    }`}
                  >
                    {actionSubmitting ? 'Processing...' : `Confirm ${lifecycleAction}`}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    );
  }

  // =====================================================================
  // LICENSES LIST VIEW
  // =====================================================================
  return (
    <div className="space-y-5">
      {/* Top Filter & Action Bar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            loadLicenses();
          }}
          className="flex flex-wrap items-center gap-3 flex-1"
        >
          <div className="relative w-72">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search license #, customer, plan..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 border border-slate-300 rounded-md text-sm"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white"
          >
            <option value="">All Statuses</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="EXPIRED">EXPIRED</option>
            <option value="SUSPENDED">SUSPENDED</option>
            <option value="REVOKED">REVOKED</option>
            <option value="REPLACED">REPLACED</option>
          </select>
          <select
            value={editionFilter}
            onChange={(e) => {
              setEditionFilter(e.target.value);
              setPage(1);
            }}
            className="border border-slate-300 rounded-md px-3 py-1.5 text-sm bg-white"
          >
            <option value="">All Editions</option>
            <option value="production">production</option>
            <option value="developer">developer</option>
          </select>
          <button
            type="submit"
            className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-sm font-medium"
          >
            Filter
          </button>
        </form>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => {
              setRawArtifactInput('');
              setStandaloneVerifyRes(null);
              setShowStandaloneVerifier(true);
            }}
            className="inline-flex items-center gap-1.5 px-3 py-2 border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 rounded-md text-sm font-medium"
          >
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            Verify External Artifact
          </button>
          {canWrite && (
            <button
              onClick={openWizard}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium shadow-sm"
            >
              <KeyRound className="w-4 h-4" />
              Issue License
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      {/* Licenses Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 flex items-center justify-center text-slate-500 text-sm">
            <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading issued licenses...
          </div>
        ) : licenses.length === 0 ? (
          <div className="p-10 text-center text-slate-500 text-sm">
            No issued licenses found. Click &quot;Issue License&quot; to generate and sign a new license.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase">
                  <th className="py-3 px-4">License Number</th>
                  <th className="py-3 px-4">Customer</th>
                  <th className="py-3 px-4">Plan & Edition</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Issued At</th>
                  <th className="py-3 px-4">Expires At</th>
                  <th className="py-3 px-4">Key ID</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {licenses.map((lic) => (
                  <tr key={lic.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4">
                      <button
                        onClick={() => loadLicenseDetail(lic.id)}
                        className="font-mono text-xs font-bold text-blue-600 hover:underline"
                      >
                        {lic.license_number}
                      </button>
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-medium text-slate-900">{lic.customer_name}</div>
                      <div className="font-mono text-xs text-slate-500">{lic.customer_code}</div>
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-xs font-medium text-slate-800">{lic.plan_code_snapshot}</div>
                      <span className="font-mono text-[11px] px-1.5 py-0.5 bg-slate-100 rounded text-slate-600">
                        {lic.edition}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={lic.license_type} />
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-600">{formatDateTime(lic.issued_at)}</td>
                    <td className="py-3 px-4 text-xs text-slate-700 font-medium">{formatDateTime(lic.expires_at)}</td>
                    <td className="py-3 px-4 font-mono text-xs text-slate-600">{lic.key_id}</td>
                    <td className="py-3 px-4">
                      <StatusBadge status={lic.effective_status} />
                    </td>
                    <td className="py-3 px-4 text-right space-x-2">
                      <button
                        onClick={() => loadLicenseDetail(lic.id)}
                        className="px-2.5 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded border border-blue-200"
                      >
                        Details
                      </button>
                      <button
                        onClick={() => downloadSignedLicenseFile(lic.id, lic.license_number)}
                        title="Download Signed Artifact"
                        className="p-1.5 text-slate-500 hover:text-blue-600 rounded hover:bg-slate-100"
                      >
                        <Download className="w-4 h-4 inline" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="px-4 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between text-xs text-slate-600">
          <span>
            Showing {licenses.length} of {total} license records
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
              disabled={page * 15 >= total}
              onClick={() => setPage((p) => p + 1)}
              className="px-2.5 py-1 border border-slate-300 bg-white rounded disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* =====================================================================
          STEP-BY-STEP LICENSE ISSUANCE WIZARD MODAL
         ===================================================================== */}
      {showIssueWizard && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full overflow-hidden max-h-[92vh] flex flex-col">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="font-semibold text-slate-900">Issue Digitally Signed License</h3>
                <p className="text-xs text-slate-500">
                  Step {wizardStep} of 3:{' '}
                  {wizardStep === 1
                    ? 'Select Customer, Product, Edition, Plan & Entitlements'
                    : wizardStep === 2
                    ? 'Review Canonical Payload Snapshot & Confirm Issuance'
                    : 'Signed License Artifact Ready'}
                </p>
              </div>
              <button onClick={() => setShowIssueWizard(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 text-sm">
              {wizardError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">{wizardError}</div>
              )}

              {wizardStep === 1 && (
                <div className="space-y-4">
                  {customers.length === 0 ? (
                    <div className="p-4 bg-amber-50 border border-amber-200 rounded text-xs text-amber-900">
                      No ACTIVE customers exist yet. Please create an active customer in the Customers tab first.
                    </div>
                  ) : (
                    <>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                          1. Select Active Customer *
                        </label>
                        <select
                          value={selectedCustomerId}
                          onChange={(e) => setSelectedCustomerId(e.target.value)}
                          className="w-full border border-slate-300 rounded px-3 py-2 bg-white"
                        >
                          {customers.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.company_name} ({c.customer_code})
                            </option>
                          ))}
                        </select>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                            2. Select Product *
                          </label>
                          <select
                            value={selectedProductId}
                            onChange={(e) => setSelectedProductId(e.target.value)}
                            className="w-full border border-slate-300 rounded px-3 py-2 bg-white"
                          >
                            {products.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.product_name} ({p.product_code})
                              </option>
                            ))}
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                            3. Select Edition *
                          </label>
                          <select
                            value={selectedEdition}
                            onChange={(e) => handleEditionChangeInWizard(e.target.value as 'developer' | 'production')}
                            className="w-full border border-slate-300 rounded px-3 py-2 bg-white"
                          >
                            <option value="production">production</option>
                            <option value="developer">developer</option>
                          </select>
                        </div>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                          4. Select Commercial License Plan *
                        </label>
                        <select
                          value={selectedPlanId}
                          onChange={(e) => {
                            const found = plans.find((pl) => pl.id === e.target.value);
                            if (found) selectPlanInWizard(found);
                          }}
                          className="w-full border border-slate-300 rounded px-3 py-2 bg-white"
                        >
                          {plans
                            .filter((p) => p.product_id === selectedProductId && p.edition === selectedEdition)
                            .map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.plan_name} [{p.plan_code}] — {p.license_type}
                              </option>
                            ))}
                        </select>
                      </div>

                      {currentWizardPlan && (
                        <div className="bg-slate-50 p-4 rounded border border-slate-200 space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-semibold text-slate-700 uppercase">
                              5. Configure Validity & Limits
                            </span>
                            <StatusBadge status={currentWizardPlan.license_type} />
                          </div>

                          {currentWizardPlan.license_type === 'SUBSCRIPTION' ? (
                            <div>
                              <label className="block text-xs text-slate-600 mb-1">Subscription Duration (Days)</label>
                              <input
                                type="number"
                                min={1}
                                max={36500}
                                disabled={!currentWizardPlan.allow_custom_duration}
                                value={customDurationDays}
                                onChange={(e) => setCustomDurationDays(Number(e.target.value))}
                                className="w-48 border border-slate-300 rounded px-3 py-1.5 font-mono bg-white disabled:bg-slate-100"
                              />
                            </div>
                          ) : (
                            <p className="text-xs text-indigo-700 font-medium">
                              Perpetual Entitlement: License will be issued with expires_at = null (never expires).
                            </p>
                          )}

                          <div className="grid grid-cols-3 gap-3">
                            <div>
                              <label className="block text-xs text-slate-600 mb-1">Max Activated Devices</label>
                              <input
                                type="number"
                                min={-1}
                                disabled={!currentWizardPlan.allow_custom_limits}
                                value={customMaxDevices}
                                onChange={(e) => setCustomMaxDevices(Number(e.target.value))}
                                className="w-full border border-slate-300 rounded px-3 py-1.5 font-mono bg-white disabled:bg-slate-100"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-600 mb-1">Max Concurrent Insp.</label>
                              <input
                                type="number"
                                min={-1}
                                disabled={!currentWizardPlan.allow_custom_limits}
                                value={customMaxConcurrent}
                                onChange={(e) => setCustomMaxConcurrent(Number(e.target.value))}
                                className="w-full border border-slate-300 rounded px-3 py-1.5 font-mono bg-white disabled:bg-slate-100"
                              />
                            </div>
                            <div>
                              <label className="block text-xs text-slate-600 mb-1">Total Insp. Quota</label>
                              <input
                                type="number"
                                min={-1}
                                disabled={!currentWizardPlan.allow_custom_limits}
                                value={customTotalQuota}
                                onChange={(e) => setCustomTotalQuota(Number(e.target.value))}
                                className="w-full border border-slate-300 rounded px-3 py-1.5 font-mono bg-white disabled:bg-slate-100"
                              />
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Feature Entitlements Configuration */}
                      <div className="bg-slate-50 p-4 rounded border border-slate-200 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-semibold text-slate-700 uppercase">
                            6. Feature Entitlements
                          </span>
                          <label className="inline-flex items-center gap-1.5 text-xs text-blue-700 font-semibold cursor-pointer">
                            <input
                              type="checkbox"
                              checked={allFeaturesEnabled}
                              onChange={(e) => setAllFeaturesEnabled(e.target.checked)}
                              className="rounded text-blue-600"
                            />
                            Sử dụng tất cả feature trong phần mềm (Mặc định)
                          </label>
                        </div>
                        {allFeaturesEnabled ? (
                          <div className="text-xs text-emerald-800 bg-emerald-50 p-2.5 rounded border border-emerald-200">
                            ★ <strong>Tất cả tính năng trong phần mềm ({ALL_SOFTWARE_FEATURES.length - 1} modules)</strong> được cấp quyền sử dụng theo mặc định ở giai đoạn này.
                          </div>
                        ) : (
                          <div className="text-xs text-slate-600 bg-white p-2.5 rounded border border-slate-200">
                            Cấp quyền theo danh sách module của gói kế hoạch đã chọn ({currentWizardPlan?.features?.length || 0} tính năng).
                          </div>
                        )}
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                          Internal Administrative Notes (Not included in signed payload)
                        </label>
                        <input
                          type="text"
                          placeholder="Optional internal reference or PO number..."
                          value={issueNotes}
                          onChange={(e) => setIssueNotes(e.target.value)}
                          className="w-full border border-slate-300 rounded px-3 py-2"
                        />
                      </div>
                    </>
                  )}
                </div>
              )}

              {wizardStep === 2 && currentWizardCustomer && currentWizardPlan && currentWizardProduct && (
                <div className="space-y-4">
                  <div className="p-4 bg-blue-50 border border-blue-200 rounded-md text-xs text-blue-900">
                    Please review the license entitlements below. Upon confirmation, the server will construct the
                    canonical RFC 8785 JSON payload, sign it with the active Ed25519 private key, verify the signature,
                    and persist the immutable record.
                  </div>

                  <div className="grid grid-cols-2 gap-4 bg-slate-50 p-4 rounded border border-slate-200 text-xs">
                    <div>
                      <span className="text-slate-500 block">Customer</span>
                      <strong className="text-slate-900">
                        {currentWizardCustomer.company_name} ({currentWizardCustomer.customer_code})
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Product & Edition</span>
                      <strong className="text-slate-900 font-mono">
                        {currentWizardProduct.product_code} / {selectedEdition}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Plan</span>
                      <strong className="text-slate-900">
                        {currentWizardPlan.plan_name} ({currentWizardPlan.plan_code})
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block">License Type & Duration</span>
                      <strong className="text-slate-900">
                        {currentWizardPlan.license_type === 'PERPETUAL'
                          ? 'PERPETUAL (No Expiration)'
                          : `SUBSCRIPTION (${customDurationDays} days)`}
                      </strong>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Limits Snapshot</span>
                      <span className="font-mono">
                        Devices: {customMaxDevices} | Concurrent: {customMaxConcurrent} | Quota: {customTotalQuota}
                      </span>
                    </div>
                    <div>
                      <span className="text-slate-500 block">Feature Entitlements</span>
                      {allFeaturesEnabled || isAllFeatures(currentWizardPlan.features) ? (
                        <div className="mt-1">
                          <span className="inline-flex items-center px-2 py-0.5 bg-emerald-50 text-emerald-800 border border-emerald-300 rounded text-xs font-semibold">
                            ★ All Software Features (*)
                          </span>
                          <span className="text-slate-500 text-xs ml-2">Toàn bộ tính năng ({ALL_SOFTWARE_FEATURES.length - 1} modules)</span>
                        </div>
                      ) : (
                        <span className="font-mono text-xs">{currentWizardPlan.features.join(', ')}</span>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {wizardStep === 3 && issuedResult && (
                <div className="space-y-4 text-center py-4">
                  <CheckCircle2 className="w-12 h-12 text-emerald-600 mx-auto" />
                  <h4 className="text-base font-bold text-slate-900">
                    License {issuedResult.license_number} Signed & Verified!
                  </h4>
                  <p className="text-xs text-slate-600 max-w-md mx-auto">
                    The license payload was signed with key <code className="font-mono">{issuedResult.key_id}</code> and
                    cryptographically verified before persistence.
                  </p>
                  <div className="flex items-center justify-center gap-3 pt-2">
                    <button
                      onClick={() => downloadSignedLicenseFile(issuedResult.id, issuedResult.license_number)}
                      className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium shadow-sm"
                    >
                      <Download className="w-4 h-4" /> Download Signed Artifact (.novalic.json)
                    </button>
                    <button
                      onClick={() => {
                        setShowIssueWizard(false);
                        loadLicenseDetail(issuedResult.id);
                      }}
                      className="px-4 py-2 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-50"
                    >
                      Open License Details
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex justify-between">
              {wizardStep === 1 && (
                <>
                  <button
                    onClick={() => setShowIssueWizard(false)}
                    className="px-4 py-2 border border-slate-300 bg-white rounded text-sm text-slate-700"
                  >
                    Cancel
                  </button>
                  <button
                    disabled={!selectedCustomerId || !selectedPlanId}
                    onClick={() => setWizardStep(2)}
                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded text-sm font-medium disabled:opacity-50"
                  >
                    Review License Details &rarr;
                  </button>
                </>
              )}
              {wizardStep === 2 && (
                <>
                  <button
                    onClick={() => setWizardStep(1)}
                    className="px-4 py-2 border border-slate-300 bg-white rounded text-sm text-slate-700"
                  >
                    &larr; Back
                  </button>
                  <button
                    disabled={issuing}
                    onClick={handleConfirmIssue}
                    className="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-sm font-medium shadow-sm disabled:opacity-50"
                  >
                    {issuing ? 'Signing & Verifying...' : 'Confirm & Sign License'}
                  </button>
                </>
              )}
              {wizardStep === 3 && (
                <div className="w-full flex justify-end">
                  <button
                    onClick={() => setShowIssueWizard(false)}
                    className="px-4 py-2 bg-slate-800 text-white rounded text-sm font-medium"
                  >
                    Close
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Standalone Artifact Verifier Modal */}
      {showStandaloneVerifier && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-sm">
                Cryptographic License Artifact Verifier (Ed25519 + RFC 8785)
              </h3>
              <button onClick={() => setShowStandaloneVerifier(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleVerifyStandaloneJson} className="p-6 space-y-4 text-sm">
              <p className="text-xs text-slate-600">
                Paste the contents of any downloaded <code>.novalic.json</code> file below to test signature
                verification and tamper detection against the server&apos;s registered Ed25519 public keys.
              </p>
              <textarea
                rows={8}
                required
                placeholder='{"artifact_format": "NOVA-LICENSE-ENVELOPE-V1", "algorithm": "Ed25519", ...}'
                value={rawArtifactInput}
                onChange={(e) => setRawArtifactInput(e.target.value)}
                className="w-full border border-slate-300 rounded p-3 font-mono text-xs"
              />
              {standaloneVerifyRes && (
                <div
                  className={`p-3.5 rounded border text-xs ${
                    standaloneVerifyRes.valid
                      ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                      : 'bg-red-50 border-red-200 text-red-900'
                  }`}
                >
                  <div className="font-bold">
                    {standaloneVerifyRes.valid ? 'VALID SIGNATURE' : 'VERIFICATION FAILED'}
                  </div>
                  <div className="mt-1">{standaloneVerifyRes.reason}</div>
                  {standaloneVerifyRes.license_number && (
                    <div className="mt-1 font-mono">
                      License: {standaloneVerifyRes.license_number} | Key ID: {standaloneVerifyRes.key_id} | Status:{' '}
                      {standaloneVerifyRes.effective_status}
                    </div>
                  )}
                </div>
              )}
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowStandaloneVerifier(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-slate-700"
                >
                  Close
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium"
                >
                  Verify Signature
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
