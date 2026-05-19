const scenario = {
  headlineMetrics: [
    { label: 'Active alerts', value: '12', meta: '2 critical, 4 high, 3 medium, 3 low' },
    { label: 'Risky hosts', value: '8', meta: 'Prioritized by fused suspicion and active alerts' },
    { label: 'Attack paths', value: '3', meta: 'Correlated recon-to-pivot chains ready for analyst review' },
    { label: 'Baseline hosts', value: '5', meta: 'Discovery seeded topology from the host registry baseline' },
  ],
  pipeline: [
    {
      title: 'Discovery bootstraps the environment',
      text: 'LateD first learns the baseline topology using passive and optional active discovery. This tells the SOC what hosts exist and how they normally relate.',
    },
    {
      title: 'Ingestion normalizes traffic',
      text: 'PCAP, Zeek, or NetFlow streams are transformed into one canonical flow schema so the detection engine can reason over a consistent event model.',
    },
    {
      title: 'Temporal graph snapshots are built',
      text: 'Network traffic is converted into temporal graph windows that capture host interactions, edge features, and evolving communication patterns.',
    },
    {
      title: 'Dual detection runs in parallel',
      text: 'A TGNN scores potential lateral movement while a separate behavioral detector scores reconnaissance. Their failures are isolated by design.',
    },
    {
      title: 'Suspicion fusion and explainability',
      text: 'Scores are fused into a host and edge suspicion model, with traceable evidence so every alert can be explained back to flows, time windows, and reasoning.',
    },
    {
      title: 'Correlation reconstructs the attack story',
      text: 'LateD chains early recon to later pivots, builds attack paths, pushes alerts to the supervision layer, and updates the SOC dashboard live.',
    },
  ],
  features: [
    {
      title: 'Network Discovery',
      body: 'Builds the baseline host registry and topology before detection begins, so the platform knows what is normal in the monitored network.',
      tag: 'Bootstrap visibility',
    },
    {
      title: 'Multi-Source Ingestion',
      body: 'Accepts PCAP, Zeek, and NetFlow sources and normalizes them into a canonical schema for replayable, auditable analysis.',
      tag: 'PCAP / Zeek / NetFlow',
    },
    {
      title: 'TGNN Lateral Movement Detection',
      body: 'Uses temporal graph modeling to flag suspicious host-to-host propagation patterns that traditional single-flow rules can miss.',
      tag: 'AI core',
    },
    {
      title: 'Reconnaissance Detection',
      body: 'Separately tracks internal scanning and behavioral recon so the platform can catch early-stage attacker movement even before pivoting.',
      tag: 'Heuristic + behavioral',
    },
    {
      title: 'Suspicion Fusion',
      body: 'Combines TGNN and recon signals without tightly coupling them, preserving explainability and failure isolation.',
      tag: 'Risk synthesis',
    },
    {
      title: 'Attack Path Reconstruction',
      body: 'Correlates events into a timeline and graph of affected hosts, likely pivots, and MITRE-style tactics so supervisors can see the full story.',
      tag: 'Forensic context',
    },
    {
      title: 'SOC Monitoring Views',
      body: 'Provides overview, alerts, attack graph, flows, timeline, and host risk views for analysts and supervisors.',
      tag: 'Operator workflow',
    },
    {
      title: 'Admin Controls',
      body: 'Supports threshold reloads and model metadata inspection to help supervisory and administrative users validate system state.',
      tag: 'Governance',
    },
  ],
  talkingPoints: [
    'Start with the mission: LateD is specialized in internal reconnaissance and lateral movement detection, not generic perimeter monitoring.',
    'Show the pipeline to explain that the platform is structured, modular, and auditable from raw traffic up to supervisor-facing alerts.',
    'Open Discovery Baseline early to show that the platform first establishes a topology graph before scoring suspicious behavior.',
    'Use the Overview tab to show executive KPIs, then move into Alerts to prove alert quality and explainability.',
    'Open Attack Reconstruction and Timeline to demonstrate that the platform does not only raise alerts; it reconstructs the attack story across hosts.',
    'Use Hosts and Flows to show drill-down capability, proving supervisors can move from global risk to concrete communication evidence.',
    'Finish with Admin to highlight operational control, threshold reloading, and model inventory without modifying core code paths.',
  ],
  tabs: [
    {
      id: 'discovery-baseline',
      kicker: 'Discovery',
      title: 'Baseline topology graph created before detection',
      badge: 'Topology baseline',
      description: 'This makes the discovery phase visible: the platform builds a baseline graph of known hosts, subnets, roles, and normal adjacency before online detection starts.',
      render: renderDiscoveryBaseline,
    },
    {
      id: 'overview',
      kicker: 'SOC Overview',
      title: 'Executive command center snapshot',
      badge: 'Supervisor ready',
      description: 'This mirrors the real overview page: a compact summary of alert pressure, high-risk hosts, reconstructed paths, and live system posture.',
      render: renderOverview,
    },
    {
      id: 'alerts',
      kicker: 'Alert Operations',
      title: 'Prioritized alert queue with explainability',
      badge: 'Live queue',
      description: 'Demonstrates how the platform prioritizes suspicious events by severity, kind, score, subject host, and MITRE-aligned context.',
      render: renderAlerts,
    },
    {
      id: 'attack-graph',
      kicker: 'Attack Graph',
      title: 'Host-to-host propagation and pivot visualization',
      badge: 'Correlated view',
      description: 'Shows how LateD reconstructs a suspected attack path across hosts and exposes likely pivot points rather than isolated alarms.',
      render: renderAttackGraph,
    },
    {
      id: 'attack-reconstruction',
      kicker: 'Correlation Engine',
      title: 'Explicit attack path reconstruction output',
      badge: 'Built from alerts',
      description: 'This tab shows how correlation turns suspicious multi-host alerts into one reconstructed attack path with pivots, chronology, confidence, and evidence mapping.',
      render: renderAttackReconstruction,
    },
    {
      id: 'timeline',
      kicker: 'Timeline',
      title: 'Recon to lateral movement chronology',
      badge: 'Incident storyline',
      description: 'Presents the event progression chronologically so the supervisor can understand how the incident unfolded over time.',
      render: renderTimeline,
    },
    {
      id: 'hosts',
      kicker: 'Host Risk',
      title: 'Top risky hosts and communication context',
      badge: 'Risk ranking',
      description: 'Highlights which machines deserve immediate attention, why they are risky, and how their risk evolved.',
      render: renderHosts,
    },
    {
      id: 'flows',
      kicker: 'Flows',
      title: 'Suspicious traffic evidence',
      badge: 'Flow evidence',
      description: 'Lets you drill down to suspicious network exchanges with byte counts, packet counts, protocols, and suspicion values.',
      render: renderFlows,
    },
    {
      id: 'admin',
      kicker: 'Admin Surface',
      title: 'Operational controls and model visibility',
      badge: 'Governance',
      description: 'Shows the supervisory angle for threshold management and model metadata inspection without editing the product itself.',
      render: renderAdmin,
    },
  ],
};

