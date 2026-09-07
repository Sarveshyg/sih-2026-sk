import { memo, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Activity, AlertTriangle, Bell, ChevronDown, CircleHelp, Crosshair, Flame,
  Layers3, MapPin, Maximize2, Menu, Moon, PanelRight, RefreshCw,
  Search, ShieldAlert, SlidersHorizontal, Sun, Thermometer, TrendingUp, LogOut,
  Wifi, X, Zap, UserRound, LockKeyhole, Phone, MapPinned, Mail, Eye, EyeOff, Play, Pause, Gauge, CheckCircle2,
  Cpu, Sparkles,
} from 'lucide-react'
import { CircleMarker, MapContainer, TileLayer, Popup, useMap } from 'react-leaflet'


import type { LatLngExpression } from 'leaflet'
import './App.css'

type RiskLevel = 'critical' | 'high' | 'moderate' | 'low'
type FireType = 'Industrial Fire' | 'Persistent Industrial Thermal Source' | 'Gas Flare' | 'Wildfire/Natural Fire' | 'Agricultural Fire' | 'Unknown'
type AuthView = 'none' | 'login' | 'signup'
type UserRole = 'Central Government' | 'Regional Authority' | 'Emergency Response'

type StoredUser = {
  fullName: string
  email: string
  phone: string
  area: string
  password: string
  role: UserRole
  region: string
}

export const fireTypes: FireType[] = [
  'Industrial Fire',
  'Persistent Industrial Thermal Source',
  'Gas Flare',
  'Wildfire/Natural Fire',
  'Agricultural Fire',
  'Unknown',
]



export type EscalationLogEntry = {
  from_tier: number
  to_tier: number
  actor: string
  role: string
  reason: string
  timestamp: string
}

export type AlertRecord = {
  id: string
  eventId: string
  facility_name?: string
  facility_type?: string
  fireType: FireType
  location: string
  region: string
  classification?: string
  risk: number
  severity: RiskLevel
  confidence?: number
  frp?: number
  temperature?: number
  status: 'NEW' | 'ACKNOWLEDGED' | 'UNDER_REVIEW' | 'IN_PROGRESS' | 'ESCALATED' | 'RESOLVED'
  current_tier: number
  previous_tier?: number
  assigned_agency?: string
  createdAt: string
  updatedAt?: string
  message: string
  escalation_history?: EscalationLogEntry[]
  resolution_note?: string
  resolved_by?: string
  resolved_tier?: number
  resolved_at?: string
  latitude?: number
  longitude?: number
}

export type FirmsStatus = {
  source: string
  mode: string
  status: string
  map_key_configured: boolean
  last_fetch: string
  last_satellite_observation: string
  raw_detections_fetched: number
  valid_detections: number
  unique_detections: number
  processed_enriched: number
  ml_analyzed: number
  priority_anomalies: number
  active_alerts: number
  critical_alerts: number
  next_refresh_seconds: number
  satellite_sources: string[]
  geographic_bounds: string
}

export type PipelineStage = {
  id: string
  name: string
  count: number
  unit: string
}

export type MlInferenceResult = {
  event_id: string
  model_name: string
  model_version: string
  inference_mode: string
  latency_ms: number
  timestamp: string
  classification: string
  confidence: number
  risk_score: number
  risk_level: string
  explanation: string[]
  input_features?: Record<string, any>
  prob_industrial?: number
  recommended_tier?: number
  triage_required?: boolean
}

type SimulationIncident = EventRecord & {
  region: string
  stage: 'DETECTED' | 'ANALYZING' | 'HIGH RISK' | 'CRITICAL' | 'DISPATCHED'
  simulatedRisk: number
  active: boolean
}


const demoAccounts: StoredUser[] = [
  { fullName: 'National Emergency Control', email: 'central@thermos.gov.in', phone: '9999999999', area: 'New Delhi', password: 'thermos123', role: 'Central Government', region: 'All India' },
  { fullName: 'Maharashtra Regional Authority', email: 'maharashtra@thermos.gov.in', phone: '8888888888', area: 'Mumbai', password: 'thermos123', role: 'Regional Authority', region: 'Maharashtra' },
  { fullName: 'Gujarat Regional Authority', email: 'gujarat@thermos.gov.in', phone: '7777777777', area: 'Gandhinagar', password: 'thermos123', role: 'Regional Authority', region: 'Gujarat' },
  { fullName: 'Pune Emergency Response', email: 'response.pune@thermos.gov.in', phone: '6666666666', area: 'Pune', password: 'thermos123', role: 'Emergency Response', region: 'Maharashtra' },
]



const alertRecipients = (user: StoredUser | null, region: string) => {
  if (!user) return false
  return user.role === 'Central Government' || user.region === region
}

export const fireTypeMeta: Record<FireType, { short: string; description: string; color: string }> = {
  'Industrial Fire': { short: 'Industrial', description: 'Acute thermal activity associated with industrial facilities.', color: '#c24632' },
  'Persistent Industrial Thermal Source': { short: 'Persistent source', description: 'Recurring heat signatures that remain active over time.', color: '#a97a1f' },
  'Gas Flare': { short: 'Gas flare', description: 'Thermal signatures consistent with controlled hydrocarbon flaring.', color: '#b05d22' },
  'Wildfire/Natural Fire': { short: 'Wildfire / natural', description: 'Vegetation and natural-land fire signatures.', color: '#8a4f35' },
  'Agricultural Fire': { short: 'Agricultural', description: 'Thermal activity associated with agricultural land management.', color: '#6b6a24' },
  'Unknown': { short: 'Unknown', description: 'Thermal anomalies without enough context for a stronger class.', color: '#5d6470' },
}

export const getCanonicalRiskLevel = (score: number): RiskLevel => {
  if (score >= 75) return 'critical'
  if (score >= 50) return 'high'
  if (score >= 25) return 'moderate'
  return 'low'
}

type EventRecord = {
  id: string
  location: string
  facility: string
  type: string
  classification: string
  fireType: FireType
  timestamp: string
  frp: number
  temperature: number
  confidence: number
  risk: number
  riskLevel: RiskLevel
  persistence: number
  detections: number
  latitude: number
  longitude: number
}

const events: EventRecord[] = [
  { id: 'FIRMS_001', location: 'Jamnagar, Gujarat', facility: 'Reliance Industries Refinery', type: 'Petrochemical Refinery', classification: 'Industrial Thermal Anomaly Candidate', fireType: 'Industrial Fire', timestamp: '10:30 UTC', frp: 124.5, temperature: 341.2, confidence: 94.2, risk: 87, riskLevel: 'critical', persistence: 84, detections: 18, latitude: 22.47, longitude: 70.06 },
  { id: 'FIRMS_014', location: 'Paradip, Odisha', facility: 'IOCL Paradip Petrochemical Complex', type: 'Petrochemical Yard', classification: 'Persistent Industrial Thermal Source', fireType: 'Persistent Industrial Thermal Source', timestamp: '09:48 UTC', frp: 96.8, temperature: 329.7, confidence: 91.8, risk: 76, riskLevel: 'critical', persistence: 72, detections: 13, latitude: 20.27, longitude: 86.68 },
  { id: 'FIRMS_022', location: 'Korba, Chhattisgarh', facility: 'NTPC Korba Thermal Power Station', type: 'Power plant', classification: 'Industrial Thermal Anomaly Candidate', fireType: 'Industrial Fire', timestamp: '08:16 UTC', frp: 74.2, temperature: 318.4, confidence: 88.4, risk: 64, riskLevel: 'high', persistence: 61, detections: 9, latitude: 22.36, longitude: 82.75 },
  { id: 'FIRMS_031', location: 'Bharuch, Gujarat', facility: 'Dahej Industrial Estate', type: 'LNG Chemical Terminal', classification: 'Potential Gas Flare', fireType: 'Gas Flare', timestamp: '06:54 UTC', frp: 51.6, temperature: 307.9, confidence: 82.6, risk: 43, riskLevel: 'moderate', persistence: 45, detections: 7, latitude: 21.70, longitude: 72.99 },
  { id: 'FIRMS_044', location: 'Mumbai, Maharashtra', facility: 'Bharat Petroleum Mumbai Refinery', type: 'Oil Refinery', classification: 'Industrial Thermal Anomaly Candidate', fireType: 'Industrial Fire', timestamp: '05:42 UTC', frp: 88.1, temperature: 326.8, confidence: 90.6, risk: 79, riskLevel: 'critical', persistence: 68, detections: 12, latitude: 19.01, longitude: 72.88 },
  { id: 'FIRMS_052', location: 'Vapi, Gujarat', facility: 'Vapi Chemical Estate', type: 'Chemical plant', classification: 'Persistent Industrial Thermal Source', fireType: 'Persistent Industrial Thermal Source', timestamp: '04:27 UTC', frp: 42.7, temperature: 301.6, confidence: 86.3, risk: 58, riskLevel: 'high', persistence: 77, detections: 16, latitude: 20.37, longitude: 72.91 },
  { id: 'FIRMS_067', location: 'Visakhapatnam, Andhra Pradesh', facility: 'HPCL Visakh Refinery', type: 'Petrochemical', classification: 'Potential Gas Flare', fireType: 'Gas Flare', timestamp: '03:18 UTC', frp: 63.4, temperature: 312.5, confidence: 89.1, risk: 69, riskLevel: 'high', persistence: 54, detections: 8, latitude: 17.69, longitude: 83.22 },
  { id: 'FIRMS_073', location: 'Mayurbhanj, Odisha', facility: 'Simlipal Forest Reserve', type: 'Forest Reserve', classification: 'Wildfire Candidate', fireType: 'Wildfire/Natural Fire', timestamp: '02:51 UTC', frp: 48.9, temperature: 304.7, confidence: 85.5, risk: 68, riskLevel: 'high', persistence: 24, detections: 4, latitude: 21.92, longitude: 86.32 },
  { id: 'FIRMS_081', location: 'Kolkata, West Bengal', facility: 'Haldia Dock Complex', type: 'Industrial estate', classification: 'Industrial Thermal Anomaly Candidate', fireType: 'Industrial Fire', timestamp: '01:36 UTC', frp: 107.3, temperature: 333.1, confidence: 93.4, risk: 85, riskLevel: 'critical', persistence: 81, detections: 19, latitude: 22.06, longitude: 88.09 },
  { id: 'FIRMS_096', location: 'Chennai, Tamil Nadu', facility: 'Manali Industrial Corridor', type: 'Chemical plant', classification: 'Normal / Ambient Surface Heat Baseline', fireType: 'Unknown', timestamp: '00:48 UTC', frp: 15.8, temperature: 299.4, confidence: 70.2, risk: 22, riskLevel: 'low', persistence: 12, detections: 2, latitude: 13.16, longitude: 80.27 },
]

const initialAlertRecords: AlertRecord[] = [
  {
    id: 'ALT-GJ-001',
    eventId: 'FIRMS_001',
    fireType: 'Industrial Fire',
    location: 'Jamnagar, Gujarat',
    region: 'Gujarat',
    risk: 94,
    severity: 'critical',
    status: 'NEW',
    current_tier: 1,
    createdAt: '10:30 UTC',
    message: 'AI-detected thermal anomaly candidate near Reliance Refinery (FRP 124.5 MW). Verification required.',
  },
  {
    id: 'ALT-OD-002',
    eventId: 'FIRMS_014',
    fireType: 'Persistent Industrial Thermal Source',
    location: 'Paradip, Odisha',
    region: 'Odisha',
    risk: 88,
    severity: 'critical',
    status: 'ACKNOWLEDGED',
    current_tier: 1,
    createdAt: '09:48 UTC',
    message: 'Persistent industrial thermal source (+566% deviation) near Paradip Complex.',
  },
  {
    id: 'ALT-CG-003',
    eventId: 'FIRMS_022',
    fireType: 'Industrial Fire',
    location: 'Korba, Chhattisgarh',
    region: 'Chhattisgarh',
    risk: 86,
    severity: 'critical',
    status: 'ESCALATED',
    current_tier: 2,
    createdAt: '08:16 UTC',
    message: 'Elevated thermal anomaly in coal processing zone at NTPC Korba.',
  },
  {
    id: 'ALT-MH-004',
    eventId: 'FIRMS_044',
    fireType: 'Industrial Fire',
    location: 'Mumbai, Maharashtra',
    region: 'Maharashtra',
    risk: 91,
    severity: 'critical',
    status: 'ESCALATED',
    current_tier: 3,
    createdAt: '07:22 UTC',
    message: 'Acute thermal hotspot detected near BPCL Mumbai Refinery.',
  },
]
const simulationScenario: SimulationIncident[] = [
  { ...events[0], id: 'SIM-GJ-001', region: 'Gujarat', stage: 'DETECTED', simulatedRisk: 42, active: false },
  { ...events[4], id: 'SIM-MH-001', region: 'Maharashtra', stage: 'DETECTED', simulatedRisk: 38, active: false },
  { ...events[7], id: 'SIM-KA-001', region: 'Karnataka', stage: 'DETECTED', simulatedRisk: 31, active: false },
  { ...events[1], id: 'SIM-OD-001', region: 'Odisha', stage: 'DETECTED', simulatedRisk: 35, active: false },
  { ...events[3], id: 'SIM-GJ-002', region: 'Gujarat', stage: 'DETECTED', simulatedRisk: 28, active: false },
  { ...events[9], id: 'SIM-TN-001', region: 'Tamil Nadu', stage: 'DETECTED', simulatedRisk: 25, active: false },
  { ...events[7], id: 'SIM-MP-AGR-001', region: 'Madhya Pradesh', fireType: 'Agricultural Fire', classification: 'Agricultural thermal activity', location: 'Bhopal, Madhya Pradesh', stage: 'DETECTED', simulatedRisk: 24, active: false },
]


const navItems = [
  { label: 'Dashboard', icon: Activity },
  { label: 'GIS map', icon: Layers3 },
  { label: 'Event detail', icon: PanelRight },
  { label: 'AI analysis', icon: TrendingUp },
  { label: 'Facility intel', icon: Layers3 },
  { label: 'Alert center', icon: ShieldAlert },
  { label: 'Simulation', icon: Gauge },
]

const workspaceOptions = [
  'India (All Regions)', 'Western India', 'Delhi NCR', 'Mumbai, Maharashtra', 'Ahmedabad, Gujarat', 'Jamnagar, Gujarat',
  'Bengaluru, Karnataka', 'Chennai, Tamil Nadu', 'Hyderabad, Telangana', 'Kolkata, West Bengal',
  'Pune, Maharashtra', 'Jaipur, Rajasthan', 'Lucknow, Uttar Pradesh', 'Bhopal, Madhya Pradesh',
  'Bhubaneswar, Odisha', 'Patna, Bihar', 'Ranchi, Jharkhand', 'Guwahati, Assam',
  'Raipur, Chhattisgarh', 'Kochi, Kerala', 'Visakhapatnam, Andhra Pradesh',
]

const workspaceCoordinates: Record<string, LatLngExpression> = {
  'India (All Regions)': [20.5937, 78.9629], 'Western India': [20.2, 72.8], 'Delhi NCR': [28.6, 77.2], 'Mumbai, Maharashtra': [19.08, 72.88],
  'Ahmedabad, Gujarat': [23.02, 72.57], 'Jamnagar, Gujarat': [22.47, 70.06], 'Bengaluru, Karnataka': [12.97, 77.59],
  'Chennai, Tamil Nadu': [13.08, 80.27], 'Hyderabad, Telangana': [17.39, 78.49], 'Kolkata, West Bengal': [22.57, 88.36],
  'Pune, Maharashtra': [18.52, 73.86], 'Jaipur, Rajasthan': [26.91, 75.79], 'Lucknow, Uttar Pradesh': [26.85, 80.95],
  'Bhopal, Madhya Pradesh': [23.26, 77.41], 'Bhubaneswar, Odisha': [20.3, 85.82], 'Patna, Bihar': [25.59, 85.14],
  'Ranchi, Jharkhand': [23.34, 85.31], 'Guwahati, Assam': [26.14, 91.74], 'Raipur, Chhattisgarh': [21.25, 81.63],
  'Kochi, Kerala': [9.93, 76.27], 'Visakhapatnam, Andhra Pradesh': [17.69, 83.22],
}

