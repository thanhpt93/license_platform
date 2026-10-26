export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: 'SUPER_ADMIN' | 'LICENSE_ADMIN' | 'AUDITOR';
  is_active: boolean;
  created_at: string;
}

export interface Customer {
  id: string;
  customer_code: string;
  company_name: string;
  contact_person: string;
  contact_email: string;
  contact_phone?: string | null;
  country_region?: string | null;
  address?: string | null;
  notes?: string | null;
  status: 'ACTIVE' | 'INACTIVE';
  issued_licenses_count: number;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: string;
  product_code: string;
  product_name: string;
  description?: string | null;
  supported_editions: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface LicensePlan {
  id: string;
  plan_code: string;
  plan_name: string;
  product_id: string;
  product_code?: string;
  product_name?: string;
  edition: 'developer' | 'production';
  description?: string | null;
  license_type: 'SUBSCRIPTION' | 'PERPETUAL';
  default_duration_days?: number | null;
  features: string[];
  max_devices: number;
  max_concurrent_inspections: number;
  total_inspection_quota: number;
  allow_custom_duration: boolean;
  allow_custom_limits: boolean;
  status: 'ACTIVE' | 'INACTIVE';
  created_at: string;
  updated_at: string;
}

export interface LicenseRelationshipItem {
  id: string;
  previous_license_id: string;
  previous_license_number?: string | null;
  new_license_id: string;
  new_license_number?: string | null;
  relationship_type: 'RENEWAL' | 'REPLACEMENT';
  reason?: string | null;
  created_at: string;
}

export interface LicenseRecord {
  id: string;
  license_number: string;
  customer_id: string;
  customer_code?: string | null;
  customer_name?: string | null;
  product_id: string;
  product_code_snapshot: string;
  plan_id: string;
  plan_code_snapshot: string;
  plan_name_snapshot: string;
  schema_version: string;
  edition: string;
  license_type: 'SUBSCRIPTION' | 'PERPETUAL';
  issued_at: string;
  not_before: string;
  expires_at?: string | null;
  features_snapshot: string[];
  limits_snapshot: {
    max_devices: number;
    max_concurrent_inspections: number;
    total_inspection_quota: number;
  };
  key_id: string;
  signature_algorithm: string;
  signature_b64: string;
  signed_artifact_json: Record<string, unknown>;
  status: string;
  effective_status: 'ACTIVE' | 'EXPIRED' | 'SUSPENDED' | 'REVOKED' | 'REPLACED';
  status_reason?: string | null;
  status_updated_at?: string | null;
  notes?: string | null;
  created_at: string;
  signature_verified?: boolean | null;
  lineage_previous: LicenseRelationshipItem[];
  lineage_next: LicenseRelationshipItem[];
}

export interface AuditLogItem {
  id: string;
  timestamp: string;
  actor_id?: string | null;
  actor_username?: string | null;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  outcome: 'SUCCESS' | 'FAILURE' | 'DENIED';
  reason?: string | null;
  metadata_json?: Record<string, unknown> | null;
}

export interface SigningKeyItem {
  id: string;
  key_id: string;
  algorithm: string;
  public_key_pem: string;
  fingerprint_sha256: string;
  is_active: boolean;
  status: string;
  description?: string | null;
  created_at: string;
  rotated_at?: string | null;
}

export interface DashboardSummary {
  total_customers: number;
  active_customers: number;
  active_licenses: number;
  expiring_soon_licenses: number;
  expired_licenses: number;
  revoked_or_suspended_licenses: number;
  issued_in_period: number;
  period_days: number;
  recent_licenses: LicenseRecord[];
  expiring_soon_list: LicenseRecord[];
  recent_audit_logs: AuditLogItem[];
  signing_engine_ready: boolean;
  active_key_id?: string | null;
}

export interface VerifyArtifactResponse {
  valid: boolean;
  license_id?: string | null;
  license_number?: string | null;
  key_id?: string | null;
  algorithm?: string | null;
  effective_status?: string | null;
  reason?: string | null;
  verified_at: string;
}

export const ALL_SOFTWARE_FEATURES: string[] = [
  '*',
  'anomaly_detection',
  'barcode_reader',
  'blob_analysis',
  'camera_calibration',
  'contour_detection',
  'deep_learning_ocr',
  'ethercat_trigger_bridge',
  'high_speed_acquisition',
  'measurement_metrology',
  'mqtt_publisher',
  'multi_camera_sync',
  'offline_simulator',
  'pipeline_studio',
  'plc_modbus_profinet',
  'qr_reader',
  'shape_analysis',
  'spc_telemetry_export',
  'surface_defect_detection',
  'tcp_ip_stream',
  'template_matching',
];

export function isAllFeatures(features?: string[] | null): boolean {
  if (!features || features.length === 0) return true;
  if (features.includes('*')) return true;
  return features.length >= ALL_SOFTWARE_FEATURES.length - 1;
}

const TOKEN_STORAGE_KEY = 'nova_license_admin_token';

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(path, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}`;
    try {
      const errData = await response.json();
      if (errData.detail) {
        if (typeof errData.detail === 'string') {
          errorMsg = errData.detail;
        } else {
          errorMsg = JSON.stringify(errData.detail);
        }
      }
      if (errData.errors && Array.isArray(errData.errors)) {
        errorMsg = errData.errors.map((e: { field: string; message: string }) => `${e.field}: ${e.message}`).join('; ');
      }
    } catch {
      // ignore json parse failure
    }
    throw new Error(errorMsg);
  }

  return response.json() as Promise<T>;
}

export async function downloadSignedLicenseFile(licenseId: string, licenseNumber: string): Promise<void> {
  const token = getStoredToken();
  const response = await fetch(`/api/licenses/${licenseId}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error('Failed to download signed license artifact');
  }
  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${licenseNumber}.novalic.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
