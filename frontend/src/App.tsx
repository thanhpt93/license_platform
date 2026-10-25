import React, { useEffect, useState } from 'react';
import {
  LayoutDashboard,
  Users,
  Layers,
  KeyRound,
  ScrollText,
  Settings,
  LogOut,
  Shield,
  Lock,
} from 'lucide-react';
import { apiRequest, getStoredToken, LicenseRecord, setStoredToken, User } from './api';
import { DashboardView } from './views/DashboardView';
import { CustomersView } from './views/CustomersView';
import { ProductsPlansView } from './views/ProductsPlansView';
import { LicensesView } from './views/LicensesView';
import { AuditLogsView } from './views/AuditLogsView';
import { SystemSettingsView } from './views/SystemSettingsView';

export function App() {
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [authChecking, setAuthChecking] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<string>('dashboard');

  // Login Form state
  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loggingIn, setLoggingIn] = useState<boolean>(false);

  // Cross-tab quick-action triggers
  const [createCustomerTrigger, setCreateCustomerTrigger] = useState<number>(0);
  const [issueLicenseTrigger, setIssueLicenseTrigger] = useState<number>(0);
  const [selectedLicenseSignal, setSelectedLicenseSignal] = useState<LicenseRecord | null>(null);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) {
      setAuthChecking(false);
      return;
    }
    apiRequest<User>('/api/auth/me')
      .then((u) => setCurrentUser(u))
      .catch(() => setStoredToken(null))
      .finally(() => setAuthChecking(false));
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoggingIn(true);
    setLoginError(null);
    try {
      const res = await apiRequest<{ access_token: string; user: User }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      });
      setStoredToken(res.access_token);
      setCurrentUser(res.user);
      setPassword('');
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoggingIn(false);
    }
  };

  const handleLogout = () => {
    setStoredToken(null);
    setCurrentUser(null);
    setActiveTab('dashboard');
  };

  if (authChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-600 text-sm">
        Initializing NOVA License Management session...
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-900 p-4">
        <div className="bg-white rounded-xl shadow-2xl max-w-md w-full overflow-hidden border border-slate-200">
          <div className="bg-slate-950 px-6 py-6 text-white flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-600 flex items-center justify-center">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg tracking-tight">NOVA License Management</h1>
              <p className="text-xs text-slate-400">Internal Enterprise Administration & Signing</p>
            </div>
          </div>

          <form onSubmit={handleLogin} className="p-6 space-y-4 text-sm">
            {loginError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs font-medium">
                {loginError}
              </div>
            )}
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Administrator Username
              </label>
              <input
                type="text"
                required
                autoFocus
                placeholder="admin"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full border border-slate-300 rounded-md px-3.5 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">Password</label>
              <input
                type="password"
                required
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-slate-300 rounded-md px-3.5 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>

            <button
              type="submit"
              disabled={loggingIn}
              className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md font-semibold shadow-sm transition disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Lock className="w-4 h-4" />
              {loggingIn ? 'Authenticating...' : 'Sign In to Administration Portal'}
            </button>
          </form>
        </div>
      </div>
    );
  }

  const canWrite = currentUser.role === 'SUPER_ADMIN' || currentUser.role === 'LICENSE_ADMIN';

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'customers', label: 'Customers', icon: Users },
    { id: 'products', label: 'Products & Plans', icon: Layers },
    { id: 'licenses', label: 'Licenses', icon: KeyRound },
    { id: 'audit', label: 'Audit Logs', icon: ScrollText },
    { id: 'settings', label: 'System Settings', icon: Settings },
  ];

  const currentNavTitle = navItems.find((n) => n.id === activeTab)?.label || 'Dashboard';

  return (
    <div className="h-screen w-screen overflow-hidden flex bg-slate-100">
      {/* Fixed Left Sidebar */}
      <aside className="w-64 bg-slate-900 text-slate-200 flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-slate-800 flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-blue-600 flex items-center justify-center shrink-0">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-bold text-sm text-white leading-tight">NOVA License</div>
            <div className="text-[11px] text-slate-400">Management Platform</div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition ${
                  active
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <Icon className="w-4 h-4" />
                {item.label}
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-800 text-xs text-slate-400 space-y-2">
          <div className="flex items-center justify-between">
            <span className="font-medium text-slate-200 truncate">{currentUser.full_name}</span>
            <span className="font-mono text-[10px] px-1.5 py-0.5 bg-slate-800 text-blue-400 rounded">
              {currentUser.role}
            </span>
          </div>
          <div className="font-mono text-[11px] text-slate-500 truncate">{currentUser.email}</div>
          <button
            onClick={handleLogout}
            className="w-full mt-2 py-1.5 px-3 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded flex items-center justify-center gap-1.5 text-xs font-medium"
          >
            <LogOut className="w-3.5 h-3.5" /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Horizontal Top Bar */}
        <header className="h-14 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <h1 className="font-semibold text-base text-slate-900">{currentNavTitle}</h1>
            <span className="text-xs text-slate-400">|</span>
            <span className="text-xs text-slate-500">NOVA Machine Vision Platform — Phase 1</span>
          </div>
          <div className="flex items-center gap-4 text-xs text-slate-600">
            <span className="font-mono bg-slate-100 px-2.5 py-1 rounded border border-slate-200">
              Schema v1.0 &bull; Ed25519
            </span>
          </div>
        </header>

        {/* Independently Scrollable Main Viewport */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-7xl mx-auto">
            {activeTab === 'dashboard' && (
              <DashboardView
                onNavigate={(tab) => setActiveTab(tab)}
                onQuickCreateCustomer={() => {
                  setActiveTab('customers');
                  setCreateCustomerTrigger((c) => c + 1);
                }}
                onQuickIssueLicense={() => {
                  setActiveTab('licenses');
                  setIssueLicenseTrigger((c) => c + 1);
                }}
                onSelectLicense={(lic) => {
                  setSelectedLicenseSignal(lic);
                  setActiveTab('licenses');
                }}
              />
            )}
            {activeTab === 'customers' && (
              <CustomersView openCreateModalSignal={createCustomerTrigger} canWrite={canWrite} />
            )}
            {activeTab === 'products' && <ProductsPlansView canWrite={canWrite} />}
            {activeTab === 'licenses' && (
              <LicensesView
                openIssueWizardSignal={issueLicenseTrigger}
                selectedLicenseSignal={selectedLicenseSignal}
                onClearSelectedLicenseSignal={() => setSelectedLicenseSignal(null)}
                canWrite={canWrite}
              />
            )}
            {activeTab === 'audit' && <AuditLogsView />}
            {activeTab === 'settings' && <SystemSettingsView currentUser={currentUser} />}
          </div>
        </main>
      </div>
    </div>
  );
}
export default App;