const mock = {
  discovery: {
    stats: [
      { label: 'Hosts discovered', value: '5', meta: 'Loaded from the baseline host registry' },
      { label: 'Subnets seen', value: '4', meta: 'User, application, management, and core service segments' },
      { label: 'Known servers', value: '4', meta: 'Application, management, domain, and file services identified' },
      { label: 'Baseline status', value: 'Ready', meta: 'Used as topology context for online detection' },
    ],
    hosts: [
      { id: 'FIN-WS-03', name: 'FIN-WS-03', ip: '10.20.5.23', subnet: '10.20.5.0/24', os: 'Windows 11', role: 'finance workstation', x: 120, y: 235, tier: 'user' },
      { id: 'APP-02', name: 'APP-02', ip: '10.20.2.12', subnet: '10.20.2.0/24', os: 'Linux', role: 'application server', x: 360, y: 120, tier: 'app' },
      { id: 'MGMT-01', name: 'MGMT-01', ip: '10.20.1.8', subnet: '10.20.1.0/24', os: 'Windows Server', role: 'management host', x: 610, y: 245, tier: 'mgmt' },
      { id: 'DC-01', name: 'DC-01', ip: '10.20.0.5', subnet: '10.20.0.0/24', os: 'Windows Server', role: 'domain controller', x: 860, y: 110, tier: 'core' },
      { id: 'FS-02', name: 'FS-02', ip: '10.20.0.11', subnet: '10.20.0.0/24', os: 'Linux', role: 'file service', x: 860, y: 345, tier: 'core' },
    ],
    edges: [
      { from: 'FIN-WS-03', to: 'APP-02', label: 'east-west app access' },
      { from: 'APP-02', to: 'MGMT-01', label: 'admin bridge' },
      { from: 'MGMT-01', to: 'DC-01', label: 'privileged auth' },
      { from: 'DC-01', to: 'FS-02', label: 'directory + shares' },
      { from: 'APP-02', to: 'FS-02', label: 'service dependency' },
    ],
  },
  overview: {
    summary: [
      { label: 'Open incidents', value: '3', meta: '1 major chain, 2 contained investigations' },
      { label: 'Critical hosts', value: '2', meta: 'DC-01 and APP-02 exceed 90% suspicion' },
      { label: 'Mean fusion score', value: '81%', meta: 'Across the latest correlated attack path' },
      { label: 'Sensor health', value: '100%', meta: 'Zeek, flow ingestion, and WS supervision online' },
    ],
    alerts: [
      { severity: 'critical', host: 'DC-01', description: 'Possible credential pivot after recon sweep', time: '09:16:20' },
      { severity: 'high', host: 'APP-02', description: 'SMB lateral movement suspicion over baseline', time: '09:15:44' },
      { severity: 'medium', host: 'FIN-WS-03', description: 'Unusual east-west port enumeration', time: '09:14:58' },
    ],
    riskyHosts: [
      { name: 'DC-01', subnet: '10.20.0.0/24', risk: 97 },
      { name: 'APP-02', subnet: '10.20.2.0/24', risk: 91 },
      { name: 'FIN-WS-03', subnet: '10.20.5.0/24', risk: 74 },
    ],
  },
  alerts: [
    {
      severity: 'critical',
      kind: 'fusion',
      score: '96%',
      host: 'DC-01',
      description: 'Reconnaissance followed by probable credential-based pivot to domain controller',
      tags: ['TA0008', 'T1021', 'T1078'],
    },
    {
      severity: 'high',
      kind: 'tgnn_lm',
      score: '91%',
      host: 'APP-02',
      description: 'Temporal graph pattern matches abnormal host-to-host propagation',
      tags: ['TA0008', 'T1021'],
    },
    {
      severity: 'medium',
      kind: 'recon',
      score: '78%',
      host: 'FIN-WS-03',
      description: 'Repeated internal sweep against multiple service ports over a short sliding window',
      tags: ['TA0007', 'T1046'],
    },
    {
      severity: 'low',
      kind: 'explainability',
      score: '61%',
      host: 'HR-WS-09',
      description: 'Early warning from suspicious east-west communication deviating from host baseline',
      tags: ['Context trace'],
    },
  ],
  attackPath: [
    {
      host: 'FIN-WS-03',
      title: 'Initial recon source',
      body: 'Performs internal service discovery and touches multiple hosts outside its recent baseline.',
      confidence: 74,
    },
    {
      host: 'APP-02',
      title: 'Lateral foothold',
      body: 'Receives suspicious SMB/RPC communication consistent with post-recon propagation behavior.',
      confidence: 91,
    },
    {
      host: 'MGMT-01',
      title: 'Pivot host',
      body: 'Acts as the bridge between application and privileged segments with repeated short-lived sessions.',
      confidence: 88,
    },
    {
      host: 'DC-01',
      title: 'Critical target',
      body: 'Final stage indicates likely privileged access attempt against domain resources.',
      confidence: 96,
    },
  ],
  reconstruction: {
    pathId: 'path-2026-05-19-01',
    confidence: '94%',
    pivots: ['APP-02', 'MGMT-01'],
    generatedFrom: '4 timeline alerts',
    sequence: [
      { step: 1, host: 'FIN-WS-03', kind: 'reconnaissance', target: 'APP-02', evidence: 'alert-recon-1046', detail: 'Correlation starts from the earliest suspicious recon step.' },
      { step: 2, host: 'APP-02', kind: 'fusion', target: 'MGMT-01', evidence: 'alert-fusion-2201', detail: 'Fusion alert links recon context to abnormal temporal graph behavior.' },
      { step: 3, host: 'MGMT-01', kind: 'lateral_movement', target: 'DC-01', evidence: 'alert-lm-8821', detail: 'Propagation analysis marks MGMT-01 as a likely pivot host.' },
      { step: 4, host: 'DC-01', kind: 'correlation', target: 'domain resources', evidence: 'alert-corr-9901', detail: 'Final correlated alert turns the host chain into a reconstructed attack path.' },
    ],
  },
  timeline: [
    { time: '09:12:04', title: 'Recon detector escalates FIN-WS-03', text: 'Burst of internal probes over 445, 3389, and 5985 against peers.', tags: ['Recon', 'TA0007'] },
    { time: '09:13:27', title: 'Fusion score rises on APP-02', text: 'TGNN and recon correlation align on abnormal host relationship changes.', tags: ['Fusion', 'Explainable'] },
    { time: '09:14:51', title: 'Pivot behavior inferred on MGMT-01', text: 'Short sequence of connections suggests bridge activity between segments.', tags: ['Pivot', 'Correlation'] },
    { time: '09:16:20', title: 'Critical alert emitted for DC-01', text: 'Supervisor-visible incident generated with full host chain and score trail.', tags: ['Critical', 'Supervisor'] },
  ],
  hosts: [
    { name: 'DC-01', risk: 97, active: 4, os: 'Windows Server', note: 'Highest-priority asset, final host in current attack chain.' },
    { name: 'APP-02', risk: 91, active: 3, os: 'Linux', note: 'Strong lateral movement signal from temporal graph scoring.' },
    { name: 'MGMT-01', risk: 88, active: 2, os: 'Windows Server', note: 'Likely pivot host connecting sensitive segments.' },
    { name: 'FIN-WS-03', risk: 74, active: 2, os: 'Windows 11', note: 'Early recon source detected before full propagation.' },
  ],
  flows: [
    { ts: '09:14:36', src: 'FIN-WS-03:51102', dst: 'APP-02:445', proto: 'tcp', bytes: '28,490', packets: '41', suspicion: '0.84' },
    { ts: '09:14:59', src: 'APP-02:49688', dst: 'MGMT-01:3389', proto: 'tcp', bytes: '92,144', packets: '105', suspicion: '0.88' },
    { ts: '09:15:44', src: 'MGMT-01:53922', dst: 'DC-01:445', proto: 'tcp', bytes: '120,877', packets: '136', suspicion: '0.96' },
    { ts: '09:16:01', src: 'DC-01:88', dst: 'APP-02:54122', proto: 'tcp', bytes: '16,224', packets: '19', suspicion: '0.72' },
  ],
  admin: {
    thresholds: [
      'Recon threshold: 0.70',
      'TGNN LM threshold: 0.82',
      'Fusion threshold: 0.86',
      'Correlation window: 15 minutes',
    ],
    modelInfo: {
      artifact: 'tgnn_lm.pt',
      mode: 'deterministic placeholder adapter',
      training_scope: 'lateral movement only',
      explainability: 'enabled',
      loaded_at: '2026-05-19 08:40:00',
    },
  },
};

