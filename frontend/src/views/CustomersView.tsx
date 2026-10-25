import React, { useEffect, useState } from 'react';
import {
  Search,
  Plus,
  Edit3,
  PowerOff,
  Power,
  Eye,
  X,
  RefreshCw,
} from 'lucide-react';
import { apiRequest, Customer } from '../api';
import { StatusBadge, formatDateTime } from '../components/StatusBadge';

interface CustomersViewProps {
  openCreateModalSignal?: number;
  canWrite: boolean;
}

export function CustomersView({ openCreateModalSignal, canWrite }: CustomersViewProps) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [search, setSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [showFormModal, setShowFormModal] = useState<boolean>(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [viewingCustomer, setViewingCustomer] = useState<Customer | null>(null);
  const [deactivatingCustomer, setDeactivatingCustomer] = useState<Customer | null>(null);
  const [deactivateReason, setDeactivateReason] = useState<string>('');

  // Form state
  const [customerCode, setCustomerCode] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [contactPerson, setContactPerson] = useState('');
  const [contactEmail, setContactEmail] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [countryRegion, setCountryRegion] = useState('');
  const [address, setAddress] = useState('');
  const [notes, setNotes] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const loadCustomers = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: '15',
      });
      if (search.trim()) params.set('search', search.trim());
      if (statusFilter) params.set('status', statusFilter);

      const res = await apiRequest<{ items: Customer[]; total: number }>(`/api/customers?${params.toString()}`);
      setCustomers(res.items);
      setTotal(res.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load customers');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCustomers();
  }, [page, statusFilter]);

  useEffect(() => {
    if (openCreateModalSignal && openCreateModalSignal > 0 && canWrite) {
      openCreateModal();
    }
  }, [openCreateModalSignal]);

  const openCreateModal = () => {
    setEditingCustomer(null);
    setCustomerCode('');
    setCompanyName('');
    setContactPerson('');
    setContactEmail('');
    setContactPhone('');
    setCountryRegion('');
    setAddress('');
    setNotes('');
    setFormError(null);
    setShowFormModal(true);
  };

  const openEditModal = (c: Customer) => {
    setEditingCustomer(c);
    setCustomerCode(c.customer_code);
    setCompanyName(c.company_name);
    setContactPerson(c.contact_person);
    setContactEmail(c.contact_email);
    setContactPhone(c.contact_phone || '');
    setCountryRegion(c.country_region || '');
    setAddress(c.address || '');
    setNotes(c.notes || '');
    setFormError(null);
    setShowFormModal(true);
  };

  const handleSaveCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      if (editingCustomer) {
        await apiRequest(`/api/customers/${editingCustomer.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            company_name: companyName,
            contact_person: contactPerson,
            contact_email: contactEmail,
            contact_phone: contactPhone || null,
            country_region: countryRegion || null,
            address: address || null,
            notes: notes || null,
          }),
        });
      } else {
        await apiRequest('/api/customers', {
          method: 'POST',
          body: JSON.stringify({
            customer_code: customerCode.toUpperCase().trim(),
            company_name: companyName,
            contact_person: contactPerson,
            contact_email: contactEmail,
            contact_phone: contactPhone || null,
            country_region: countryRegion || null,
            address: address || null,
            notes: notes || null,
          }),
        });
      }
      setShowFormModal(false);
      await loadCustomers();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save customer');
    } finally {
      setSubmitting(false);
    }
  };

  const handleConfirmDeactivate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!deactivatingCustomer) return;
    setSubmitting(true);
    setFormError(null);
    try {
      await apiRequest(`/api/customers/${deactivatingCustomer.id}/deactivate`, {
        method: 'POST',
        body: JSON.stringify({ reason: deactivateReason }),
      });
      setDeactivatingCustomer(null);
      setDeactivateReason('');
      await loadCustomers();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to deactivate customer');
    } finally {
      setSubmitting(false);
    }
  };

  const handleReactivate = async (c: Customer) => {
    try {
      await apiRequest(`/api/customers/${c.id}/activate`, { method: 'POST' });
      await loadCustomers();
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to reactivate customer');
    }
  };

  return (
    <div className="space-y-5">
      {/* Header & Filter Bar */}
      <div className="bg-white border border-slate-200 rounded-lg p-4 flex flex-wrap items-center justify-between gap-4 shadow-sm">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            loadCustomers();
          }}
          className="flex flex-wrap items-center gap-3 flex-1"
        >
          <div className="relative w-72">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search code, company, email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
            <option value="INACTIVE">INACTIVE</option>
          </select>
          <button
            type="submit"
            className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-md text-sm font-medium"
          >
            Search
          </button>
        </form>

        {canWrite && (
          <button
            onClick={openCreateModal}
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium shadow-sm"
          >
            <Plus className="w-4 h-4" />
            Create Customer
          </button>
        )}
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      {/* Customer Table */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 flex items-center justify-center text-slate-500 text-sm">
            <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading customers...
          </div>
        ) : customers.length === 0 ? (
          <div className="p-10 text-center text-slate-500 text-sm">
            No customers match the current search/filter criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase">
                  <th className="py-3 px-4">Customer Code</th>
                  <th className="py-3 px-4">Company Name</th>
                  <th className="py-3 px-4">Contact Person</th>
                  <th className="py-3 px-4">Contact Email</th>
                  <th className="py-3 px-4">Issued Licenses</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Created Date</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {customers.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50">
                    <td className="py-3 px-4 font-mono text-xs font-semibold text-blue-700">{c.customer_code}</td>
                    <td className="py-3 px-4 font-medium text-slate-900">{c.company_name}</td>
                    <td className="py-3 px-4 text-slate-700">{c.contact_person}</td>
                    <td className="py-3 px-4 text-slate-600">{c.contact_email}</td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-100 text-slate-800 font-mono text-xs font-medium">
                        {c.issued_licenses_count}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="py-3 px-4 text-xs text-slate-500">{formatDateTime(c.created_at)}</td>
                    <td className="py-3 px-4 text-right space-x-2">
                      <button
                        onClick={() => setViewingCustomer(c)}
                        title="View Details"
                        className="p-1.5 text-slate-500 hover:text-blue-600 rounded hover:bg-slate-100"
                      >
                        <Eye className="w-4 h-4 inline" />
                      </button>
                      {canWrite && (
                        <>
                          <button
                            onClick={() => openEditModal(c)}
                            title="Edit Customer"
                            className="p-1.5 text-slate-500 hover:text-blue-600 rounded hover:bg-slate-100"
                          >
                            <Edit3 className="w-4 h-4 inline" />
                          </button>
                          {c.status === 'ACTIVE' ? (
                            <button
                              onClick={() => {
                                setDeactivatingCustomer(c);
                                setDeactivateReason('');
                                setFormError(null);
                              }}
                              title="Deactivate Customer"
                              className="p-1.5 text-slate-500 hover:text-amber-600 rounded hover:bg-slate-100"
                            >
                              <PowerOff className="w-4 h-4 inline" />
                            </button>
                          ) : (
                            <button
                              onClick={() => handleReactivate(c)}
                              title="Reactivate Customer"
                              className="p-1.5 text-slate-500 hover:text-emerald-600 rounded hover:bg-slate-100"
                            >
                              <Power className="w-4 h-4 inline" />
                            </button>
                          )}
                        </>
                      )}
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
            Showing {customers.length} of {total} customer records
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

      {/* Create / Edit Customer Modal */}
      {showFormModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">
                {editingCustomer ? `Edit Customer (${editingCustomer.customer_code})` : 'Create New Customer'}
              </h3>
              <button onClick={() => setShowFormModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSaveCustomer} className="p-6 space-y-4 text-sm">
              {formError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">{formError}</div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Customer Code *
                  </label>
                  <input
                    type="text"
                    required
                    disabled={!!editingCustomer}
                    placeholder="e.g. CUST-ACME-01"
                    value={customerCode}
                    onChange={(e) => setCustomerCode(e.target.value.toUpperCase())}
                    className="w-full border border-slate-300 rounded px-3 py-2 font-mono disabled:bg-slate-100"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Country / Region
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Vietnam / APAC"
                    value={countryRegion}
                    onChange={(e) => setCountryRegion(e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Legal / Company Name *
                </label>
                <input
                  type="text"
                  required
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Contact Person *
                  </label>
                  <input
                    type="text"
                    required
                    value={contactPerson}
                    onChange={(e) => setContactPerson(e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Contact Email *
                  </label>
                  <input
                    type="email"
                    required
                    value={contactEmail}
                    onChange={(e) => setContactEmail(e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Contact Phone
                  </label>
                  <input
                    type="text"
                    value={contactPhone}
                    onChange={(e) => setContactPhone(e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                    Address
                  </label>
                  <input
                    type="text"
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    className="w-full border border-slate-300 rounded px-3 py-2"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Administrative Notes
                </label>
                <textarea
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3 border-t border-slate-200">
                <button
                  type="button"
                  onClick={() => setShowFormModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-slate-700 hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium disabled:opacity-50"
                >
                  {submitting ? 'Saving...' : editingCustomer ? 'Save Changes' : 'Create Customer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Deactivate Confirmation Modal */}
      {deactivatingCustomer && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">Confirm Customer Deactivation</h3>
              <button onClick={() => setDeactivatingCustomer(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleConfirmDeactivate} className="p-6 space-y-4 text-sm">
              {formError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">{formError}</div>
              )}
              <p className="text-slate-600">
                You are deactivating customer{' '}
                <strong className="text-slate-900">
                  {deactivatingCustomer.company_name} ({deactivatingCustomer.customer_code})
                </strong>
                . Historical issued licenses will be preserved untouched, but new licenses cannot be issued while the
                customer is INACTIVE.
              </p>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Deactivation Reason *
                </label>
                <textarea
                  required
                  minLength={3}
                  rows={3}
                  placeholder="Provide an auditable reason for deactivating this customer..."
                  value={deactivateReason}
                  onChange={(e) => setDeactivateReason(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setDeactivatingCustomer(null)}
                  className="px-4 py-2 border border-slate-300 rounded text-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded font-medium"
                >
                  {submitting ? 'Deactivating...' : 'Confirm Deactivate'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* View Customer Details Modal */}
      {viewingCustomer && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">Customer Record Details</h3>
              <button onClick={() => setViewingCustomer(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-xs text-slate-500 block">Customer Code</span>
                  <span className="font-mono font-semibold text-blue-700">{viewingCustomer.customer_code}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Status</span>
                  <StatusBadge status={viewingCustomer.status} />
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Company Name</span>
                  <span className="font-medium text-slate-900">{viewingCustomer.company_name}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Issued Licenses</span>
                  <span className="font-mono font-semibold">{viewingCustomer.issued_licenses_count}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Contact Person</span>
                  <span>{viewingCustomer.contact_person}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Contact Email</span>
                  <span>{viewingCustomer.contact_email}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Phone</span>
                  <span>{viewingCustomer.contact_phone || '—'}</span>
                </div>
                <div>
                  <span className="text-xs text-slate-500 block">Country / Region</span>
                  <span>{viewingCustomer.country_region || '—'}</span>
                </div>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Address</span>
                <span>{viewingCustomer.address || '—'}</span>
              </div>
              <div>
                <span className="text-xs text-slate-500 block">Notes</span>
                <p className="text-slate-700 bg-slate-50 p-2.5 rounded border border-slate-200 mt-1">
                  {viewingCustomer.notes || 'No notes recorded.'}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-200 text-xs text-slate-500">
                <div>Created: {formatDateTime(viewingCustomer.created_at)}</div>
                <div>Updated: {formatDateTime(viewingCustomer.updated_at)}</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
