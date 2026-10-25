import React, { useEffect, useState } from 'react';
import { KeyRound, ShieldCheck, ShieldAlert, UserPlus, Plus, X, RefreshCw } from 'lucide-react';
import { apiRequest, SigningKeyItem, User } from '../api';
import { StatusBadge, formatDateTime } from '../components/StatusBadge';

interface SystemSettingsViewProps {
  currentUser: User;
}

interface SigningEngineStatus {
  signing_engine_ready: boolean;
  configured_key_id: string | null;
  private_key_loaded: boolean;
  active_db_key_id: string | null;
  active_db_key_fingerprint: string | null;
  status_message: string;
}

export function SystemSettingsView({ currentUser }: SystemSettingsViewProps) {
  const [engineStatus, setEngineStatus] = useState<SigningEngineStatus | null>(null);
  const [signingKeys, setSigningKeys] = useState<SigningKeyItem[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Register Public Key Modal
  const [showKeyModal, setShowKeyModal] = useState<boolean>(false);
  const [newKeyId, setNewKeyId] = useState<string>('');
  const [newPubKeyPem, setNewPubKeyPem] = useState<string>('');
  const [newKeyDesc, setNewKeyDesc] = useState<string>('');
  const [setActiveKey, setSetActiveKey] = useState<boolean>(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Create Admin User Modal
  const [showUserModal, setShowUserModal] = useState<boolean>(false);
  const [newUsername, setNewUsername] = useState<string>('');
  const [newEmail, setNewEmail] = useState<string>('');
  const [newFullName, setNewFullName] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [newRole, setNewRole] = useState<'SUPER_ADMIN' | 'LICENSE_ADMIN' | 'AUDITOR'>('LICENSE_ADMIN');

  const isSuperAdmin = currentUser.role === 'SUPER_ADMIN';

  const loadSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const [statusRes, keysRes, usersRes] = await Promise.all([
        apiRequest<SigningEngineStatus>('/api/signing-keys/status'),
        apiRequest<SigningKeyItem[]>('/api/signing-keys'),
        apiRequest<User[]>('/api/auth/users'),
      ]);
      setEngineStatus(statusRes);
      setSigningKeys(keysRes);
      setUsers(usersRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load system settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleRegisterKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);
    try {
      await apiRequest('/api/signing-keys', {
        method: 'POST',
        body: JSON.stringify({
          key_id: newKeyId.trim(),
          public_key_pem: newPubKeyPem.trim(),
          description: newKeyDesc || null,
          set_active: setActiveKey,
        }),
      });
      setShowKeyModal(false);
      await loadSettings();
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Failed to register public key');
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalError(null);
    try {
      await apiRequest('/api/auth/users', {
        method: 'POST',
        body: JSON.stringify({
          username: newUsername.trim(),
          email: newEmail.trim(),
          full_name: newFullName.trim(),
          password: newPassword,
          role: newRole,
        }),
      });
      setShowUserModal(false);
      await loadSettings();
    } catch (err) {
      setModalError(err instanceof Error ? err.message : 'Failed to create user');
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center text-slate-500 text-sm">
        <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading cryptographic key boundary & user accounts...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>
      )}

      {/* Active Signing Authority Status */}
      {engineStatus && (
        <div className="bg-white border border-slate-200 rounded-lg p-5 shadow-sm">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              {engineStatus.signing_engine_ready ? (
                <ShieldCheck className="w-8 h-8 text-emerald-600" />
              ) : (
                <ShieldAlert className="w-8 h-8 text-red-600" />
              )}
              <div>
                <h3 className="font-semibold text-slate-900">Ed25519 Cryptographic Signing Boundary</h3>
                <p className="text-xs text-slate-600 mt-0.5">{engineStatus.status_message}</p>
              </div>
            </div>
            <StatusBadge status={engineStatus.signing_engine_ready ? 'ACTIVE' : 'FAILURE'} />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4 pt-4 border-t border-slate-200 text-xs">
            <div>
              <span className="text-slate-500 block">Configured Server Key ID</span>
              <span className="font-mono font-semibold text-slate-900">
                {engineStatus.configured_key_id || 'Not Configured'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">Private Key Loaded in Server Memory</span>
              <span className="font-semibold text-slate-900">
                {engineStatus.private_key_loaded ? 'Yes (Protected External File/Secret)' : 'No'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">Active Public Key SHA-256 Fingerprint</span>
              <span className="font-mono text-[11px] text-slate-700 break-all">
                {engineStatus.active_db_key_fingerprint || '—'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Registered Verification Public Keys */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <KeyRound className="w-5 h-5 text-blue-600" />
            <div>
              <h3 className="font-semibold text-slate-900 text-sm">
                Registered Verification Public Keys & Key Rotation
              </h3>
              <p className="text-xs text-slate-500">
                Only public keys are stored in the database. Retired keys remain available to verify historical licenses.
              </p>
            </div>
          </div>
          {isSuperAdmin && (
            <button
              onClick={() => {
                setNewKeyId('');
                setNewPubKeyPem('');
                setNewKeyDesc('');
                setSetActiveKey(false);
                setModalError(null);
                setShowKeyModal(true);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-medium"
            >
              <Plus className="w-3.5 h-3.5" /> Register / Rotate Public Key
            </button>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase">
                <th className="py-3 px-4">Key ID</th>
                <th className="py-3 px-4">Algorithm</th>
                <th className="py-3 px-4">SHA-256 Fingerprint</th>
                <th className="py-3 px-4">Public Key PEM</th>
                <th className="py-3 px-4">Signing Role</th>
                <th className="py-3 px-4">Created / Rotated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {signingKeys.map((k) => (
                <tr key={k.id} className="hover:bg-slate-50">
                  <td className="py-3 px-4 font-mono text-xs font-bold text-blue-700">{k.key_id}</td>
                  <td className="py-3 px-4 font-mono text-xs">{k.algorithm}</td>
                  <td className="py-3 px-4 font-mono text-[11px] text-slate-600 max-w-xs break-all">
                    {k.fingerprint_sha256}
                  </td>
                  <td className="py-3 px-4">
                    <pre className="font-mono text-[10px] bg-slate-50 p-2 rounded border border-slate-200 max-w-xs overflow-x-auto">
                      {k.public_key_pem}
                    </pre>
                  </td>
                  <td className="py-3 px-4">
                    <StatusBadge status={k.is_active ? 'ACTIVE' : k.status} />
                  </td>
                  <td className="py-3 px-4 text-xs text-slate-500">
                    <div>Created: {formatDateTime(k.created_at)}</div>
                    {k.rotated_at && <div>Rotated: {formatDateTime(k.rotated_at)}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Administrative User Accounts */}
      <div className="bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-slate-900 text-sm">Administrative Accounts & RBAC Roles</h3>
            <p className="text-xs text-slate-500">
              Roles: SUPER_ADMIN (full control + key rotation), LICENSE_ADMIN (customers, plans, licenses), AUDITOR
              (read-only)
            </p>
          </div>
          {isSuperAdmin && (
            <button
              onClick={() => {
                setNewUsername('');
                setNewEmail('');
                setNewFullName('');
                setNewPassword('');
                setNewRole('LICENSE_ADMIN');
                setModalError(null);
                setShowUserModal(true);
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 rounded-md text-xs font-medium"
            >
              <UserPlus className="w-3.5 h-3.5" /> Add Administrator
            </button>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500 uppercase">
                <th className="py-3 px-4">Username</th>
                <th className="py-3 px-4">Full Name</th>
                <th className="py-3 px-4">Email</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Created At</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-50">
                  <td className="py-2.5 px-4 font-mono text-xs font-semibold text-slate-900">{u.username}</td>
                  <td className="py-2.5 px-4 text-slate-800">{u.full_name}</td>
                  <td className="py-2.5 px-4 text-slate-600 text-xs">{u.email}</td>
                  <td className="py-2.5 px-4 font-mono text-xs font-semibold text-blue-700">{u.role}</td>
                  <td className="py-2.5 px-4">
                    <StatusBadge status={u.is_active ? 'ACTIVE' : 'INACTIVE'} />
                  </td>
                  <td className="py-2.5 px-4 text-xs text-slate-500">{formatDateTime(u.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Register Key Modal */}
      {showKeyModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-lg w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-sm">Register / Rotate Ed25519 Public Key</h3>
              <button onClick={() => setShowKeyModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleRegisterKey} className="p-6 space-y-4 text-sm">
              {modalError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">{modalError}</div>
              )}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Key ID *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. nova-key-2027-01"
                  value={newKeyId}
                  onChange={(e) => setNewKeyId(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Ed25519 Public Key (PEM) *
                </label>
                <textarea
                  rows={4}
                  required
                  placeholder="-----BEGIN PUBLIC KEY-----..."
                  value={newPubKeyPem}
                  onChange={(e) => setNewPubKeyPem(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 font-mono text-xs"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Description</label>
                <input
                  type="text"
                  value={newKeyDesc}
                  onChange={(e) => setNewKeyDesc(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2"
                />
              </div>
              <label className="inline-flex items-center gap-2 text-xs text-slate-700">
                <input
                  type="checkbox"
                  checked={setActiveKey}
                  onChange={(e) => setSetActiveKey(e.target.checked)}
                />
                Set as active signing key (retires previous key to RETIRED verification-only status)
              </label>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowKeyModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-slate-700"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded font-medium">
                  Register Public Key
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add User Modal */}
      {showUserModal && (
        <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-sm">Create Administrative User</h3>
              <button onClick={() => setShowUserModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="p-6 space-y-4 text-sm">
              {modalError && (
                <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">{modalError}</div>
              )}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Username *</label>
                <input
                  type="text"
                  required
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Full Name *</label>
                <input
                  type="text"
                  required
                  value={newFullName}
                  onChange={(e) => setNewFullName(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Email *</label>
                <input
                  type="email"
                  required
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Password (min 8 chars) *
                </label>
                <input
                  type="password"
                  minLength={8}
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full border border-slate-300 rounded px-3 py-2"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Role *</label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value as 'SUPER_ADMIN' | 'LICENSE_ADMIN' | 'AUDITOR')}
                  className="w-full border border-slate-300 rounded px-3 py-2 bg-white"
                >
                  <option value="LICENSE_ADMIN">LICENSE_ADMIN</option>
                  <option value="AUDITOR">AUDITOR (Read-Only)</option>
                  <option value="SUPER_ADMIN">SUPER_ADMIN</option>
                </select>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowUserModal(false)}
                  className="px-4 py-2 border border-slate-300 rounded text-slate-700"
                >
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded font-medium">
                  Create User
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