let activeTab = scenario.tabs[0].id;
let playing = false;
let playTimer = null;

const refs = {
  metrics: document.getElementById('headline-metrics'),
  pipeline: document.getElementById('pipeline-steps'),
  featureGrid: document.getElementById('feature-grid'),
  scriptList: document.getElementById('script-list'),
  tabList: document.getElementById('tab-list'),
  tabKicker: document.getElementById('tab-kicker'),
  tabTitle: document.getElementById('tab-title'),
  tabBadge: document.getElementById('tab-badge'),
  tabDescription: document.getElementById('tab-description'),
  tabContent: document.getElementById('tab-content'),
  scenarioStatus: document.getElementById('scenario-status'),
  playButton: document.getElementById('play-scenario'),
  resetButton: document.getElementById('reset-scenario'),
};

function init() {
  renderHeadlineMetrics();
  renderPipeline();
  renderFeatures();
  renderTalkingPoints();
  renderTabs();
  renderActiveTab();
  setScenarioStatus('Baseline topology loaded. Detection, correlation, and supervisory views are synchronized.');

  refs.playButton.addEventListener('click', playScenario);
  refs.resetButton.addEventListener('click', resetScenario);
}

function renderHeadlineMetrics() {
  refs.metrics.innerHTML = scenario.headlineMetrics.map((item) => `
    <div class="metric">
      <span class="label">${item.label}</span>
      <span class="value">${item.value}</span>
      <p class="meta">${item.meta}</p>
    </div>
  `).join('');
}

