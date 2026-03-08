import { useState, useRef, useEffect } from "react";

const AGENTS = [
  {
    id: "orchestrator",
    label: "Orchestrator Agent",
    subtitle: "Central Coordinator",
    desc: "Decomposes user requirements into tasks, delegates to specialist agents, manages execution order & dependencies, handles error recovery and re-planning.",
    color: "#E8C547",
    textColor: "#1a1a1a",
    x: 400,
    y: 60,
    tier: 0,
  },
  {
    id: "pm",
    label: "Product Manager Agent",
    subtitle: "Requirements & Planning",
    desc: "Analyzes user input, generates PRD, defines user stories, acceptance criteria, and feature priorities. Feeds structured specs downstream.",
    color: "#4ECDC4",
    textColor: "#1a1a1a",
    x: 130,
    y: 200,
    tier: 1,
  },
  {
    id: "architect",
    label: "Architect Agent",
    subtitle: "System Design",
    desc: "Designs system architecture, selects tech stack, defines APIs, DB schemas, microservice boundaries, and produces architecture decision records.",
    color: "#45B7D1",
    textColor: "#1a1a1a",
    x: 400,
    y: 200,
    tier: 1,
  },
  {
    id: "planner",
    label: "Planner Agent",
    subtitle: "Task Decomposition",
    desc: "Breaks architecture into atomic coding tasks with dependency DAG. Determines execution order, parallelism opportunities, and estimated complexity.",
    color: "#96CEB4",
    textColor: "#1a1a1a",
    x: 670,
    y: 200,
    tier: 1,
  },
  {
    id: "coder",
    label: "Coder Agent",
    subtitle: "Code Generation",
    desc: "Writes production code per task specs. Uses RAG to retrieve relevant patterns, existing code, and documentation. Follows architecture constraints.",
    color: "#FF6B6B",
    textColor: "#fff",
    x: 130,
    y: 380,
    tier: 2,
  },
  {
    id: "reviewer",
    label: "Code Reviewer Agent",
    subtitle: "Quality Gate",
    desc: "Reviews generated code for correctness, security, performance, style. Provides structured feedback with severity levels. Can reject and trigger rework.",
    color: "#C06CF0",
    textColor: "#fff",
    x: 400,
    y: 380,
    tier: 2,
  },
  {
    id: "tester",
    label: "Testing Agent",
    subtitle: "Verification & Validation",
    desc: "Generates unit tests, integration tests, and e2e tests. Runs test suites, measures coverage, reports failures with root cause analysis back to Coder.",
    color: "#F38181",
    textColor: "#fff",
    x: 670,
    y: 380,
    tier: 2,
  },
  {
    id: "debugger",
    label: "Debugger Agent",
    subtitle: "Error Resolution",
    desc: "Receives failing tests or runtime errors. Performs root cause analysis using traces & logs. Patches code or escalates to Architect if design flaw detected.",
    color: "#FCE38A",
    textColor: "#1a1a1a",
    x: 130,
    y: 540,
    tier: 3,
  },
  {
    id: "docs",
    label: "Documentation Agent",
    subtitle: "Knowledge Capture",
    desc: "Generates API docs, README, inline comments, architecture docs, and changelog. Updates shared knowledge base used by RAG retrieval.",
    color: "#95E1D3",
    textColor: "#1a1a1a",
    x: 400,
    y: 540,
    tier: 3,
  },
  {
    id: "devops",
    label: "DevOps Agent",
    subtitle: "Build & Deploy",
    desc: "Configures CI/CD pipelines, Dockerfiles, infra-as-code. Handles build, containerization, deployment, and monitoring setup.",
    color: "#AA96DA",
    textColor: "#1a1a1a",
    x: 670,
    y: 540,
    tier: 3,
  },
];

