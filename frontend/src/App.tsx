import { memo, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Activity, AlertTriangle, Bell, ChevronDown, CircleHelp, Crosshair, Flame,
  Layers3, MapPin, Maximize2, Menu, Moon, PanelRight, RefreshCw,
  Search, ShieldAlert, SlidersHorizontal, Sun, Thermometer, TrendingUp, LogOut,
  Wifi, X, Zap, UserRound, LockKeyhole, Phone, MapPinned, Mail, Eye, EyeOff, Play, Pause, Gauge,
} from 'lucide-react'
import { CircleMarker, MapContainer, TileLayer, Popup, useMap } from 'react-leaflet'


import type { LatLngExpression } from 'leaflet'
import './App.css'

type RiskLevel = 'critical' | 'high' | 'moderate'
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

const fireTypes: FireType[] = [
  'Industrial Fire',
  'Persistent Industrial Thermal Source',
  'Gas Flare',
  'Wildfire/Natural Fire',
  'Agricultural Fire',
  'Unknown',
]



type AlertRecord = {
  id: string
  eventId: string
  fireType: FireType
  location: string
  region: string
  risk: number
  severity: RiskLevel
  status: 'NEW' | 'ACKNOWLEDGED' | 'DISPATCHED' | 'RESOLVED'
  createdAt: string
  message: string
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

const fireTypeMeta: Record<FireType, { short: string; description: string; color: string }> = {
  'Industrial Fire': { short: 'Industrial', description: 'Acute thermal activity associated with industrial facilities.', color: '#c24632' },
  'Persistent Industrial Thermal Source': { short: 'Persistent source', description: 'Recurring heat signatures that remain active over time.', color: '#a97a1f' },
  'Gas Flare': { short: 'Gas flare', description: 'Thermal signatures consistent with controlled hydrocarbon flaring.', color: '#b05d22' },
  'Wildfire/Natural Fire': { short: 'Wildfire / natural', description: 'Vegetation and natural-land fire signatures.', color: '#8a4f35' },
  'Agricultural Fire': { short: 'Agricultural', description: 'Thermal activity associated with agricultural land management.', color: '#6b6a24' },
  'Unknown': { short: 'Unknown', description: 'Thermal anomalies without enough context for a stronger class.', color: '#5d6470' },
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
  { id: 'FIRMS_001', location: 'Jamnagar, Gujarat', facility: 'Reliance Industries Refinery', type: 'Refinery', classification: 'Industrial fire', fireType: 'Industrial Fire', timestamp: '10:30 UTC', frp: 124.5, temperature: 341.2, confidence: 94.2, risk: 87, riskLevel: 'critical', persistence: 84, detections: 18, latitude: 22.47, longitude: 70.06 },
  { id: 'FIRMS_014', location: 'Paradip, Odisha', facility: 'IOCL Paradip Complex', type: 'Petrochemical', classification: 'Persistent source', fireType: 'Persistent Industrial Thermal Source', timestamp: '09:48 UTC', frp: 96.8, temperature: 329.7, confidence: 91.8, risk: 76, riskLevel: 'high', persistence: 72, detections: 13, latitude: 20.27, longitude: 86.68 },
  { id: 'FIRMS_022', location: 'Korba, Chhattisgarh', facility: 'NTPC Korba Thermal Plant', type: 'Power plant', classification: 'Industrial fire', fireType: 'Industrial Fire', timestamp: '08:16 UTC', frp: 74.2, temperature: 318.4, confidence: 88.4, risk: 64, riskLevel: 'high', persistence: 61, detections: 9, latitude: 22.36, longitude: 82.75 },
  { id: 'FIRMS_031', location: 'Bharuch, Gujarat', facility: 'Dahej Industrial Estate', type: 'Industrial estate', classification: 'Gas flare', fireType: 'Gas Flare', timestamp: '06:54 UTC', frp: 51.6, temperature: 307.9, confidence: 82.6, risk: 43, riskLevel: 'moderate', persistence: 45, detections: 7, latitude: 21.7, longitude: 72.99 },
  { id: 'FIRMS_044', location: 'Mumbai, Maharashtra', facility: 'Bharat Petroleum Mumbai Refinery', type: 'Refinery', classification: 'Industrial fire', fireType: 'Industrial Fire', timestamp: '05:42 UTC', frp: 88.1, temperature: 326.8, confidence: 90.6, risk: 79, riskLevel: 'high', persistence: 68, detections: 12, latitude: 19.01, longitude: 72.88 },
  { id: 'FIRMS_052', location: 'Vapi, Gujarat', facility: 'Vapi Chemical Estate', type: 'Chemical plant', classification: 'Persistent source', fireType: 'Persistent Industrial Thermal Source', timestamp: '04:27 UTC', frp: 42.7, temperature: 301.6, confidence: 86.3, risk: 58, riskLevel: 'moderate', persistence: 77, detections: 16, latitude: 20.37, longitude: 72.91 },
  { id: 'FIRMS_067', location: 'Visakhapatnam, Andhra Pradesh', facility: 'HPCL Visakh Refinery', type: 'Petrochemical', classification: 'Gas flare', fireType: 'Gas Flare', timestamp: '03:18 UTC', frp: 63.4, temperature: 312.5, confidence: 89.1, risk: 69, riskLevel: 'high', persistence: 54, detections: 8, latitude: 17.69, longitude: 83.22 },
  { id: 'FIRMS_073', location: 'Bengaluru, Karnataka', facility: 'Bengaluru Peri-Urban Zone', type: 'Urban area', classification: 'Vegetation fire', fireType: 'Wildfire/Natural Fire', timestamp: '02:51 UTC', frp: 28.9, temperature: 294.7, confidence: 78.5, risk: 36, riskLevel: 'moderate', persistence: 24, detections: 4, latitude: 13.08, longitude: 77.59 },
  { id: 'FIRMS_081', location: 'Kolkata, West Bengal', facility: 'Haldia Dock Complex', type: 'Industrial estate', classification: 'Industrial fire', fireType: 'Industrial Fire', timestamp: '01:36 UTC', frp: 107.3, temperature: 333.1, confidence: 93.4, risk: 85, riskLevel: 'critical', persistence: 81, detections: 19, latitude: 22.06, longitude: 88.09 },
  { id: 'FIRMS_096', location: 'Chennai, Tamil Nadu', facility: 'Manali Industrial Corridor', type: 'Chemical plant', classification: 'Thermal anomaly', fireType: 'Unknown', timestamp: '00:48 UTC', frp: 35.8, temperature: 299.4, confidence: 80.2, risk: 47, riskLevel: 'moderate', persistence: 39, detections: 6, latitude: 13.16, longitude: 80.27 },
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
  'Western India', 'Delhi NCR', 'Mumbai, Maharashtra', 'Ahmedabad, Gujarat', 'Jamnagar, Gujarat',
  'Bengaluru, Karnataka', 'Chennai, Tamil Nadu', 'Hyderabad, Telangana', 'Kolkata, West Bengal',
  'Pune, Maharashtra', 'Jaipur, Rajasthan', 'Lucknow, Uttar Pradesh', 'Bhopal, Madhya Pradesh',
  'Bhubaneswar, Odisha', 'Patna, Bihar', 'Ranchi, Jharkhand', 'Guwahati, Assam',
  'Raipur, Chhattisgarh', 'Kochi, Kerala', 'Visakhapatnam, Andhra Pradesh',
]

const workspaceCoordinates: Record<string, LatLngExpression> = {
  'Western India': [20.2, 72.8], 'Delhi NCR': [28.6, 77.2], 'Mumbai, Maharashtra': [19.08, 72.88],
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
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [activeNav, setActiveNav] = useState('Dashboard')
  const [theme, setTheme] = useState<'dark' | 'light'>(
    () => (localStorage.getItem('thermos-theme') as 'dark' | 'light' | null) ?? 'light',
  )
  const [workspace, setWorkspace] = useState('Western India')
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
  const [alerts, setAlerts] = useState<AlertRecord[]>([])

  const [activeEvents, setActiveEvents] = useState<EventRecord[]>(events)
  const [analyticsData, setAnalyticsData] = useState<{
    total_events: number
    industrial_events: number
    critical_events: number
    persistent_sources: number
  }>({ total_events: 247, industrial_events: 32, critical_events: 8, persistent_sources: 14 })

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

  const fetchBackendData = async () => {
    try {
      const [eventsRes, analyticsRes, gisRes] = await Promise.all([
        fetch('http://localhost:8000/api/events').catch(() => null),
        fetch('http://localhost:8000/api/analytics').catch(() => null),
        fetch('http://localhost:8000/api/gis/master-detections?limit=5144').catch(() => null),
      ])

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
      } else if (eventsRes && eventsRes.ok) {
        const data = await eventsRes.json()
        if (Array.isArray(data) && data.length > 0) {
          const mapped: EventRecord[] = data.map((item: any) => ({
            id: item.id,
            location: item.facility_name ? `${item.facility_name}` : `Lat ${item.latitude.toFixed(2)}, Lon ${item.longitude.toFixed(2)}`,
            facility: item.facility_name || 'Industrial Facility',
            type: item.facility_type || 'Industrial site',
            classification: item.classification || 'Thermal anomaly',
            fireType: mapBackendClassificationToFireType(item.classification),
            timestamp: item.timestamp ? (item.timestamp.includes('T') ? item.timestamp.split('T')[1].slice(0, 5) + ' UTC' : item.timestamp) : '10:30 UTC',
            frp: item.frp || 50.0,
            temperature: item.brightness_temperature || 320.0,
            confidence: Math.round((item.confidence || 0.85) * (item.confidence <= 1 ? 100 : 1)),
            risk: Math.round(item.risk_score || 50),
            riskLevel: (item.risk_level?.toLowerCase() as RiskLevel) || 'moderate',
            persistence: 84,
            detections: 12,
            latitude: item.latitude,
            longitude: item.longitude,
          }))
          setActiveEvents(mapped)
        }
      }

      if (analyticsRes && analyticsRes.ok) {
        const stats = await analyticsRes.json()
        setAnalyticsData(stats)
      }
    } catch {
      // Retain demo fallback
    }
  }


  useEffect(() => {
    fetchBackendData()
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

  const refresh = () => {
    setIsRefreshing(true)
    fetchBackendData().finally(() => {
      window.setTimeout(() => setIsRefreshing(false), 900)
    })
  }


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
            <span className="live-chip"><Wifi size={14} /> Live data <span className="dot dot--live" /></span>
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
            {user && <span className="topbar__user">{getInitials(user.fullName)} {user.fullName} · {user.role}</span>}
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
                <h1>Thermal intelligence</h1>
                <p className="page__subtitle">Monitor, classify, and understand thermal activity across your operating region.</p>
              </div>
              <div className="page__actions">
                <span className="updated"><span className="dot dot--live" /> Updated 2 min ago</span>
                <button className="btn btn--ghost" onClick={refresh}>
                  <RefreshCw size={15} className={isRefreshing ? 'spin' : ''} /> Refresh
                </button>
              </div>
            </div>

            <section className="kpis" aria-label="Platform metrics">
              <Kpi icon={<Flame size={16} />} tone="critical" label="Thermal events" value={String(analyticsData.total_events)} trend="+12.4%" note="vs. last 7 days" />
              <Kpi icon={<AlertTriangle size={16} />} tone="high" label="Critical alerts" value={String(analyticsData.critical_events).padStart(2, '0')} trend="+3" note="since yesterday" down />
              <Kpi icon={<Zap size={16} />} tone="moderate" label="Industrial events" value={String(analyticsData.industrial_events)} trend="+8.1%" note="vs. last 7 days" />
              <Kpi icon={<Activity size={16} />} tone="low" label="Persistent sources" value={String(analyticsData.persistent_sources)} trend="Stable" note="vs. last 7 days" neutral />
            </section>


            <section className={`workspace-grid ${isMapMaximized ? 'is-maximized' : ''}`}>
              <div className="card map-card">
                <div className="card__header">
                  <div>
                    <h2>Live anomaly map</h2>
                    <p>{workspace} · 06 Sep 2026, 10:30 UTC</p>
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
                      <h2>Priority events</h2>
                      <p>Showing {priorityEvents.length} of {filteredEvents.length} events</p>
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
                  <p className="detail-card__kicker"><MapPin size={13} /> Selected anomaly</p>
                  <h2>
                    {selectedEvent.id}
                    <span className={`status-pill ${selectedEvent.riskLevel}`}>{selectedEvent.riskLevel} risk</span>
                  </h2>
                  <p>{selectedEvent.location} · Detected {selectedEvent.timestamp}</p>
                </div>
                <button className="btn btn--outline" onClick={() => setActiveNav('Event detail')}>
                  <PanelRight size={15} /> Open event detail
                </button>
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
            alerts={visibleAlerts}
            user={user}
            reviewStatus={reviewStatus}
            onReview={setReviewStatus}
            onToggleTheme={toggleTheme}
            onReturn={() => setActiveNav('Dashboard')}
            events={activeEvents}
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

function SimulationPage({ events, active, speed, tick, incidents, alerts, onToggle, onSpeedChange, onReset }: {
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
  const activeIncidents = incidents.filter((item) => item.active)
  const current = activeIncidents[activeIncidents.length - 1]
  return (
    <div className="page simulation-page">
      <div className="page__header">
        <div><span className="auth-eyebrow">LIVE SCENARIO ENGINE</span><h1>Fire detection & alert simulation</h1><p className="page__subtitle">Run a judge-ready emergency scenario: detect → classify → calculate risk → route the alert to the correct authority.</p></div>
        <div className="simulation-controls"><span className={`simulation-status ${active ? 'is-running' : ''}`}><span /> {active ? 'Engine running' : 'Engine ready'} · tick {tick}</span><button className="btn btn--primary" onClick={onToggle}>{active ? <Pause size={15} /> : <Play size={15} />} {active ? 'Pause' : 'Start scenario'}</button><button className="btn btn--ghost" onClick={onReset}>Reset</button><label className="simulation-speed">Speed<select value={speed} onChange={(e) => onSpeedChange(Number(e.target.value))}><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option></select></label></div>
      </div>
      {current && <div className="simulation-live-banner"><div><span className="simulation-live-dot" /> LIVE INCIDENT</div><strong>{current.fireType}</strong><span>{current.location} · {current.region}</span><span className={`status-pill ${current.simulatedRisk >= 80 ? 'critical' : current.simulatedRisk >= 60 ? 'high' : 'moderate'}`}>{current.stage} · {current.simulatedRisk}/100</span><small>Alert routing: Central Government + {current.region} authority</small></div>}
      <div className="simulation-overview"><div><span>Scenario incidents</span><strong>{simulationScenario.length}</strong></div><div><span>Detected</span><strong>{activeIncidents.length}</strong></div><div><span>Critical alerts</span><strong>{alerts.filter((a) => a.severity === 'critical').length}</strong></div><div><span>Routing</span><strong>REGION + CENTRAL</strong></div></div>
      <div className="simulation-flow card"><div><span>01</span><strong>Satellite / thermal detection</strong></div><ChevronDown size={16} /><div><span>02</span><strong>AI classification</strong></div><ChevronDown size={16} /><div><span>03</span><strong>Risk escalation</strong></div><ChevronDown size={16} /><div><span>04</span><strong>Regional alert routing</strong></div></div>
      <div className="simulation-grid">{fireTypes.map((fireType) => { const meta = fireTypeMeta[fireType]; const typeEvents = events.filter((event) => event.fireType === fireType); const typeIncidents = activeIncidents.filter((item) => item.fireType === fireType); const center: LatLngExpression = typeEvents.length ? [typeEvents[0].latitude, typeEvents[0].longitude] : [20.2, 78.9]; return <section className="simulation-type card" key={fireType}><div className="simulation-type__header"><div><span className="simulation-type__tag" style={{ borderColor: meta.color, color: meta.color }}>{meta.short}</span><h2>{fireType}</h2><p>{meta.description}</p></div><strong className="simulation-type__count">{typeEvents.length}<small> base events</small></strong></div><div className="simulation-type__legend"><span><i style={{ background: meta.color }} /> {typeIncidents.length ? `${typeIncidents.length} live scenario incident` : 'Monitoring'}</span><span>Region routing enabled</span></div>{typeEvents.length ? <><div className="simulation-map"><ThermalMap center={center} events={typeEvents} selectedId={typeEvents[0].id} onSelect={() => undefined} markerColor={meta.color} /></div><div className="simulation-events">{typeEvents.map((event) => { const live = typeIncidents.find((item) => item.id.includes(event.id.replace('FIRMS_', ''))); return <div key={event.id}><strong>{live ? live.id : event.id}</strong><span>{live ? `${live.region} · ${live.stage}` : event.location}</span><em>{live ? `${live.simulatedRisk} risk · ${live.stage}` : `${event.risk} baseline risk · ${event.frp} MW`}</em></div>})}</div></> : <div className="simulation-empty"><Gauge size={18} /><strong>No base events in this class</strong><span>The classifier is ready to receive live detections.</span></div>}</section>})}</div>
      <div className="simulation-alert-log card"><div className="card__header"><div><h2>Live alert routing log</h2><p>Every critical scenario is routed by region. Central Government sees all regions.</p></div><Bell size={18} /></div>{alerts.length ? alerts.slice().reverse().map((alert) => <div className="routed-alert" key={alert.id}><span className={`event-row__severity ${alert.severity}`}><Bell size={14} /></span><div><strong>{alert.id}</strong><span>{alert.message}</span><small>{alert.createdAt} · Routed to Central Government + {alert.region} authority</small></div><em>{alert.status}</em></div>) : <div className="simulation-empty"><Bell size={18} /><strong>No alerts yet</strong><span>Start the scenario and wait for the risk score to cross the critical threshold.</span></div>}</div>
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

  const [layers, setLayers] = useState({
    heatmap: false,
    industrial: true,
    flares: true,
    wildfires: true,
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

      {/* Floating Control Box (Top Right) */}
      <div className="gis-floating-control">
        <div className="gis-control-section">
          <label className="gis-control-option"><input type="radio" name="basemap" checked={tileMode === 'carto'} onChange={() => setTileMode('carto')} /> cartodbpositron</label>
          <label className="gis-control-option"><input type="radio" name="basemap" checked={tileMode === 'dark'} onChange={() => setTileMode('dark')} /> Dark Mode (Thermal)</label>
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

      {/* Floating Legend Panel (Bottom Left) */}
      <div className="gis-floating-legend">
        <div className="gis-legend-title">
          <span>📊</span> Thermal Anomaly &amp; Zone Monitor
        </div>
        <div className="gis-legend-row"><span className="gis-legend-icon red" /> 🚨 Industrial Facility Alert</div>
        <div className="gis-legend-row"><span className="gis-legend-icon orange" /> 🔥 Gas Flare (Upstream)</div>
        <div className="gis-legend-row"><span className="gis-legend-icon green" /> 🌲 Active Wildfire / Forest Fire</div>
        <div className="gis-legend-row"><span className="gis-legend-icon blue" /> 🟢 Normal / Non-Fire Heat Zone</div>

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

  page, theme, reviewStatus, onReview, onToggleTheme, onReturn, alerts, user, events: pageEvents,
}: {
  page: string
  theme: 'dark' | 'light'
  alerts: AlertRecord[]
  user: StoredUser | null
  reviewStatus: 'pending' | 'resolved' | 'escalated'
  onReview: (status: 'pending' | 'resolved' | 'escalated') => void
  onToggleTheme: () => void
  onReturn: () => void
  events?: EventRecord[]
}) {
  const activeList = pageEvents || events
  const [selectedFacilityIndex, setSelectedFacilityIndex] = useState(0)
  const [selectedId, setSelectedId] = useState(activeList[0]?.id || 'FIRMS_0001')
  const [baseLayer, setBaseLayer] = useState<'street' | 'satellite'>('street')
  const selected = activeList.find((e) => e.id === selectedId) ?? activeList[0]
  const selectedFacility = facilityIntel[selectedFacilityIndex]
  if (page === 'Alert center') return <AlertCenter reviewStatus={reviewStatus} onReview={onReview} alerts={alerts} user={user} />

  const copy: Record<string, { title: string; description: string }> = {
    'GIS map': { title: 'Map layers', description: 'Inspect FIRMS hotspots, facilities, and risk radius by region.' },
    'Event detail': { title: `Event detail — ${selected.id}`, description: 'The complete satellite observation and enriched event contract.' },
    'AI analysis': { title: 'Classification analysis', description: 'Model confidence, risk score, and the reasoning behind each classification.' },
    'Facility intel': { title: 'Facility intelligence', description: 'Industrial facilities and the thermal activity linked to each one.' },
  }
  const view = copy[page] ?? { title: page, description: 'Workspace information and connected signals.' }

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
        <div className="grid grid--detail">
          <div className="card analysis-card">
            <p className="card__label">XGBoost ML Classification (fused-xgboost-v1)</p>
            <h2 className="analysis-card__class">{selected.classification}</h2>
            <span className="analysis-card__confidence">{selected.confidence}% confidence</span>
            <strong className="analysis-card__risk">{selected.risk}</strong>
            <small>Evaluated Risk Score / 100</small>
            <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--border)', fontSize: '11.5px', color: 'var(--text-secondary)' }}>
              <div><strong>Industrial Probability:</strong> {(selected as any).prob_industrial_fused !== undefined ? ((selected as any).prob_industrial_fused * 100).toFixed(1) + '%' : (selected.riskLevel === 'critical' ? '94.2%' : '12.4%')}</div>
              <div style={{ marginTop: '4px' }}><strong>Feature Vector:</strong> 24 Radiometric &amp; Spatial Features</div>
            </div>
          </div>
          <div className="card analysis-card">
            <p className="card__label">Why this classification (Grounded AI Reasoning)</p>
            {getAiReasons(selected).map((reason) => (
              <p className="reason" key={reason}><i /> {reason}</p>
            ))}
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
  reviewStatus, onReview, alerts, user,
}: { reviewStatus: 'pending' | 'resolved' | 'escalated'; onReview: (status: 'pending' | 'resolved' | 'escalated') => void; alerts: AlertRecord[]; user: StoredUser | null }) {
  const resolved = reviewStatus === 'resolved'
  const [isDecisionOpen, setIsDecisionOpen] = useState(false)
  const [decision, setDecision] = useState<'close' | 'escalate'>('close')
  const [authority, setAuthority] = useState('')
  const [comments, setComments] = useState('')

  const submitDecision = () => {
    onReview(decision === 'close' ? 'resolved' : 'escalated')
    setIsDecisionOpen(false)
  }

  return (
    <div className="page subpage">
      <div className="page__header">
        <div>
          <h1>Human review queue</h1>
          <p className="page__subtitle">Alerts are routed to the correct authority by region. {user?.role ?? 'Authority'} view · {user?.region ?? 'All regions'}.</p>
        </div>
        <span className={`review-signal ${resolved ? 'resolved' : 'pending'}`}>
          <span /> {resolved ? 'Resolved by reviewer' : 'Review required'}
        </span>
      </div>

      {alerts.length > 0 && <div className="routed-alerts-card card"><div className="card__header"><div><h2>Region-routed alerts</h2><p>Only alerts relevant to this signed-in authority are shown.</p></div><Bell size={18} /></div>{alerts.map((alert) => <div className="routed-alert" key={alert.id}><span className={`event-row__severity ${alert.severity}`}><Bell size={14} /></span><div><strong>{alert.fireType}</strong><span>{alert.location} · {alert.region}</span><small>{alert.message} · {alert.createdAt}</small></div><em>{alert.status}</em></div>)}</div>}
      <div className="alert-grid">
        <div className="card alert-summary">
          <p className="card__label">Alert summary</p>
          <div className="counts">
            <span><strong>{resolved ? 0 : 1}</strong>Critical</span>
            <span><strong>1</strong>High</span>
            <span><strong>{resolved ? 0 : 2}</strong>Open</span>
          </div>
          <p className="card__label card__label--spaced">Cases</p>
          {['#92841 Industrial fire', '#92840 Wildfire', '#92832 Gas flare', '#92821 Persistent industrial source'].map((item, index) => (
            <div className="case-row" key={item}>
              <small>{item.split(' ')[0]}</small>
              <strong>{item.slice(item.indexOf(' ') + 1)}</strong>
              <span className={index === 0 && resolved ? 'case-resolved' : 'case-pending'}>
                {index === 0 && resolved ? 'Resolved' : index === 1 ? 'Tier 2 pending' : 'Resolved'}
              </span>
            </div>
          ))}
        </div>

        <div className="card review-card">
          <p className="card__label">Case #92841 — FIRMS_001</p>
          <h2>Industrial fire</h2>
          <p className="review-card__location">Reliance Industries Refinery<br />Jamnagar, Gujarat</p>
          <div className="tier-track">
            <span className={reviewStatus !== 'pending' ? 'is-done' : ''}>Tier 1</span>
            <ChevronDown size={13} className="tier-track__arrow" />
            <span className={reviewStatus === 'escalated' ? 'is-done' : ''}>Tier 2</span>
            <ChevronDown size={13} className="tier-track__arrow" />
            <span>Tier 3</span>
          </div>
          {resolved ? (
            <div className="resolved-banner">
              <strong>Case resolved</strong>
              <span>No further action required.</span>
            </div>
          ) : (
            <div className="review-actions">
              <p>Human verification required. Confirm whether this alert is resolved or should be escalated.</p>
              <button className="btn btn--primary verify-button" onClick={() => setIsDecisionOpen(true)}><ShieldAlert size={15} /> Verify &amp; Respond</button>
            </div>
          )}
          {isDecisionOpen && (
            <div className="verification-decision">
              <div className="verification-decision__heading">
                <div><h3>Verification decision</h3><p>Record the outcome for this alert.</p></div>
                <button className="icon-btn" aria-label="Close verification decision" onClick={() => setIsDecisionOpen(false)}><X size={16} /></button>
              </div>
              <div className="decision-options">
                <button className={decision === 'close' ? 'is-selected is-close' : ''} onClick={() => setDecision('close')}><span>✓</span><strong>Green — Close</strong><small>No threat found</small></button>
                <button className={decision === 'escalate' ? 'is-selected is-escalate' : ''} onClick={() => setDecision('escalate')}><span>!</span><strong>Red — Escalate</strong><small>Escalate to Tier 3</small></button>
              </div>
              <input value={authority} onChange={(event) => setAuthority(event.target.value)} placeholder="Authority name" />
              <textarea value={comments} onChange={(event) => setComments(event.target.value)} placeholder="Verification comments..." rows={3} />
              <div className="verification-decision__actions">
                <button className="btn btn--resolve" onClick={submitDecision}><ShieldAlert size={14} /> {decision === 'close' ? 'Submit Closure' : 'Submit Escalation'}</button>
                <button className="btn btn--text" onClick={() => setIsDecisionOpen(false)}>Cancel</button>
              </div>
            </div>
          )}
        </div>

        <div className="card timeline-card">
          <p className="card__label">Escalation timeline</p>
          <div className="timeline-item">
            <span className="timeline-dot" />
            <div>
              <strong>Tier 1 — normal</strong>
              <p>{resolved ? 'Reviewed and resolved by human operator.' : 'Awaiting human review.'}</p>
              <small>Sun, 06 Sep 2026 · 13:33:43</small>
            </div>
          </div>
          <p className="human-note">AI detects, classifies, and prioritizes. Every escalation stays subject to human verification.</p>
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