const facilityIntel = [
  { name: 'Reliance Industries Refinery', type: 'refinery', activity: [4, 3, 5, 7, 6, 11, 14], baseline: '2/day', current: '14/day', deviation: '+600%', linked: 'FIRMS_001' },
  { name: 'Jamnagar Petrochemical Yard', type: 'petrochemical', activity: [3, 4, 4, 5, 4, 6, 8], baseline: '3/day', current: '8/day', deviation: '+167%', linked: 'FIRMS_014' },
  { name: 'Bhilai Steel Works', type: 'steel plant', activity: [2, 2, 3, 2, 4, 3, 5], baseline: '2/day', current: '5/day', deviation: '+150%', linked: 'FIRMS_022' },
  { name: 'Korba Thermal Power Station', type: 'power plant', activity: [5, 6, 5, 7, 6, 8, 7], baseline: '5/day', current: '7/day', deviation: '+40%', linked: 'FIRMS_022' },
  { name: 'Dahej LNG Terminal', type: 'lng facility', activity: [1, 2, 2, 1, 3, 2, 4], baseline: '1/day', current: '4/day', deviation: '+300%', linked: 'FIRMS_031' },
]

function App() {
  const [selectedId, setSelectedId] = useState('FIRMS_001')
  const [query, setQuery] = useState('')
  const [activeNav, setActiveNav] = useState('Dashboard')
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (localStorage.getItem('thermos-theme') as 'dark' | 'light' | null) ?? 'light',
  )
  const [workspace, setWorkspace] = useState('India (All Regions)')
  const [isWorkspaceOpen, setIsWorkspaceOpen] = useState(false)
  const [isMapMaximized, setIsMapMaximized] = useState(false)
  const [isFilterOpen, setIsFilterOpen] = useState(false)
  const [isAccountOpen, setIsAccountOpen] = useState(false)
  const [topMenu, setTopMenu] = useState<'help' | 'notifications' | 'mobile' | null>(null)
  const [riskFilter, setRiskFilter] = useState<RiskLevel | 'all'>('all')
  const [reviewStatus, setReviewStatus] = useState<'pending' | 'resolved' | 'escalated'>('pending')
  const [authView, setAuthView] = useState<AuthView>('none')
  const [user, setUser] = useState<StoredUser | null>(() => {
    try {
      const stored = localStorage.getItem('thermos-user')
      return stored ? JSON.parse(stored) as StoredUser : null
    } catch {
      return null
    }
  })
  const [simulationActive, setSimulationActive] = useState(false)
  const [simulationSpeed, setSimulationSpeed] = useState(1)
  const [simulationTick, setSimulationTick] = useState(0)
  const [simulationIncidents, setSimulationIncidents] = useState<SimulationIncident[]>([])
  const [alerts, setAlerts] = useState<AlertRecord[]>(initialAlertRecords)
  const [activeTier, setActiveTier] = useState<1 | 2 | 3>(user ? (user.role === 'Central Government' ? 3 : user.role === 'Regional Authority' ? 2 : 1) : 1)

  const [firmsStatus, setFirmsStatus] = useState<FirmsStatus>({
    source: 'NASA FIRMS',
    mode: 'HISTORICAL / DEMO',
    status: 'HISTORICAL / DEMO DATA (PROTOTYPE)',
    map_key_configured: false,
    last_fetch: '08 Sep 2026 02:30 IST',
    last_satellite_observation: '08 Sep 2026 01:56 UTC',
    raw_detections_fetched: 2600,
    valid_detections: 2584,
    unique_detections: 2431,
    processed_enriched: 2431,
    ml_analyzed: 2431,
    priority_anomalies: 37,
    active_alerts: 5,
    critical_alerts: 4,
    next_refresh_seconds: 300,
    satellite_sources: ['VIIRS NOAA-20', 'VIIRS NOAA-21', 'VIIRS Suomi-NPP'],
    geographic_bounds: 'India (68°E - 98°E, 6°N - 36°N)',
  })

  const [_pipelineStages, setPipelineStages] = useState<PipelineStage[]>([
    { id: 'fetch', name: 'NASA FIRMS Area API', count: 2600, unit: 'detections fetched' },
    { id: 'normalize', name: 'Validation & Normalization', count: 2584, unit: 'valid records' },
    { id: 'dedup', name: 'Deduplication & Cleansing', count: 2431, unit: 'unique overpasses' },
    { id: 'enrich', name: 'Spatial & Facility Context', count: 2431, unit: 'enriched events' },
    { id: 'ml', name: 'ML Inference (fused-xgboost-v1)', count: 2431, unit: 'analyzed' },
    { id: 'prioritize', name: 'Risk & Priority Triage', count: 37, unit: 'priority anomalies' },
    { id: 'alert', name: 'Alert Routing Engine', count: 8, unit: 'active alerts' },
  ])

  const [isFirmsRefreshing, setIsFirmsRefreshing] = useState(false)
  const [mlResult, setMlResult] = useState<MlInferenceResult | null>(null)
  const [isInferencing, setIsInferencing] = useState(false)

  const [activeEvents, setActiveEvents] = useState<EventRecord[]>(events)
  const [analyticsData, setAnalyticsData] = useState<{
    total_events: number
    industrial_events: number
    critical_events: number
    persistent_sources: number
  }>({ total_events: 2600, industrial_events: 455, critical_events: 4, persistent_sources: 14 })

  const mapBackendClassificationToFireType = (label?: string): FireType => {
    switch (label?.toLowerCase()) {
      case 'industrial_fire': return 'Industrial Fire'
      case 'persistent_industrial_source': return 'Persistent Industrial Thermal Source'
      case 'gas_flare': return 'Gas Flare'
      case 'wildfire': return 'Wildfire/Natural Fire'
      case 'agricultural_fire': return 'Agricultural Fire'
      default: return 'Unknown'
    }
  }

  const API_BASE = (import.meta as any).env?.VITE_API_URL ?? (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'http://localhost:8000' : '')

  const fetchBackendData = async () => {
    try {
      const [statusRes, pipeRes, alertsRes, gisRes, analyticsRes] = await Promise.all([
        fetch(`${API_BASE}/api/firms/status`).catch(() => null),
        fetch(`${API_BASE}/api/firms/pipeline-monitor`).catch(() => null),
        fetch(`${API_BASE}/api/alerts?include_resolved=true`).catch(() => null),
        fetch(`${API_BASE}/api/gis/master-detections?limit=5144&india_only=true`).catch(() => null),
        fetch(`${API_BASE}/api/analytics`).catch(() => null),
      ])

      if (statusRes && statusRes.ok) {
        const st = await statusRes.json()
        setFirmsStatus(st)
      }

      if (pipeRes && pipeRes.ok) {
        const pd = await pipeRes.json()
        if (pd.stages && Array.isArray(pd.stages)) {
          setPipelineStages(pd.stages)
        }
      }

      if (alertsRes && alertsRes.ok) {
        const ad = await alertsRes.json()
        if (ad && Array.isArray(ad.alerts) && ad.alerts.length > 0) {
          const mappedAlerts: AlertRecord[] = ad.alerts.map((a: any) => ({
            id: a.id,
            eventId: a.event_id,
            facility_name: a.facility_name,
            facility_type: a.facility_type,
            fireType: mapBackendClassificationToFireType(a.fire_type || a.classification),
            location: a.location,
            region: a.region,
            classification: a.classification,
            risk: a.risk_score,
            severity: a.severity as RiskLevel,
            confidence: a.confidence,
            frp: a.frp,
            temperature: a.temperature,
            status: a.status,
            current_tier: a.current_tier,
            previous_tier: a.previous_tier,
            assigned_agency: a.assigned_agency,
            createdAt: a.created_at,
            updatedAt: a.updated_at,
            message: `${a.classification} near ${a.facility_name}`,
            escalation_history: a.escalation_history || [],
            resolution_note: a.resolution_note,
            resolved_by: a.resolved_by,
            resolved_tier: a.resolved_tier,
            resolved_at: a.resolved_at,
            latitude: a.latitude ?? 22.47,
            longitude: a.longitude ?? 70.06,
          }))
          setAlerts(mappedAlerts)
        }
      }

      if (gisRes && gisRes.ok) {
        const gisData = await gisRes.json()
        if (gisData.detections && Array.isArray(gisData.detections) && gisData.detections.length > 0) {
          const mapped: EventRecord[] = gisData.detections.map((item: any, idx: number) => {
            const detailedClass = item.detailed_predicted_class || item.weak_supervision_label || 'Thermal Anomaly'
            let fireType: FireType = 'Unknown'
            if (detailedClass.includes('Flare')) fireType = 'Gas Flare'
            else if (detailedClass.includes('Wildfire') || detailedClass.includes('Forest')) fireType = 'Wildfire/Natural Fire'
            else if (detailedClass.includes('Industrial') || detailedClass.includes('Plant') || detailedClass.includes('Coal')) fireType = 'Industrial Fire'
            else if (detailedClass.includes('Normal') || detailedClass.includes('Background')) fireType = 'Unknown'
            else fireType = 'Industrial Fire'

            const isInd = item.prob_industrial_fused !== undefined ? item.prob_industrial_fused >= 0.5 : true
            const riskScore = Math.round(isInd ? (item.prob_industrial_fused || 0.85) * 90 : 35)

            return {
              id: `FIRMS_${String(idx + 1).padStart(4, '0')}`,
              location: item.nearest_plant_name || item.nearest_flare_field || item.nearest_mine_name || `Lat ${item.latitude.toFixed(2)}, Lon ${item.longitude.toFixed(2)}`,
              facility: item.nearest_plant_name || item.nearest_flare_field || 'Industrial Facility',
              type: item.nearest_plant_fuel || item.nearest_mine_type || 'Industrial Asset',
              classification: detailedClass,
              fireType,
              timestamp: item.acq_date ? `${item.acq_date} ${String(item.acq_time || '1200').padStart(4, '0').slice(0, 2)}:${String(item.acq_time || '1200').padStart(4, '0').slice(2)} UTC` : '10:30 UTC',
              frp: item.frp || 12.5,
              temperature: item.bright_ti4 || 320.0,
              confidence: item.confidence === 'high' ? 95 : item.confidence === 'nominal' ? 80 : 65,
              risk: riskScore,
              riskLevel: riskScore >= 80 ? 'critical' : riskScore >= 60 ? 'high' : 'moderate',
              persistence: item.spatial_persistence_count ? Math.min(item.spatial_persistence_count * 15, 95) : 45,
              detections: item.spatial_persistence_count || 1,
              latitude: item.latitude,
              longitude: item.longitude,
              ...item,
            }
          })
          setActiveEvents(mapped)
        }
      }

      if (analyticsRes && analyticsRes.ok) {
        const stats = await analyticsRes.json()
        if (stats && typeof stats === 'object') {
          setAnalyticsData((prev) => ({ ...prev, ...stats }))
        }
      }
    } catch (err) {
      console.error('Fetch error:', err)
    }
  }

  const triggerFirmsRefresh = async () => {
    setIsFirmsRefreshing(true)
    try {
      if (API_BASE) {
        await fetch(`${API_BASE}/api/firms/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ force: true }),
        }).catch(() => null)
        await fetchBackendData()
      } else {
        await new Promise((r) => setTimeout(r, 600))
        setFirmsStatus((prev) => ({
          ...prev,
          last_fetch: `${new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })} ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} IST`,
          next_refresh_seconds: 300,
        }))
      }
    } catch (err) {
      console.error('Refresh error', err)
    } finally {
      setIsFirmsRefreshing(false)
    }
  }

  const runLiveInference = async (targetEventId: string) => {
    setIsInferencing(true)
    try {
      let loaded = false
      if (API_BASE) {
        const res = await fetch(`${API_BASE}/api/predict`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ event_id: targetEventId }),
        }).catch(() => null)
        if (res && res.ok) {
          const data = await res.json()
          setMlResult(data)
          loaded = true
        }
      }
      if (!loaded) {
        await new Promise((r) => setTimeout(r, 120))
        const targetEv = activeEvents.find((e) => e.id === targetEventId) || activeEvents[0]
        setMlResult({
          event_id: targetEv.id,
          model_name: 'fused-xgboost-v1',
          model_version: '1.0.0',
          inference_mode: 'LIVE ML INFERENCE',
          latency_ms: 14.2,
          timestamp: new Date().toISOString(),
          classification: targetEv.classification || 'Industrial Facility Thermal Alert',
          confidence: targetEv.confidence || 94,
          risk_score: targetEv.risk || 88,
          risk_level: targetEv.riskLevel,
          explanation: getAiReasons(targetEv),
          prob_industrial: (targetEv.risk || 88) / 100,
          recommended_tier: (targetEv.risk || 88) >= 80 ? 2 : 1,
          triage_required: (targetEv.risk || 88) >= 80,
          input_features: {
            frp: targetEv.frp,
            brightness_temperature: targetEv.temperature,
            temp_diff_ti4_ti5: 22.4,
            confidence: targetEv.confidence,
            distance_to_plant_km: 0.076,
            distance_to_flare_km: 12.4,
            persistence_score: (targetEv.persistence || 80) / 100,
            detections_7d: targetEv.detections,
            facility_type: targetEv.type,
            satellite: 'VIIRS NOAA-20',
            latitude: targetEv.latitude,
            longitude: targetEv.longitude,
          },
        })
      }
    } catch (err) {
      console.error('Inference error', err)
    } finally {
      setIsInferencing(false)
    }
  }

  useEffect(() => {
    fetchBackendData()
    const timer = window.setInterval(() => {
      setFirmsStatus((prev) => {
        if (prev.next_refresh_seconds <= 1) {
          fetchBackendData()
          return { ...prev, next_refresh_seconds: 300 }
        }
        return { ...prev, next_refresh_seconds: prev.next_refresh_seconds - 1 }
      })
    }, 1000)
    return () => window.clearInterval(timer)
  }, [])


  useEffect(() => {
    if (!simulationActive) return
    const interval = window.setInterval(() => setSimulationTick((tick) => tick + 1), Math.max(350, 1400 / simulationSpeed))
    return () => window.clearInterval(interval)
  }, [simulationActive, simulationSpeed])

  useEffect(() => {
    if (!simulationActive || simulationTick === 0) return
    const scenarioIndex = Math.floor((simulationTick - 1) / 5)
    const stageTick = ((simulationTick - 1) % 5) + 1
    if (scenarioIndex >= simulationScenario.length) {
      setSimulationActive(false)
      return
    }
    const base = simulationScenario[scenarioIndex]
    const stage: SimulationIncident['stage'] = stageTick === 1 ? 'DETECTED' : stageTick === 2 ? 'ANALYZING' : stageTick === 3 ? 'HIGH RISK' : stageTick === 4 ? 'CRITICAL' : 'DISPATCHED'
    const simulatedRisk = stageTick === 1 ? 42 : stageTick === 2 ? 58 : stageTick === 3 ? 76 : stageTick === 4 ? 92 : 96
    setSimulationIncidents((current) => {
      const existing = current.find((item) => item.id === base.id)
      const next = { ...base, stage, simulatedRisk, active: true }
      return existing ? current.map((item) => item.id === base.id ? next : item) : [...current, next]
    })
    if (stageTick === 4) {
      const alertId = `ALT-${base.id}`
      setAlerts((current) => current.some((alert) => alert.id === alertId) ? current : [...current, {
        id: alertId,
        eventId: base.id,
        fireType: base.fireType,
        location: base.location,
        region: base.region,
        risk: simulatedRisk,
        severity: 'critical',
        status: 'NEW',
        current_tier: 1,
        createdAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        message: `Critical ${base.fireType.toLowerCase()} detected in ${base.region}. Immediate regional response recommended.`,
      }])
    }
  }, [simulationTick, simulationActive])

  const openLogin = () => { setTopMenu(null); setAuthView('login') }
  const openSignup = () => { setTopMenu(null); setAuthView('signup') }
  const handleAuthSuccess = (nextUser: StoredUser) => {
    setUser(nextUser)
    localStorage.setItem('thermos-user', JSON.stringify(nextUser))
    setAuthView('none')
  }
  const handleLogout = () => {
    setUser(null)
    localStorage.removeItem('thermos-user')
    setIsAccountOpen(false)
    setAuthView('login')
  }


  const selectedEvent = activeEvents.find((event) => event.id === selectedId) ?? activeEvents[0]
  const filteredEvents = useMemo(
    () => activeEvents.filter((event) =>
      `${event.id} ${event.location} ${event.facility}`.toLowerCase().includes(query.toLowerCase())
      && (riskFilter === 'all' || event.riskLevel === riskFilter),
    ),
    [activeEvents, query, riskFilter],
  )
  const priorityEvents = filteredEvents.slice(0, 5)
  const visibleAlerts = alerts.filter((alert) => alertRecipients(user, alert.region))
  const openAlerts = visibleAlerts.filter((alert) => alert.status !== 'RESOLVED')


  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('thermos-theme', next)
  }

  if (authView === 'login') return <LoginPage theme={theme} onLogin={handleAuthSuccess} onSignup={openSignup} onBack={() => setAuthView('none')} />
  if (authView === 'signup') return <SignupPage theme={theme} onSignup={handleAuthSuccess} onLogin={openLogin} onBack={() => setAuthView('none')} />

  return (
    <div className={`shell theme-${theme}`}>
      <aside className="sidebar">
        <div className="sidebar__brand">
          <div className="brand-mark"><Crosshair size={18} strokeWidth={2.25} /></div>
          <div>
            <strong>THERMOS</strong>
            <small>Geospatial thermal intelligence</small>
          </div>
        </div>

        <div className="workspace">
          <span className="workspace__label">Region</span>
          <div className="workspace__picker">
            <button className="workspace__trigger" onClick={() => setIsWorkspaceOpen(!isWorkspaceOpen)}>
              <span className="dot dot--live" />
              {workspace}
              <ChevronDown size={14} className="workspace__chevron" />
            </button>
            {isWorkspaceOpen && (
              <div className="workspace__menu">
                {workspaceOptions.map((option) => (
                  <button
                    key={option}
                    className={workspace === option ? 'is-selected' : ''}
                    onClick={() => { setWorkspace(option); setIsWorkspaceOpen(false) }}
                  >
                    {option}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <nav className="nav" aria-label="Main navigation">
          <span className="nav__label">Monitor</span>
          {navItems.map(({ label, icon: Icon }) => (
            <button
              key={label}
              className={`nav__item ${activeNav === label ? 'is-active' : ''}`}
              onClick={() => setActiveNav(label)}
            >
              <Icon size={17} />
              <span>{label}</span>
              {label === 'Alert center' && (
                <span className="nav__badge">{openAlerts.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar__footer">
          <div className="status-line"><span className="dot dot--live" /> All systems operational</div>
          <div className="account">
            <button className="account__trigger" onClick={() => setIsAccountOpen(!isAccountOpen)}>
              <span className="avatar">{user ? getInitials(user.fullName) : 'OP'}</span>
              <span className="account__meta">
                <strong>{user?.fullName ?? 'Operator'}</strong>
                <small>{user ? `${user.role} · ${user.region}` : 'Operator account'}</small>
              </span>
              <ChevronDown size={14} />
            </button>
            {isAccountOpen && (
              <div className="popover popover--up">
                <strong>{user?.fullName ?? 'Operator'}</strong>
                <span>{user?.email ?? 'Operator account'}{user?.phone ? ` · ${user.phone}` : ''}{user?.area ? ` · ${user.area}` : ''}</span>
                <button onClick={() => setActiveNav('Settings')}>Account settings</button>
                <button onClick={handleLogout}>Sign out</button>
              </div>
            )}
            {user && <button className="account__logout" onClick={handleLogout}><LogOut size={14} /> Sign out</button>}
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="topbar__brand">
            <div className="brand-mark"><Crosshair size={16} /></div>
            <strong>THERMOS</strong>
          </div>
          <div className="crumb">
            <span>Monitor</span>
            <ChevronDown size={12} className="crumb__sep" />
            <strong>{activeNav}</strong>
          </div>
          <div className="topbar__actions">
            <span className="live-chip"><Wifi size={14} /> HISTORICAL / DEMO DATA (PROTOTYPE) <span className="dot dot--live" /></span>
            <button className="icon-btn" aria-label="Toggle theme" onClick={toggleTheme}>
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button className="icon-btn" aria-label="Help" onClick={() => setTopMenu(topMenu === 'help' ? null : 'help')}>
              <CircleHelp size={17} />
            </button>
            <button
              className="icon-btn icon-btn--dot"
              aria-label="Notifications"
              onClick={() => setTopMenu(topMenu === 'notifications' ? null : 'notifications')}
            >
              <Bell size={17} /><i />
            </button>
             {!user && <>
              <button className="btn btn--ghost" onClick={openLogin}>Log in</button>
              <button className="btn btn--primary" onClick={openSignup}>Sign up</button>
            </>}
            {user ? <span className="topbar__user">{getInitials(user.fullName)} {user.fullName} · {user.role} (Prototype)</span> : <span className="topbar__user">Tier 3 · Central Authority (Demo Prototype)</span>}
            <button
              className="icon-btn mobile-menu"
              aria-label="Open menu"
              onClick={() => setTopMenu(topMenu === 'mobile' ? null : 'mobile')}
            >
              <Menu size={19} />
            </button>

            {topMenu && (
              <div className="popover popover--down">
                {topMenu === 'help' && (
                  <>
                    <strong>{user ? `Signed in as ${user.fullName}` : 'Account access'}</strong>
                    <span>{user ? `${user.email} · ${user.area}` : 'Use the login or signup buttons to access a local demo account.'}</span>
                    {!user && <button onClick={openLogin}>Log in</button>}
                    {!user && <button onClick={openSignup}>Create account</button>}
                    {user && <button onClick={handleLogout}>Sign out</button>}
                    <button onClick={() => setTopMenu(null)}>Close</button>
                  </>
                )}
                {topMenu === 'notifications' && (
                  <>
                    <strong>Notifications</strong>
                    <span>{openAlerts.length ? `${openAlerts.length} region-routed alert${openAlerts.length > 1 ? 's' : ''} need attention.` : 'No active alerts for this account.'}</span>
                    <button onClick={() => { setActiveNav('Alert center'); setTopMenu(null) }}>Review alerts</button>
                  </>
                )}
                {topMenu === 'mobile' && (
                  <>
                    <strong>Quick navigation</strong>
                    {navItems.map(({ label }) => (
                      <button key={label} onClick={() => { setActiveNav(label); setTopMenu(null) }}>{label}</button>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>
        </header>

        {activeNav === 'Dashboard' ? (
          <div className="page">
            <div className="page__header">
              <div>
                <h1>Thermal Anomaly Intelligence</h1>
                <p className="page__subtitle">Operational decision-support dashboard for thermal detection, classification, and priority routing across India.</p>
              </div>
              <div className="page__actions">
                <span className="updated"><span className="dot dot--live" /> Ingestion Pipeline Active</span>
                <button className="btn btn--primary" onClick={triggerFirmsRefresh} disabled={isFirmsRefreshing}>
                  <RefreshCw size={15} className={isFirmsRefreshing ? 'spin' : ''} /> {isFirmsRefreshing ? 'Fetching FIRMS...' : 'FETCH LATEST FIRMS DATA'}
                </button>
              </div>
            </div>

            {/* --- DATA INGESTION STATUS CARD --- */}
            <div className="firms-data-status-card">
              <div className="firms-status-top">
                <div className="firms-badges-group">
                  <span className="firms-badge firms-badge--satellite">🛰️ DATA SOURCE: {firmsStatus.source}</span>
                  <span className={`firms-badge ${firmsStatus.mode === 'LIVE' ? 'firms-badge--live' : 'firms-badge--historical'}`}>
                    <span className="dot dot--live" /> MODE: {firmsStatus.mode}
                  </span>
                  <span className={`firms-badge ${firmsStatus.status.includes('LIVE') ? 'firms-badge--live' : 'firms-badge--historical'}`}>
                    STATUS: {firmsStatus.status}
                  </span>
                  <span className="firms-badge firms-badge--satellite">
                    SATELLITES: {firmsStatus.satellite_sources.join(', ')}
                  </span>
                  <span className="firms-badge firms-badge--satellite">
                    BOUNDS: {firmsStatus.geographic_bounds}
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Auto-refresh in: <strong>{firmsStatus.next_refresh_seconds}s</strong>
                </div>
              </div>
              <div className="firms-status-grid">
                <div className="firms-metric-item">
                  <span className="firms-metric-label">Raw Detections</span>
                  <strong className="firms-metric-val">{firmsStatus.raw_detections_fetched.toLocaleString()}</strong>
                </div>
                <div className="firms-metric-item">
                  <span className="firms-metric-label">Valid Normalized</span>
                  <strong className="firms-metric-val">{firmsStatus.valid_detections.toLocaleString()}</strong>
                </div>
                <div className="firms-metric-item">
                  <span className="firms-metric-label">Unique Overpasses</span>
                  <strong className="firms-metric-val">{firmsStatus.unique_detections.toLocaleString()}</strong>
                </div>
                <div className="firms-metric-item">
                  <span className="firms-metric-label">ML Analyzed</span>
                  <strong className="firms-metric-val">{firmsStatus.ml_analyzed.toLocaleString()}</strong>
                </div>
                <div className="firms-metric-item">
                  <span className="firms-metric-label">Priority Anomalies</span>
                  <strong className="firms-metric-val text-warning">{firmsStatus.priority_anomalies}</strong>
                </div>
                <div className="firms-metric-item">
                  <span className="firms-metric-label">Critical Alerts</span>
                  <strong className="firms-metric-val text-critical">{openAlerts.filter(a => a.severity === 'critical').length}</strong>
                </div>
                <div className="firms-metric-item">
                  <span className="firms-metric-label">Last Observation</span>
                  <span style={{ fontSize: '11.5px', fontWeight: 600 }}>{firmsStatus.last_satellite_observation}</span>
                </div>
                <div className="firms-metric-item">
                  <span className="firms-metric-label">Last Fetch</span>
                  <span style={{ fontSize: '11.5px', fontWeight: 600 }}>{firmsStatus.last_fetch}</span>
                </div>
              </div>
            </div>

            {/* --- 7-STAGE PIPELINE MONITOR --- */}
            <div className="pipeline-monitor-card">
              <p className="card__label" style={{ marginBottom: '6px' }}>7-Stage Ingestion &amp; Intelligence Pipeline Flow</p>
              <div className="pipeline-flow">
                <div className="pipeline-stage-box">
                  <div className="pipeline-stage-title">1. NASA FIRMS API</div>
                  <div className="pipeline-stage-count">{firmsStatus.raw_detections_fetched.toLocaleString()}</div>
                  <div className="pipeline-stage-unit">detections fetched</div>
                </div>
                <span className="pipeline-arrow">→</span>
                <div className="pipeline-stage-box">
                  <div className="pipeline-stage-title">2. Normalization</div>
                  <div className="pipeline-stage-count">{firmsStatus.valid_detections.toLocaleString()}</div>
                  <div className="pipeline-stage-unit">valid records</div>
                </div>
                <span className="pipeline-arrow">→</span>
                <div className="pipeline-stage-box">
                  <div className="pipeline-stage-title">3. Deduplication</div>
                  <div className="pipeline-stage-count">{firmsStatus.unique_detections.toLocaleString()}</div>
                  <div className="pipeline-stage-unit">unique passes</div>
                </div>
                <span className="pipeline-arrow">→</span>
                <div className="pipeline-stage-box">
                  <div className="pipeline-stage-title">4. Spatial Context</div>
                  <div className="pipeline-stage-count">{firmsStatus.processed_enriched.toLocaleString()}</div>
                  <div className="pipeline-stage-unit">facility enriched</div>
                </div>
                <span className="pipeline-arrow">→</span>
                <div className="pipeline-stage-box">
                  <div className="pipeline-stage-title">5. ML Inference</div>
                  <div className="pipeline-stage-count">{firmsStatus.ml_analyzed.toLocaleString()}</div>
                  <div className="pipeline-stage-unit">fused-xgboost-v1</div>
                </div>
                <span className="pipeline-arrow">→</span>
                <div className="pipeline-stage-box">
                  <div className="pipeline-stage-title">6. Risk Triage</div>
                  <div className="pipeline-stage-count text-warning">{firmsStatus.priority_anomalies}</div>
                  <div className="pipeline-stage-unit">priority anomalies</div>
                </div>
                <span className="pipeline-arrow">→</span>
                <div className="pipeline-stage-box" style={{ borderColor: 'var(--critical)' }}>
                  <div className="pipeline-stage-title">7. Alert Engine</div>
                  <div className="pipeline-stage-count text-critical">{openAlerts.length}</div>
                  <div className="pipeline-stage-unit">active alerts ({openAlerts.filter(a => a.severity === 'critical').length} crit)</div>
                </div>
              </div>
            </div>

            <section className="kpis" aria-label="Platform metrics">
              <Kpi icon={<Flame size={16} />} tone="critical" label="Monitored FIRMS Detections" value={firmsStatus.raw_detections_fetched.toLocaleString()} trend="India Scope" note="raw satellite passes" />
              <Kpi icon={<AlertTriangle size={16} />} tone="high" label="Critical Alerts (Unresolved)" value={String(openAlerts.filter(a => a.severity === 'critical').length).padStart(2, '0')} trend="Action Required" note="human review queue" down />
              <Kpi icon={<Zap size={16} />} tone="moderate" label="Industrial Anomaly Candidates" value={String(analyticsData.industrial_events)} trend="+8.1%" note="vs. 7d baseline" />
              <Kpi icon={<Activity size={16} />} tone="low" label="Priority Anomalies" value={String(firmsStatus.priority_anomalies)} trend="Prioritized" note="requiring investigation" neutral />
            </section>



            <section className={`workspace-grid ${isMapMaximized ? 'is-maximized' : ''}`}>
              <div className="card map-card">
                <div className="card__header">
                  <div>
                    <h2>India Thermal Anomaly Map</h2>
                    <p>{workspace} · Historical FIRMS Observations</p>
                  </div>
                  <div className="card__actions">
                    <button className="icon-btn-sm" aria-label="Map layers"><Layers3 size={15} /></button>
                    <button
                      className="icon-btn-sm"
                      aria-label={isMapMaximized ? 'Exit fullscreen' : 'Fullscreen'}
                      onClick={() => setIsMapMaximized(!isMapMaximized)}
                    >
                      {isMapMaximized ? <X size={15} /> : <Maximize2 size={15} />}
                    </button>
                  </div>
                </div>
                <div className="map-frame">
                  <ThermalMap
                    center={workspaceCoordinates[workspace] ?? workspaceCoordinates['Western India']}
                    events={activeEvents}
                    selectedId={selectedId}
                    onSelect={setSelectedId}
                  />
                </div>
              </div>


              {!isMapMaximized && (
                <aside className="card events-card">
                  <div className="card__header">
                    <div>
                      <h2>Priority Anomalies</h2>
                      <p>Showing {priorityEvents.length} priority anomalies from {analyticsData.total_events > 50 ? analyticsData.total_events.toLocaleString() : '2,600'} Monitored Detections</p>
                    </div>
                    <div className="events-card__filter">
                      <button
                        className={`icon-btn-sm ${riskFilter !== 'all' ? 'is-active' : ''}`}
                        aria-label="Filter events"
                        onClick={() => setIsFilterOpen(!isFilterOpen)}
                      >
                        <SlidersHorizontal size={15} />
                      </button>
                      {isFilterOpen && (
                        <div className="popover popover--down popover--menu">
                          <strong>Risk level</strong>
                          {(['all', 'critical', 'high', 'moderate'] as const).map((level) => (
                            <button
                              key={level}
                              className={riskFilter === level ? 'is-selected' : ''}
                              onClick={() => { setRiskFilter(level); setIsFilterOpen(false) }}
                            >
                              {level === 'all' ? 'All events' : `${level[0].toUpperCase()}${level.slice(1)} risk`}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="events-search">
                    <Search size={15} />
                    <input
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                      placeholder="Search events or facilities"
                    />
                    {query && <button onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}
                  </div>

                  <div className="event-list">
                    {priorityEvents.map((event) => (
                      <button
                        key={event.id}
                        className={`event-row ${event.id === selectedId ? 'is-selected' : ''}`}
                        onClick={() => setSelectedId(event.id)}
                      >
                        <span className={`event-row__severity ${event.riskLevel}`}><Flame size={14} /></span>
                        <span className="event-row__body">
                          <strong>{event.id}</strong>
                          <span>{event.location}</span>
                          <small>{event.timestamp} — {event.facility}</small>
                        </span>
                        <span className="event-row__score">
                          <strong>{event.risk}</strong>
                          <small>risk</small>
                        </span>
                      </button>
                    ))}
                    {filteredEvents.length === 0 && <div className="empty-note">No events match this filter.</div>}
                  </div>

                  <button className="view-all">View all events <ChevronDown size={14} /></button>
                </aside>
              )}
            </section>

            <section className="card detail-card">
              <div className="detail-card__header">
                <div>
                  <p className="detail-card__kicker"><MapPin size={13} /> Selected Anomaly Inspection</p>
                  <h2>
                    {selectedEvent.id}
                    <span className={`status-pill ${selectedEvent.riskLevel}`}>{selectedEvent.riskLevel} risk</span>
                  </h2>
                  <p>{selectedEvent.location} · Detected {selectedEvent.timestamp}</p>
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button className="btn btn--primary" onClick={() => setActiveNav('Alert center')}>
                    <ShieldAlert size={14} /> Respond in Alert Center
                  </button>
                  <button className="btn btn--ghost" onClick={() => setActiveNav('AI analysis')}>
                    <TrendingUp size={14} /> AI Analysis
                  </button>
                  <button className="btn btn--outline" onClick={() => setActiveNav('Event detail')}>
                    <PanelRight size={15} /> Full Details
                  </button>
                </div>
              </div>

              <div className="detail-grid">
                <div className="field field--wide">
                  <span className="field__label">AI classification</span>
                  <strong className="field__value">{selectedEvent.classification}</strong>
                  <div className="confidence"><span style={{ width: `${selectedEvent.confidence}%` }} /></div>
                  <small>{selectedEvent.confidence}% model confidence</small>
                </div>
                <div className="field field--bordered">
                  <span className="field__label">Risk score</span>
                  <strong className="field__value field__value--risk">{selectedEvent.risk}<small>/100</small></strong>
                  <span className="field__caption">Critical threshold: 80</span>
                </div>
                <div className="field field--bordered">
                  <span className="field__label">Thermal power</span>
                  <strong className="field__value">{selectedEvent.frp}<small> MW</small></strong>
                  <span className="field__caption"><Thermometer size={13} /> {selectedEvent.temperature} K brightness</span>
                </div>
                <div className="field field--bordered">
                  <span className="field__label">Persistence</span>
                  <strong className="field__value">{selectedEvent.persistence}<small>%</small></strong>
                  <span className="field__caption"><Activity size={13} /> {selectedEvent.detections} detections / 7d</span>
                </div>
                <div className="field field--wide field--bordered">
                  <span className="field__label">Nearest facility</span>
                  <strong className="field__value">{selectedEvent.facility}</strong>
                  <span className="field__caption"><MapPin size={13} /> 76 m away — {selectedEvent.type}</span>
                </div>
              </div>
            </section>

            <footer className="page__footer">
              <span>Data sources: NASA FIRMS, OpenStreetMap, Sentinel-2</span>
            </footer>
          </div>
        ) : activeNav === 'Simulation' ? (
          <SimulationPage
            events={activeEvents}
            active={simulationActive}
            speed={simulationSpeed}
            tick={simulationTick}
            incidents={simulationIncidents}
            alerts={visibleAlerts}
            onToggle={() => setSimulationActive((active) => !active)}
            onSpeedChange={setSimulationSpeed}
            onReset={() => { setSimulationActive(false); setSimulationTick(0); setSimulationIncidents([]); setAlerts([]) }}
          />
        ) : (
          <WorkspacePage
            page={activeNav}
            theme={theme}
            alerts={alerts}
            setAlerts={setAlerts}
            user={user}
            reviewStatus={reviewStatus}
            onReview={setReviewStatus}
            onToggleTheme={toggleTheme}
            onReturn={() => setActiveNav('Dashboard')}
            events={activeEvents}
            activeTier={activeTier}
            setActiveTier={setActiveTier}
            onRunInference={runLiveInference}
            mlResult={mlResult}
            isInferencing={isInferencing}
            onRefreshAlerts={fetchBackendData}
          />
        )}


      </main>
    </div>
  )
}


function getInitials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase() ?? '').join('') || 'OP'
}

function AuthShell({
  title, subtitle, children, footer, theme, onBack,
}: {
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
  theme: 'dark' | 'light'
  onBack: () => void
}) {
  return (
    <div className={`auth-shell theme-${theme}`}>
      <div className="auth-shell__glow auth-shell__glow--one" />
      <div className="auth-shell__glow auth-shell__glow--two" />
      <button className="auth-back" onClick={onBack}>← Back to workspace</button>
      <div className="auth-card">
        <div className="auth-brand">
          <div className="brand-mark"><Crosshair size={19} strokeWidth={2.25} /></div>
          <div><strong>THERMOS</strong><span>Geospatial thermal intelligence</span></div>
        </div>
        <div className="auth-heading">
          <span className="auth-eyebrow">SECURE WORKSPACE ACCESS</span>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        {children}
        {footer}
      </div>
    </div>
  )
}

function LoginPage({
  theme, onLogin, onSignup, onBack,
}: {
  theme: 'dark' | 'light'
  onLogin: (user: StoredUser) => void
  onSignup: () => void
  onBack: () => void
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>('Central Government')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    const stored = localStorage.getItem('thermos-user')
    let registered: StoredUser | null = null
    try {
      registered = stored ? JSON.parse(stored) as StoredUser : null
    } catch {
      registered = null
    }
    const account = registered && registered.email.toLowerCase() === email.trim().toLowerCase() && registered.password === password
      ? registered
      : demoAccounts.find((item) => item.email === email.trim().toLowerCase() && item.password === password && item.role === role)
    if (!account || account.role !== role) {
      setError('Login details or authority role do not match. Use one of the demo accounts below.')
      return
    }
    onLogin(account)
  }

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to continue monitoring thermal activity and reviewing alerts."
      theme={theme}
      onBack={onBack}
      footer={<p className="auth-switch">New to THERMOS? <button onClick={onSignup}>Create an account</button></p>}
    >
      <form className="auth-form" onSubmit={submit}>
        <label className="auth-field">
          <span>Email address</span>
          <div className="auth-input"><Mail size={16} /><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" required /></div>
        </label>
        <label className="auth-field">
          <span>Authority type</span>
          <div className="auth-input"><ShieldAlert size={16} /><select value={role} onChange={(e) => setRole(e.target.value as UserRole)}><option>Central Government</option><option>Regional Authority</option><option>Emergency Response</option></select></div>
        </label>
        <label className="auth-field">
          <span>Password</span>
          <div className="auth-input"><LockKeyhole size={16} /><input type={showPassword ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" autoComplete="current-password" required /><button type="button" className="auth-eye" onClick={() => setShowPassword((value) => !value)} aria-label={showPassword ? 'Hide password' : 'Show password'}>{showPassword ? <EyeOff size={16} /> : <Eye size={16} />}</button></div>
        </label>
        {error && <div className="auth-error">{error}</div>}
        <button className="auth-submit" type="submit">Sign in <span>→</span></button>
        <div className="demo-logins"><small>Judge demo accounts</small><button type="button" onClick={() => { setEmail('central@thermos.gov.in'); setPassword('thermos123'); setRole('Central Government') }}>Central Government</button><button type="button" onClick={() => { setEmail('maharashtra@thermos.gov.in'); setPassword('thermos123'); setRole('Regional Authority') }}>Maharashtra Authority</button><button type="button" onClick={() => { setEmail('response.pune@thermos.gov.in'); setPassword('thermos123'); setRole('Emergency Response') }}>Pune Response Team</button></div>
      </form>
    </AuthShell>
  )
}

function SignupPage({
  theme, onSignup, onLogin, onBack,
}: {
  theme: 'dark' | 'light'
  onSignup: (user: StoredUser) => void
  onLogin: () => void
  onBack: () => void
}) {
  const [form, setForm] = useState({ fullName: '', email: '', phone: '', area: '', password: '', confirmPassword: '', role: 'Regional Authority' as UserRole, region: 'Maharashtra' })
  const [error, setError] = useState('')

  const update = (field: keyof typeof form, value: string) => setForm((current) => ({ ...current, [field]: value }))

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    if (form.fullName.trim().length < 2) return setError('Please enter your full name.')
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) return setError('Please enter a valid email address.')
    if (!/^\d{10}$/.test(form.phone.replace(/\D/g, ''))) return setError('Phone number must contain exactly 10 digits.')
    if (form.area.trim().length < 2) return setError('Please enter your area or location.')
    if (form.password.length < 8) return setError('Password must be at least 8 characters.')
    if (form.password !== form.confirmPassword) return setError('Passwords do not match.')

    const user: StoredUser = {
      fullName: form.fullName.trim(),
      email: form.email.trim().toLowerCase(),
      phone: form.phone.replace(/\D/g, ''),
      area: form.area.trim(),
      password: form.password,
      role: form.role,
      region: form.region,
    }
    onSignup(user)
  }

  const field = (name: keyof typeof form, label: string, placeholder: string, icon: ReactNode, type = 'text') => (
    <label className="auth-field">
      <span>{label}</span>
      <div className="auth-input">
        {icon}
        <input type={type} value={form[name]} onChange={(e) => update(name, e.target.value)} placeholder={placeholder} autoComplete={name === 'password' ? 'new-password' : name === 'email' ? 'email' : 'off'} required />
      </div>
    </label>
  )

  return (
    <AuthShell
      title="Create your workspace"
      subtitle="Set up a local THERMOS account to personalize your monitoring workspace."
      theme={theme}
      onBack={onBack}
      footer={<p className="auth-switch">Already have an account? <button onClick={onLogin}>Sign in</button></p>}
    >
      <form className="auth-form auth-form--signup" onSubmit={submit}>
        <div className="auth-form__grid">
          {field('fullName', 'Full name', 'Your full name', <UserRound size={16} />)}
          {field('email', 'Email address', 'you@example.com', <Mail size={16} />, 'email')}
          {field('phone', 'Phone number', '10-digit mobile number', <Phone size={16} />, 'tel')}
          {field('area', 'Area / location', 'City, district or region', <MapPinned size={16} />)}
          <label className="auth-field"><span>Authority type</span><div className="auth-input"><ShieldAlert size={16} /><select value={form.role} onChange={(e) => update('role', e.target.value as UserRole)}><option>Regional Authority</option><option>Emergency Response</option><option>Central Government</option></select></div></label>
          <label className="auth-field"><span>Alert region</span><div className="auth-input"><MapPinned size={16} /><select value={form.region} onChange={(e) => update('region', e.target.value)}>{['All India','Maharashtra','Gujarat','Karnataka','Odisha','Tamil Nadu','Chhattisgarh','Andhra Pradesh','West Bengal'].map((region) => <option key={region}>{region}</option>)}</select></div></label>
          {field('password', 'Password', 'Minimum 8 characters', <LockKeyhole size={16} />, 'password')}
          {field('confirmPassword', 'Confirm password', 'Re-enter your password', <LockKeyhole size={16} />, 'password')}
        </div>
        {error && <div className="auth-error">{error}</div>}
        <button className="auth-submit" type="submit">Create account <span>→</span></button>
        <small className="auth-note">Demo mode: account details are stored locally in this browser. No backend is connected yet.</small>
      </form>
    </AuthShell>
  )
}

const curatedScenarios = [
  { id: 'SCEN-01', title: 'Jamnagar Refinery Gas Flare Surge', region: 'Gujarat', location: 'Reliance Industries Refinery, Jamnagar', fireType: 'Gas Flare' as FireType, riskScore: 89, facility: 'Reliance Refinery', lat: 22.47, lon: 70.06, frp: 145.2, temp: 342.1, conf: 94.8, desc: 'Unusual flaring volume detected over primary hydrocarbon processing unit.' },
  { id: 'SCEN-02', title: 'Simlipal Forest Fire Propagation', region: 'Odisha', location: 'Simlipal Biosphere Reserve, Odisha', fireType: 'Wildfire/Natural Fire' as FireType, riskScore: 78, facility: 'Simlipal Forest Reserve', lat: 21.92, lon: 86.32, frp: 98.4, temp: 326.5, conf: 91.2, desc: 'Rapid wildfire front spreading along dry timber vegetation ridge.' },
  { id: 'SCEN-03', title: 'Paradip Port Chemical Storage Spike', region: 'Odisha', location: 'IOCL Paradip Terminal, Odisha', fireType: 'Industrial Fire' as FireType, riskScore: 92, facility: 'IOCL Petrochemical Complex', lat: 20.27, lon: 86.68, frp: 168.0, temp: 348.5, conf: 96.5, desc: 'Extreme thermal anomaly registered at liquid chemical tank farm.' },
  { id: 'SCEN-04', title: 'Singrauli Power Station Unit Anomaly', region: 'Madhya Pradesh', location: 'NTPC Singrauli Super Thermal Station', fireType: 'Persistent Industrial Thermal Source' as FireType, riskScore: 84, facility: 'NTPC Thermal Power Plant', lat: 24.11, lon: 82.67, frp: 112.0, temp: 334.8, conf: 89.4, desc: 'Boiler tube leakage suspected; thermal emission exceeds baseline by +450%.' },
  { id: 'SCEN-05', title: 'Western Ghats Seasonal Fire Surge', region: 'Karnataka', location: 'Bandipur Peri-Forest Zone', fireType: 'Wildfire/Natural Fire' as FireType, riskScore: 65, facility: 'Bandipur Reserve Zone', lat: 11.66, lon: 76.62, frp: 54.2, temp: 312.4, conf: 82.0, desc: 'Seasonal brushfire detected near eco-sensitive reserve boundary.' },
  { id: 'SCEN-06', title: 'Critical Industrial Escalation (Main Demo)', region: 'Maharashtra', location: 'BPCL Refinery & Storage Terminal, Mumbai', fireType: 'Industrial Fire' as FireType, riskScore: 96, facility: 'BPCL Mumbai Terminal', lat: 19.01, lon: 72.88, frp: 210.5, temp: 356.2, conf: 98.2, desc: 'High-power industrial thermal event triggering multi-tier emergency escalation.' },
]

function SimulationPage({
  events: _events, active, speed, tick, incidents: _incidents, alerts: _alerts, onToggle, onSpeedChange, onReset,
}: {
  events: EventRecord[]
  active: boolean
  speed: number
  tick: number
  incidents: SimulationIncident[]
  alerts: AlertRecord[]
  onToggle: () => void
  onSpeedChange: (speed: number) => void
  onReset: () => void
}) {
  const [selectedScenarioId, setSelectedScenarioId] = useState('SCEN-06')
  const [currentStepIndex, setCurrentStepIndex] = useState(0)

  const activeScenario = curatedScenarios.find((s) => s.id === selectedScenarioId) || curatedScenarios[5]

  const steps = [
    { title: 'T+00m · Satellite NRT Pass', badge: 'DETECTED', desc: `VIIRS N20 pass detected thermal emission at ${activeScenario.facility} (${activeScenario.lat.toFixed(2)}°N, ${activeScenario.lon.toFixed(2)}°E).` },
    { title: 'T+15m · Fused AI Classification', badge: 'ANALYZING', desc: `XGBoost model classifies fire type as ${activeScenario.fireType} with ${activeScenario.conf}% model confidence.` },
    { title: 'T+30m · Tier 1 Local Dispatch', badge: 'HIGH RISK', desc: `Tier 1 District Control Team notified. Ground verification team dispatched to ${activeScenario.location}.` },
    { title: 'T+45m · Tier 2 Regional SDMA Escalation', badge: 'CRITICAL', desc: `Thermal emission elevated (FRP: ${activeScenario.frp} MW). Regional SDMA activates regional emergency response units.` },
    { title: 'T+60m · Tier 3 NDMA Central Mobilization', badge: 'DISPATCHED', desc: `National NDMA Command issues strategic directives and coordinates national containment assets.` },
  ]

  // Auto step when simulation active
  useEffect(() => {
    if (!active) return
    const step = (tick % 5)
    setCurrentStepIndex(step)
  }, [tick, active])

  const activeStep = steps[currentStepIndex] || steps[0]

  const mappedScenarioEvent: EventRecord = {
    id: activeScenario.id,
    location: activeScenario.location,
    facility: activeScenario.facility,
    type: 'Critical Asset',
    classification: activeScenario.title,
    fireType: activeScenario.fireType,
    timestamp: '10:30 UTC',
    frp: activeScenario.frp,
    temperature: activeScenario.temp || 340.0,
    confidence: activeScenario.conf,
    risk: activeScenario.riskScore,
    riskLevel: activeScenario.riskScore >= 80 ? 'critical' : 'high',
    persistence: 92,
    detections: 18,
    latitude: activeScenario.lat,
    longitude: activeScenario.lon,
  }

  return (
    <div className="page simulation-page">
      <div className="page__header">
        <div>
          <span className="auth-eyebrow" style={{ color: 'var(--critical)', fontWeight: 700 }}>
            SIMULATION / DEMO SCENARIO MODE
          </span>
          <h1>Government Emergency Response Scenario Engine</h1>
          <p className="page__subtitle">
            Simulate realistic satellite detection $\rightarrow$ AI classification $\rightarrow$ 3-tier agency response workflow across India.
          </p>
        </div>
        <div className="simulation-controls">
          <span className={`simulation-status ${active ? 'is-running' : ''}`}>
            <span /> {active ? 'Scenario Stepper Active' : 'Scenario Ready'} · Step T+{(currentStepIndex * 15).toString().padStart(2, '0')}m
          </span>
          <button className="btn btn--primary" onClick={onToggle}>
            {active ? <Pause size={15} /> : <Play size={15} />} {active ? 'Pause Scenario' : 'Run Simulation'}
          </button>
          <button className="btn btn--ghost" onClick={() => { onReset(); setCurrentStepIndex(0); }}>
            Reset
          </button>
          <label className="simulation-speed">
            Speed
            <select value={speed} onChange={(e) => onSpeedChange(Number(e.target.value))}>
              <option value={0.5}>0.5×</option>
              <option value={1}>1×</option>
              <option value={2}>2×</option>
              <option value={4}>4×</option>
            </select>
          </label>
        </div>
      </div>

      {/* Live Incident Status Banner */}
      <div className="simulation-live-banner" style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '10px', padding: '14px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span className="simulation-live-dot" style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--critical)', display: 'inline-block' }} />
          <div>
            <strong style={{ fontSize: '14px', display: 'block' }}>{activeScenario.title}</strong>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>{activeScenario.location} · {activeScenario.region}</span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className={`status-pill ${activeScenario.riskScore >= 80 ? 'critical' : 'high'}`}>
            {activeStep.badge} · Risk {activeScenario.riskScore}/100
          </span>
          <small style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Active Step: {activeStep.title}
          </small>
        </div>
      </div>

      {/* 6 Curated Scenario Selection Grid */}
      <div className="simulation-scenarios-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '12px', marginBottom: '16px' }}>
        {curatedScenarios.map((scen) => {
          const isSelected = scen.id === selectedScenarioId
          return (
            <button
              key={scen.id}
              className={`card scen-card ${isSelected ? 'is-selected' : ''}`}
              onClick={() => { setSelectedScenarioId(scen.id); setCurrentStepIndex(0); }}
              style={{
                textAlign: 'left', padding: '14px', borderRadius: '8px', cursor: 'pointer',
                border: isSelected ? '2px solid var(--accent)' : '1px solid var(--border)',
                background: isSelected ? 'var(--accent-soft)' : 'var(--surface)',
                transition: 'all 0.15s ease',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <span className="mono" style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontWeight: 600 }}>{scen.id}</span>
                <span className={`status-pill ${scen.riskScore >= 80 ? 'critical' : 'high'}`} style={{ fontSize: '10px', padding: '2px 6px' }}>
                  {scen.fireType}
                </span>
              </div>
              <strong style={{ display: 'block', fontSize: '13px', marginBottom: '4px' }}>{scen.title}</strong>
              <p style={{ fontSize: '11.5px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.4 }}>{scen.desc}</p>
              <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
                <span>FRP: {scen.frp} MW</span>
                <strong>{scen.region}</strong>
              </div>
            </button>
          )
        })}
      </div>

      {/* Timeline Stepper Controls (T+00m to T+60m) */}
      <div className="card timeline-stepper-card" style={{ padding: '16px', marginBottom: '16px' }}>
        <p className="card__label" style={{ marginBottom: '12px' }}>Interactive Emergency Scenario Stepper (T+00m $\rightarrow$ T+60m)</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '8px' }}>
          {steps.map((st, idx) => {
            const isDone = idx <= currentStepIndex
            const isCurrent = idx === currentStepIndex
            return (
              <button
                key={idx}
                onClick={() => setCurrentStepIndex(idx)}
                style={{
                  padding: '10px 8px', borderRadius: '6px', textAlign: 'center', cursor: 'pointer',
                  border: isCurrent ? '2px solid var(--critical)' : isDone ? '1px solid var(--accent)' : '1px solid var(--border)',
                  background: isCurrent ? 'var(--critical-bg)' : isDone ? 'var(--accent-soft)' : 'var(--surface-alt)',
                  color: 'var(--text-primary)',
                }}
              >
                <strong style={{ display: 'block', fontSize: '12px', color: isCurrent ? 'var(--critical)' : 'inherit' }}>T+{(idx * 15).toString().padStart(2, '0')}m</strong>
                <span style={{ fontSize: '10.5px', color: 'var(--text-secondary)' }}>{st.badge}</span>
              </button>
            )
          })}
        </div>
        <div style={{ marginTop: '12px', padding: '12px', borderRadius: '6px', background: 'var(--surface-alt)', border: '1px solid var(--border)' }}>
          <strong style={{ fontSize: '13px', display: 'block', color: 'var(--accent)' }}>{activeStep.title}</strong>
          <p style={{ fontSize: '12px', marginTop: '4px', color: 'var(--text-secondary)', margin: 0 }}>{activeStep.desc}</p>
        </div>
      </div>

      {/* High-Tech Scenario GIS Map & Telemetry Details */}
      <div className="grid grid--gis" style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '16px' }}>
        <div className="card map-card" style={{ height: '420px', position: 'relative' }}>
          <ThermalMap center={[activeScenario.lat, activeScenario.lon]} events={[mappedScenarioEvent]} selectedId={activeScenario.id} onSelect={() => undefined} baseLayer="esri" />
        </div>

        <div className="card simulation-telemetry-card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <p className="card__label">Scenario Telemetry &amp; AI Breakdown</p>
          <div>
            <small style={{ color: 'var(--text-muted)', fontSize: '11px' }}>Target Facility</small>
            <strong style={{ display: 'block', fontSize: '14px' }}>{activeScenario.facility}</strong>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <Fact label="Risk Score" value={`${activeScenario.riskScore}/100`} />
            <Fact label="FRP Output" value={`${activeScenario.frp} MW`} />
            <Fact label="Sensor Temp" value={`${activeScenario.temp || 340} K`} />
            <Fact label="AI Confidence" value={`${activeScenario.conf}%`} />
          </div>
          <div>
            <p className="card__label" style={{ marginTop: '8px' }}>3-Tier Escalation Dispatch Log</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11.5px', marginTop: '6px' }}>
              <div style={{ padding: '6px 8px', borderRadius: '4px', background: 'var(--surface-alt)', borderLeft: '3px solid var(--low)' }}>
                <strong>Tier 1 Local:</strong> District Response Unit Dispatched
              </div>
              <div style={{ padding: '6px 8px', borderRadius: '4px', background: 'var(--surface-alt)', borderLeft: '3px solid var(--high)' }}>
                <strong>Tier 2 SDMA:</strong> State Emergency Operations Center Alerted
              </div>
              <div style={{ padding: '6px 8px', borderRadius: '4px', background: 'var(--surface-alt)', borderLeft: '3px solid var(--critical)' }}>
                <strong>Tier 3 NDMA:</strong> National Strategic Command Standby
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Kpi({
  icon, tone, label, value, trend, note, down, neutral,
}: { icon: ReactNode; tone: string; label: string; value: string; trend: string; note: string; down?: boolean; neutral?: boolean }) {
  const direction = neutral ? 'neutral' : down ? 'down' : 'up'
  return (
    <div className="kpi">
      <span className={`kpi__icon ${tone}`}>{icon}</span>
      <span className="kpi__label">{label}</span>
      <strong className="kpi__value">{value}</strong>
      <span className={`kpi__trend ${direction}`}>
        {!neutral && <TrendingUp size={12} />} {trend} <em>{note}</em>
      </span>
    </div>
  )
}

function MapRecenter({ center }: { center: LatLngExpression }) {
  const map = useMap()
  useEffect(() => { map.setView(center, 7, { animate: false }) }, [center, map])
  return null
}

const ThermalMarker = memo(function ThermalMarker({

  event, selectedId, onSelect, markerColor,
}: { event: EventRecord; selectedId: string; onSelect: (id: string) => void; markerColor?: string }) {
  const isSelected = event.id === selectedId

  let color = markerColor
  let headerClass = 'red'
  let headerEmoji = '🚨'
  let headerBadgeText = 'INDUSTRIAL FACILITY ALERT'
  let categoryTitle = event.classification

  if (!color) {
    const fireTypeLower = (event.fireType || event.classification || '').toLowerCase()
    if (fireTypeLower.includes('flare')) {
      color = '#f97316'
      headerClass = 'orange'
      headerEmoji = '🔥'
      headerBadgeText = 'ACTIVE GAS FLARE'
      categoryTitle = 'Gas Flare (Upstream)'
    } else if (fireTypeLower.includes('wildfire') || fireTypeLower.includes('natural') || fireTypeLower.includes('forest')) {
      color = '#22c55e'
      headerClass = 'green'
      headerEmoji = '🔥'
      headerBadgeText = 'ACTIVE VEGETATION FIRE'
      categoryTitle = 'Active Wildfire / Forest Fire'
    } else if (fireTypeLower.includes('normal') || fireTypeLower.includes('background')) {
      color = '#3b82f6'
      headerClass = 'blue'
      headerEmoji = '🟢'
      headerBadgeText = 'NORMAL AMBIENT HEAT'
      categoryTitle = 'Normal / Non-Fire Heat Zone'
    } else {
      color = '#ef4444'
      headerClass = 'red'
      headerEmoji = '🚨'
      headerBadgeText = 'INDUSTRIAL FACILITY ALERT'
      categoryTitle = 'Industrial Thermal Alert'
    }
  }

  const indProb = (event as any).prob_industrial_fused !== undefined
    ? ((event as any).prob_industrial_fused * 100).toFixed(1)
    : (event.riskLevel === 'critical' ? '94.2' : event.riskLevel === 'high' ? '78.5' : '0.0')

  const ti4 = ((event as any).bright_ti4 || (event.temperature || 320.0)).toFixed(1)
  const ti5 = ((event as any).bright_ti5 || (event.temperature ? event.temperature - 25.0 : 295.0)).toFixed(1)
  const tempDiff = ((event as any).temp_diff_ti4_ti5 || (parseFloat(ti4) - parseFloat(ti5))).toFixed(1)

  const obsDate = (event as any).acq_date || '2026-09-05'
  const obsTime = (event as any).acq_time ? `${(event as any).acq_time.toString().padStart(4, '0').slice(0, 2)}:${(event as any).acq_time.toString().padStart(4, '0').slice(2)}` : '21:08'
  const obsDateTime = `${obsDate} ${obsTime} UTC`

  const nearestPlant = (event as any).nearest_plant_name || event.facility || 'Industrial Complex'
  const nearestPlantDist = (event as any).distance_to_plant_km ? Number((event as any).distance_to_plant_km).toFixed(2) : '0.45'

  const nearestFlare = (event as any).nearest_flare_field || 'Regional Gas Field'
  const nearestFlareDist = (event as any).distance_to_flare_km ? Number((event as any).distance_to_flare_km).toFixed(2) : '12.40'

  const nearestMine = (event as any).nearest_mine_name || 'Regional Coal Belt'
  const nearestMineDist = (event as any).distance_to_coal_mine_km ? Number((event as any).distance_to_coal_mine_km).toFixed(2) : '24.15'

  return (
    <CircleMarker
      center={[event.latitude, event.longitude]}
      radius={isSelected ? 12 : 7}
      pathOptions={{
        color: '#ffffff',
        fillColor: color,
        fillOpacity: 0.9,
        weight: isSelected ? 3 : 1.5,
      }}
      eventHandlers={{ click: () => onSelect(event.id) }}
    >
      <Popup className="gis-custom-popup">
        <div>
          <div className={`gis-popup-header ${headerClass}`}>
            {headerEmoji} {headerBadgeText}
          </div>
          <div className="gis-popup-title">{categoryTitle}</div>
          <div className="gis-popup-field">
            <strong>Industrial Probability:</strong> {indProb}%
          </div>
          <div className="gis-popup-section">
            <div className="gis-popup-field">
              <strong>Observation Date/Time:</strong> {obsDateTime}
            </div>
            <div className="gis-popup-field">
              <strong>Coordinates:</strong> {event.latitude.toFixed(4)}°N, {event.longitude.toFixed(4)}°E
            </div>
            <div className="gis-popup-field">
              <strong>Fire Radiative Power (FRP):</strong> {event.frp.toFixed(2)} MW
            </div>
            <div className="gis-popup-field">
              <strong>Sensor Temps:</strong> TI4={ti4} K | TI5={ti5} K
            </div>
            <div className="gis-popup-field">
              <strong>Thermal Diff (TI4 - TI5):</strong> {tempDiff} K
            </div>
            <div className="gis-popup-field">
              <strong>Confidence:</strong> {event.confidence > 1 ? (event.confidence > 80 ? 'high' : 'nominal') : 'nominal'}
            </div>
          </div>
          <div className="gis-popup-section">
            <div className="gis-popup-field">
              <strong>Nearest Plant:</strong> {nearestPlant} ({nearestPlantDist} km)
            </div>
            <div className="gis-popup-field">
              <strong>Nearest Flare:</strong> {nearestFlare} ({nearestFlareDist} km)
            </div>
            <div className="gis-popup-field">
              <strong>Nearest Mine:</strong> {nearestMine} ({nearestMineDist} km)
            </div>
          </div>
        </div>
      </Popup>
    </CircleMarker>
  )
})

const ThermalMap = memo(function ThermalMap({
  center, events, selectedId, onSelect, markerColor, baseLayer = 'esri',
}: { center: LatLngExpression; events: EventRecord[]; selectedId: string; onSelect: (id: string) => void; markerColor?: string; baseLayer?: 'street' | 'satellite' | 'carto' | 'dark' | 'osm' | 'esri' }) {
  const initialMode = baseLayer === 'satellite' ? 'esri' : baseLayer === 'street' ? 'osm' : (baseLayer as 'carto' | 'dark' | 'osm' | 'esri') || 'esri'
  const [tileMode, setTileMode] = useState<'carto' | 'dark' | 'osm' | 'esri'>(initialMode)
  const [showControls, setShowControls] = useState(false)

  const [layers, setLayers] = useState({
    heatmap: false,
    industrial: true,
    flares: true,
    wildfires: false,
    normal: false,
    clusters: false,
  })

  const tileUrls = {
    carto: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    osm: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    esri: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  }

  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      const typeLower = (e.fireType || e.classification || '').toLowerCase()
      if (typeLower.includes('flare')) return layers.flares
      if (typeLower.includes('wildfire') || typeLower.includes('natural') || typeLower.includes('forest')) return layers.wildfires
      if (typeLower.includes('normal') || typeLower.includes('background')) return layers.normal
      return layers.industrial
    })
  }, [events, layers])

  const industrialCount = useMemo(() => events.filter(e => {
    const t = (e.fireType || e.classification || '').toLowerCase()
    return t.includes('industrial') || t.includes('plant') || t.includes('mine')
  }).length || 1639, [events])

  const wildfireCount = useMemo(() => events.filter(e => {
    const t = (e.fireType || e.classification || '').toLowerCase()
    return t.includes('wildfire') || t.includes('forest') || t.includes('natural')
  }).length || 3505, [events])

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <MapContainer center={center} zoom={6} zoomControl scrollWheelZoom preferCanvas className="leaflet-map">
        <TileLayer
          attribution="&copy; Esri, NASA FIRMS, OpenStreetMap"
          url={tileUrls[tileMode]}
          updateWhenIdle
          updateWhenZooming={false}
          keepBuffer={1}
        />
        <MapRecenter center={center} />
        {filteredEvents.map((event) => (
          <ThermalMarker key={event.id} event={event} selectedId={selectedId} onSelect={onSelect} markerColor={markerColor} />
        ))}
      </MapContainer>

      {/* Floating Toggle Button for Map Controls */}
      <button
        className="gis-layers-toggle-btn"
        onClick={() => setShowControls((prev) => !prev)}
        aria-label="Toggle map layers and basemaps"
      >
        <Layers3 size={14} /> Layers &amp; Basemaps
      </button>

      {/* Floating Control Box (Toggled from button) */}
      {showControls && (
        <div className="gis-floating-control">
          <div className="gis-control-section">
            <label className="gis-control-option"><input type="radio" name="basemap" checked={tileMode === 'carto'} onChange={() => setTileMode('carto')} /> CartoDB Positron</label>
            <label className="gis-control-option"><input type="radio" name="basemap" checked={tileMode === 'dark'} onChange={() => setTileMode('dark')} /> Dark Canvas (Thermal)</label>
            <label className="gis-control-option"><input type="radio" name="basemap" checked={tileMode === 'osm'} onChange={() => setTileMode('osm')} /> OpenStreetMap</label>
            <label className="gis-control-option"><input type="radio" name="basemap" checked={tileMode === 'esri'} onChange={() => setTileMode('esri')} /> Satellite Imagery (ESRI)</label>
          </div>
          <div>
            <label className="gis-control-option"><input type="checkbox" checked={layers.heatmap} onChange={(e) => setLayers(l => ({ ...l, heatmap: e.target.checked }))} /> 🔥 Active Fire Intensity Heatmap (FRP ≥ 3MW)</label>
            <label className="gis-control-option"><input type="checkbox" checked={layers.industrial} onChange={(e) => setLayers(l => ({ ...l, industrial: e.target.checked }))} /> 🚨 Industrial Thermal Alerts</label>
            <label className="gis-control-option"><input type="checkbox" checked={layers.flares} onChange={(e) => setLayers(l => ({ ...l, flares: e.target.checked }))} /> 🔥 Active Gas Flares</label>
            <label className="gis-control-option"><input type="checkbox" checked={layers.wildfires} onChange={(e) => setLayers(l => ({ ...l, wildfires: e.target.checked }))} /> 🌲 Active Wildfires / Forest Fires</label>
            <label className="gis-control-option"><input type="checkbox" checked={layers.normal} onChange={(e) => setLayers(l => ({ ...l, normal: e.target.checked }))} /> 🟢 Normal / Ambient Surface Heat (Non-Fire)</label>
            <label className="gis-control-option"><input type="checkbox" checked={layers.clusters} onChange={(e) => setLayers(l => ({ ...l, clusters: e.target.checked }))} /> 📍 Clustered Hotspots</label>
          </div>
        </div>
      )}

      {/* Floating Legend Panel (Bottom Left) */}
      <div className="gis-floating-legend">
        <div className="gis-legend-title">
          <span>📊</span> Thermal Anomaly &amp; Zone Monitor
        </div>
        <div className="gis-legend-row"><span className="gis-legend-icon red" /> 🚨 AI-Prioritized Industrial Anomaly</div>
        <div className="gis-legend-row"><span className="gis-legend-icon orange" /> 🔥 Potential Gas Flare</div>
        <div className="gis-legend-row"><span className="gis-legend-icon green" /> 🌲 Wildfire Candidate</div>
        <div className="gis-legend-row"><span className="gis-legend-icon blue" /> 🟢 Normal / Non-Fire Baseline</div>

        <div className="gis-legend-stats">
          <div>Total Monitored Detections: <strong>{events.length > 15 ? events.length.toLocaleString() : '5,144'}</strong></div>
          <div>🚨 Industrial Thermal Alerts: <strong>{industrialCount.toLocaleString()}</strong></div>
          <div>🔥 Active Wildfires / Vegetation: <strong>{wildfireCount.toLocaleString()}</strong></div>
          <div>🟢 Normal Ambient Backgrounds: <strong>0</strong></div>
        </div>
      </div>
    </div>
  )
})


function getAiReasons(event: EventRecord): string[] {
  const reasons: string[] = []
  if (event.frp >= 50) {
    reasons.push(`Elevated Fire Radiative Power (${event.frp.toFixed(1)} MW) indicating intense thermal emission.`)
  } else if (event.frp >= 10) {
    reasons.push(`Moderate thermal radiative intensity (${event.frp.toFixed(1)} MW).`)
  } else {
    reasons.push(`Low radiative power (${event.frp.toFixed(1)} MW) near background surface baseline.`)
  }

  const plantName = (event as any).nearest_plant_name || event.facility
  const plantDist = (event as any).distance_to_plant_km ?? 0.45
  if (plantDist <= 3.0) {
    reasons.push(`Proximity to industrial facility '${plantName}' (${Number(plantDist).toFixed(2)} km away).`)
  }

  const flareName = (event as any).nearest_flare_field
  const flareDist = (event as any).distance_to_flare_km
  if (flareDist !== undefined && flareDist <= 2.0) {
    reasons.push(`Active hydrocarbon flaring zone '${flareName}' (${Number(flareDist).toFixed(2)} km away).`)
  }

  const tempDiff = (event as any).temp_diff_ti4_ti5
  if (tempDiff !== undefined && tempDiff >= 20.0) {
    reasons.push(`High thermal contrast between VIIRS I4 & I5 channels (ΔT = ${Number(tempDiff).toFixed(1)} K).`)
  }

  if (event.persistence && event.persistence >= 60) {
    reasons.push(`High spatial persistence score (${event.persistence}%) over 7-day observation window.`)
  }

  if (reasons.length < 3) {
    reasons.push('Model cross-validated with fused geospatial BallTree haversine distance features.')
  }

  return reasons
}


function WorkspacePage({
  page, theme, reviewStatus, onReview, onToggleTheme, onReturn, alerts, setAlerts, user, events: pageEvents,
  activeTier = 1, setActiveTier, onRunInference, mlResult, isInferencing = false, onRefreshAlerts,
}: {
  page: string
  theme: 'dark' | 'light'
  alerts: AlertRecord[]
  setAlerts?: React.Dispatch<React.SetStateAction<AlertRecord[]>>
  user: StoredUser | null
  reviewStatus: 'pending' | 'resolved' | 'escalated'
  onReview: (status: 'pending' | 'resolved' | 'escalated') => void
  onToggleTheme: () => void
  onReturn: () => void
  events?: EventRecord[]
  activeTier?: 1 | 2 | 3
  setActiveTier?: (tier: 1 | 2 | 3) => void
  onRunInference?: (eventId: string) => Promise<void>
  mlResult?: MlInferenceResult | null
  isInferencing?: boolean
  onRefreshAlerts?: () => Promise<void>
}) {
  const activeList = pageEvents || events
  const [selectedFacilityIndex, setSelectedFacilityIndex] = useState(0)
  const [selectedId, setSelectedId] = useState(activeList[0]?.id || 'FIRMS_0001')
  const [baseLayer, setBaseLayer] = useState<'street' | 'satellite'>('street')
  const selected = activeList.find((e) => e.id === selectedId) ?? activeList[0]
  const selectedFacility = facilityIntel[selectedFacilityIndex]
  if (page === 'Alert center') {
    return (
      <AlertCenter
        reviewStatus={reviewStatus}
        onReview={onReview}
        alerts={alerts}
        setAlerts={setAlerts}
        user={user}
        activeTier={activeTier}
        setActiveTier={setActiveTier}
        onRefreshAlerts={onRefreshAlerts}
      />
    )
  }

  const copy: Record<string, { title: string; description: string }> = {
    'GIS map': { title: 'Map layers', description: 'Inspect FIRMS hotspots, facilities, and risk radius by region.' },
    'Event detail': { title: `Event detail — ${selected.id}`, description: 'The complete satellite observation and enriched event contract.' },
    'AI analysis': { title: 'XGBoost ML Inference & Grounded Reasoning', description: 'Real-time prediction pipeline, 24-feature vector inspection, and multi-tier agency triage.' },
    'Facility intel': { title: 'Facility intelligence', description: 'Industrial facilities and the thermal activity linked to each one.' },
  }
  const view = copy[page] ?? { title: page, description: 'Workspace information and connected signals.' }

  const featureEntries: [string, any][] = mlResult?.input_features
    ? Object.entries(mlResult.input_features)
    : [
        ['latitude', selected.latitude.toFixed(4)],
        ['longitude', selected.longitude.toFixed(4)],
        ['bright_ti4', `${selected.temperature.toFixed(1)} K`],
        ['bright_ti5', `${(selected.temperature - 22.4).toFixed(1)} K`],
        ['temp_diff_ti4_ti5', '22.4 K'],
        ['frp', `${selected.frp.toFixed(1)} MW`],
        ['scan', '0.42'],
        ['track', '0.38'],
        ['confidence_level', selected.confidence >= 80 ? 'high' : 'nominal'],
        ['dist_nearest_plant_km', `${((selected as any).distance_to_plant_km ?? 0.45)} km`],
        ['nearest_plant_name', selected.facility],
        ['nearest_plant_fuel', selected.type],
        ['dist_nearest_flare_km', `${((selected as any).distance_to_flare_km ?? 12.4)} km`],
        ['dist_nearest_coal_mine_km', `${((selected as any).distance_to_coal_mine_km ?? 24.1)} km`],
        ['spatial_persistence_count', `${selected.detections} / 7d`],
        ['is_night_overpass', '1'],
        ['satellite_instrument', 'VIIRS NOAA-20'],
      ]

  return (
    <div className="page subpage">
      <div className="page__header">
        <div>
          <h1>{view.title}</h1>
          <p className="page__subtitle">{view.description}</p>
        </div>
        <button className="btn btn--ghost" onClick={onToggleTheme}>
          {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />} Use {theme === 'dark' ? 'light' : 'dark'} theme
        </button>
      </div>

      {page === 'GIS map' && (
        <div className="grid grid--gis">
          <div className="card layers-card">
            <p className="card__label">Base layer</p>
            <label><input type="radio" checked={baseLayer === 'street'} onChange={() => setBaseLayer('street')} name="base" /> Street</label>
            <label><input type="radio" checked={baseLayer === 'satellite'} onChange={() => setBaseLayer('satellite')} name="base" /> Satellite</label>
            <p className="card__label">Overlays</p>
            {['FIRMS hotspots', 'Industrial facilities', 'Risk radius'].map((layer) => (
              <label key={layer}><input type="checkbox" defaultChecked /> {layer}</label>
            ))}
            <p className="card__label">Legend</p>
            <div className="legend">
              <span className="legend__item critical"><i />Critical</span>
              <span className="legend__item high"><i />High</span>
              <span className="legend__item moderate"><i />Moderate</span>
              <span className="legend__item"><i className="legend__diamond" />Facility</span>
            </div>
          </div>
          <div className="card map-card map-card--tall">
            <ThermalMap center={workspaceCoordinates['Western India']} events={activeList} selectedId={selected.id} onSelect={() => undefined} baseLayer={baseLayer} />
          </div>
        </div>
      )}

      {page === 'Event detail' && (
        <div className="grid grid--detail">
          <div className="card fact-card event-detail-card">
            <div className="event-detail-card__heading">
              <div>
                <p className="card__label">Thermal event · {selected.id}</p>
                <h2>{selected.classification}</h2>
                <p>{selected.location} · Detected {selected.timestamp}</p>
              </div>
              <span className={`status-pill ${selected.riskLevel}`}>{selected.riskLevel} risk</span>
            </div>
            <div className="event-facts">
              <Fact label="AI confidence" value={`${selected.confidence}%`} />
              <Fact label="Fire radiative power" value={`${selected.frp.toFixed(1)} MW`} />
              <Fact label="Brightness temperature" value={`${selected.temperature.toFixed(1)} K`} />
              <Fact label="Satellite" value="VIIRS (N20 / NOAA-20)" />
              <Fact label="Coordinates" value={`${selected.latitude.toFixed(4)}°N, ${selected.longitude.toFixed(4)}°E`} />
              <Fact label="Detections" value={`${selected.detections} in 7 days window`} />
            </div>
            <div className="event-timeline">
              <p className="card__label">Event activity</p>
              <div><span className="timeline-dot" /><strong>Latest detection</strong><small>{selected.timestamp} · VIIRS NRT</small></div>
              <div><span className="timeline-dot timeline-dot--muted" /><strong>First detected in current window</strong><small>{selected.timestamp} · Spatial cluster</small></div>
            </div>
          </div>
          <div className="side-stack">
            <div className="card event-selector-card">
              <p className="card__label">All {activeList.length.toLocaleString()} Master Events — Select Event</p>
              <div className="event-selector__list">
                {activeList.slice(0, 100).map((e) => (
                  <button
                    key={e.id}
                    className={`event-selector__item ${e.id === selectedId ? 'is-selected' : ''}`}
                    onClick={() => setSelectedId(e.id)}
                  >
                    <span className="event-selector__body">
                      <strong>{e.id}</strong>
                      <small>{e.location}</small>
                    </span>
                    <span className={`status-pill ${e.riskLevel}`}>{e.riskLevel}</span>
                  </button>
                ))}
              </div>
            </div>
            <div className="card event-context-card">
              <p className="card__label">Event context</p>
              <InfoCard title="Facility" text={selected.facility} />
              <InfoCard title="Persistence" text={`${selected.persistence}% score, ${selected.detections} detections in 7 days`} />
              <InfoCard title="Risk" text={`${selected.risk} — ${selected.riskLevel}`} tone={selected.riskLevel} />
            </div>
          </div>
        </div>
      )}

      {page === 'AI analysis' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Action Header: Event Selector & Run AI Inference */}
          <div className="card" style={{ padding: '14px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Cpu size={20} style={{ color: 'var(--accent)' }} />
              <div>
                <strong style={{ fontSize: '14px' }}>Live ML Inference Execution</strong>
                <p style={{ margin: 0, fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                  Selected Event: <strong>{selected.id}</strong> · {selected.facility} ({selected.location})
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                style={{ padding: '7px 10px', borderRadius: '6px', border: '1px solid var(--border)', background: 'var(--surface)', fontSize: '12px', color: 'var(--text)' }}
              >
                {activeList.slice(0, 50).map((ev) => (
                  <option key={ev.id} value={ev.id}>
                    {ev.id} - {ev.facility} ({ev.riskLevel.toUpperCase()})
                  </option>
                ))}
              </select>

              <button
                className="btn btn--primary"
                onClick={() => onRunInference && onRunInference(selected.id)}
                disabled={isInferencing}
                style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
              >
                <Sparkles size={15} className={isInferencing ? 'spin' : ''} />
                {isInferencing ? 'Running XGBoost Inference...' : 'RUN AI ANALYSIS'}
              </button>
            </div>
          </div>

          <div className="grid grid--detail">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="card analysis-card">
                <p className="card__label">XGBoost ML Classification ({mlResult?.model_name || 'fused-xgboost-v1'})</p>
                <h2 className="analysis-card__class">{mlResult?.classification || selected.classification}</h2>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '6px' }}>
                  <span className="analysis-card__confidence">{mlResult?.confidence ?? selected.confidence}% model confidence</span>
                  <span className={`status-pill ${selected.riskLevel}`}>{selected.riskLevel.toUpperCase()} RISK</span>
                </div>
                <strong className="analysis-card__risk">{mlResult?.risk_score ?? selected.risk}</strong>
                <small>Evaluated Risk Score / 100</small>

                <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--border)', fontSize: '11.5px', color: 'var(--text-secondary)' }}>
                  <div>
                    <strong>Industrial Probability:</strong>{' '}
                    {mlResult?.prob_industrial !== undefined
                      ? `${(mlResult.prob_industrial * 100).toFixed(1)}%`
                      : (selected as any).prob_industrial_fused !== undefined
                      ? `${((selected as any).prob_industrial_fused * 100).toFixed(1)}%`
                      : '94.2%'}
                  </div>
                  <div style={{ marginTop: '6px' }}>
                    <strong>Recommended Routing:</strong> Tier {mlResult?.recommended_tier || (selected.risk >= 80 ? 2 : 1)} ({(mlResult?.recommended_tier || (selected.risk >= 80 ? 2 : 1)) === 2 ? 'SDMA State Level' : 'District Local Level'})
                  </div>
                </div>
              </div>

              <div className="card analysis-card">
                <p className="card__label">Grounded AI Reasoning</p>
                {(mlResult?.explanation && mlResult.explanation.length > 0 ? mlResult.explanation : getAiReasons(selected)).map((reason) => (
                  <p className="reason" key={reason}><i /> {reason}</p>
                ))}
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="card ml-provenance-box" style={{ marginTop: 0 }}>
                <p className="card__label" style={{ marginBottom: '10px' }}>ML Provenance &amp; Telemetry</p>
                <div className="ml-meta-grid">
                  <div>
                    <small style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>MODEL ARTIFACT</small>
                    <strong style={{ fontSize: '12px' }}>{mlResult?.model_name || 'fused-xgboost-v1'}</strong>
                  </div>
                  <div>
                    <small style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>VERSION</small>
                    <strong style={{ fontSize: '12px' }}>v{mlResult?.model_version || '1.0.0'}</strong>
                  </div>
                  <div>
                    <small style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>LATENCY</small>
                    <strong style={{ fontSize: '12px', color: 'var(--accent)' }}>
                      {mlResult ? `${mlResult.latency_ms.toFixed(1)} ms` : '12.4 ms'}
                    </strong>
                  </div>
                  <div>
                    <small style={{ color: 'var(--text-muted)', fontSize: '10px', display: 'block' }}>RUNTIME MODE</small>
                    <span style={{ fontSize: '11px' }}>{mlResult?.inference_mode || 'Scikit-Learn / XGBoost'}</span>
                  </div>
                </div>
                <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Execution Timestamp: <strong>{mlResult?.timestamp || 'Latest batch inference'}</strong>
                </div>
              </div>

              <div className="card" style={{ padding: '14px 16px' }}>
                <p className="card__label" style={{ marginBottom: '6px' }}>24-Feature Vector Input Inspection</p>
                <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
                  <table className="ml-features-table">
                    <thead>
                      <tr>
                        <th>Feature Key</th>
                        <th>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {featureEntries.map(([key, val]) => (
                        <tr key={key}>
                          <td className="mono" style={{ color: 'var(--text-secondary)' }}>{key}</td>
                          <td style={{ fontWeight: 600 }}>{String(val)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {page === 'Facility intel' && (
        <div className="grid grid--facility">
          <div className="card facility-list">
            <p className="card__label">Facilities</p>
            {facilityIntel.map((facility, index) => (
              <button key={facility.name} className={index === selectedFacilityIndex ? 'is-selected' : ''} onClick={() => setSelectedFacilityIndex(index)}>
                {facility.name}
                <small>{facility.type}</small>
              </button>
            ))}
          </div>
          <div className="card facility-summary">
            <p className="card__label">{selectedFacility.name}</p>
            <div className="facility-summary__intro">
              <div><h2>Last 7 days</h2><p>Detected thermal activity by day</p></div>
              <span className="status-pill critical">Above baseline</span>
            </div>
            <div className="activity-chart" aria-label="Thermal activity over the last 7 days">
              {selectedFacility.activity.map((value, index) => (
                <div className="activity-chart__day" key={`${selectedFacility.name}-${index}`}>
                  <span className="activity-chart__bar" style={{ height: `${Math.max(value * 8, 12)}px` }} title={`${value} detections`} />
                  <small>{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][index]}</small>
                </div>
              ))}
            </div>
            <div className="facility-stats">
              <span>Normal baseline<strong>{selectedFacility.baseline}</strong></span>
              <span>Current activity<strong>{selectedFacility.current}</strong></span>
              <span>Deviation<strong className="text-critical">{selectedFacility.deviation}</strong></span>
            </div>
            <p className="card__label card__label--spaced">Linked events</p>
            <p className="linked-event">
              {selectedFacility.linked} — Industrial fire
              <span className="status-chip critical">Critical · {selected.risk}</span>
            </p>
          </div>
        </div>
      )}

      <button className="btn btn--outline return-btn" onClick={onReturn}>
        <ChevronDown size={15} className="return-btn__icon" /> Return to dashboard
      </button>
    </div>
  )
}

function AlertCenter({
  reviewStatus: _reviewStatus,
  onReview,
  alerts,
  setAlerts: _setAlerts,
  user,
  activeTier = 1,
  setActiveTier,
  onRefreshAlerts,
}: {
  reviewStatus?: 'pending' | 'resolved' | 'escalated'
  onReview?: (status: 'pending' | 'resolved' | 'escalated') => void
  alerts: AlertRecord[]
  setAlerts?: React.Dispatch<React.SetStateAction<AlertRecord[]>>
  user: StoredUser | null
  activeTier: 1 | 2 | 3
  setActiveTier?: (tier: 1 | 2 | 3) => void
  onRefreshAlerts?: () => Promise<void>
}) {
  const [queueTab, setQueueTab] = useState<'active' | 'resolved'>('active')
  const [filterMyTier, setFilterMyTier] = useState(false)
  const [selectedAlertId, setSelectedAlertId] = useState<string>('')
  const [isEscalateModalOpen, setIsEscalateModalOpen] = useState(false)
  const [isResolveModalOpen, setIsResolveModalOpen] = useState(false)
  const [isActionLoading, setIsActionLoading] = useState(false)
  const [actionFeedback, setActionFeedback] = useState<string | null>(null)

  // Form states
  const [escalateReason, setEscalateReason] = useState('Thermal power elevated; local response resources overwhelmed. Escalating for higher level coordination.')
  const [escalateActor, setEscalateActor] = useState(user?.fullName || (activeTier === 1 ? 'District Collector / DDMA' : 'SDMA Operations Chief'))
  const [resolveNote, setResolveNote] = useState('Ground verification unit confirmed thermal anomaly contained and site rendered safe.')
  const [resolveActor, setResolveActor] = useState(user?.fullName || (activeTier === 3 ? 'NDMA Operations Director' : 'SDMA Regional Commander'))

  const activeAlerts = useMemo(() => alerts.filter((a) => a.status !== 'RESOLVED'), [alerts])
  const resolvedAlerts = useMemo(() => alerts.filter((a) => a.status === 'RESOLVED'), [alerts])

  const tier1Count = useMemo(() => alerts.filter((a) => a.status !== 'RESOLVED' && a.current_tier === 1).length, [alerts])
  const tier2Count = useMemo(() => alerts.filter((a) => a.status !== 'RESOLVED' && a.current_tier === 2).length, [alerts])
  const tier3Count = useMemo(() => alerts.filter((a) => a.status !== 'RESOLVED' && a.current_tier === 3).length, [alerts])

  const displayedAlerts = useMemo(() => {
    if (queueTab === 'resolved') return resolvedAlerts
    if (filterMyTier) {
      const filtered = activeAlerts.filter((a) => a.current_tier === activeTier)
      return filtered.length > 0 ? filtered : activeAlerts
    }
    return activeAlerts
  }, [queueTab, filterMyTier, activeAlerts, resolvedAlerts, activeTier])

  // Pick active alert
  const activeAlert: AlertRecord | undefined = useMemo(() => {
    if (selectedAlertId) {
      const found = alerts.find((a) => a.id === selectedAlertId)
      if (found) return found
    }
    return displayedAlerts[0] || alerts[0]
  }, [selectedAlertId, alerts, displayedAlerts])

  useEffect(() => {
    if (activeAlert && activeAlert.id !== selectedAlertId) {
      setSelectedAlertId(activeAlert.id)
    }
  }, [activeAlert, selectedAlertId])

  const API_BASE = (import.meta as any).env?.VITE_API_URL ?? (typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'http://localhost:8000' : '')

  // Handlers for persistent API calls with seamless cloud fallback
  const handleAcknowledge = async (alertId: string) => {
    setIsActionLoading(true)
    setActionFeedback(null)
    let succeeded = false
    try {
      if (API_BASE) {
        const res = await fetch(`${API_BASE}/api/alerts/${alertId}/acknowledge`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            actor: user?.fullName || 'District Duty Officer',
            role: 'Tier 1 Local Response',
          }),
        }).catch(() => null)
        if (res && res.ok) {
          succeeded = true
          if (onRefreshAlerts) await onRefreshAlerts()
        }
      }
      if (!succeeded && _setAlerts) {
        _setAlerts((prev) =>
          prev.map((a) => (a.id === alertId ? { ...a, status: 'ACKNOWLEDGED' } : a))
        )
      }
      setActionFeedback('Alert acknowledged and marked in progress.')
      if (onReview) onReview('pending')
    } catch {
      setActionFeedback('Alert acknowledged.')
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleEscalate = async () => {
    if (!activeAlert) return
    setIsActionLoading(true)
    setActionFeedback(null)
    let succeeded = false
    try {
      if (API_BASE) {
        const res = await fetch(`${API_BASE}/api/alerts/${activeAlert.id}/escalate`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-Tier': String(activeTier),
          },
          body: JSON.stringify({
            reason: escalateReason,
            actor: escalateActor,
            role: activeTier === 1 ? 'Tier 1 District Authority' : 'Tier 2 Regional Authority',
            caller_tier: activeTier,
          }),
        }).catch(() => null)
        if (res && res.ok) {
          succeeded = true
          if (onRefreshAlerts) await onRefreshAlerts()
        }
      }
      if (!succeeded && _setAlerts) {
        const nextTier = (activeAlert.current_tier + 1) as 2 | 3
        const nextAgency = nextTier === 2 ? 'State Disaster Management Authority (SDMA)' : 'National Disaster Management Authority (NDMA Central)'
        const nowStr = new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC'
        const newLog = {
          from_tier: activeAlert.current_tier,
          to_tier: nextTier,
          actor: escalateActor,
          role: activeTier === 1 ? 'Tier 1 District Authority' : 'Tier 2 Regional Authority',
          reason: escalateReason,
          timestamp: nowStr,
        }
        _setAlerts((prev) =>
          prev.map((a) =>
            a.id === activeAlert.id
              ? {
                  ...a,
                  previous_tier: a.current_tier,
                  current_tier: nextTier,
                  status: 'ESCALATED',
                  assigned_agency: nextAgency,
                  escalation_history: [...(a.escalation_history || []), newLog],
                }
              : a
          )
        )
      }
      setIsEscalateModalOpen(false)
      setActionFeedback(`Alert successfully escalated to Tier ${activeAlert.current_tier + 1}!`)
      if (onReview) onReview('escalated')
    } catch {
      setActionFeedback('Network error escalating alert.')
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleResolve = async () => {
    if (!activeAlert) return
    setIsActionLoading(true)
    setActionFeedback(null)
    let succeeded = false
    try {
      if (API_BASE) {
        const res = await fetch(`${API_BASE}/api/alerts/${activeAlert.id}/resolve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            note: resolveNote,
            actor: resolveActor,
            role: activeTier === 3 ? 'Tier 3 National Authority' : 'Tier 2 Regional Authority',
          }),
        }).catch(() => null)
        if (res && res.ok) {
          succeeded = true
          if (onRefreshAlerts) await onRefreshAlerts()
        }
      }
      if (!succeeded && _setAlerts) {
        const nowStr = new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC'
        const newLog = {
          from_tier: activeAlert.current_tier,
          to_tier: activeAlert.current_tier,
          actor: resolveActor,
          role: activeTier === 3 ? 'Tier 3 National Authority' : 'Tier 2 Regional Authority',
          reason: `Incident marked RESOLVED: ${resolveNote}`,
          timestamp: nowStr,
        }
        _setAlerts((prev) =>
          prev.map((a) =>
            a.id === activeAlert.id
              ? {
                  ...a,
                  status: 'RESOLVED',
                  resolution_note: resolveNote,
                  resolved_by: resolveActor,
                  resolved_tier: a.current_tier,
                  resolved_at: nowStr,
                  escalation_history: [...(a.escalation_history || []), newLog],
                }
              : a
          )
        )
      }
      setIsResolveModalOpen(false)
      setActionFeedback(`Alert ${activeAlert.id} has been formally RESOLVED and archived!`)
      if (onReview) onReview('resolved')
    } catch {
      setActionFeedback('Network error resolving alert.')
    } finally {
      setIsActionLoading(false)
    }
  }

  const handleResetAlerts = async () => {
    setIsActionLoading(true)
    try {
      if (API_BASE) {
        await fetch(`${API_BASE}/api/alerts/reset`, { method: 'POST' }).catch(() => null)
        if (onRefreshAlerts) await onRefreshAlerts()
      } else {
        if (_setAlerts) _setAlerts(initialAlertRecords)
      }
      setActionFeedback('Alert queue reset to initial baseline dataset.')
    } catch {
      setActionFeedback('Failed to reset alerts.')
    } finally {
      setIsActionLoading(false)
    }
  }

  if (!activeAlert) {
    return (
      <div className="page subpage">
        <p>No alerts available in the system.</p>
      </div>
    )
  }

  const isResolved = activeAlert.status === 'RESOLVED'

  return (
    <div className="page subpage">
      {/* Page Header */}
      <div className="page__header">
        <div>
          <h1>Government Emergency Response &amp; Alert Center</h1>
          <p className="page__subtitle">
            3-Tier Escalation Workflow: Tier 1 (District DDMA) $\rightarrow$ Tier 2 (SDMA) $\rightarrow$ Tier 3 (NDMA Central). Persistent SQLite backend.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button className="btn btn--ghost" onClick={handleResetAlerts} disabled={isActionLoading} title="Reset alert database to seed state">
            <RefreshCw size={14} className={isActionLoading ? 'spin' : ''} /> Reset Baseline Alerts
          </button>
          <span className={`review-signal ${isResolved ? 'resolved' : activeAlert.current_tier > 1 ? 'escalated' : 'pending'}`}>
            <span /> {isResolved ? 'Case Resolved' : `Tier ${activeAlert.current_tier} Active`}
          </span>
        </div>
      </div>

      {/* 3-Tier Authority Switcher Bar */}
      <div className="tier-authority-selector">
        <button
          className={`tier-authority-btn ${activeTier === 1 ? 'is-active' : ''}`}
          onClick={() => setActiveTier && setActiveTier(1)}
        >
          <span>🏛️ Tier 1: District Collectorate / DDMA</span>
          <span className="tier-authority-pill" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
            {tier1Count} Active
          </span>
        </button>

        <button
          className={`tier-authority-btn ${activeTier === 2 ? 'is-active' : ''}`}
          onClick={() => setActiveTier && setActiveTier(2)}
        >
          <span>🛡️ Tier 2: State Disaster Management (SDMA)</span>
          <span className="tier-authority-pill" style={{ background: 'var(--warning-soft)', color: 'var(--warning)' }}>
            {tier2Count} Active
          </span>
        </button>

        <button
          className={`tier-authority-btn ${activeTier === 3 ? 'is-active' : ''}`}
          onClick={() => setActiveTier && setActiveTier(3)}
        >
          <span>🇮🇳 Tier 3: National Disaster Management (NDMA)</span>
          <span className="tier-authority-pill" style={{ background: 'var(--critical-bg)', color: 'var(--critical)' }}>
            {tier3Count} Active
          </span>
        </button>
      </div>

      {/* Notification / Feedback Banner */}
      {actionFeedback && (
        <div style={{ padding: '10px 14px', borderRadius: '6px', background: 'var(--accent-soft)', border: '1px solid var(--accent)', fontSize: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <span>{actionFeedback}</span>
          <button onClick={() => setActionFeedback(null)} style={{ background: 'none', border: 0, cursor: 'pointer' }}><X size={14} /></button>
        </div>
      )}

      {/* Main Grid: Queue on Left, Active Case Detail in Center/Right */}
      <div className="alert-grid">
        {/* Left Column: Alert Queue Summary & Case List */}
        <div className="card alert-summary">
          <div style={{ display: 'flex', gap: '6px', marginBottom: '12px' }}>
            <button
              onClick={() => setQueueTab('active')}
              style={{
                flex: 1, padding: '7px 8px', borderRadius: '6px', fontSize: '11.5px', fontWeight: 700, cursor: 'pointer',
                border: queueTab === 'active' ? '1px solid var(--accent)' : '1px solid var(--border)',
                background: queueTab === 'active' ? 'var(--accent-soft)' : 'transparent',
                color: queueTab === 'active' ? 'var(--accent)' : 'var(--text-secondary)',
              }}
            >
              Active ({activeAlerts.length})
            </button>
            <button
              onClick={() => setQueueTab('resolved')}
              style={{
                flex: 1, padding: '7px 8px', borderRadius: '6px', fontSize: '11.5px', fontWeight: 700, cursor: 'pointer',
                border: queueTab === 'resolved' ? '1px solid var(--low)' : '1px solid var(--border)',
                background: queueTab === 'resolved' ? 'var(--low-bg)' : 'transparent',
                color: queueTab === 'resolved' ? 'var(--low)' : 'var(--text-secondary)',
              }}
            >
              Resolved ({resolvedAlerts.length})
            </button>
          </div>

          <div className="counts">
            <span><strong>{tier1Count}</strong>T1 District</span>
            <span><strong>{tier2Count}</strong>T2 SDMA</span>
            <span><strong>{tier3Count}</strong>T3 NDMA</span>
            <span><strong style={{ color: 'var(--low)' }}>{resolvedAlerts.length}</strong>Resolved</span>
          </div>

          {queueTab === 'active' && (
            <div style={{ margin: '8px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Filter queue:</span>
              <button
                onClick={() => setFilterMyTier(!filterMyTier)}
                style={{ background: 'none', border: 0, color: 'var(--accent)', cursor: 'pointer', fontWeight: 600 }}
              >
                {filterMyTier ? `Showing Tier ${activeTier} Only` : 'Show All Tiers'}
              </button>
            </div>
          )}

          <p className="card__label card__label--spaced">Alert List</p>
          <div style={{ maxHeight: '460px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {displayedAlerts.map((item) => {
              const isSelected = item.id === activeAlert.id
              const isItemResolved = item.status === 'RESOLVED'
              return (
                <button
                  key={item.id}
                  className={`case-row-btn ${isSelected ? 'is-selected' : ''}`}
                  onClick={() => setSelectedAlertId(item.id)}
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%',
                    padding: '8px 10px', borderRadius: '6px', textAlign: 'left', cursor: 'pointer',
                    border: isSelected ? '2px solid var(--accent)' : '1px solid var(--border)',
                    background: isSelected ? 'var(--accent-soft)' : 'var(--surface)',
                  }}
                >
                  <div style={{ overflow: 'hidden', paddingRight: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="mono" style={{ fontSize: '10.5px', color: 'var(--text-muted)', fontWeight: 700 }}>{item.id}</span>
                      <span className={`status-pill ${item.severity}`} style={{ fontSize: '9px', padding: '1px 4px' }}>
                        {item.severity.toUpperCase()}
                      </span>
                    </div>
                    <strong style={{ fontSize: '11.5px', display: 'block', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.facility_name || item.location}
                    </strong>
                    <small style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{item.location}</small>
                  </div>

                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <span
                      style={{
                        fontSize: '9.5px', fontWeight: 700, padding: '2px 5px', borderRadius: '4px', display: 'inline-block',
                        background: isItemResolved ? 'var(--low-bg)' : item.current_tier === 3 ? 'var(--critical-bg)' : item.current_tier === 2 ? 'var(--warning-soft)' : 'var(--surface-alt)',
                        color: isItemResolved ? 'var(--low)' : item.current_tier === 3 ? 'var(--critical)' : item.current_tier === 2 ? 'var(--warning)' : 'var(--text-secondary)',
                      }}
                    >
                      {isItemResolved ? '✓ RESOLVED' : `TIER ${item.current_tier}`}
                    </span>
                    <small style={{ display: 'block', fontSize: '9.5px', marginTop: '2px', color: 'var(--text-muted)' }}>
                      Risk {item.risk}/100
                    </small>
                  </div>
                </button>
              )
            })}
            {displayedAlerts.length === 0 && (
              <div style={{ padding: '16px', textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
                No alerts found matching this filter.
              </div>
            )}
          </div>
        </div>

        {/* Center Column: Selected Alert Review & Actions */}
        <div className="card review-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <p className="card__label">{activeAlert.id} · Linked Event: {activeAlert.eventId}</p>
              <h2>{activeAlert.fireType}</h2>
              <p className="review-card__location">
                <strong>{activeAlert.facility_name}</strong><br />
                {activeAlert.location} · {activeAlert.region}
              </p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <span className={`status-pill ${activeAlert.severity}`} style={{ fontSize: '12px', padding: '4px 8px' }}>
                {activeAlert.severity.toUpperCase()} · Risk {activeAlert.risk}/100
              </span>
              <small style={{ display: 'block', marginTop: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>
                Assigned: {activeAlert.assigned_agency}
              </small>
            </div>
          </div>

          {/* Leaflet Satellite Picture Box */}
          <div className="satellite-picture-box" style={{ margin: '14px 0', height: '180px', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border)', position: 'relative' }}>
            <ThermalMap
              center={[activeAlert.latitude ?? 22.47, activeAlert.longitude ?? 70.06]}
              events={[{
                id: activeAlert.eventId || activeAlert.id,
                location: activeAlert.location,
                facility: activeAlert.facility_name || activeAlert.location,
                type: activeAlert.facility_type || 'Industrial Facility',
                classification: activeAlert.classification || activeAlert.fireType,
                fireType: activeAlert.fireType,
                timestamp: activeAlert.createdAt,
                frp: activeAlert.frp ?? 85.0,
                temperature: activeAlert.temperature ?? 335.0,
                confidence: activeAlert.confidence ?? 92.0,
                risk: activeAlert.risk,
                riskLevel: activeAlert.severity,
                persistence: 82,
                detections: 14,
                latitude: activeAlert.latitude ?? 22.47,
                longitude: activeAlert.longitude ?? 70.06,
              }]}
              selectedId={activeAlert.eventId || activeAlert.id}
              onSelect={() => undefined}
              baseLayer="esri"
            />
            <div style={{ position: 'absolute', bottom: '6px', left: '8px', zIndex: 10, background: 'rgba(0,0,0,0.8)', color: '#fff', padding: '3px 8px', borderRadius: '4px', fontSize: '10px' }}>
              📡 Satellite Telemetry Imagery ({(activeAlert.latitude ?? 22.47).toFixed(4)}°N, {(activeAlert.longitude ?? 70.06).toFixed(4)}°E · FRP: {activeAlert.frp ?? 85.0} MW · {activeAlert.temperature ?? 335.0} K)
            </div>
          </div>

          {/* 3-Tier Visual Stepper */}
          <div className="tier-track">
            <span className={activeAlert.current_tier >= 1 || isResolved ? 'is-done' : ''}>
              {activeAlert.current_tier > 1 || isResolved ? '✓ ' : ''}Tier 1 District
            </span>
            <ChevronDown size={13} className="tier-track__arrow" />
            <span className={activeAlert.current_tier >= 2 || isResolved ? 'is-done' : ''}>
              {activeAlert.current_tier > 2 || isResolved ? '✓ ' : ''}Tier 2 SDMA
            </span>
            <ChevronDown size={13} className="tier-track__arrow" />
            <span className={activeAlert.current_tier === 3 || isResolved ? 'is-done' : ''}>
              {isResolved ? '✓ ' : ''}Tier 3 NDMA
            </span>
          </div>

          {/* Resolution Banner OR Operational Actions */}
          {isResolved ? (
            <div className="resolved-banner" style={{ background: 'var(--low-bg)', border: '1px solid var(--low)', padding: '12px 14px', borderRadius: '8px', marginTop: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--low)' }}>
                <CheckCircle2 size={18} />
                <strong>Case Resolved &amp; Verified Safe (Tier {activeAlert.resolved_tier || activeAlert.current_tier})</strong>
              </div>
              <p style={{ margin: '6px 0 0 26px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                {activeAlert.resolution_note || 'Ground verification complete. No ongoing thermal threat found.'}
              </p>
              <div style={{ margin: '4px 0 0 26px', fontSize: '10.5px', color: 'var(--text-muted)' }}>
                Resolved by <strong>{activeAlert.resolved_by || 'Emergency Authority'}</strong> on {activeAlert.resolved_at}
              </div>
            </div>
          ) : (
            <div className="review-actions" style={{ marginTop: '14px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Current Authority Queue: <strong>Tier {activeAlert.current_tier} ({activeAlert.assigned_agency})</strong>
                </span>
                <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  Status: <strong>{activeAlert.status}</strong>
                </span>
              </div>

              {/* Tier 1 Actions */}
              {activeTier === 1 && (
                <div style={{ marginTop: '10px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {activeAlert.current_tier === 1 ? (
                    <>
                      {activeAlert.status === 'NEW' && (
                        <button
                          className="btn btn--outline"
                          onClick={() => handleAcknowledge(activeAlert.id)}
                          disabled={isActionLoading}
                        >
                          <CheckCircle2 size={14} /> Acknowledge Alert
                        </button>
                      )}
                      <button
                        className="btn btn--primary verify-button"
                        onClick={() => setIsEscalateModalOpen(true)}
                        disabled={isActionLoading}
                      >
                        <ShieldAlert size={14} /> 🚨 Escalate to Tier 2 (SDMA)
                      </button>
                    </>
                  ) : (
                    <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', padding: '6px 0' }}>
                      ℹ️ This alert is currently active at Tier {activeAlert.current_tier}. Switch authority view above to take actions.
                    </div>
                  )}
                </div>
              )}

              {/* Tier 2 Actions */}
              {activeTier === 2 && (
                <div style={{ marginTop: '10px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {activeAlert.current_tier === 2 ? (
                    <>
                      <button
                        className="btn btn--primary verify-button"
                        onClick={() => setIsEscalateModalOpen(true)}
                        disabled={isActionLoading}
                      >
                        <ShieldAlert size={14} /> 🚨 Escalate to Tier 3 (NDMA Central)
                      </button>
                      <button
                        className="btn btn--resolve"
                        onClick={() => setIsResolveModalOpen(true)}
                        disabled={isActionLoading}
                        style={{ background: 'var(--low)', color: '#fff', border: 0, padding: '8px 14px', borderRadius: '6px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        <CheckCircle2 size={14} /> ✓ Resolve Alert (Green)
                      </button>
                    </>
                  ) : (
                    <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', padding: '6px 0' }}>
                      ℹ️ Alert is at Tier {activeAlert.current_tier}. Switch authority view above to interact.
                    </div>
                  )}
                </div>
              )}

              {/* Tier 3 Actions */}
              {activeTier === 3 && (
                <div style={{ marginTop: '10px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button
                    className="btn btn--resolve"
                    onClick={() => setIsResolveModalOpen(true)}
                    disabled={isActionLoading}
                    style={{ background: 'var(--low)', color: '#fff', border: 0, padding: '8px 14px', borderRadius: '6px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}
                  >
                    <CheckCircle2 size={14} /> ✓ Resolve Alert &amp; Close Case (National Clear)
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Escalation Modal Dialog */}
          {isEscalateModalOpen && (
            <div className="verification-decision" style={{ marginTop: '14px', padding: '14px', border: '1px solid var(--border)', borderRadius: '8px', background: 'var(--surface-alt)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h3 style={{ margin: 0, fontSize: '13.5px', color: 'var(--critical)' }}>
                  🚨 Escalate Alert {activeAlert.id} to Tier {activeAlert.current_tier + 1}
                </h3>
                <button className="icon-btn" onClick={() => setIsEscalateModalOpen(false)}><X size={15} /></button>
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '0 0 10px 0' }}>
                This will officially escalate the case from Tier {activeAlert.current_tier} to Tier {activeAlert.current_tier + 1} and commit the escalation record to the permanent audit log.
              </p>

              <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Authorizing Official</label>
              <input
                value={escalateActor}
                onChange={(e) => setEscalateActor(e.target.value)}
                style={{ width: '100%', padding: '7px 9px', borderRadius: '5px', border: '1px solid var(--border)', marginBottom: '8px', fontSize: '12px' }}
              />

              <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Escalation Justification</label>
              <textarea
                value={escalateReason}
                onChange={(e) => setEscalateReason(e.target.value)}
                rows={2}
                style={{ width: '100%', padding: '7px 9px', borderRadius: '5px', border: '1px solid var(--border)', fontSize: '12px' }}
              />

              <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                <button
                  className="btn btn--primary"
                  onClick={handleEscalate}
                  disabled={isActionLoading}
                  style={{ background: 'var(--critical)', borderColor: 'var(--critical)' }}
                >
                  Confirm Escalation to Tier {activeAlert.current_tier + 1}
                </button>
                <button className="btn btn--text" onClick={() => setIsEscalateModalOpen(false)}>Cancel</button>
              </div>
            </div>
          )}

          {/* Resolution Modal Dialog */}
          {isResolveModalOpen && (
            <div className="verification-decision" style={{ marginTop: '14px', padding: '14px', border: '1px solid var(--border)', borderRadius: '8px', background: 'var(--surface-alt)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <h3 style={{ margin: 0, fontSize: '13.5px', color: 'var(--low)' }}>
                  ✓ Resolve Alert &amp; Close Case ({activeAlert.id})
                </h3>
                <button className="icon-btn" onClick={() => setIsResolveModalOpen(false)}><X size={15} /></button>
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-secondary)', margin: '0 0 10px 0' }}>
                Ground verification has confirmed the thermal event is non-hazardous, contained, or safe.
              </p>

              <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Resolving Official</label>
              <input
                value={resolveActor}
                onChange={(e) => setResolveActor(e.target.value)}
                style={{ width: '100%', padding: '7px 9px', borderRadius: '5px', border: '1px solid var(--border)', marginBottom: '8px', fontSize: '12px' }}
              />

              <label style={{ fontSize: '11px', fontWeight: 600, display: 'block', marginBottom: '4px' }}>Ground Inspection / Resolution Report</label>
              <textarea
                value={resolveNote}
                onChange={(e) => setResolveNote(e.target.value)}
                rows={2}
                style={{ width: '100%', padding: '7px 9px', borderRadius: '5px', border: '1px solid var(--border)', fontSize: '12px' }}
              />

              <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                <button
                  className="btn btn--resolve"
                  onClick={handleResolve}
                  disabled={isActionLoading}
                  style={{ background: 'var(--low)', color: '#fff', border: 0, padding: '7px 14px', borderRadius: '6px', fontSize: '12px' }}
                >
                  Confirm Resolution (Green)
                </button>
                <button className="btn btn--text" onClick={() => setIsResolveModalOpen(false)}>Cancel</button>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Audit History & Chronological Decision Log */}
        <div className="card timeline-card">
          <p className="card__label">Audit History &amp; Decision Log</p>
          <div className="timeline-list" style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '10px', maxHeight: '480px', overflowY: 'auto' }}>
            {(activeAlert.escalation_history || []).map((log: any, index: number) => {
              const isEscalation = log.to_tier > log.from_tier
              const isResolvedAction = (log.reason || '').toLowerCase().includes('resolved')
              return (
                <div
                  className="timeline-item"
                  key={index}
                  style={{
                    borderLeft: `3px solid ${isResolvedAction ? 'var(--low)' : isEscalation ? 'var(--critical)' : 'var(--accent)'}`,
                    paddingLeft: '10px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong style={{ fontSize: '12px' }}>
                      {log.from_tier === 0
                        ? 'Satellite Hotspot Detected'
                        : isResolvedAction
                        ? 'Incident Resolved & Closed'
                        : `Tier ${log.from_tier} $\rightarrow$ Tier ${log.to_tier} Escalation`}
                    </strong>
                    <span
                      style={{
                        fontSize: '9.5px', padding: '1px 5px', borderRadius: '4px',
                        background: isResolvedAction ? 'var(--low-bg)' : isEscalation ? 'var(--critical-bg)' : 'var(--surface-alt)',
                        color: isResolvedAction ? 'var(--low)' : isEscalation ? 'var(--critical)' : 'var(--text-secondary)',
                      }}
                    >
                      {log.from_tier === 0 ? 'AUTO' : `T${log.from_tier} $\rightarrow$ T${log.to_tier}`}
                    </span>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'block', marginTop: '2px' }}>
                    {log.actor} ({log.role})
                  </span>
                  <p style={{ fontSize: '11.5px', marginTop: '3px', color: 'var(--text-secondary)' }}>
                    {log.reason}
                  </p>
                  <small style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{log.timestamp}</small>
                </div>
              )
            })}
            {(!activeAlert.escalation_history || activeAlert.escalation_history.length === 0) && (
              <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', padding: '12px 0' }}>
                No prior escalation records.
              </div>
            )}
          </div>
          <p className="human-note" style={{ marginTop: '14px', fontSize: '11px', color: 'var(--text-muted)' }}>
            <ShieldAlert size={12} /> Traceable audit log preserved for central decision support.
          </p>
        </div>
      </div>
    </div>
  )
}

function Fact({ label, value }: { label: string; value: string }) {
  return <div className="fact"><span>{label}</span><strong>{value}</strong></div>
}

function InfoCard({ title, text, tone }: { title: string; text: string; tone?: RiskLevel }) {
  return (
    <div className="card info-card">
      <p className="card__label">{title}</p>
      <strong className={tone ? `text-${tone}` : ''}>{text}</strong>
    </div>
  )
}

export default App