const CONNECTIONS = [
  { from: "orchestrator", to: "pm", label: "Requirements" },
  { from: "orchestrator", to: "architect", label: "Design Brief" },
  { from: "orchestrator", to: "planner", label: "Task Scope" },
  { from: "pm", to: "architect", label: "PRD / Stories" },
  { from: "architect", to: "planner", label: "Architecture" },
  { from: "planner", to: "coder", label: "Task Queue" },
  { from: "coder", to: "reviewer", label: "Pull Request" },
  { from: "reviewer", to: "coder", label: "Feedback", dashed: true },
  { from: "reviewer", to: "tester", label: "Approved Code" },
  { from: "tester", to: "debugger", label: "Failures", dashed: true },
  { from: "debugger", to: "coder", label: "Patches", dashed: true },
  { from: "tester", to: "docs", label: "Passing Suite" },
  { from: "tester", to: "devops", label: "Ready to Deploy" },
  { from: "docs", to: "devops", label: "Docs Bundle" },
];

const INFRA = [
  {
    id: "memory",
    label: "Shared Memory Store",
    desc: "Long-term episodic memory (vector DB) + short-term working memory (context window). Stores decisions, rationale, agent interactions, code evolution history. Each agent reads/writes scoped memory segments.",
    icon: "🧠",
    color: "#2D3436",
    border: "#E8C547",
  },
  {
    id: "rag",
    label: "RAG Pipeline",
    desc: "Retrieval-Augmented Generation: embeds codebase, docs, Stack Overflow, API references into vector store. Agents query relevant chunks before generating. Includes re-ranking and context compression.",
    icon: "🔍",
    color: "#2D3436",
    border: "#FF6B6B",
  },
  {
    id: "kb",
    label: "Knowledge Base",
    desc: "Persistent project knowledge: architecture decisions, coding standards, resolved bugs, test patterns, deployment configs. Continuously updated by Documentation Agent. Source of truth for RAG.",
    icon: "📚",
    color: "#2D3436",
    border: "#4ECDC4",
  },
  {
    id: "msg",
    label: "Message Bus",
    desc: "Async event-driven communication between agents. Supports pub/sub patterns, task queues, priority routing, and dead-letter handling. Enables parallel agent execution.",
    icon: "⚡",
    color: "#2D3436",
    border: "#C06CF0",
  },
];

const TIERS = [
  { label: "COORDINATION LAYER", y: 40, color: "#E8C547" },
  { label: "PLANNING LAYER", y: 180, color: "#4ECDC4" },
  { label: "EXECUTION LAYER", y: 360, color: "#FF6B6B" },
  { label: "SUPPORT LAYER", y: 520, color: "#95E1D3" },
];

const NODE_W = 200;
const NODE_H = 80;

function getCenter(agent) {
  return { cx: agent.x + NODE_W / 2, cy: agent.y + NODE_H / 2 };
}

function buildPath(fromAgent, toAgent) {
  const { cx: x1, cy: y1 } = getCenter(fromAgent);
  const { cx: x2, cy: y2 } = getCenter(toAgent);
  const dx = x2 - x1;
  const dy = y2 - y1;

  if (Math.abs(dy) < 10) {
    const cy = y1 - 40;
    return `M${x1},${y1} Q${(x1 + x2) / 2},${cy} ${x2},${y2}`;
  }

  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;
  const offset = dx === 0 ? 0 : dx > 0 ? 20 : -20;
  return `M${x1},${y1} Q${mx + offset},${my} ${x2},${y2}`;
}

