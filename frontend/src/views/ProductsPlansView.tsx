import React, { useEffect, useState } from 'react';
import { Plus, Edit3, Package, Layers, X, RefreshCw } from 'lucide-react';
import { apiRequest, LicensePlan, Product } from '../api';
import { StatusBadge, formatLimitValue } from '../components/StatusBadge';

interface ProductsPlansViewProps {
  canWrite: boolean;
}

export function ProductsPlansView({ canWrite }: ProductsPlansViewProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [plans, setPlans] = useState<LicensePlan[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [showProductModal, setShowProductModal] = useState<boolean>(false);
  const [showPlanModal, setShowPlanModal] = useState<boolean>(false);
  const [editingPlan, setEditingPlan] = useState<LicensePlan | null>(null);

  // Product Form
  const [productCode, setProductCode] = useState('');
  const [productName, setProductName] = useState('');
  const [productDesc, setProductDesc] = useState('');

  // Plan Form
  const [planCode, setPlanCode] = useState('');
  const [planName, setPlanName] = useState('');
  const [selectedProductId, setSelectedProductId] = useState('');
  const [edition, setEdition] = useState<'developer' | 'production'>('production');
  const [licenseType, setLicenseType] = useState<'SUBSCRIPTION' | 'PERPETUAL'>('SUBSCRIPTION');
  const [defaultDurationDays, setDefaultDurationDays] = useState<number>(365);
  const [featuresText, setFeaturesText] = useState<string>(
    'high_speed_acquisition, multi_camera_sync, plc_modbus_profinet, deep_learning_ocr, surface_defect_detection'
  );
  const [maxDevices, setMaxDevices] = useState<number>(1);
  const [maxConcurrentInspections, setMaxConcurrentInspections] = useState<number>(4);
  const [totalInspectionQuota, setTotalInspectionQuota] = useState<number>(-1);
  const [allowCustomDuration, setAllowCustomDuration] = useState<boolean>(true);
  const [allowCustomLimits, setAllowCustomLimits] = useState<boolean>(true);
  const [planStatus, setPlanStatus] = useState<'ACTIVE' | 'INACTIVE'>('ACTIVE');
  const [planDesc, setPlanDesc] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const loadAll = async () => {
    setLoading(true);
    setError(null);
    try {
      const [prods, plns] = await Promise.all([
        apiRequest<Product[]>('/api/products'),
        apiRequest<LicensePlan[]>('/api/license-plans'),
      ]);
      setProducts(prods);
      setPlans(plns);
      if (prods.length > 0 && !selectedProductId) {
        setSelectedProductId(prods[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load products and plans');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const openCreatePlanModal = () => {
    setEditingPlan(null);
    setPlanCode('');
    setPlanName('');
    setSelectedProductId(products[0]?.id || '');
    setEdition('production');
    setLicenseType('SUBSCRIPTION');
    setDefaultDurationDays(365);
    setFeaturesText(
      'high_speed_acquisition, multi_camera_sync, plc_modbus_profinet, deep_learning_ocr, surface_defect_detection'
    );
    setMaxDevices(1);
    setMaxConcurrentInspections(4);
    setTotalInspectionQuota(-1);
    setAllowCustomDuration(true);
    setAllowCustomLimits(true);
    setPlanStatus('ACTIVE');
    setPlanDesc('');
    setFormError(null);
    setShowPlanModal(true);
  };

  const openEditPlanModal = (p: LicensePlan) => {
    setEditingPlan(p);
    setPlanCode(p.plan_code);
    setPlanName(p.plan_name);
    setSelectedProductId(p.product_id);
    setEdition(p.edition);
    setLicenseType(p.license_type);
    setDefaultDurationDays(p.default_duration_days || 365);
    setFeaturesText((p.features || []).join(', '));
    setMaxDevices(p.max_devices);
    setMaxConcurrentInspections(p.max_concurrent_inspections);
    setTotalInspectionQuota(p.total_inspection_quota);
    setAllowCustomDuration(p.allow_custom_duration);
    setAllowCustomLimits(p.allow_custom_limits);
    setPlanStatus(p.status);
    setPlanDesc(p.description || '');
    setFormError(null);
    setShowPlanModal(true);
  };

  const handleSaveProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      await apiRequest('/api/products', {
        method: 'POST',
        body: JSON.stringify({
          product_code: productCode.toUpperCase().trim(),
          product_name: productName,
          description: productDesc || null,
          supported_editions: ['developer', 'production'],
        }),
      });
      setShowProductModal(false);
      await loadAll();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create product');
    } finally {
      setSubmitting(false);
    }
  };

  const handleSavePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    const featuresList = featuresText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      if (editingPlan) {
        await apiRequest(`/api/license-plans/${editingPlan.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            plan_name: planName,
            description: planDesc || null,
            default_duration_days: licenseType === 'SUBSCRIPTION' ? Number(defaultDurationDays) : null,
            features: featuresList,
            max_devices: Number(maxDevices),
            max_concurrent_inspections: Number(maxConcurrentInspections),
            total_inspection_quota: Number(totalInspectionQuota),
            allow_custom_duration: allowCustomDuration,
            allow_custom_limits: allowCustomLimits,
            status: planStatus,
          }),
        });
      } else {
        await apiRequest('/api/license-plans', {
          method: 'POST',
          body: JSON.stringify({
            plan_code: planCode.toUpperCase().trim(),
            plan_name: planName,
            product_id: selectedProductId,
            edition,
            description: planDesc || null,
            license_type: licenseType,
            default_duration_days: licenseType === 'SUBSCRIPTION' ? Number(defaultDurationDays) : null,
            features: featuresList,
            max_devices: Number(maxDevices),
            max_concurrent_inspections: Number(maxConcurrentInspections),
            total_inspection_quota: Number(totalInspectionQuota),
            allow_custom_duration: allowCustomDuration,
            allow_custom_limits: allowCustomLimits,
            status: planStatus,
          }),
        });
      }
      setShowPlanModal(false);
      await loadAll();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save license plan');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center text-slate-500 text-sm">
        <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading products and commercial plans...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      {/* Registered Products Section */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Package className="w-5 h-5 text-blue-600" />
            <div>
              <h3 className="font-semibold text-slate-900 text-sm">Registered Products</h3>
              <p className="text-xs text-slate-500">
                Core signing mechanism supports multiple products without schema changes
              </p>
            </div>
          </div>
          {canWrite && (
            <button
              onClick={() => {
                setProductCode('');
                setProductName('');
                setProductDesc('');
                setFormError(null);
                setShowProductModal(true);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 hover:bg-slate-50 rounded-md text-xs font-medium text-slate-700"
            >
              <Plus className="w-3.5 h-3.5" /> Add Product
            </button>
          )}
        </div>
        <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {products.map((prod) => (
            <div key={prod.id} className="border border-slate-200 rounded-md p-4 bg-slate-50/50">
              <div className="flex items-center justify-between">
                <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                  {prod.product_code}
                </span>
                <StatusBadge status={prod.status} />
              </div>
              <h4 className="font-semibold text-slate-900 mt-2 text-sm">{prod.product_name}</h4>
              <p className="text-xs text-slate-600 mt-1">{prod.description || 'No description'}</p>
              <div className="mt-3 flex items-center gap-1.5 flex-wrap">
                <span className="text-xs text-slate-500">Editions:</span>
                {prod.supported_editions.map((ed) => (
                  <span
                    key={ed}
                    className="text-xs font-mono px-2 py-0.5 bg-white border border-slate-200 rounded text-slate-700"
                  >
                    {ed}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Commercial License Plans Section */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-blue-600" />
            <div>
              <h3 className="font-semibold text-slate-900 text-sm">Commercial License Plans</h3>
              <p className="text-xs text-slate-500">
                Editing a plan only affects future licenses. Previously issued licenses retain their immutable snapshot.
              </p>
            </div>
          </div>
          {canWrite && (
            <button
              onClick={openCreatePlanModal}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium shadow-sm"
            >
              <Plus className="w-4 h-4" /> Create License Plan
            </button>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase">
                <th className="py-3 px-4">Plan Code & Name</th>
                <th className="py-3 px-4">Product / Edition</th>
                <th className="py-3 px-4">Model & Duration</th>
                <th className="py-3 px-4">Limits (Dev / Conc / Quota)</th>
                <th className="py-3 px-4">Feature Entitlements</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {plans.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50">
                  <td className="py-3 px-4">
                    <div className="font-mono text-xs font-semibold text-blue-700">{p.plan_code}</div>
                    <div className="font-medium text-slate-900">{p.plan_name}</div>
                  </td>
                  <td className="py-3 px-4">
                    <div className="text-xs font-semibold text-slate-700">{p.product_code || 'NOVA-MVP'}</div>
                    <span className="inline-block mt-0.5 font-mono text-xs px-2 py-0.5 bg-slate-100 rounded text-slate-800">
                      {p.edition}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge status={p.license_type} />
                    <div className="text-xs text-slate-500 mt-1">
                      {p.license_type === 'PERPETUAL'
                        ? 'No expiration'
                        : `${p.default_duration_days} days default`}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-xs font-mono text-slate-700 space-y-0.5">
                    <div>Devices: {formatLimitValue(p.max_devices)}</div>
                    <div>Inspections: {formatLimitValue(p.max_concurrent_inspections)}</div>
                    <div>Quota: {formatLimitValue(p.total_inspection_quota)}</div>
                  </td>
                  <td className="py-3 px-4 max-w-xs">
                    <div className="flex flex-wrap gap-1">
                      {p.features.map((f) => (
                        <span
                          key={f}
                          className="px-2 py-0.5 bg-blue-50 text-blue-800 border border-blue-200 rounded text-xs font-mono"
                        >
                          {f}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge status={p.status} />
                  </td>
                  <td className="py-3 px-4 text-right">
                    {canWrite && (
                      <button
                        onClick={() => openEditPlanModal(p)}
                        className="p-1.5 text-slate-500 hover:text-blue-600 rounded hover:bg-slate-100"
                        title="Edit License Plan"
                      >
                        <Edit3 className="w-4 h-4 inline" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Product Modal */}
      {showProductModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">Register New Product</h3>
              <button onClick={() => setShowProductModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSaveProduct} className="p-6 space-y-4 text-sm">
              {formError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">{formError}</div>
              )}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Product Code *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. NOVA-MVP"
                  value={productCode}
                  onChange={(e) => setProductCode(e.target.value.toUpperCase())}
                  className="w-full border border-slate-300 rounded px-3 py-2 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Product Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. NOVA Machine Vision Platform"
                  value={productName}
                  onChange={(e) => setProductName(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Description</label>
                <textarea
                  rows={2}
                  value={productDesc}
                  onChange={(e) => setProductDesc(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowProductModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium"
                >
                  Register Product
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create / Edit Plan Modal */}
      {showPlanModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full overflow-hidden max-h-[92vh] flex flex-col">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">
                {editingPlan ? `Edit License Plan (${editingPlan.plan_code})` : 'Create Commercial License Plan'}
              </h3>
              <button onClick={() => setShowPlanModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSavePlan} className="p-6 space-y-4 text-sm overflow-y-auto">
              {formError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">{formError}</div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Plan Code *</label>
                  <input
                    type="text"
                    required
                    disabled={!!editingPlan}
                    placeholder="e.g. NOVA-PROD-SUB-1Y"
                    value={planCode}
                    onChange={(e) => setPlanCode(e.target.value.toUpperCase())}
                    className="w-full border border-slate-300 rounded px-3 py-2 font-mono disabled:bg-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Plan Name *</label>
                  <input
                    type="text"
                    required
                    value={planName}
                    onChange={(e) => setPlanName(e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Product *</label>
                  <select
                    disabled={!!editingPlan}
                    value={selectedProductId}
                    onChange={(e) => setSelectedProductId(e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2 bg-white disabled:bg-slate-100"
                  >
                    {products.map((pr) => (
                      <option key={pr.id} value={pr.id}>
                        {pr.product_code}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Edition *</label>
                  <select
                    disabled={!!editingPlan}
                    value={edition}
                    onChange={(e) => setEdition(e.target.value as 'developer' | 'production')}
                    className="w-full border border-slate-300 rounded px-3 py-2 bg-white disabled:bg-slate-100"
                  >
                    <option value="production">production</option>
                    <option value="developer">developer</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Licensing Model *</label>
                  <select
                    disabled={!!editingPlan}
                    value={licenseType}
                    onChange={(e) => setLicenseType(e.target.value as 'SUBSCRIPTION' | 'PERPETUAL')}
                    className="w-full border border-slate-300 rounded px-3 py-2 bg-white disabled:bg-slate-100"
                  >
                    <option value="SUBSCRIPTION">SUBSCRIPTION</option>
                    <option value="PERPETUAL">PERPETUAL</option>
                  </select>
                </div>
              </div>

              {licenseType === 'SUBSCRIPTION' && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Default Subscription Duration (Days) *
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={36500}
                    required
                    value={defaultDurationDays}
                    onChange={(e) => setDefaultDurationDays(Number(e.target.value))}
                    className="w-48 border border-slate-300 rounded px-3 py-2 font-mono"
                  />
                </div>
              )}

              <div className="bg-slate-50 p-3.5 rounded border border-slate-200 space-y-3">
                <div className="text-xs font-semibold text-slate-700 uppercase">
                  Quantitative Entitlement Limits (-1 = Unlimited, 0 = Disabled/Unavailable, &gt;0 = Exact Cap)
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-xs text-slate-600 mb-1">Max Activated Devices</label>
                    <input
                      type="number"
                      min={-1}
                      required
                      value={maxDevices}
                      onChange={(e) => setMaxDevices(Number(e.target.value))}
                      className="w-full border border-slate-300 rounded px-3 py-1.5 font-mono bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-600 mb-1">Max Concurrent Inspections</label>
                    <input
                      type="number"
                      min={-1}
                      required
                      value={maxConcurrentInspections}
                      onChange={(e) => setMaxConcurrentInspections(Number(e.target.value))}
                      className="w-full border border-slate-300 rounded px-3 py-1.5 font-mono bg-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-600 mb-1">Total Inspection Quota</label>
                    <input
                      type="number"
                      min={-1}
                      required
                      value={totalInspectionQuota}
                      onChange={(e) => setTotalInspectionQuota(Number(e.target.value))}
                      className="w-full border border-slate-300 rounded px-3 py-1.5 font-mono bg-white"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Enabled Features (comma-separated identifiers)
                </label>
                <input
                  type="text"
                  value={featuresText}
                  onChange={(e) => setFeaturesText(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 font-mono text-xs"
                />
              </div>

              <div className="grid grid-cols-3 gap-4 items-center">
                <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                  <input
                    type="checkbox"
                    checked={allowCustomDuration}
                    onChange={(e) => setAllowCustomDuration(e.target.checked)}
                  />
                  Allow duration override on issue
                </label>
                <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                  <input
                    type="checkbox"
                    checked={allowCustomLimits}
                    onChange={(e) => setAllowCustomLimits(e.target.checked)}
                  />
                  Allow limit override on issue
                </label>
                <div>
                  <label className="text-xs font-semibold text-slate-700 mr-2">Status:</label>
                  <select
                    value={planStatus}
                    onChange={(e) => setPlanStatus(e.target.value as 'ACTIVE' | 'INACTIVE')}
                    className="border border-slate-300 rounded px-2.5 py-1 text-xs bg-white"
                  >
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="INACTIVE">INACTIVE</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setShowPlanModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium"
                >
                  {submitting ? 'Saving...' : editingPlan ? 'Save Plan Changes' : 'Create Plan'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