function renderPipeline() {
  refs.pipeline.innerHTML = scenario.pipeline.map((step, index) => `
    <li data-step="${index + 1}">
      <strong>${step.title}</strong>
      <p>${step.text}</p>
    </li>
  `).join('');
}

function renderFeatures() {
  refs.featureGrid.innerHTML = scenario.features.map((feature) => `
    <article class="feature-card">
      <h3>${feature.title}</h3>
      <p>${feature.body}</p>
      <span class="feature-tag">${feature.tag}</span>
    </article>
  `).join('');
}

function renderTalkingPoints() {
  refs.scriptList.innerHTML = scenario.talkingPoints.map((point) => `<li>${point}</li>`).join('');
}

function renderTabs() {
  refs.tabList.innerHTML = scenario.tabs.map((tab) => `
    <button class="tab-button ${tab.id === activeTab ? 'active' : ''}" data-tab="${tab.id}">
      <span class="tab-title">${tab.title}</span>
      <span class="tab-meta">${tab.kicker}</span>
    </button>
  `).join('');

  refs.tabList.querySelectorAll('[data-tab]').forEach((button) => {
    button.addEventListener('click', () => {
      activeTab = button.getAttribute('data-tab');
      renderTabs();
      renderActiveTab();
    });
  });
}

function renderActiveTab() {
  const tab = scenario.tabs.find((entry) => entry.id === activeTab);
  if (!tab) return;

  refs.tabKicker.textContent = tab.kicker;
  refs.tabTitle.textContent = tab.title;
  refs.tabBadge.textContent = tab.badge;
  refs.tabDescription.textContent = tab.description;
  refs.tabContent.innerHTML = tab.render();
}