export default function MultiAgentArchitecture() {
  const [selected, setSelected] = useState(null);
  const [hoveredConn, setHoveredConn] = useState(null);
  const [activeTab, setActiveTab] = useState("agents");
  const svgRef = useRef(null);

  const agentMap = {};
  AGENTS.forEach((a) => (agentMap[a.id] = a));

  const selectedAgent = selected ? agentMap[selected] : null;
  const selectedInfra = selected ? INFRA.find((i) => i.id === selected) : null;

  const connectedIds = new Set();
  if (selected) {
    CONNECTIONS.forEach((c) => {
      if (c.from === selected) connectedIds.add(c.to);
      if (c.to === selected) connectedIds.add(c.from);
    });
  }

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0D1117",
        color: "#C9D1D9",
        fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace",
        padding: 0,
        margin: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "28px 32px 20px",
          borderBottom: "1px solid #21262D",
          background: "linear-gradient(180deg, #161B22 0%, #0D1117 100%)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            marginBottom: 6,
          }}
        >
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: "#E8C547",
              boxShadow: "0 0 12px #E8C54788",
            }}
          />
          <h1
            style={{
              margin: 0,
              fontSize: 22,
              fontWeight: 700,
              letterSpacing: "-0.5px",
              color: "#F0F6FC",
              fontFamily:
                "'Space Grotesk', 'Inter', -apple-system, sans-serif",
            }}
          >
            Multi-Agent Software Engineering System
          </h1>
        </div>
        <p
          style={{
            margin: 0,
            fontSize: 12,
            color: "#8B949E",
            letterSpacing: "0.5px",
          }}
        >
          ARCHITECTURE · MEMORY · RAG · AGENT COORDINATION
        </p>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: "1px solid #21262D",
          background: "#161B22",
        }}
      >
        {[
          { key: "agents", label: "Agent Graph" },
          { key: "infra", label: "Infrastructure" },
          { key: "flow", label: "Data Flow" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "10px 20px",
              background: "transparent",
              border: "none",
              borderBottom:
                activeTab === tab.key
                  ? "2px solid #E8C547"
                  : "2px solid transparent",
              color: activeTab === tab.key ? "#F0F6FC" : "#8B949E",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              letterSpacing: "0.5px",
              fontFamily: "inherit",
              transition: "all 0.2s",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", minHeight: "calc(100vh - 130px)" }}>
        {/* Main Canvas */}
        <div style={{ flex: 1, padding: 24, overflow: "auto" }}>
          {activeTab === "agents" && (
            <div style={{ position: "relative" }}>
              <svg
                ref={svgRef}
                viewBox="0 0 870 640"
                style={{
                  width: "100%",
                  maxWidth: 870,
                  height: "auto",
                }}
              >
                <defs>
                  <marker
                    id="arrow"
                    viewBox="0 0 10 8"
                    refX="9"
                    refY="4"
                    markerWidth="8"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M0,0 L10,4 L0,8 Z" fill="#8B949E" />
                  </marker>
                  <marker
                    id="arrow-active"
                    viewBox="0 0 10 8"
                    refX="9"
                    refY="4"
                    markerWidth="8"
                    markerHeight="6"
                    orient="auto-start-reverse"
                  >
                    <path d="M0,0 L10,4 L0,8 Z" fill="#E8C547" />
                  </marker>
                  <filter id="glow">
                    <feGaussianBlur stdDeviation="3" result="blur" />
                    <feMerge>
                      <feMergeNode in="blur" />
                      <feMergeNode in="SourceGraphic" />
                    </feMerge>
                  </filter>
                </defs>

                {/* Tier labels */}
                {TIERS.map((t, i) => (
                  <g key={i}>
                    <line
                      x1={10}
                      y1={t.y}
                      x2={860}
                      y2={t.y}
                      stroke="#21262D"
                      strokeDasharray="4,6"
                    />
                    <text
                      x={860}
                      y={t.y + 14}
                      fill={t.color}
                      fontSize={9}
                      fontWeight={700}
                      textAnchor="end"
                      opacity={0.5}
                      fontFamily="inherit"
                      letterSpacing="1.5"
                    >
                      {t.label}
                    </text>
                  </g>
                ))}

                {/* Connections */}
                {CONNECTIONS.map((conn, i) => {
                  const from = agentMap[conn.from];
                  const to = agentMap[conn.to];
                  if (!from || !to) return null;
                  const path = buildPath(from, to);
                  const isActive =
                    selected &&
                    (conn.from === selected || conn.to === selected);
                  const isHovered = hoveredConn === i;

                  return (
                    <g
                      key={i}
                      onMouseEnter={() => setHoveredConn(i)}
                      onMouseLeave={() => setHoveredConn(null)}
                      style={{ cursor: "pointer" }}
                    >
                      <path
                        d={path}
                        fill="none"
                        stroke={
                          isActive
                            ? "#E8C547"
                            : isHovered
                            ? "#C9D1D9"
                            : "#30363D"
                        }
                        strokeWidth={isActive ? 2.5 : isHovered ? 2 : 1.5}
                        strokeDasharray={conn.dashed ? "6,4" : "none"}
                        markerEnd={
                          isActive
                            ? "url(#arrow-active)"
                            : "url(#arrow)"
                        }
                        opacity={
                          selected && !isActive ? 0.15 : isHovered ? 1 : 0.6
                        }
                        style={{ transition: "all 0.3s" }}
                      />
                      {(isHovered || isActive) && (
                        <text
                          dy={-8}
                          fontSize={9}
                          fill={isActive ? "#E8C547" : "#C9D1D9"}
                          fontWeight={600}
                          fontFamily="inherit"
                        >
                          <textPath
                            href={`#conn-path-${i}`}
                            startOffset="50%"
                            textAnchor="middle"
                          >
                            {conn.label}
                          </textPath>
                        </text>
                      )}
                      <path id={`conn-path-${i}`} d={path} fill="none" />
                    </g>
                  );
                })}

                {/* Agent Nodes */}
                {AGENTS.map((agent) => {
                  const isSelected = selected === agent.id;
                  const isConnected = connectedIds.has(agent.id);
                  const dimmed =
                    selected && !isSelected && !isConnected;

                  return (
                    <g
                      key={agent.id}
                      onClick={() =>
                        setSelected(isSelected ? null : agent.id)
                      }
                      style={{ cursor: "pointer" }}
                      opacity={dimmed ? 0.2 : 1}
                    >
                      {isSelected && (
                        <rect
                          x={agent.x - 4}
                          y={agent.y - 4}
                          width={NODE_W + 8}
                          height={NODE_H + 8}
                          rx={12}
                          fill="none"
                          stroke={agent.color}
                          strokeWidth={2}
                          opacity={0.6}
                          filter="url(#glow)"
                        />
                      )}
                      <rect
                        x={agent.x}
                        y={agent.y}
                        width={NODE_W}
                        height={NODE_H}
                        rx={8}
                        fill={agent.color}
                        opacity={isSelected ? 1 : 0.9}
                        style={{ transition: "all 0.2s" }}
                      />
                      <text
                        x={agent.x + NODE_W / 2}
                        y={agent.y + 30}
                        textAnchor="middle"
                        fontSize={12}
                        fontWeight={700}
                        fill={agent.textColor}
                        fontFamily="inherit"
                      >
                        {agent.label}
                      </text>
                      <text
                        x={agent.x + NODE_W / 2}
                        y={agent.y + 50}
                        textAnchor="middle"
                        fontSize={9}
                        fill={agent.textColor}
                        opacity={0.7}
                        fontFamily="inherit"
                        letterSpacing="0.5"
                      >
                        {agent.subtitle}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}

          {activeTab === "infra" && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 16,
                maxWidth: 800,
              }}
            >
              {INFRA.map((item) => (
                <div
                  key={item.id}
                  onClick={() =>
                    setSelected(selected === item.id ? null : item.id)
                  }
                  style={{
                    background: item.color,
                    border: `1.5px solid ${
                      selected === item.id ? item.border : "#30363D"
                    }`,
                    borderRadius: 10,
                    padding: 20,
                    cursor: "pointer",
                    transition: "all 0.2s",
                    boxShadow:
                      selected === item.id
                        ? `0 0 20px ${item.border}33`
                        : "none",
                  }}
                >
                  <div
                    style={{
                      fontSize: 28,
                      marginBottom: 8,
                    }}
                  >
                    {item.icon}
                  </div>
                  <h3
                    style={{
                      margin: "0 0 8px",
                      fontSize: 14,
                      fontWeight: 700,
                      color: item.border,
                    }}
                  >
                    {item.label}
                  </h3>
                  <p
                    style={{
                      margin: 0,
                      fontSize: 11,
                      lineHeight: 1.6,
                      color: "#8B949E",
                    }}
                  >
                    {item.desc}
                  </p>
                </div>
              ))}

              {/* Memory Architecture Detail */}
              <div
                style={{
                  gridColumn: "1 / -1",
                  background: "#161B22",
                  border: "1px solid #21262D",
                  borderRadius: 10,
                  padding: 20,
                }}
              >
                <h3
                  style={{
                    margin: "0 0 14px",
                    fontSize: 13,
                    fontWeight: 700,
                    color: "#E8C547",
                    letterSpacing: "0.5px",
                  }}
                >
                  MEMORY ARCHITECTURE DETAIL
                </h3>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr 1fr",
                    gap: 12,
                  }}
                >
                  {[
                    {
                      title: "Working Memory",
                      items:
                        "Current task context, active agent state, in-flight code diffs, live test results. Cleared per task cycle.",
                      c: "#FF6B6B",
                    },
                    {
                      title: "Episodic Memory",
                      items:
                        "Past decisions, bug resolutions, review feedback, architectural trade-offs. Vector-indexed for similarity retrieval.",
                      c: "#4ECDC4",
                    },
                    {
                      title: "Semantic Memory",
                      items:
                        "Domain knowledge, coding patterns, API schemas, best practices. Populated via RAG from codebase + external docs.",
                      c: "#C06CF0",
                    },
                  ].map((mem) => (
                    <div
                      key={mem.title}
                      style={{
                        background: "#0D1117",
                        borderRadius: 8,
                        padding: 14,
                        borderLeft: `3px solid ${mem.c}`,
                      }}
                    >
                      <h4
                        style={{
                          margin: "0 0 6px",
                          fontSize: 11,
                          fontWeight: 700,
                          color: mem.c,
                        }}
                      >
                        {mem.title}
                      </h4>
                      <p
                        style={{
                          margin: 0,
                          fontSize: 10,
                          lineHeight: 1.6,
                          color: "#8B949E",
                        }}
                      >
                        {mem.items}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === "flow" && (
            <div style={{ maxWidth: 800 }}>
              <div
                style={{
                  background: "#161B22",
                  border: "1px solid #21262D",
                  borderRadius: 10,
                  padding: 24,
                  marginBottom: 16,
                }}
              >
                <h3
                  style={{
                    margin: "0 0 16px",
                    fontSize: 13,
                    fontWeight: 700,
                    color: "#E8C547",
                    letterSpacing: "0.5px",
                  }}
                >
                  END-TO-END PIPELINE
                </h3>
                {[
                  {
                    step: "1",
                    label: "User Input",
                    detail:
                      'Natural language requirement → Orchestrator parses intent, creates project context in Memory Store',
                    color: "#E8C547",
                  },
                  {
                    step: "2",
                    label: "Spec Generation",
                    detail:
                      "PM Agent generates PRD with user stories. RAG retrieves similar past projects for reference. Architect designs system.",
                    color: "#4ECDC4",
                  },
                  {
                    step: "3",
                    label: "Task Planning",
                    detail:
                      "Planner creates dependency DAG of atomic tasks. Each task includes: spec, constraints, relevant code context from RAG, estimated complexity.",
                    color: "#96CEB4",
                  },
                  {
                    step: "4",
                    label: "Code → Review → Test Loop",
                    detail:
                      "Coder generates code (RAG-augmented). Reviewer gates quality. Tester validates. Failures route to Debugger. Loop until all tests pass.",
                    color: "#FF6B6B",
                  },
                  {
                    step: "5",
                    label: "Documentation & Deploy",
                    detail:
                      "Docs Agent updates knowledge base (feeds back into RAG). DevOps Agent builds, containerizes, deploys. Memory Store logs full project history.",
                    color: "#95E1D3",
                  },
                ].map((s) => (
                  <div
                    key={s.step}
                    style={{
                      display: "flex",
                      gap: 14,
                      marginBottom: 16,
                      alignItems: "flex-start",
                    }}
                  >
                    <div
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: "50%",
                        background: s.color,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontWeight: 800,
                        fontSize: 13,
                        color: "#0D1117",
                        flexShrink: 0,
                      }}
                    >
                      {s.step}
                    </div>
                    <div>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 700,
                          color: "#F0F6FC",
                          marginBottom: 3,
                        }}
                      >
                        {s.label}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "#8B949E",
                          lineHeight: 1.6,
                        }}
                      >
                        {s.detail}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* RAG Detail */}
              <div
                style={{
                  background: "#161B22",
                  border: "1px solid #21262D",
                  borderRadius: 10,
                  padding: 24,
                }}
              >
                <h3
                  style={{
                    margin: "0 0 16px",
                    fontSize: 13,
                    fontWeight: 700,
                    color: "#FF6B6B",
                    letterSpacing: "0.5px",
                  }}
                >
                  RAG PIPELINE DETAIL
                </h3>
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    alignItems: "center",
                    flexWrap: "wrap",
                  }}
                >
                  {[
                    "Codebase + Docs",
                    "→ Chunking",
                    "→ Embedding",
                    "→ Vector DB",
                    "→ Query (agent context)",
                    "→ Re-rank",
                    "→ Context Injection",
                    "→ LLM Generation",
                  ].map((step, i) => (
                    <div
                      key={i}
                      style={{
                        padding: "6px 12px",
                        background:
                          step.startsWith("→") ? "transparent" : "#0D1117",
                        border: step.startsWith("→")
                          ? "none"
                          : "1px solid #30363D",
                        borderRadius: 6,
                        fontSize: 10,
                        color: step.startsWith("→") ? "#8B949E" : "#C9D1D9",
                        fontWeight: step.startsWith("→") ? 400 : 600,
                      }}
                    >
                      {step}
                    </div>
                  ))}
                </div>
                <div
                  style={{
                    marginTop: 16,
                    padding: 12,
                    background: "#0D1117",
                    borderRadius: 8,
                    borderLeft: "3px solid #FF6B6B",
                  }}
                >
                  <p
                    style={{
                      margin: 0,
                      fontSize: 10,
                      color: "#8B949E",
                      lineHeight: 1.6,
                    }}
                  >
                    <strong style={{ color: "#FF6B6B" }}>Key insight:</strong>{" "}
                    Each agent has scoped retrieval — the Coder retrieves code
                    patterns & API docs, the Tester retrieves test patterns &
                    failure history, the Architect retrieves design decisions &
                    trade-offs. This prevents context pollution and keeps
                    retrieval relevant.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Detail Panel */}
        <div
          style={{
            width: 280,
            background: "#161B22",
            borderLeft: "1px solid #21262D",
            padding: 20,
            overflow: "auto",
          }}
        >
          {selectedAgent || selectedInfra ? (
            <div>
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background:
                    selectedAgent?.color || selectedInfra?.border,
                  marginBottom: 10,
                  boxShadow: `0 0 10px ${
                    selectedAgent?.color || selectedInfra?.border
                  }88`,
                }}
              />
              <h2
                style={{
                  margin: "0 0 4px",
                  fontSize: 16,
                  fontWeight: 700,
                  color: "#F0F6FC",
                }}
              >
                {selectedAgent?.label || selectedInfra?.label}
              </h2>
              {selectedAgent && (
                <div
                  style={{
                    fontSize: 10,
                    color: selectedAgent.color,
                    fontWeight: 600,
                    marginBottom: 12,
                    letterSpacing: "0.5px",
                  }}
                >
                  {selectedAgent.subtitle}
                </div>
              )}
              <p
                style={{
                  fontSize: 11,
                  color: "#8B949E",
                  lineHeight: 1.7,
                  margin: "0 0 16px",
                }}
              >
                {selectedAgent?.desc || selectedInfra?.desc}
              </p>

              {selectedAgent && (
                <>
                  <h4
                    style={{
                      margin: "0 0 8px",
                      fontSize: 10,
                      fontWeight: 700,
                      color: "#E8C547",
                      letterSpacing: "1px",
                    }}
                  >
                    CONNECTIONS
                  </h4>
                  {CONNECTIONS.filter(
                    (c) =>
                      c.from === selected || c.to === selected
                  ).map((c, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        padding: "6px 0",
                        borderBottom: "1px solid #21262D",
                        fontSize: 10,
                      }}
                    >
                      <span style={{ color: "#C9D1D9" }}>
                        {c.from === selected
                          ? `→ ${agentMap[c.to]?.label}`
                          : `← ${agentMap[c.from]?.label}`}
                      </span>
                      <span
                        style={{
                          color: "#8B949E",
                          fontStyle: "italic",
                        }}
                      >
                        {c.label}
                      </span>
                    </div>
                  ))}

                  <h4
                    style={{
                      margin: "20px 0 8px",
                      fontSize: 10,
                      fontWeight: 700,
                      color: "#E8C547",
                      letterSpacing: "1px",
                    }}
                  >
                    MEMORY ACCESS
                  </h4>
                  <div
                    style={{
                      fontSize: 10,
                      color: "#8B949E",
                      lineHeight: 1.6,
                      background: "#0D1117",
                      padding: 10,
                      borderRadius: 6,
                    }}
                  >
                    {selected === "orchestrator" &&
                      "Read/Write: Full project state, task registry, agent status. Manages memory lifecycle."}
                    {selected === "pm" &&
                      "Write: Requirements, user stories, acceptance criteria. Read: Past project specs via RAG."}
                    {selected === "architect" &&
                      "Write: Architecture Decision Records, schemas. Read: Past architectures, design patterns via RAG."}
                    {selected === "planner" &&
                      "Write: Task DAG, dependency graph. Read: Architecture docs, complexity estimates from episodic memory."}
                    {selected === "coder" &&
                      "Read: Task spec, codebase context via RAG, coding patterns. Write: Generated code, implementation notes."}
                    {selected === "reviewer" &&
                      "Read: Code diff, architecture constraints, review history. Write: Review feedback, quality metrics."}
                    {selected === "tester" &&
                      "Read: Code, test patterns via RAG, coverage history. Write: Test results, coverage reports, failure logs."}
                    {selected === "debugger" &&
                      "Read: Error traces, code, past bug fixes via RAG. Write: Root cause analysis, patches, regression notes."}
                    {selected === "docs" &&
                      "Read: All agent outputs. Write: API docs, README, architecture docs → feeds back into Knowledge Base."}
                    {selected === "devops" &&
                      "Read: Build configs, infra templates via RAG. Write: CI/CD configs, deployment logs, monitoring setup."}
                  </div>
                </>
              )}
            </div>
          ) : (
            <div>
              <h3
                style={{
                  margin: "0 0 8px",
                  fontSize: 13,
                  color: "#8B949E",
                  fontWeight: 600,
                }}
              >
                Select a node
              </h3>
              <p
                style={{
                  margin: 0,
                  fontSize: 11,
                  color: "#484F58",
                  lineHeight: 1.6,
                }}
              >
                Click any agent or infrastructure component to see its role,
                connections, and memory access patterns.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
