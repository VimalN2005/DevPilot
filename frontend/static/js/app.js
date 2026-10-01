document.addEventListener("DOMContentLoaded", () => {
  let activeRepoId = null;
  let currentWorkflowId = null;

  // 1. Tab Switching
  const tabBtns = document.querySelectorAll(".nav-tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const target = document.getElementById(btn.getAttribute("data-tab"));
      if (target) target.classList.add("active");

      // Auto-load data for specific tabs
      if (btn.getAttribute("data-tab") === "tab-telemetry") loadTelemetry();
      if (btn.getAttribute("data-tab") === "tab-eval") loadEvaluation();
      if (btn.getAttribute("data-tab") === "tab-repos") loadRepos();
      if (btn.getAttribute("data-tab") === "tab-bot") loadBotEvents();
      if (btn.getAttribute("data-tab") === "tab-settings") loadSettings();
    });
  });

  // 2. Load Repositories
  async function loadRepos() {
    try {
      const res = await fetch("/api/v1/repos");
      const repos = await res.json();
      const listEl = document.getElementById("repo-list");
      listEl.innerHTML = "";

      if (repos.length === 0) {
        listEl.innerHTML = "<div style='color: var(--text-muted); font-size: 0.88rem;'>No repositories connected yet. Ingest your first repo above!</div>";
        return;
      }

      document.getElementById("dash-repos-count").textContent = repos.length;
      let totalChunks = 0;

      repos.forEach(repo => {
        totalChunks += repo.total_chunks || 0;
        if (!activeRepoId) activeRepoId = repo.id;

        const item = document.createElement("div");
        item.style.padding = "0.75rem 1rem";
        item.style.background = repo.id === activeRepoId ? "rgba(59, 130, 246, 0.12)" : "var(--bg-card-hover)";
        item.style.border = "1px solid var(--border-color)";
        item.style.borderRadius = "6px";
        item.style.cursor = "pointer";
        item.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong>${repo.name}</strong>
            <span class="badge ${repo.status === 'ready' ? 'badge-green' : 'badge-amber'}">${repo.status.toUpperCase()}</span>
          </div>
          <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem;">
            Files: ${repo.total_files} | Chunks: ${repo.total_chunks} | Branch: ${repo.branch}
          </div>
        `;
        item.onclick = () => {
          activeRepoId = repo.id;
          loadRepos();
        };
        listEl.appendChild(item);
      });

      document.getElementById("dash-chunks-count").textContent = totalChunks;
    } catch (e) {
      console.error("Error loading repos:", e);
    }
  }

  // 3. Connect & Ingest Repository Form
  const repoForm = document.getElementById("connect-repo-form");
  if (repoForm) {
    repoForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = document.getElementById("repo-name").value;
      const url = document.getElementById("repo-url").value;
      const branch = document.getElementById("repo-branch").value;
      const btn = document.getElementById("btn-index-repo");
      const progBox = document.getElementById("repo-progress-container");
      const progBar = document.getElementById("repo-progress-bar");

      btn.disabled = true;
      progBox.style.display = "block";
      progBar.style.width = "20%";

      try {
        const res = await fetch("/api/v1/repos/connect", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, clone_url: url || null, branch })
        });
        const data = await res.json();
        activeRepoId = data.repo_id;

        // Poll job status
        const jobId = data.job_id;
        const interval = setInterval(async () => {
          const jRes = await fetch(`/api/v1/jobs/${jobId}`);
          const job = await jRes.json();
          progBar.style.width = `${Math.max(30, job.progress)}%`;

          if (job.status === "completed" || job.status === "failed") {
            clearInterval(interval);
            btn.disabled = false;
            progBar.style.width = "100%";
            setTimeout(() => { progBox.style.display = "none"; }, 1500);
            loadRepos();
          }
        }, 600);
      } catch (err) {
        alert("Ingestion error: " + err.message);
        btn.disabled = false;
        progBox.style.display = "none";
      }
    });
  }

  // 4. Streaming SSE RAG Chat
  const btnChatSend = document.getElementById("btn-chat-send");
  const chatInput = document.getElementById("chat-query");
  const chatMessages = document.getElementById("chat-messages");

  async function sendChatMessage() {
    const query = chatInput.value.trim();
    if (!query) return;

    if (!activeRepoId) {
      alert("Please ensure a repository is selected under Repository Studio.");
      return;
    }

    // Append User message
    const userMsg = document.createElement("div");
    userMsg.className = "chat-bubble chat-bubble-user";
    userMsg.textContent = query;
    chatMessages.appendChild(userMsg);
    chatInput.value = "";
    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Create AI bubble container
    const aiMsg = document.createElement("div");
    aiMsg.className = "chat-bubble chat-bubble-ai";

    const thoughtContainer = document.createElement("div");
    thoughtContainer.className = "thought-steps";
    aiMsg.appendChild(thoughtContainer);

    const contentText = document.createElement("div");
    contentText.style.whiteSpace = "pre-wrap";
    contentText.style.lineHeight = "1.6";
    aiMsg.appendChild(contentText);

    const citationsBox = document.createElement("div");
    citationsBox.className = "citations-box";
    citationsBox.style.display = "none";
    aiMsg.appendChild(citationsBox);

    chatMessages.appendChild(aiMsg);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
      const response = await fetch("/api/v1/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo_id: activeRepoId, query })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const eventData = JSON.parse(line.substring(6));

            if (eventData.type === "status") {
              const badge = document.createElement("span");
              badge.className = "thought-badge";
              badge.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${eventData.message}`;
              thoughtContainer.appendChild(badge);
            } else if (eventData.type === "token") {
              contentText.textContent += eventData.content;
            } else if (eventData.type === "sources") {
              citationsBox.style.display = "block";
              citationsBox.innerHTML = "<strong>Referenced Code Modules:</strong><br>";
              eventData.data.forEach(s => {
                const chip = document.createElement("span");
                chip.className = "citation-chip";
                chip.textContent = `${s.file_path} (L${s.start_line}-${s.end_line})`;
                citationsBox.appendChild(chip);
              });
            }
          }
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }
    } catch (e) {
      contentText.textContent += "\n[Error communicating with DevPilot stream: " + e.message + "]";
    }
  }

  btnChatSend.addEventListener("click", sendChatMessage);
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChatMessage();
  });

  // 5. AI Issue Analyzer
  const btnAnalyzeIssue = document.getElementById("btn-analyze-issue");
  if (btnAnalyzeIssue) {
    btnAnalyzeIssue.addEventListener("click", async () => {
      const title = document.getElementById("issue-title").value;
      const description = document.getElementById("issue-desc").value;
      const out = document.getElementById("issue-analysis-output");
      btnAnalyzeIssue.disabled = true;
      out.innerHTML = "<div style='color: var(--text-muted);'><i class='fa-solid fa-spinner fa-spin'></i> Triage & Root Cause Analysis in progress...</div>";

      try {
        const res = await fetch("/api/v1/issues/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            repo_id: activeRepoId || "devpilot",
            title,
            description
          })
        });
        const data = await res.json();
        btnAnalyzeIssue.disabled = false;

        document.getElementById("issue-badge-severity").textContent = `Severity: ${data.severity}`;

        out.innerHTML = `
          <div style="margin-bottom: 1rem;">
            <div style="font-weight: 600; font-size: 0.9rem; color: #93c5fd; margin-bottom: 0.25rem;">Implicated Codebase Modules:</div>
            ${data.likely_modules.map(m => `<span class="badge badge-blue" style="margin-right: 0.35rem;">${m}</span>`).join("")}
          </div>
          <div style="margin-bottom: 1rem;">
            <div style="font-weight: 600; font-size: 0.9rem; color: #93c5fd; margin-bottom: 0.25rem;">Probable Root Cause:</div>
            <p style="font-size: 0.88rem; color: var(--text-main);">${data.probable_cause}</p>
          </div>
          <div style="margin-bottom: 1rem;">
            <div style="font-weight: 600; font-size: 0.9rem; color: #93c5fd; margin-bottom: 0.25rem;">Suggested Fix Patch:</div>
            <pre style="max-height: 160px; font-size: 0.82rem;">${data.suggested_fix.replace(/```python|```/g, '')}</pre>
          </div>
          <div>
            <div style="font-weight: 600; font-size: 0.9rem; color: #93c5fd; margin-bottom: 0.25rem;">Suggested Regression Tests:</div>
            <ul style="padding-left: 1.25rem; font-size: 0.85rem; font-family: monospace; color: var(--accent-green);">
              ${data.suggested_tests.map(t => `<li>${t}</li>`).join("")}
            </ul>
          </div>
        `;
      } catch (err) {
        btnAnalyzeIssue.disabled = false;
        out.textContent = "Error: " + err.message;
      }
    });
  }

  // 6. PR Review Agent
  const btnReviewPR = document.getElementById("btn-review-pr");
  if (btnReviewPR) {
    btnReviewPR.addEventListener("click", async () => {
      const pr_title = document.getElementById("pr-title").value;
      const diff_text = document.getElementById("pr-diff").value;
      const out = document.getElementById("pr-audit-output");
      btnReviewPR.disabled = true;
      out.innerHTML = "<div style='color: var(--text-muted);'><i class='fa-solid fa-spinner fa-spin'></i> Auditing PR across 8 dimensions...</div>";

      try {
        const res = await fetch("/api/v1/pr/review", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pr_title, diff_text, pr_number: 142 })
        });
        const data = await res.json();
        btnReviewPR.disabled = false;

        const badge = document.getElementById("pr-verdict-badge");
        badge.textContent = data.verdict;
        badge.className = `badge ${data.verdict === 'APPROVED' ? 'badge-green' : 'badge-rose'}`;

        out.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.75rem;">
            <div>Overall Quality Score: <strong style="color: var(--primary); font-size: 1.1rem;">${data.overall_score}/100</strong></div>
            <div style="font-size: 0.85rem; color: var(--text-muted);">
              Warnings: <span style="color: var(--accent-amber);">${data.warning_count}</span> | Critical: <span style="color: var(--accent-rose);">${data.critical_count}</span>
            </div>
          </div>
          <div style="margin-bottom: 1rem;">
            <div style="font-weight: 600; font-size: 0.9rem; margin-bottom: 0.4rem;">Findings & Recommendations:</div>
            ${data.findings.length === 0 ? "<div style='color: var(--accent-green);'>✓ Clean PR! No violations found across 8 audit dimensions.</div>" : data.findings.map(f => `
              <div style="background: #0b0f17; border-left: 3px solid ${f.severity === 'CRITICAL' ? 'var(--accent-rose)' : 'var(--accent-amber)'}; padding: 0.75rem; margin-bottom: 0.6rem; border-radius: 4px;">
                <div style="display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 0.25rem;">
                  <strong style="color: ${f.severity === 'CRITICAL' ? 'var(--accent-rose)' : 'var(--accent-amber)'};">${f.category} (${f.severity})</strong>
                  <span style="font-family: monospace; color: var(--text-muted);">${f.file}</span>
                </div>
                <div style="font-size: 0.85rem; margin-bottom: 0.25rem;">${f.issue}</div>
                <div style="font-size: 0.8rem; color: #94a3b8;"><i class="fa-solid fa-lightbulb" style="color: var(--accent-cyan);"></i> Fix: ${f.recommendation}</div>
              </div>
            `).join("")}
          </div>
        `;
      } catch (err) {
        btnReviewPR.disabled = false;
        out.textContent = "Error: " + err.message;
      }
    });
  }

  // 7. Multi-Agent Workflow
  const btnRunWorkflow = document.getElementById("btn-run-workflow");
  if (btnRunWorkflow) {
    btnRunWorkflow.addEventListener("click", async () => {
      const goal = document.getElementById("agent-goal").value;
      btnRunWorkflow.disabled = true;
      const area = document.getElementById("workflow-execution-area");
      const stepsList = document.getElementById("agent-steps-list");
      area.style.display = "block";
      stepsList.innerHTML = "<div style='color: var(--text-muted); padding: 1rem;'><i class='fa-solid fa-spinner fa-spin'></i> Spawning Planner, Search, Analysis, Test, and Reviewer Agents...</div>";

      try {
        const res = await fetch("/api/v1/agents/workflow", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            repo_id: activeRepoId || "devpilot",
            issue_title: goal,
            issue_description: goal
          })
        });
        const data = await res.json();
        btnRunWorkflow.disabled = false;
        currentWorkflowId = data.workflow_id;

        document.getElementById("workflow-status-badge").textContent = data.status.replace(/_/g, " ");
        document.getElementById("workflow-proposed-patch").textContent = data.proposed_patch;

        stepsList.innerHTML = data.agents.map(a => `
          <div class="workflow-step-card">
            <div class="workflow-step-header">
              <span>${a.agent}</span>
              <span class="badge badge-green">${a.status}</span>
            </div>
            <div style="font-size: 0.85rem; color: var(--text-muted);">
              ${a.agent === 'Planner Agent' ? a.milestones.join('<br>') : (a.root_cause || a.implicated_files?.join(', ') || a.verdict || 'Task completed.')}
            </div>
          </div>
        `).join("");

        document.getElementById("human-approval-gate").style.display = "block";
      } catch (err) {
        btnRunWorkflow.disabled = false;
        stepsList.textContent = "Workflow error: " + err.message;
      }
    });
  }

  // Human Approval Button
  const btnApprove = document.getElementById("btn-approve-patch");
  if (btnApprove) {
    btnApprove.addEventListener("click", async () => {
      if (!currentWorkflowId) return;
      btnApprove.disabled = true;
      try {
        const res = await fetch("/api/v1/agents/approve-patch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ workflow_id: currentWorkflowId, approved_by: "Lead Engineer" })
        });
        const data = await res.json();
        document.getElementById("workflow-status-badge").textContent = "APPROVED & COMMITTED";
        document.getElementById("workflow-status-badge").className = "badge badge-green";
        alert(`Patch successfully approved! Commit SHA: ${data.commit_sha}`);
      } catch (err) {
        alert("Approval failed: " + err.message);
      } finally {
        btnApprove.disabled = false;
      }
    });
  }

  // 8. Load Observability Telemetry
  async function loadTelemetry() {
    try {
      const res = await fetch("/api/v1/telemetry/metrics");
      const data = await res.json();
      document.getElementById("tele-requests").textContent = data.total_requests.toLocaleString();
      document.getElementById("tele-latency").textContent = `${data.avg_latency_sec}s`;
      document.getElementById("tele-error").textContent = `${data.error_rate_pct}%`;
      document.getElementById("tele-cost").textContent = `$${data.estimated_cost_usd}`;

      const tbody = document.getElementById("telemetry-table-body");
      tbody.innerHTML = "";
      data.recent_logs.forEach(log => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td style="font-family: monospace; font-size: 0.8rem;">${log.request_id}</td>
          <td>${log.endpoint}</td>
          <td><span class="badge badge-purple">${log.model}</span></td>
          <td style="font-family: monospace;">${log.tokens_input} / ${log.tokens_output}</td>
          <td>${log.latency_ms}ms</td>
          <td>$${log.cost_usd.toFixed(6)}</td>
          <td><span class="badge ${log.success ? 'badge-green' : 'badge-rose'}">${log.success ? 'SUCCESS' : 'FAILED'}</span></td>
        `;
        tbody.appendChild(row);
      });
    } catch (e) {
      console.error("Error loading telemetry:", e);
    }
  }

  // 9. Load AI Evaluation
  async function loadEvaluation() {
    try {
      const res = await fetch("/api/v1/eval/latest");
      const data = await res.json();
      document.getElementById("eval-faith").textContent = `${data.faithfulness}%`;
      document.getElementById("eval-rel").textContent = `${data.answer_relevance}%`;
      document.getElementById("eval-recall").textContent = `${data.retrieval_recall}%`;
      document.getElementById("eval-lat").textContent = `${data.avg_latency_sec}s`;

      const tbody = document.getElementById("eval-table-body");
      tbody.innerHTML = "";
      (data.benchmark_results || []).forEach(b => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td style="font-weight: 500;">${b.question}</td>
          <td style="font-family: monospace; font-size: 0.8rem;">${b.expected_target}</td>
          <td style="font-family: monospace; font-size: 0.8rem;">${b.retrieved_target}</td>
          <td><span class="badge ${b.recall === 1 ? 'badge-green' : 'badge-rose'}">${(b.recall * 100).toFixed(0)}%</span></td>
          <td><span class="badge badge-cyan">${(b.faithfulness * 100).toFixed(0)}%</span></td>
          <td>${b.latency_sec}s</td>
        `;
        tbody.appendChild(row);
      });
    } catch (e) {
      console.error("Error loading eval:", e);
    }
  }

  const btnRunEval = document.getElementById("btn-run-eval");
  if (btnRunEval) {
    btnRunEval.addEventListener("click", async () => {
      btnRunEval.disabled = true;
      btnRunEval.innerHTML = "<i class='fa-solid fa-spinner fa-spin'></i> Running Benchmarks...";
      try {
        await fetch("/api/v1/eval/run", { method: "POST" });
        await loadEvaluation();
      } finally {
        btnRunEval.disabled = false;
        btnRunEval.innerHTML = "<i class='fa-solid fa-play'></i> Re-Run Benchmark Suite";
      }
    });
  }

  // 10. Settings Management
  async function loadSettings() {
    try {
      const res = await fetch("/api/v1/settings");
      const data = await res.json();

      const provSelect = document.getElementById("cfg-provider");
      const modelInput = document.getElementById("cfg-model");
      if (provSelect && data.provider) provSelect.value = data.provider;
      if (modelInput && data.model) modelInput.value = data.model;

      const badgeModel = document.getElementById("badge-model");
      if (badgeModel && data.model) {
        badgeModel.innerHTML = `<i class="fa-solid fa-microchip"></i> ${data.model}`;
      }

      // Update key status badges
      const gBadge = document.getElementById("status-gemini-key");
      if (gBadge) {
        gBadge.textContent = data.has_gemini_key ? `Configured (${data.gemini_key_masked})` : "Not Configured";
        gBadge.className = `badge ${data.has_gemini_key ? "badge-green" : "badge-amber"}`;
      }

      const oBadge = document.getElementById("status-openai-key");
      if (oBadge) {
        oBadge.textContent = data.has_openai_key ? `Configured (${data.openai_key_masked})` : "Not Configured";
        oBadge.className = `badge ${data.has_openai_key ? "badge-green" : "badge-amber"}`;
      }

      const ghBadge = document.getElementById("status-github-token");
      if (ghBadge) {
        ghBadge.textContent = data.has_github_token ? `Configured (${data.github_token_masked})` : "Not Configured";
        ghBadge.className = `badge ${data.has_github_token ? "badge-green" : "badge-amber"}`;
      }

      const sysDb = document.getElementById("sys-db-type");
      if (sysDb && data.database_type) sysDb.textContent = data.database_type;

      const sysEnv = document.getElementById("sys-env");
      if (sysEnv && data.environment) sysEnv.textContent = data.environment;
    } catch (e) {
      console.error("Error loading settings:", e);
    }
  }

  const btnSaveSettings = document.getElementById("btn-save-settings");
  if (btnSaveSettings) {
    btnSaveSettings.addEventListener("click", async () => {
      const provider = document.getElementById("cfg-provider").value;
      const model = document.getElementById("cfg-model").value;
      const gemini_key = document.getElementById("cfg-gemini-key").value;
      const openai_key = document.getElementById("cfg-openai-key").value;
      const github_token = document.getElementById("cfg-github-token").value;
      const msgBox = document.getElementById("settings-status-msg");

      btnSaveSettings.disabled = true;
      btnSaveSettings.innerHTML = "<i class='fa-solid fa-spinner fa-spin'></i> Saving...";

      const payload = { provider, model };
      if (gemini_key.trim()) payload.gemini_api_key = gemini_key.trim();
      if (openai_key.trim()) payload.openai_api_key = openai_key.trim();
      if (github_token.trim()) payload.github_token = github_token.trim();

      try {
        const res = await fetch("/api/v1/settings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        msgBox.style.display = "block";
        msgBox.style.color = "var(--accent-green)";
        msgBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${data.message} Active Model: <strong>${data.model}</strong>`;

        // Clear password inputs
        document.getElementById("cfg-gemini-key").value = "";
        document.getElementById("cfg-openai-key").value = "";
        document.getElementById("cfg-github-token").value = "";

        await loadSettings();
        setTimeout(() => { msgBox.style.display = "none"; }, 4000);
      } catch (err) {
        msgBox.style.display = "block";
        msgBox.style.color = "var(--accent-rose)";
        msgBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Failed to save settings: ${err.message}`;
      } finally {
        btnSaveSettings.disabled = false;
        btnSaveSettings.innerHTML = "<i class='fa-solid fa-floppy-disk'></i> Save Settings";
      }
    });
  }

  const btnTestConn = document.getElementById("btn-test-connection");
  if (btnTestConn) {
    btnTestConn.addEventListener("click", async () => {
      const provider = document.getElementById("cfg-provider").value;
      const model = document.getElementById("cfg-model").value;
      const gemini_key = document.getElementById("cfg-gemini-key").value;
      const openai_key = document.getElementById("cfg-openai-key").value;
      const msgBox = document.getElementById("settings-status-msg");

      btnTestConn.disabled = true;
      btnTestConn.innerHTML = "<i class='fa-solid fa-spinner fa-spin'></i> Testing...";
      msgBox.style.display = "block";
      msgBox.style.color = "var(--text-muted)";
      msgBox.innerHTML = "Pinging AI provider endpoint...";

      try {
        const res = await fetch("/api/v1/settings/test-connection", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider,
            model,
            api_key: provider === "gemini" ? (gemini_key.trim() || undefined) : (openai_key.trim() || undefined)
          })
        });
        const data = await res.json();
        if (data.status === "success") {
          msgBox.style.color = "var(--accent-green)";
          msgBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${data.message}`;
        } else {
          msgBox.style.color = "var(--accent-amber)";
          msgBox.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> ${data.message}`;
        }
      } catch (err) {
        msgBox.style.color = "var(--accent-rose)";
        msgBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Connection error: ${err.message}`;
      } finally {
        btnTestConn.disabled = false;
        btnTestConn.innerHTML = "<i class='fa-solid fa-plug-circle-check'></i> Test Connection";
      }
    });
  }

  // 11. GitHub Bot & Webhook Studio
  async function loadBotEvents() {
    try {
      const res = await fetch("/api/v1/github/events");
      const data = await res.json();
      const tbody = document.getElementById("bot-events-table-body");
      if (!tbody) return;

      tbody.innerHTML = "";
      if (!data.events || data.events.length === 0) {
        tbody.innerHTML = "<tr><td colspan='6' style='text-align: center; color: var(--text-muted);'>No webhook events received yet. Dispatch a simulated event above!</td></tr>";
        return;
      }

      data.events.forEach(evt => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td style="font-family: monospace; font-size: 0.8rem;">${evt.id}</td>
          <td><span class="badge ${evt.type === 'pull_request' ? 'badge-purple' : (evt.type === 'issues' ? 'badge-amber' : 'badge-blue')}">${evt.type}.${evt.action}</span></td>
          <td>${evt.repository}</td>
          <td style="font-family: monospace;">#${evt.number}</td>
          <td style="font-weight: 500;">${evt.title}</td>
          <td><span class="badge ${evt.post_status === 'success' || evt.post_status === 'simulated' ? 'badge-green' : 'badge-rose'}">${(evt.post_status || 'DELIVERED').toUpperCase()}</span></td>
        `;
        row.style.cursor = "pointer";
        row.onclick = () => {
          const preview = document.getElementById("bot-comment-preview");
          if (preview && evt.comment_markdown) {
            preview.textContent = evt.comment_markdown;
          }
        };
        tbody.appendChild(row);
      });
    } catch (e) {
      console.error("Error loading bot events:", e);
    }
  }

  const botEventType = document.getElementById("bot-event-type");
  if (botEventType) {
    botEventType.addEventListener("change", () => {
      const t = botEventType.value;
      const titleInput = document.getElementById("bot-event-title");
      const bodyInput = document.getElementById("bot-event-body");

      if (t === "pull_request") {
        titleInput.value = "feat(auth): add user logout endpoint and token revoke";
        bodyInput.value = "diff --git a/backend/app/auth.py b/backend/app/auth.py\n@@ -10,4 +10,6 @@\n+def logout():\n+    # Token not revoked in DB\n+    session.clear()\n+    return {'message': 'Logged out'}";
      } else if (t === "issues") {
        titleInput.value = "API returns 500 when refresh token expires";
        bodyInput.value = "When a user's refresh token reaches expiration, calling POST /api/v1/auth/refresh throws an unhandled jwt.ExpiredSignatureError resulting in HTTP 500 instead of a clean 401 Unauthorized.";
      } else if (t === "issue_comment") {
        titleInput.value = "Slash Command on PR #142";
        bodyInput.value = "/devpilot review";
      }
    });
  }

  const btnSimulate = document.getElementById("btn-simulate-webhook");
  if (btnSimulate) {
    btnSimulate.addEventListener("click", async () => {
      const event_type = document.getElementById("bot-event-type").value;
      const repo_name = document.getElementById("bot-repo-name").value;
      const number = parseInt(document.getElementById("bot-pr-num").value) || 142;
      const title = document.getElementById("bot-event-title").value;
      const bodyOrDiff = document.getElementById("bot-event-body").value;
      const preview = document.getElementById("bot-comment-preview");
      const badge = document.getElementById("bot-status-badge");

      btnSimulate.disabled = true;
      btnSimulate.innerHTML = "<i class='fa-solid fa-spinner fa-spin'></i> Processing Webhook...";
      badge.textContent = "Analyzing & Generating...";
      badge.className = "badge badge-purple";

      try {
        const payload = {
          event_type,
          repo_name,
          number,
          title
        };
        if (event_type === "pull_request") payload.diff_text = bodyOrDiff;
        else if (event_type === "issues") payload.body = bodyOrDiff;
        else if (event_type === "issue_comment") payload.command = bodyOrDiff;

        const res = await fetch("/api/v1/github/simulate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();

        badge.textContent = "Delivered & Commented";
        badge.className = "badge badge-green";

        const commentText = data.comment || data.response || JSON.stringify(data, null, 2);
        preview.textContent = commentText;

        await loadBotEvents();
      } catch (err) {
        badge.textContent = "Error";
        badge.className = "badge badge-rose";
        preview.textContent = "Webhook error: " + err.message;
      } finally {
        btnSimulate.disabled = false;
        btnSimulate.innerHTML = "<i class='fa-solid fa-paper-plane'></i> Dispatch Webhook Event";
      }
    });
  }

  const btnRefreshBot = document.getElementById("btn-refresh-bot-events");
  if (btnRefreshBot) {
    btnRefreshBot.addEventListener("click", loadBotEvents);
  }

  // Initial Boot
  loadRepos();
  loadSettings();
});
