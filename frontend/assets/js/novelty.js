/**
 * Lemma Novelty Advisor & Conference Acceptance Engine (novelty.js)
 * 
 * Features:
 * - 5-Dimensional Novelty Vector (Dynamic SVG Radar Chart)
 * - Reviewer 2 Attack Simulation & Tactical Rebuttal Shield
 * - Prior Art Delta Matrix (vs real arXiv / Semantic Scholar papers)
 * - Conference Venue Fit & Acceptance Probability Meter
 * - One-Click IEEE/ACM Contribution Statement Polisher
 */

(function () {
    let noveltyData = null;
    let activeTone = "Pioneering & Authoritative";

    function getApiBaseUrl() {
        if (window.APIConfigManager && typeof window.APIConfigManager.getApiBaseUrl === 'function') {
            return window.APIConfigManager.getApiBaseUrl();
        }
        return window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
            ? 'http://localhost:8000'
            : window.location.origin;
    }

    function initNoveltyAdvisor() {
        const navNovelty = document.getElementById("nav-novelty");
        const btnAnalyze = document.getElementById("btn-novelty-analyze");
        const btnSample = document.getElementById("btn-novelty-sample");
        const fileInput = document.getElementById("novelty-file-input");
        const dropZone = document.getElementById("novelty-dropzone");
        const inputArea = document.getElementById("novelty-input-text");

        if (navNovelty) {
            navNovelty.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".sidebar-nav li").forEach(el => el.classList.remove("active"));
                navNovelty.classList.add("active");
                if (typeof window.showView === 'function') {
                    window.showView("novelty-view");
                } else {
                    document.querySelectorAll(".workspace-view").forEach(v => v.classList.add("hidden"));
                    const target = document.getElementById("novelty-view");
                    if (target) target.classList.remove("hidden");
                }
            });
        }

        // Sample text loader
        if (btnSample && inputArea) {
            btnSample.addEventListener("click", () => {
                inputArea.value = `Title: Linear-State Attention for Scalable Deep Representation Learning\n\nAbstract:\nIn this paper, we propose Linear-State Attention (LSA), a novel architectural mechanism for deep representation learning. Unlike classical softmax self-attention which suffers from quadratic complexity O(N^2), our formulation projects queries and keys into an orthogonal reproducing kernel Hilbert space, guaranteeing strictly linear computational complexity O(N) and reduced memory footprint. We evaluate LSA against established SOTA baselines including Transformer and FlashAttention across four standard language modeling benchmarks. Our empirical results demonstrate a 2.8x speedup and statistically significant improvements (p < 0.01) in perplexity while maintaining parameter efficiency. Furthermore, we provide formal proof of the convergence bounds in Theorem 1 and conduct extensive component-wise ablations.`;
                const domainSelect = document.getElementById("novelty-domain-select");
                if (domainSelect) domainSelect.value = "Artificial Intelligence & Machine Learning";
            });
        }

        // File dropzone
        if (dropZone && fileInput) {
            dropZone.addEventListener("click", () => fileInput.click());
            fileInput.addEventListener("change", (e) => {
                if (e.target.files.length > 0) {
                    handleNoveltyFile(e.target.files[0]);
                }
            });

            dropZone.addEventListener("dragover", (e) => {
                e.preventDefault();
                dropZone.classList.add("dragover");
            });
            dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
            dropZone.addEventListener("drop", (e) => {
                e.preventDefault();
                dropZone.classList.remove("dragover");
                if (e.dataTransfer.files.length > 0) {
                    handleNoveltyFile(e.dataTransfer.files[0]);
                }
            });
        }

        if (btnAnalyze) {
            btnAnalyze.addEventListener("click", triggerNoveltyAnalysis);
        }

        // Return button to run another audit or edit inputs
        const btnNewAudit = document.getElementById("btn-novelty-new-audit");
        if (btnNewAudit) {
            btnNewAudit.addEventListener("click", () => {
                const inputCard = document.getElementById("novelty-input-card");
                const results = document.getElementById("novelty-results-container");
                if (results) results.classList.add("hidden");
                if (inputCard) inputCard.classList.remove("hidden");
                const noveltyView = document.getElementById("novelty-view");
                if (noveltyView) {
                    noveltyView.scrollIntoView({ behavior: 'smooth', block: 'start' });
                } else {
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            });
        }

        // Tab switching within novelty view
        document.querySelectorAll(".novelty-tab-btn").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const targetTab = btn.getAttribute("data-tab");
                document.querySelectorAll(".novelty-tab-btn").forEach(b => b.classList.remove("active"));
                document.querySelectorAll(".novelty-tab-pane").forEach(p => p.classList.add("hidden"));
                btn.classList.add("active");
                const pane = document.getElementById(`novelty-pane-${targetTab}`);
                if (pane) pane.classList.remove("hidden");
            });
        });
    }

    let selectedNoveltyFile = null;

    function handleNoveltyFile(file) {
        const allowed = ["txt", "docx", "pdf"];
        const ext = file.name.split(".").pop().toLowerCase();
        if (!allowed.includes(ext)) {
            showToastMessage(`Unsupported file format .${ext}. Please use PDF, DOCX, or TXT.`, "error");
            return;
        }
        selectedNoveltyFile = file;
        const dropText = document.getElementById("novelty-dropzone-text");
        if (dropText) {
            dropText.innerHTML = `<strong>Selected:</strong> ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
        }
        showToastMessage(`Loaded file: ${file.name}`, "info");
    }

    async function triggerNoveltyAnalysis() {
        const textInput = document.getElementById("novelty-input-text")?.value?.trim() || "";
        const titleInput = document.getElementById("novelty-title-input")?.value?.trim() || "";
        const domainSelect = document.getElementById("novelty-domain-select")?.value || "";

        if (!textInput && !selectedNoveltyFile) {
            showToastMessage("Please enter abstract text or upload a document first.", "error");
            return;
        }

        const inputCard = document.getElementById("novelty-input-card");
        const loader = document.getElementById("novelty-loading-state");
        const results = document.getElementById("novelty-results-container");
        const emptyState = document.getElementById("novelty-empty-state");

        // Hide generation input card immediately when analysis starts so screen is replaced
        if (inputCard) inputCard.classList.add("hidden");
        if (loader) loader.classList.remove("hidden");
        if (results) results.classList.add("hidden");
        if (emptyState) emptyState.classList.add("hidden");

        // Animate progressive steps
        simulateLoadingSteps();

        try {
            const baseUrl = await getApiBaseUrl();
            let response;

            if (selectedNoveltyFile) {
                const formData = new FormData();
                formData.append("file", selectedNoveltyFile);
                if (textInput) formData.append("text", textInput);
                if (titleInput) formData.append("title", titleInput);
                if (domainSelect) formData.append("domain", domainSelect);
                response = await fetch(`${baseUrl}/api/v1/novelty/analyze`, {
                    method: "POST",
                    body: formData
                });
            } else {
                const formData = new FormData();
                formData.append("text", textInput);
                if (titleInput) formData.append("title", titleInput);
                if (domainSelect) formData.append("domain", domainSelect);
                response = await fetch(`${baseUrl}/api/v1/novelty/analyze`, {
                    method: "POST",
                    body: formData
                });
            }

            if (!response.ok) {
                const err = await response.json().catch(() => ({ detail: "Analysis failed" }));
                throw new Error(err.detail || `Server returned status ${response.status}`);
            }

            const data = await response.json();
            noveltyData = data;
            renderNoveltyDashboard(data);

            if (loader) loader.classList.add("hidden");
            if (results) results.classList.remove("hidden");
            // Screen content replaced: generation window stays hidden, scroll directly to report at top
            const noveltyView = document.getElementById("novelty-view");
            if (noveltyView) {
                noveltyView.scrollIntoView({ behavior: 'smooth', block: 'start' });
            } else {
                window.scrollTo({ top: 0, behavior: 'smooth' });
            }
            showToastMessage("Novelty & Defensibility audit completed!", "success");

        } catch (error) {
            console.error("Novelty analysis error:", error);
            if (loader) loader.classList.add("hidden");
            if (inputCard) inputCard.classList.remove("hidden"); // restore input form on failure
            if (emptyState) emptyState.classList.remove("hidden");
            showToastMessage(`Analysis failed: ${error.message}`, "error");
        }
    }

    function simulateLoadingSteps() {
        const stepEl = document.getElementById("novelty-loading-step-text");
        const steps = [
            "Extracting core research claims and mathematical formulations...",
            "Scanning arXiv and Semantic Scholar for closest published prior art...",
            "Computing 5-dimensional novelty vector & algorithmic differentiation...",
            "Simulating Reviewer 2 adversarial critiques & defense rebuttals...",
            "Calibrating conference venue fit & generating polished IEEE contributions..."
        ];
        let idx = 0;
        const interval = setInterval(() => {
            idx++;
            if (idx < steps.length && stepEl) {
                stepEl.textContent = steps[idx];
            } else {
                clearInterval(interval);
            }
        }, 700);
    }

    function renderNoveltyDashboard(data) {
        // 1. Executive Banner
        const scoreEl = document.getElementById("novelty-score-number");
        const tierEl = document.getElementById("novelty-tier-badge");
        const titleEl = document.getElementById("novelty-doc-title");
        const verdictEl = document.getElementById("novelty-executive-verdict");
        const domainEl = document.getElementById("novelty-detected-domain");

        if (scoreEl) scoreEl.textContent = `${data.overall_novelty_score}%`;
        if (tierEl) {
            tierEl.textContent = data.novelty_tier;
            tierEl.style.backgroundColor = `${data.tier_badge_color}22`;
            tierEl.style.color = data.tier_badge_color;
            tierEl.style.borderColor = `${data.tier_badge_color}66`;
        }
        if (titleEl) titleEl.textContent = data.document_title;
        if (verdictEl) verdictEl.textContent = data.executive_verdict;
        if (domainEl) domainEl.textContent = data.domain;

        // Animate circular meter
        const meter = document.getElementById("novelty-circular-meter");
        if (meter) {
            meter.style.background = `conic-gradient(${data.tier_badge_color} ${data.overall_novelty_score * 3.6}deg, rgba(255,255,255,0.06) 0deg)`;
        }

        // 2. Render SVG 5-D Spider / Radar Chart
        renderRadarChart(data.dimensions);

        // 3. Render Dimension Cards
        renderDimensionCards(data.dimensions);

        // 4. Render Reviewer 2 Attacks
        renderReviewerAttacks(data.reviewer_attacks);

        // 5. Render Prior Art Delta Table
        renderPriorArtDelta(data.prior_art_deltas);

        // 6. Render Venue Fit & Level Up
        renderVenueFit(data.venue_fit);

        // 7. Render Polished Contributions
        renderContributions(data.polished_contributions);

        // 8. Render Elevation Roadmap
        renderElevationRoadmap(data.elevation_roadmap);
    }

    function renderRadarChart(dimensions) {
        const svg = document.getElementById("novelty-radar-svg");
        if (!svg) return;

        const size = 320;
        const center = size / 2;
        const radius = 115;
        const numAxes = dimensions.length;
        const angleStep = (Math.PI * 2) / numAxes;

        let svgHtml = `
            <defs>
                <linearGradient id="radarGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#6366f1" stop-opacity="0.5"/>
                    <stop offset="100%" stop-color="#10b981" stop-opacity="0.3"/>
                </linearGradient>
            </defs>
        `;

        // Background concentric pentagon webs (20%, 40%, 60%, 80%, 100%)
        [0.2, 0.4, 0.6, 0.8, 1.0].forEach(level => {
            let pts = [];
            for (let i = 0; i < numAxes; i++) {
                const angle = i * angleStep - Math.PI / 2;
                const r = radius * level;
                pts.push(`${center + r * Math.cos(angle)},${center + r * Math.sin(angle)}`);
            }
            svgHtml += `<polygon points="${pts.join(' ')}" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="1.2"/>`;
        });

        // Axes lines & labels
        let polygonPoints = [];
        dimensions.forEach((dim, i) => {
            const angle = i * angleStep - Math.PI / 2;
            const x = center + radius * Math.cos(angle);
            const y = center + radius * Math.sin(angle);
            svgHtml += `<line x1="${center}" y1="${center}" x2="${x}" y2="${y}" stroke="rgba(255,255,255,0.12)" stroke-width="1.5"/>`;

            // Data point
            const dataR = radius * (dim.score / 100);
            const dataX = center + dataR * Math.cos(angle);
            const dataY = center + dataR * Math.sin(angle);
            polygonPoints.push(`${dataX},${dataY}`);

            // Label position slightly outside
            const labelR = radius + 24;
            const lx = center + labelR * Math.cos(angle);
            const ly = center + labelR * Math.sin(angle);
            const align = Math.abs(Math.cos(angle)) < 0.2 ? 'middle' : (Math.cos(angle) > 0 ? 'start' : 'end');

            const shortName = dim.name.split("&")[0].split(" ")[0];
            svgHtml += `
                <text x="${lx}" y="${ly + 4}" fill="var(--text-secondary)" font-size="11" font-weight="600" text-anchor="${align}">
                    ${shortName} (${dim.score}%)
                </text>
            `;
        });

        // The user's novelty polygon
        svgHtml += `
            <polygon points="${polygonPoints.join(' ')}" fill="url(#radarGrad)" stroke="#10b981" stroke-width="2.5" />
        `;

        // Glowing dots on vertices
        dimensions.forEach((dim, i) => {
            const angle = i * angleStep - Math.PI / 2;
            const dataR = radius * (dim.score / 100);
            const dataX = center + dataR * Math.cos(angle);
            const dataY = center + dataR * Math.sin(angle);
            svgHtml += `<circle cx="${dataX}" cy="${dataY}" r="4.5" fill="#10b981" stroke="#ffffff" stroke-width="1.5"/>`;
        });

        svg.innerHTML = svgHtml;
    }

    function renderDimensionCards(dimensions) {
        const container = document.getElementById("novelty-dimensions-container");
        if (!container) return;

        container.innerHTML = dimensions.map(d => `
            <div class="novelty-dim-card">
                <div class="novelty-dim-header">
                    <div>
                        <h4>${d.name}</h4>
                        <p class="dim-summary">${d.summary}</p>
                    </div>
                    <div class="dim-badge" style="background: ${d.score >= 80 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(99, 102, 241, 0.15)'}; color: ${d.score >= 80 ? '#10b981' : '#818cf8'};">
                        ${d.score}% • ${d.grade}
                    </div>
                </div>
                <div class="dim-progress-bar">
                    <div class="dim-progress-fill" style="width: ${d.score}%; background: ${d.score >= 80 ? '#10b981' : (d.score >= 65 ? '#6366f1' : '#f59e0b')};"></div>
                </div>
                <div class="dim-strengths-vulns">
                    <div class="dim-sub-list">
                        <span class="sub-label strength"><i class="fa-solid fa-circle-check"></i> Key Strength:</span>
                        <span>${d.strengths[0] || 'Clear structural presentation.'}</span>
                    </div>
                    <div class="dim-sub-list">
                        <span class="sub-label vuln"><i class="fa-solid fa-triangle-exclamation"></i> Critical Gate:</span>
                        <span>${d.vulnerabilities[0] || 'Ensure baseline ablation is present.'}</span>
                    </div>
                </div>
            </div>
        `).join("");
    }

    function renderReviewerAttacks(attacks) {
        const container = document.getElementById("novelty-attacks-container");
        if (!container) return;

        container.innerHTML = attacks.map((atk, idx) => `
            <div class="novelty-attack-card">
                <div class="attack-header">
                    <div class="attack-title-row">
                        <span class="attack-pill ${atk.severity.toLowerCase()}">${atk.severity} Risk</span>
                        <span class="attack-category">${atk.attack_category}</span>
                    </div>
                    <h4>${atk.vector_title}</h4>
                </div>
                <div class="reviewer-quote-box">
                    <div class="quote-header"><i class="fa-solid fa-quote-left"></i> Reviewer 2 Skeptical Critique:</div>
                    <p class="quote-text">"${atk.reviewer_critique}"</p>
                </div>
                <div class="defense-rebuttal-box">
                    <div class="rebuttal-header"><i class="fa-solid fa-shield-halved"></i> Preemptive Defense Rebuttal:</div>
                    <p class="rebuttal-text">${atk.defense_rebuttal}</p>
                    <div class="patch-location">
                        <strong>Target Manuscript Edit:</strong> <code>${atk.paper_section_to_patch}</code>
                    </div>
                </div>
            </div>
        `).join("");
    }

    function renderPriorArtDelta(deltas) {
        const container = document.getElementById("novelty-priorart-container");
        if (!container) return;

        container.innerHTML = `
            <table class="delta-table">
                <thead>
                    <tr>
                        <th style="width: 28%;">Closest Published Work (Prior Art)</th>
                        <th style="width: 32%;">What Prior Art Established</th>
                        <th style="width: 40%;">Your Unique Novelty Delta</th>
                    </tr>
                </thead>
                <tbody>
                    ${deltas.map(d => `
                        <tr>
                            <td>
                                <strong>${d.paper_title}</strong>
                                <div class="delta-meta">${d.authors} (${d.year})</div>
                                <span class="delta-risk-badge ${d.risk_level.toLowerCase().includes('critical') ? 'high' : 'medium'}">${d.risk_level}</span>
                                ${d.url ? `<a href="${d.url}" target="_blank" class="delta-link"><i class="fa-solid fa-arrow-up-right-from-square"></i> arXiv</a>` : ''}
                            </td>
                            <td>
                                <div class="prior-core-text">${d.prior_art_core}</div>
                            </td>
                            <td>
                                <div class="author-delta-text">
                                    <i class="fa-solid fa-sparkles" style="color: #10b981; margin-right: 4px;"></i>
                                    ${d.author_unique_delta}
                                </div>
                            </td>
                        </tr>
                    `).join("")}
                </tbody>
            </table>
        `;
    }

    function renderVenueFit(venue) {
        const container = document.getElementById("novelty-venue-container");
        if (!container) return;

        container.innerHTML = `
            <div class="venue-fit-card">
                <div class="venue-fit-header">
                    <div>
                        <span class="venue-tier-badge">${venue.target_tier}</span>
                        <h3>${venue.tier_label}</h3>
                        <p class="venue-readiness">${venue.current_readiness}</p>
                    </div>
                    <div class="venue-prob-circle">
                        <div class="prob-num">${venue.acceptance_probability}%</div>
                        <div class="prob-label">Estimated Acceptance</div>
                    </div>
                </div>
                <div class="venue-recommended-list">
                    <h4>Recommended Target Venues:</h4>
                    <div class="venue-chips">
                        ${venue.recommended_venues.map(v => `<span class="venue-chip"><i class="fa-solid fa-award"></i> ${v}</span>`).join("")}
                    </div>
                </div>
                <div class="venue-gates-box">
                    <h4><i class="fa-solid fa-list-check"></i> Actionable Gates to Guarantee Acceptance:</h4>
                    <ul class="venue-gates-list">
                        ${venue.level_up_gates.map(g => `<li><i class="fa-solid fa-circle-arrow-right"></i> ${g}</li>`).join("")}
                    </ul>
                </div>
            </div>
        `;
    }

    function renderContributions(contributions) {
        const container = document.getElementById("novelty-contributions-container");
        if (!container) return;

        container.innerHTML = `
            <div class="contribution-tones-nav">
                ${contributions.map((c, i) => `
                    <button class="btn-tone ${i === 0 ? 'active' : ''}" data-tone-idx="${i}">
                        ${c.tone}
                    </button>
                `).join("")}
            </div>
            <div class="contribution-content-box" id="contribution-active-content">
                <!-- Dynamically populated by tone click -->
            </div>
        `;

        function updateTone(idx) {
            const c = contributions[idx];
            const contentBox = document.getElementById("contribution-active-content");
            if (!contentBox) return;

            contentBox.innerHTML = `
                <div class="contribution-headline">${c.headline}</div>
                <div class="contribution-bullets">
                    ${c.bullet_points.map(pt => `
                        <div class="bullet-item">
                            <i class="fa-solid fa-diamond"></i>
                            <span>${pt}</span>
                        </div>
                    `).join("")}
                </div>
                <div class="contribution-actions">
                    <button class="btn btn-primary btn-copy-contrib" id="btn-copy-contrib">
                        <i class="fa-regular fa-copy"></i> Copy IEEE Section I Bullets
                    </button>
                </div>
            `;

            document.getElementById("btn-copy-contrib")?.addEventListener("click", () => {
                const textToCopy = `Our main contributions are summarized as follows:\n` +
                    c.bullet_points.map((pt, i) => `• ${pt}`).join("\n");
                navigator.clipboard.writeText(textToCopy);
                showToastMessage("Copied contribution statements to clipboard!", "success");
            });
        }

        // Setup tone button handlers
        container.querySelectorAll(".btn-tone").forEach((btn, idx) => {
            btn.addEventListener("click", () => {
                container.querySelectorAll(".btn-tone").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                updateTone(idx);
            });
        });

        // Initialize first tone
        updateTone(0);
    }

    function renderElevationRoadmap(roadmap) {
        const container = document.getElementById("novelty-roadmap-container");
        if (!container) return;

        container.innerHTML = roadmap.map(r => `
            <div class="roadmap-step-card">
                <div class="step-badge">${r.step}</div>
                <h4>${r.action}</h4>
                <p>${r.detail}</p>
            </div>
        `).join("");
    }

    function showToastMessage(msg, type = "info") {
        if (typeof window.showToast === 'function') {
            window.showToast(msg, type);
            return;
        }
        const container = document.getElementById("toast-container");
        if (!container) return;
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `<i class="fa-solid fa-circle-info"></i> <div class="toast-message">${msg}</div>`;
        container.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    // Expose init globally
    window.initNoveltyAdvisor = initNoveltyAdvisor;
    document.addEventListener("DOMContentLoaded", initNoveltyAdvisor);
})();