function renderOverview() {
  return `
    <div class="summary-grid">
      ${mock.overview.summary.map((item) => `
        <div class="summary-card">
          <span class="label">${item.label}</span>
          <span class="value">${item.value}</span>
          <p class="meta">${item.meta}</p>
        </div>
      `).join('')}
    </div>
    <div class="table-grid">
      <section class="table-card">
        <h3>Recent alerts</h3>
        <table class="mock-table">
          <thead>
            <tr><th>Severity</th><th>Description</th><th>Host</th><th>Time</th></tr>
          </thead>
          <tbody>
            ${mock.overview.alerts.map((alert) => `
              <tr>
                <td><span class="severity ${alert.severity}">${alert.severity}</span></td>
                <td>${alert.description}</td>
                <td>${alert.host}</td>
                <td>${alert.time}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </section>
      <section class="table-card">
        <h3>Top risky hosts</h3>
        <table class="mock-table">
          <thead>
            <tr><th>Host</th><th>Subnet</th><th>Risk</th></tr>
          </thead>
          <tbody>
            ${mock.overview.riskyHosts.map((host) => `
              <tr>
                <td>${host.name}</td>
                <td>${host.subnet}</td>
                <td><span class="score ${host.risk >= 90 ? 'critical' : host.risk >= 80 ? 'high' : 'medium'}">${host.risk}%</span></td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </section>
    </div>
  `;
}

function renderDiscoveryBaseline() {
  const nodeMap = Object.fromEntries(mock.discovery.hosts.map((host) => [host.id, host]));
  const edgeMarkup = mock.discovery.edges.map((edge) => {
    const from = nodeMap[edge.from];
    const to = nodeMap[edge.to];
    const midX = (from.x + to.x) / 2;
    const midY = (from.y + to.y) / 2;
    return `
      <g>
        <line class="topology-edge" x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" />
        <text class="topology-edge-label" x="${midX}" y="${midY - 10}">${edge.label}</text>
      </g>
    `;
  }).join('');

  const nodeMarkup = mock.discovery.hosts.map((host) => `
    <g class="topology-node-group">
      <circle class="topology-node-orbit ${host.tier}" cx="${host.x}" cy="${host.y}" r="42" />
      <circle class="topology-node-core ${host.tier}" cx="${host.x}" cy="${host.y}" r="27" />
      <text class="topology-node-title" x="${host.x}" y="${host.y - 2}">${host.name}</text>
      <text class="topology-node-subtitle" x="${host.x}" y="${host.y + 17}">${host.role}</text>
    </g>
  `).join('');

  return `
    <div class="summary-grid">
      ${mock.discovery.stats.map((item) => `
        <div class="summary-card">
          <span class="label">${item.label}</span>
          <span class="value">${item.value}</span>
          <p class="meta">${item.meta}</p>
        </div>
      `).join('')}
    </div>
    <section class="topology-layout">
      <article class="table-card topology-canvas-card">
        <div class="topology-header">
          <div>
            <h3>Baseline topology graph</h3>
            <p class="table-meta">Discovery establishes the network context used by graph modeling and downstream correlation.</p>
          </div>
          <div class="legend-strip">
            <span class="legend-item"><span class="legend-dot user"></span>User</span>
            <span class="legend-item"><span class="legend-dot app"></span>App</span>
            <span class="legend-item"><span class="legend-dot mgmt"></span>Mgmt</span>
            <span class="legend-item"><span class="legend-dot core"></span>Core</span>
          </div>
        </div>
        <div class="topology-canvas">
          <svg class="topology-svg" viewBox="0 0 980 460" role="img" aria-label="Baseline topology graph">
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(124, 160, 201, 0.08)" stroke-width="1" />
              </pattern>
              <filter id="softGlow">
                <feGaussianBlur stdDeviation="8" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            <rect x="0" y="0" width="980" height="460" fill="url(#grid)" rx="24" />
            <rect class="topology-zone user" x="34" y="152" width="180" height="166" rx="22" />
            <rect class="topology-zone app" x="258" y="52" width="200" height="146" rx="22" />
            <rect class="topology-zone mgmt" x="505" y="164" width="210" height="160" rx="22" />
            <rect class="topology-zone core" x="748" y="56" width="188" height="336" rx="22" />
            <text class="topology-zone-label" x="58" y="178">User segment</text>
            <text class="topology-zone-label" x="284" y="78">Application segment</text>
            <text class="topology-zone-label" x="531" y="190">Management segment</text>
            <text class="topology-zone-label" x="774" y="82">Core services</text>
            <g filter="url(#softGlow)">
              ${edgeMarkup}
              ${nodeMarkup}
            </g>
          </svg>
        </div>
      </article>
      <article class="table-card registry-card">
        <h3>Host registry snapshot</h3>
        <div class="registry-list">
          ${mock.discovery.hosts.map((host) => `
            <article class="registry-item">
              <div class="registry-head">
                <span class="small-label">${host.role}</span>
                <span class="tag ${host.tier === 'core' ? 'critical' : host.tier === 'mgmt' ? 'high' : 'medium'}">${host.tier}</span>
              </div>
              <h3>${host.name}</h3>
              <p>${host.ip}</p>
              <p class="host-meta">${host.subnet} · ${host.os}</p>
            </article>
          `).join('')}
        </div>
        <p class="table-meta">This registry becomes the baseline graph context that anchors normal host relationships before suspicious sequences are scored.</p>
      </article>
    </section>
  `;
}

function renderAlerts() {
  return `
    <section class="table-card">
      <h3>Alert queue</h3>
      <table class="mock-table">
        <thead>
          <tr><th>Severity</th><th>Kind</th><th>Host</th><th>Description</th><th>Score</th></tr>
        </thead>
        <tbody>
          ${mock.alerts.map((alert) => `
            <tr>
              <td><span class="severity ${alert.severity}">${alert.severity}</span></td>
              <td>${alert.kind}</td>
              <td>${alert.host}</td>
              <td>
                ${alert.description}
                <div>${alert.tags.map((tag) => `<span class="tag">${tag}</span>`).join('')}</div>
              </td>
              <td><span class="score ${alert.severity}">${alert.score}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <p class="table-meta">Use this view to explain alert prioritization, role-based handling, and evidence-driven triage.</p>
    </section>
  `;
}

function renderAttackGraph() {
  return `
    <div class="path-chain">
      ${mock.attackPath.map((step) => `
        <article class="path-step">
          <span class="small-label">${step.host}</span>
          <h3>${step.title}</h3>
          <p>${step.body}</p>
          <div class="signal-bar"><span style="width:${step.confidence}%"></span></div>
          <p class="path-meta">Path confidence ${step.confidence}%</p>
        </article>
      `).join('')}
    </div>
  `;
}

function renderAttackReconstruction() {
  return `
    <div class="summary-grid reconstruction-grid">
      <div class="summary-card">
        <span class="label">Path ID</span>
        <span class="value reconstruction-value">${mock.reconstruction.pathId}</span>
        <p class="meta">Correlation output stored for supervision and replay.</p>
      </div>
      <div class="summary-card">
        <span class="label">Confidence</span>
        <span class="value">${mock.reconstruction.confidence}</span>
        <p class="meta">Filtered above the minimum path confidence threshold.</p>
      </div>
      <div class="summary-card">
        <span class="label">Pivot hosts</span>
        <span class="value">${mock.reconstruction.pivots.length}</span>
        <p class="meta">${mock.reconstruction.pivots.join(', ')}</p>
      </div>
      <div class="summary-card">
        <span class="label">Source evidence</span>
        <span class="value">${mock.reconstruction.generatedFrom}</span>
        <p class="meta">Built from the chronological alert timeline.</p>
      </div>
    </div>
    <section class="timeline-list">
      ${mock.reconstruction.sequence.map((item) => `
        <article class="timeline-item">
          <div class="timeline-time">Step ${item.step}</div>
          <div>
            <h3>${item.host} → ${item.target}</h3>
            <p>${item.detail}</p>
            <div class="timeline-meta">
              <span class="tag">${item.kind}</span>
              <span class="tag">${item.evidence}</span>
            </div>
          </div>
        </article>
      `).join('')}
    </section>
  `;
}

function renderTimeline() {
  return `
    <section class="timeline-list">
      ${mock.timeline.map((item) => `
        <article class="timeline-item">
          <div class="timeline-time">${item.time}</div>
          <div>
            <h3>${item.title}</h3>
            <p>${item.text}</p>
            <div class="timeline-meta">${item.tags.map((tag) => `<span class="tag">${tag}</span>`).join('')}</div>
          </div>
        </article>
      `).join('')}
    </section>
  `;
}

function renderHosts() {
  return `
    <div class="host-cards">
      ${mock.hosts.map((host) => `
        <article class="host-card">
          <span class="small-label">${host.os}</span>
          <h3>${host.name}</h3>
          <p>${host.note}</p>
          <p class="host-meta">Active alerts: ${host.active}</p>
          <div class="signal-bar"><span style="width:${host.risk}%"></span></div>
          <p class="host-meta">Current risk ${host.risk}%</p>
        </article>
      `).join('')}
    </div>
  `;
}

function renderFlows() {
  return `
    <section class="table-card">
      <h3>Suspicious flow evidence</h3>
      <table class="mock-table">
        <thead>
          <tr><th>Time</th><th>Source</th><th>Destination</th><th>Proto</th><th>Bytes</th><th>Packets</th><th>Suspicion</th></tr>
        </thead>
        <tbody>
          ${mock.flows.map((flow) => `
            <tr>
              <td>${flow.ts}</td>
              <td>${flow.src}</td>
              <td>${flow.dst}</td>
              <td>${flow.proto}</td>
              <td>${flow.bytes}</td>
              <td>${flow.packets}</td>
              <td><span class="score medium">${flow.suspicion}</span></td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <p class="table-meta">This is the evidence layer supervisors can reference when asked how a host score or alert was justified.</p>
    </section>
  `;
}

function renderAdmin() {
  return `
    <div class="admin-grid">
      <article class="admin-card">
        <h3>Threshold controls</h3>
        <p>Illustrates the operational capability to reload supervisory thresholds without changing detection logic or restarting the service.</p>
        <div class="admin-meta">${mock.admin.thresholds.map((item) => `<div class="tag success">${item}</div>`).join('')}</div>
      </article>
      <article class="admin-card">
        <h3>Model inventory</h3>
        <p>Shows the currently loaded inference artifact and emphasizes that the trained model concerns lateral movement only.</p>
        <pre class="table-meta">${JSON.stringify(mock.admin.modelInfo, null, 2)}</pre>
      </article>
    </div>
  `;
}

function playScenario() {
  if (playing) return;
  playing = true;
  refs.playButton.disabled = true;

  const order = scenario.tabs.map((tab) => tab.id);
  let index = 0;

  setScenarioStatus('Incident playback active. Cycling through topology, detection, correlation, and investigation views.');

  playTimer = setInterval(() => {
    activeTab = order[index];
    renderTabs();
    renderActiveTab();

    const current = scenario.tabs[index];
    setScenarioStatus(`${current.title} loaded. View synchronized for supervisory review and operator drill-down.`);

    index += 1;
    if (index >= order.length) {
      clearInterval(playTimer);
      playing = false;
      refs.playButton.disabled = false;
      setScenarioStatus('Incident playback complete. All views remain available for manual inspection.');
    }
  }, 2200);
}

function resetScenario() {
  if (playTimer !== null) {
    clearInterval(playTimer);
  }
  playing = false;
  refs.playButton.disabled = false;
  activeTab = scenario.tabs[0].id;
  renderTabs();
  renderActiveTab();
  setScenarioStatus('Workspace reset. Baseline topology restored as the primary entry view.');
}

function setScenarioStatus(text) {
  refs.scenarioStatus.textContent = text;
}

init();
