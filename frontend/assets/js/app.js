/**
 * Lemma Frontend Engine (Vanilla JS)
 */

document.addEventListener("DOMContentLoaded", () => {
    // API URL configuration
    let API_BASE_URL = window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1') ? 'http://localhost:8000' : window.location.origin;
    let API_UPLOAD_URL = `${API_BASE_URL}/api/v1/documents/upload`;
    let API_ANALYZE_URL = `${API_BASE_URL}/api/v1/analyze`;
    let API_STATUS_URL = `${API_BASE_URL}/api/v1/status`;
    let API_COACH_URL = `${API_BASE_URL}/api/v1/coach`;
    let API_REWRITE_URL = `${API_BASE_URL}/api/v1/rewrite`;
    let API_HEALTH_URL = `${API_BASE_URL}/api/v1/health`;

    function updateApiUrls(base) {
        API_BASE_URL = base;
        API_UPLOAD_URL = `${API_BASE_URL}/api/v1/documents/upload`;
        API_ANALYZE_URL = `${API_BASE_URL}/api/v1/analyze`;
        API_STATUS_URL = `${API_BASE_URL}/api/v1/status`;
        API_COACH_URL = `${API_BASE_URL}/api/v1/coach`;
        API_REWRITE_URL = `${API_BASE_URL}/api/v1/rewrite`;
        API_HEALTH_URL = `${API_BASE_URL}/api/v1/health`;
    }

    // DOM Elements
    // Main Workspace Layout Views
    const dashboardHomeView = document.getElementById("dashboard-home-view");
    const placeholderWorkspace = document.getElementById("placeholder-workspace");
    const dropZone = document.getElementById("drop-zone");
    const fileInput = document.getElementById("file-input");
    const documentViewer = document.getElementById("document-viewer");
    const documentRender = document.getElementById("document-content-render");
    const viewerFilename = document.getElementById("viewer-filename");
    const viewerDocType = document.getElementById("viewer-doc-type");
    const btnReupload = document.getElementById("btn-reupload");
    const btnRunAnalysis = document.getElementById("btn-run-analysis");
    const btnDownloadPdf = document.getElementById("btn-download-pdf");
    const toastContainer = document.getElementById("toast-container");

    // Metadata Elements
    const metaChars = document.getElementById("meta-chars");
    const metaSentences = document.getElementById("meta-sentences");
    const metaFilename = document.getElementById("meta-filename");
    const metaStatus = document.getElementById("meta-status");

    // Inspector Elements
    const inspectorPlaceholder = document.getElementById("inspector-placeholder");
    const inspectorData = document.getElementById("inspector-data");
    const inspectStart = document.getElementById("inspect-start");
    const inspectEnd = document.getElementById("inspect-end");
    const inspectText = document.getElementById("inspect-text");
    const btnQuickParaphrase = document.getElementById("btn-quick-paraphrase");

    // Reports Workspace Elements
    const reportsWorkspace = document.getElementById("reports-workspace");
    const reportsTable = document.getElementById("reports-table");
    const reportsTableBody = document.getElementById("reports-table-body");
    const reportsEmptyState = document.getElementById("reports-empty-state");
    const btnClearHistory = document.getElementById("btn-clear-history");

    // App State
    let activeFile = null;
    let uploadResponseData = null;
    let currentJobId = null;
    let isAnalyzing = false;
    let isParaphrasing = false;

    // Initialize Page
    async function initApiConfig() {
        try {
            const resolvedUrl = await APIConfigManager.getApiBaseUrl();
            updateApiUrls(resolvedUrl);
            console.log("Resolved API URL:", resolvedUrl);
        } catch (err) {
            console.warn("Failed resolving API from config manager, fallback to default URL:", err);
        } finally {
            checkServerHealth();
            setInterval(checkServerHealth, 15000); // Check health every 15 seconds
        }
    }

    initApiConfig();

    // Theme Switcher Controller
    function initThemeSwitcher() {
        const themeBtn = document.getElementById("theme-toggle-btn");
        if (!themeBtn) return;

        const sunIcon = themeBtn.querySelector(".sun-icon");
        const moonIcon = themeBtn.querySelector(".moon-icon");

        function updateIcons(theme) {
            if (theme === "light") {
                sunIcon.classList.add("hidden");
                moonIcon.classList.remove("hidden");
            } else {
                sunIcon.classList.remove("hidden");
                moonIcon.classList.add("hidden");
            }
        }

        // Set initial icon states
        const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
        updateIcons(currentTheme);

        themeBtn.addEventListener("click", () => {
            const activeTheme = document.documentElement.getAttribute("data-theme") || "dark";
            const newTheme = activeTheme === "dark" ? "light" : "dark";

            document.documentElement.setAttribute("data-theme", newTheme);
            localStorage.setItem("lemma-theme", newTheme);
            localStorage.setItem("lemma-theme-manual", "true");

            updateIcons(newTheme);
            showToast(`Switched to ${newTheme === "dark" ? "Dark Mode" : "Light Mode"}`, "info");
        });

        // Setup real-time system theme change listener for all users
        window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (e) => {
            const hasManualTheme = localStorage.getItem("lemma-theme-manual");
            if (!hasManualTheme) {
                const newTheme = e.matches ? "dark" : "light";
                document.documentElement.setAttribute("data-theme", newTheme);
                localStorage.setItem("lemma-theme", newTheme);
                updateIcons(newTheme);
                showToast(`System theme shifted to ${newTheme === "dark" ? "Dark Mode" : "Light Mode"}`, "info");
            }
        });
    }
    initThemeSwitcher();

    /* -------------------------------------------------------------
     * Server Health Checking
     * ------------------------------------------------------------- */
    let healthConsecutiveFailures = 0;

    async function checkServerHealth() {
        const hOllama = document.getElementById("health-ollama");
        const hOllamaDot = document.getElementById("health-ollama-dot");
        const hOllamaText = document.getElementById("health-ollama-text");

        const hEs = document.getElementById("health-es");
        const hEsDot = document.getElementById("health-es-dot");
        const hEsText = document.getElementById("health-es-text");

        const hDb = document.getElementById("health-db");
        const hDbDot = document.getElementById("health-db-dot");
        const hDbText = document.getElementById("health-db-text");

        const hCelery = document.getElementById("health-celery");
        const hCeleryDot = document.getElementById("health-celery-dot");
        const hCeleryText = document.getElementById("health-celery-text");

        if (!hOllama || !hEs || !hDb || !hCelery) return;

        // Check if any research paper generation or analysis job is actively in progress
        const isResearchRunning = window.lemmaResearch && window.lemmaResearch.state && window.lemmaResearch.state.pollingJobType;
        if (isAnalyzing || isParaphrasing || isResearchRunning) {
            hDb.className = "health-item connected-green";
            hDbText.textContent = "Connected";
            hCelery.className = "health-item working-orange";
            hCeleryText.textContent = "Working";
            if (isParaphrasing) {
                hOllama.className = "health-item working-orange";
                hOllamaText.textContent = "Working";
            }
            return;
        }

        try {
            const response = await fetch(API_HEALTH_URL, { signal: AbortSignal.timeout(10000) });
            if (response.ok) {
                healthConsecutiveFailures = 0;
                const healthData = await response.json();
                const services = healthData.services || {};

                // 1. Ollama status
                const ollama = services.ollama || {};
                if (ollama.status === "running") {
                    hOllama.className = "health-item online-green";
                    hOllamaText.textContent = "Running";
                } else if (ollama.status === "no_models") {
                    hOllama.className = "health-item working-orange";
                    hOllamaText.textContent = "No Models";
                } else {
                    hOllama.className = "health-item offline-red";
                    hOllamaText.textContent = "Offline";
                }

                // 2. Elasticsearch status
                const es = services.elasticsearch || {};
                if (es.status === "healthy") {
                    hEs.className = "health-item healthy-green";
                    hEsText.textContent = "Healthy";
                } else if (es.status === "unhealthy") {
                    hEs.className = "health-item working-orange";
                    hEsText.textContent = "Degraded";
                } else {
                    hEs.className = "health-item offline-red";
                    hEsText.textContent = "Offline";
                }

                // 3. PostgreSQL Database status
                const db = services.database || {};
                if (db.status === "connected") {
                    hDb.className = "health-item connected-green";
                    hDbText.textContent = "Connected";
                } else {
                    hDb.className = "health-item offline-red";
                    hDbText.textContent = "Offline";
                }

                // 4. Celery Queue status (Idle vs Working)
                const celery = services.celery || {};
                const isFrontendRunningJob = (currentJobId !== null && uploadResponseData === null);
                if (isFrontendRunningJob || celery.status === "working") {
                    hCelery.className = "health-item working-orange";
                    hCeleryText.textContent = "Working";
                } else if (celery.status === "idle") {
                    hCelery.className = "health-item idle-green";
                    hCeleryText.textContent = "Idle";
                } else {
                    hCelery.className = "health-item offline-red";
                    hCeleryText.textContent = "Offline";
                }
            } else {
                throw new Error("Health response not OK");
            }
        } catch (error) {
            healthConsecutiveFailures++;
            console.warn(`Health check attempt ${healthConsecutiveFailures} failed:`, error);
            // Only update UI to offline if 3 consecutive checks fail, to avoid false alarms during heavy computation
            if (healthConsecutiveFailures >= 3) {
                hOllama.className = "health-item offline-red"; hOllamaText.textContent = "Offline";
                hEs.className = "health-item offline-red"; hEsText.textContent = "Offline";
                hDb.className = "health-item offline-red"; hDbText.textContent = "Offline";
                hCelery.className = "health-item offline-red"; hCeleryText.textContent = "Offline";
            }
        }
    }

    /* -------------------------------------------------------------
     * Toast Notifications Helper
     * ------------------------------------------------------------- */
    function showToast(message, type = "info") {
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;

        let icon = '<i class="fa-solid fa-circle-info"></i>';
        if (type === "error") icon = '<i class="fa-solid fa-circle-exclamation"></i>';
        if (type === "success") icon = '<i class="fa-solid fa-circle-check"></i>';

        toast.innerHTML = `
            ${icon}
            <div class="toast-message">${message}</div>
        `;

        toastContainer.appendChild(toast);

        // Slide out and remove
        setTimeout(() => {
            toast.style.animation = "slide-in 0.3s reverse forwards";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    /* -------------------------------------------------------------
     * Ingestion / Drag-and-Drop Handlers
     * ------------------------------------------------------------- */
    // Open file dialog on click
    dropZone.addEventListener("click", () => fileInput.click());

    fileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
        }
    });

    // Drag over styling
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileSelection(e.dataTransfer.files[0]);
        }
    });

    function handleFileSelection(file) {
        const allowedExtensions = ["txt", "docx", "pdf"];
        const fileExt = file.name.split(".").pop().toLowerCase();

        if (!allowedExtensions.includes(fileExt)) {
            showToast(`Unsupported file type: .${fileExt}. Please upload PDF, DOCX, or TXT.`, "error");
            return;
        }

        if (file.size > 100 * 1024 * 1024) {
            showToast("File size exceeds 100MB limit.", "error");
            return;
        }

        activeFile = file;
        uploadDocument(file);
    }

    /* -------------------------------------------------------------
     * Document Upload Service Call (Async Queue Flow)
     * ------------------------------------------------------------- */
    function resetMetricsUI() {
        const lexicalChk = document.getElementById("chk-lexical");
        const semanticChk = document.getElementById("chk-semantic");
        const progressScore = document.getElementById("plagiarism-score-text");
        const progressCircle = document.querySelector(".circular-progress");

        if (progressScore) progressScore.textContent = "0%";
        if (progressCircle) {
            progressCircle.style.background = `conic-gradient(var(--border-color) 360deg, transparent 0deg)`;
        }

        document.getElementById("legend-val-lexical").textContent = "0%";
        document.getElementById("legend-val-hybrid").textContent = "0%";
        document.getElementById("legend-val-semantic").textContent = "0%";
        document.getElementById("legend-val-original").textContent = "100%";

        lexicalChk.innerHTML = '<i class="fa-regular fa-circle"></i> Lexical Matching (TF-IDF)';
        lexicalChk.className = "checklist-item";
        semanticChk.innerHTML = '<i class="fa-regular fa-circle"></i> Semantic Indexing (Embeddings)';
        semanticChk.className = "checklist-item";
    }

    async function uploadDocument(file) {
        // Update Metadata sidebar indicators
        metaFilename.textContent = file.name;
        metaStatus.innerHTML = '<span class="badge badge-dim">Uploading...</span>';

        // Show loading progress
        showToast(`Uploading ${file.name}...`, "info");

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch(API_UPLOAD_URL, {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Failed to upload document");
            }

            uploadResponseData = data;
            showToast("Document uploaded and segmented successfully.", "success");

            // Render Document Viewer (plain text)
            renderDocument(uploadResponseData);

            // Reset metrics cards in UI
            resetMetricsUI();

            // Enable Run Analysis button
            btnRunAnalysis.disabled = false;
            btnDownloadPdf.classList.add("hidden");
            metaStatus.innerHTML = '<span class="badge badge-dim">Uploaded</span>';

        } catch (error) {
            console.error("Upload Error:", error);
            showToast(error.message, "error");

            // Reset metadata card on failure
            metaFilename.textContent = "No file uploaded";
            metaStatus.innerHTML = '<span class="badge badge-dim">Idle</span>';
            btnRunAnalysis.disabled = true;
        }
    }

    async function triggerPlagiarismAnalysis(file) {
        if (!file) {
            showToast("No active file to analyze.", "error");
            return;
        }

        const lexicalChk = document.getElementById("chk-lexical");
        const semanticChk = document.getElementById("chk-semantic");

        btnRunAnalysis.disabled = true;
        showToast("Submitting document to plagiarism checker...", "info");

        // Set visual loading indicators
        metaStatus.innerHTML = '<span class="badge badge-dim">Queued...</span>';
        lexicalChk.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Checking Lexical Database...';
        lexicalChk.className = "checklist-item done";

        // Mark that a job is actively running to update the health footer to Working
        isAnalyzing = true;
        checkServerHealth();

        const formData = new FormData();
        formData.append("file", file);

        try {
            const response = await fetch(API_ANALYZE_URL, {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Failed to submit analysis job");
            }

            const jobId = data.job_id;
            currentJobId = jobId;

            // Start polling the job status
            pollAnalysisStatus(jobId, file.name);

        } catch (error) {
            console.error("Analysis Submission Error:", error);
            showToast(error.message, "error");
            metaStatus.innerHTML = '<span class="badge badge-dim">Failed</span>';
            btnRunAnalysis.disabled = false;
            resetMetricsUI();
            isAnalyzing = false;
            checkServerHealth();
        }
    }

    async function pollAnalysisStatus(jobId, filename) {
        const lexicalChk = document.getElementById("chk-lexical");
        const semanticChk = document.getElementById("chk-semantic");
        const progressScore = document.getElementById("plagiarism-score-text");
        const progressCircle = document.querySelector(".circular-progress");

        let consecutiveErrors = 0;
        const MAX_CONSECUTIVE_ERRORS = 8;

        const interval = setInterval(async () => {
            try {
                const response = await fetch(`${API_STATUS_URL}/${jobId}`);
                if (!response.ok) {
                    consecutiveErrors++;
                    if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
                        const data = await response.json().catch(() => ({}));
                        throw new Error(data.detail || "Status check failed after retries");
                    }
                    return; // Wait for next tick
                }

                const data = await response.json();
                consecutiveErrors = 0; // Reset error counter on successful response

                if (data.status === "completed") {
                    clearInterval(interval);
                    isAnalyzing = false;
                    checkServerHealth();

                    uploadResponseData = data.result;

                    showToast("Document analysis complete!", "success");
                    metaStatus.innerHTML = '<span class="badge badge-dim" style="color: #10b981;">Analyzed (100%)</span>';

                    // Update checklist
                    lexicalChk.innerHTML = '<i class="fa-regular fa-circle-check" style="color: #10b981;"></i> Lexical Matching Complete';
                    lexicalChk.className = "checklist-item done";
                    semanticChk.innerHTML = '<i class="fa-regular fa-circle-check" style="color: #10b981;"></i> Semantic Matching Complete';
                    semanticChk.className = "checklist-item done";

                    // Calculate real percentages
                    const analysis = uploadResponseData.analysis;
                    const total = analysis.total_sentences;
                    const lexicalCount = analysis.lexical_matches_count;
                    const hybridCount = analysis.hybrid_matches_count || 0;
                    const semanticCount = analysis.semantic_matches_count;

                    const pctL = total > 0 ? Math.round((lexicalCount / total) * 100) : 0;
                    const pctH = total > 0 ? Math.round((hybridCount / total) * 100) : 0;
                    const pctS = total > 0 ? Math.round((semanticCount / total) * 100) : 0;
                    const pctO = Math.max(0, 100 - pctL - pctH - pctS);

                    // Set circular progress middle text
                    const realPlagScore = pctL + pctH + pctS;
                    progressScore.textContent = `${realPlagScore}%`;

                    // Set conic gradient
                    const degL = pctL * 3.6;
                    const degH = pctH * 3.6;
                    const degS = pctS * 3.6;
                    progressCircle.style.background = `conic-gradient(#ef4444 0deg ${degL}deg, #f59e0b ${degL}deg ${degL + degH}deg, #8b5cf6 ${degL + degH}deg ${degL + degH + degS}deg, #10b981 ${degL + degH + degS}deg 360deg)`;

                    // Update Legend Values
                    document.getElementById("legend-val-lexical").textContent = `${pctL}%`;
                    document.getElementById("legend-val-hybrid").textContent = `${pctH}%`;
                    document.getElementById("legend-val-semantic").textContent = `${pctS}%`;
                    document.getElementById("legend-val-original").textContent = `${pctO}%`;

                    // Apply visual highlights to document sentences
                    applyPlagiarismHighlights(analysis);

                    // Show Download PDF button
                    btnDownloadPdf.classList.remove("hidden");

                    // Save report to history
                    saveReportToHistory(uploadResponseData.filename, jobId, realPlagScore, uploadResponseData);

                    // Enable button
                    btnRunAnalysis.disabled = false;

                    // Final success toast
                    if (realPlagScore > 0) {
                        showToast(`Analysis complete. Found ${realPlagScore}% similarity match.`, "success");
                    } else {
                        showToast("Analysis complete. Document is 100% original and clean!", "success");
                    }

                } else if (data.status === "failed") {
                    clearInterval(interval);
                    isAnalyzing = false;
                    checkServerHealth();
                    throw new Error(data.error || "Analysis task failed");
                } else if (data.status === "processing") {
                    const step = data.progress_step || "Analyzing...";
                    const pct = data.progress_pct || 50;
                    
                    metaStatus.innerHTML = `<span class="badge badge-dim"><i class="fa-solid fa-spinner fa-spin"></i> ${step} (${pct}%)</span>`;
                    
                    // Show live progress inside gauge while processing
                    progressScore.textContent = `${pct}%`;
                    const deg = pct * 3.6;
                    progressCircle.style.background = `conic-gradient(var(--accent-purple) 0deg ${deg}deg, var(--border-color) ${deg}deg 360deg)`;

                    if (pct >= 65) {
                        lexicalChk.innerHTML = '<i class="fa-regular fa-circle-check" style="color: #10b981;"></i> Lexical Matching (TF-IDF)';
                        lexicalChk.className = "checklist-item done";
                    } else if (pct >= 30) {
                        lexicalChk.innerHTML = '<i class="fa-solid fa-spinner fa-spin" style="color: #6366f1;"></i> Lexical Matching (TF-IDF)...';
                        lexicalChk.className = "checklist-item done";
                    }

                    if (pct >= 90) {
                        semanticChk.innerHTML = '<i class="fa-regular fa-circle-check" style="color: #10b981;"></i> Semantic Indexing Complete';
                        semanticChk.className = "checklist-item done";
                    } else if (pct >= 65) {
                        semanticChk.innerHTML = '<i class="fa-solid fa-spinner fa-spin" style="color: #8b5cf6;"></i> Semantic Indexing (Embeddings)...';
                        semanticChk.className = "checklist-item done";
                    }
                } else {
                    const step = data.progress_step || "Queued...";
                    const pct = data.progress_pct || 10;
                    metaStatus.innerHTML = `<span class="badge badge-dim"><i class="fa-solid fa-clock"></i> ${step} (${pct}%)</span>`;
                    progressScore.textContent = `${pct}%`;
                }
            } catch (error) {
                consecutiveErrors++;
                if (consecutiveErrors < MAX_CONSECUTIVE_ERRORS) {
                    return; // Gracefully retry on transient error
                }
                clearInterval(interval);
                isAnalyzing = false;
                checkServerHealth();

                console.error("Polling Error:", error);
                showToast(error.message, "error");

                metaStatus.innerHTML = '<span class="badge badge-dim" style="color: #ef4444;">Failed</span>';
                btnRunAnalysis.disabled = false;
                resetMetricsUI();
            }
        }, 800);
    }

    /* -------------------------------------------------------------
     * Document Rendering & Highlight Setup
     * ------------------------------------------------------------- */
    function renderDocument(data) {
        // Update details card
        viewerFilename.textContent = data.filename;
        const fileExt = data.filename.split(".").pop().toUpperCase();
        viewerDocType.textContent = fileExt;

        metaChars.textContent = data.char_count.toLocaleString();
        metaSentences.textContent = data.sentence_count.toLocaleString();
        metaStatus.innerHTML = '<span class="badge badge-dim">Segmented</span>';

        // Clear contents
        documentRender.innerHTML = "";

        // If no sentences were parsed
        if (!data.sentences || data.sentences.length === 0) {
            documentRender.textContent = data.text || "Empty document.";
            return;
        }

        // We construct the HTML dynamically using segments and coordinate index spans
        // Let's rebuild the text using sentence bounds to ensure coordinates align exactly
        let fullText = data.text;
        let lastOffset = 0;

        data.sentences.forEach((sentence, index) => {
            const start = sentence.start_char;
            const end = sentence.end_char;

            // Append any raw text between sentences (like original spaces or newlines)
            if (start > lastOffset) {
                const intermediateText = fullText.substring(lastOffset, start);
                const textSpan = document.createTextNode(intermediateText);
                documentRender.appendChild(textSpan);
            }

            // Create sentence highlights
            const sentSpan = document.createElement("span");
            sentSpan.className = "doc-sentence";
            sentSpan.textContent = sentence.text;
            sentSpan.dataset.index = index;
            sentSpan.dataset.start = start;
            sentSpan.dataset.end = end;

            // Hover interactions
            sentSpan.addEventListener("mouseenter", () => {
                highlightSentence(sentSpan, sentence);
            });

            // Click interactions (persists coordinates details in inspector)
            sentSpan.addEventListener("click", (e) => {
                e.stopPropagation();
                // Toggle active selection state
                document.querySelectorAll(".doc-sentence").forEach(s => s.classList.remove("active"));
                sentSpan.classList.add("active");
                const matchData = sentSpan.dataset.match ? JSON.parse(sentSpan.dataset.match) : null;
                inspectSentence(sentence, matchData, true);
            });

            documentRender.appendChild(sentSpan);
            lastOffset = end;
        });

        // Append remaining tail text
        if (lastOffset < fullText.length) {
            const tailText = fullText.substring(lastOffset);
            const textSpan = document.createTextNode(tailText);
            documentRender.appendChild(textSpan);
        }

        // Show viewer, hide upload panel
        dropZone.classList.add("hidden");
        documentViewer.classList.remove("hidden");
    }

    /* -------------------------------------------------------------
     * Coordinate Inspection Handlers
     * ------------------------------------------------------------- */
    function highlightSentence(element, sentence) {
        // If there's no clicked sentence active, update on hover
        const hasActiveClick = document.querySelector(".doc-sentence.active") !== null;
        if (!hasActiveClick) {
            const matchData = element.dataset.match ? JSON.parse(element.dataset.match) : null;
            inspectSentence(sentence, matchData, false);
        }
    }

    function inspectSentence(sentence, matchData, isClicked) {
        inspectorPlaceholder.classList.add("hidden");
        inspectorData.classList.remove("hidden");

        inspectStart.textContent = sentence.start_char;
        inspectEnd.textContent = sentence.end_char;
        inspectText.textContent = `"${sentence.text}"`;

        // Hide paraphrase result block from previous inspect runs
        const paraphraseBlock = document.getElementById("paraphrase-result-block");
        if (paraphraseBlock) {
            paraphraseBlock.classList.add("hidden");
        }

        const matchDetailsDiv = document.getElementById("plagiarism-match-details");
        const inspectMatchRefText = document.getElementById("inspect-match-ref-text");
        const matchSourceBlock = inspectMatchRefText ? inspectMatchRefText.closest(".inspector-text-block") : null;

        if (matchData) {
            matchDetailsDiv.classList.remove("hidden");
            if (matchSourceBlock) {
                matchSourceBlock.classList.remove("hidden");
            }

            const matchTypeBadge = document.getElementById("inspect-match-type");
            const matchScoreBadge = document.getElementById("inspect-match-score");
            const matchTitle = document.getElementById("inspect-match-title");
            const matchCitation = document.getElementById("inspect-match-citation");

            // Set Match Type Badge
            if (matchData.match_type === "lexical") {
                matchTypeBadge.className = "badge badge-red";
                matchTypeBadge.textContent = "Lexical Match";
            } else if (matchData.match_type === "hybrid") {
                matchTypeBadge.className = "badge badge-orange";
                matchTypeBadge.textContent = "Hybrid Match";
            } else {
                matchTypeBadge.className = "badge badge-purple";
                matchTypeBadge.textContent = "Semantic Match";
            }

            // Set Match Score
            const pct = Math.round(matchData.score * 100);
            matchScoreBadge.textContent = `${pct}% Similarity`;
            matchScoreBadge.className = "badge " + (
                matchData.match_type === "lexical" ? "badge-red" :
                    (matchData.match_type === "hybrid" ? "badge-orange" : "badge-purple")
            );

            // Set reference sentence and doc info
            inspectMatchRefText.textContent = `"${matchData.matched_sentence.text}"`;
            matchTitle.textContent = matchData.matched_sentence.doc_title;
            matchCitation.textContent = `${matchData.matched_sentence.doc_author} â€” ${matchData.matched_sentence.doc_source}`;
        } else {
            // Check if this sentence was marked as original
            const sentenceSpans = document.querySelectorAll(".doc-sentence");
            let isOriginal = false;
            sentenceSpans.forEach(span => {
                if (parseInt(span.dataset.start) === sentence.start_char && span.classList.contains("original")) {
                    isOriginal = true;
                }
            });

            if (isOriginal) {
                matchDetailsDiv.classList.remove("hidden");

                const matchTypeBadge = document.getElementById("inspect-match-type");
                const matchScoreBadge = document.getElementById("inspect-match-score");

                matchTypeBadge.className = "badge badge-green";
                matchTypeBadge.textContent = "Original Segment";

                matchScoreBadge.className = "badge badge-green";
                matchScoreBadge.textContent = "0% Similarity";

                if (matchSourceBlock) {
                    matchSourceBlock.classList.add("hidden");
                }
            } else {
                matchDetailsDiv.classList.add("hidden");
            }
        }
    }

    function applyPlagiarismHighlights(analysis) {
        if (!analysis || !analysis.matches) return;

        // Map query sentence start_char to its match object for quick lookup
        const matchesMap = {};
        analysis.matches.forEach(m => {
            matchesMap[m.query_sentence.start_char] = m;
        });

        // Select all sentence spans in the viewer
        const sentenceSpans = document.querySelectorAll(".doc-sentence");
        sentenceSpans.forEach(span => {
            const start = parseInt(span.dataset.start);
            const match = matchesMap[start];

            // Reset any old analysis classes first
            span.className = "doc-sentence";

            if (match) {
                const text = span.textContent;

                span.classList.add("plagiarized");
                if (match.match_type === "lexical") {
                    span.classList.add("match-lexical");
                } else if (match.match_type === "hybrid") {
                    span.classList.add("match-hybrid");
                } else {
                    span.classList.add("match-semantic");
                }
                span.dataset.match = JSON.stringify(match);

                // Re-render sentence text with word-level mark tags
                const highlights = match.highlights;
                if (highlights && highlights.length > 0) {
                    const sortedHls = highlights.map(hl => ({
                        start: hl.start_char - start,
                        end: hl.end_char - start,
                        text: hl.text
                    })).sort((a, b) => a.start - b.start);

                    let htmlContent = "";
                    let lastIdx = 0;

                    sortedHls.forEach(hl => {
                        if (hl.start > lastIdx) {
                            htmlContent += escapeHtml(text.substring(lastIdx, hl.start));
                        }
                        const markClass = match.match_type === "lexical" ? "mark-lexical" :
                            (match.match_type === "hybrid" ? "mark-hybrid" : "mark-semantic");
                        htmlContent += `<mark class="${markClass}">${escapeHtml(text.substring(hl.start, hl.end))}</mark>`;
                        lastIdx = hl.end;
                    });

                    if (lastIdx < text.length) {
                        htmlContent += escapeHtml(text.substring(lastIdx));
                    }

                    span.innerHTML = htmlContent;
                } else {
                    const markClass = match.match_type === "lexical" ? "mark-lexical" :
                        (match.match_type === "hybrid" ? "mark-hybrid" : "mark-semantic");
                    span.innerHTML = `<mark class="${markClass}">${escapeHtml(text)}</mark>`;
                }
            } else {
                // If it is not a match, it is clean/original! Apply original styles
                span.classList.add("original");
                span.removeAttribute("data-match");
            }
        });
    }

    function escapeHtml(str) {
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Reset Viewer/Upload Ingestion state
    btnReupload.addEventListener("click", () => {
        documentViewer.classList.add("hidden");
        dropZone.classList.remove("hidden");
        fileInput.value = ""; // clear input stream

        // Reset Metadata stats
        metaChars.textContent = "-";
        metaSentences.textContent = "-";
        metaFilename.textContent = "No file uploaded";
        metaStatus.innerHTML = '<span class="badge badge-dim">Idle</span>';

        // Reset Inspector state
        inspectorPlaceholder.classList.remove("hidden");
        inspectorData.classList.add("hidden");
        const paraphraseBlock = document.getElementById("paraphrase-result-block");
        if (paraphraseBlock) {
            paraphraseBlock.classList.add("hidden");
        }
        document.querySelectorAll(".doc-sentence").forEach(s => {
            s.className = "doc-sentence";
            s.removeAttribute("data-match");
            s.innerHTML = escapeHtml(s.textContent);
        });

        // Reset Plagiarism progress metrics & legend values
        const progressScore = document.getElementById("plagiarism-score-text");
        const progressCircle = document.querySelector(".circular-progress");
        const lexicalChk = document.getElementById("chk-lexical");
        const semanticChk = document.getElementById("chk-semantic");

        progressScore.textContent = "0%";
        progressCircle.style.background = "conic-gradient(var(--border-color) 360deg, transparent 0deg)";

        lexicalChk.innerHTML = '<i class="fa-regular fa-circle"></i> Lexical Matching (TF-IDF)';
        lexicalChk.className = "checklist-item";
        semanticChk.innerHTML = '<i class="fa-regular fa-circle"></i> Semantic Indexing (Embeddings)';
        semanticChk.className = "checklist-item";

        document.getElementById("legend-val-lexical").textContent = "0%";
        document.getElementById("legend-val-hybrid").textContent = "0%";
        document.getElementById("legend-val-semantic").textContent = "0%";
        document.getElementById("legend-val-original").textContent = "100%";

        activeFile = null;
        uploadResponseData = null;
        currentJobId = null;
        btnDownloadPdf.classList.add("hidden");
        btnRunAnalysis.disabled = true;
    });

    // Trigger analysis toast (Phase 2 Integration)
    // Trigger analysis (Phase 2 Integration)
    btnRunAnalysis.addEventListener("click", () => {
        if (!activeFile) {
            showToast("Please upload a file first.", "error");
            return;
        }
        triggerPlagiarismAnalysis(activeFile);
    });

    // Download PDF Report
    btnDownloadPdf.addEventListener("click", () => {
        if (!currentJobId) {
            showToast("No active report job ID found.", "error");
            return;
        }
        showToast("Downloading official Plagiarism PDF report...", "info");
        const downloadUrl = `${API_BASE_URL}/api/v1/documents/report/${currentJobId}`;
        const a = document.createElement("a");
        a.href = downloadUrl;
        a.download = `plagiarism_report_${currentJobId}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });

    // Notification Dropdown Toggle & Clear Event Handlers
    const notificationBtn = document.getElementById("notification-btn");
    const notificationDropdown = document.getElementById("notification-dropdown");
    const btnClearNotifications = document.getElementById("btn-clear-notifications");
    const notificationBadge = document.getElementById("notification-badge");

    if (notificationBtn && notificationDropdown) {
        notificationBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            notificationDropdown.classList.toggle("hidden");
        });

        // Hide dropdown when clicking outside
        document.addEventListener("click", (e) => {
            if (!notificationDropdown.contains(e.target) && e.target !== notificationBtn && !notificationBtn.contains(e.target)) {
                notificationDropdown.classList.add("hidden");
            }
        });

        if (btnClearNotifications) {
            btnClearNotifications.addEventListener("click", (e) => {
                e.stopPropagation();
                if (notificationBadge) {
                    notificationBadge.classList.remove("active");
                }
                const notificationList = document.getElementById("notification-list");
                if (notificationList) {
                    notificationList.innerHTML = '<div class="notification-empty">No new notifications</div>';
                }
                showToast("Notifications cleared.", "info");
            });
        }
    }

    // Paraphrase button triggers Ollama API call
    btnQuickParaphrase.addEventListener("click", async () => {
        const sentenceText = inspectText.textContent.replace(/^"|"$/g, "").trim();
        if (!sentenceText) return;

        const paraphraseBlock = document.getElementById("paraphrase-result-block");
        const paraphraseText = document.getElementById("inspect-paraphrase-text");

        // Disable button and show spinner
        btnQuickParaphrase.disabled = true;
        btnQuickParaphrase.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Paraphrasing...';
        showToast("Paraphrasing segment with local Ollama...", "info");

        // Mark that Ollama is paraphrasing to update the health footer to Working
        isParaphrasing = true;
        checkServerHealth();

        try {
            const response = await fetch(API_REWRITE_URL, {
                method: "POST",
                headers: {
                    'Authorization': 'Bearer ' + (sessionStorage.getItem('lemma_access_token') || localStorage.getItem('lemma_access_token') || ''),
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    text: sentenceText,
                    tone: "academic"
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Paraphrasing failed");
            }

            // Show result
            paraphraseText.textContent = `"${data.rewritten_text}"`;
            paraphraseBlock.classList.remove("hidden");
            showToast("Sentence paraphrased successfully!", "success");
        } catch (error) {
            console.error("Paraphrase Error:", error);
            showToast(error.message, "error");
        } finally {
            // Restore button
            btnQuickParaphrase.disabled = false;
            btnQuickParaphrase.innerHTML = '<i class="fa-solid fa-pen-nib"></i> Paraphrase Segment';
            isParaphrasing = false;
            checkServerHealth();
        }
    });

    /* -------------------------------------------------------------
     * Sidebar Nav Navigation & Workspace Switching
     * ------------------------------------------------------------- */
    const navItems = document.querySelectorAll(".nav-item");
    const dashboardWorkspace = document.getElementById("dashboard-workspace");
    const paraphraserWorkspace = document.getElementById("paraphraser-workspace");

    window.showToast = showToast;
    window.API_BASE = API_BASE_URL;
    window.LEMMA_API_BASE = API_BASE_URL;

    function showView(viewId) {
        // Hide all workspace views and legacy containers
        document.querySelectorAll(".workspace-view").forEach(v => {
            v.classList.add("hidden");
            v.style.display = "none";
        });
        const legacyViews = [
            dashboardHomeView,
            dashboardWorkspace,
            paraphraserWorkspace,
            reportsWorkspace,
            placeholderWorkspace,
            document.getElementById('citations-workspace')
        ];
        legacyViews.forEach(v => {
            if (v) {
                v.classList.add("hidden");
                v.style.display = "none";
            }
        });

        const target = document.getElementById(viewId);
        if (target) {
            target.classList.remove("hidden");
            target.style.display = target.classList.contains("content-grid") ? "grid" : "flex";
        }

        if (viewId === 'paper-editor-view') {
            document.body.classList.add('in-paper-editor');
        } else {
            document.body.classList.remove('in-paper-editor');
        }

        // Update nav item active state
        navItems.forEach(n => n.classList.remove("active"));
        const navMap = {
            'dashboard-home-view': 'nav-dashboard',
            'dashboard-workspace': 'nav-plagiarism',
            'generate-paper-view': 'nav-generate',
            'restructure-view': 'nav-restructure',
            'simcheck-view': 'nav-simcheck',
            'simresults-view': 'nav-simcheck',
            'mypapers-view': 'nav-mypapers',
            'paraphraser-workspace': 'nav-aichat',
            'humanizer-workspace': 'nav-humanizer',
            'reports-workspace': 'nav-export',
            'citations-workspace': 'nav-citations',
        };
        const activeNavId = navMap[viewId];
        if (activeNavId) {
            const navEl = document.getElementById(activeNavId);
            if (navEl) navEl.classList.add("active");
        }
    }
    window.showView = showView;

    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();

            // Close mobile sidebar drawer if it was opened
            const sidebar = document.getElementById("sidebar-panel");
            const overlay = document.querySelector(".sidebar-overlay");
            if (sidebar && sidebar.classList.contains("open")) {
                sidebar.classList.remove("open");
                if (overlay) overlay.classList.remove("active");
            }

            const tabId = item.id;

            if (tabId === "nav-dashboard") {
                showView("dashboard-home-view");
            } else if (tabId === "nav-generate") {
                showView("generate-paper-view");
            } else if (tabId === "nav-restructure") {
                showView("restructure-view");
            } else if (tabId === "nav-simcheck") {
                showView("simcheck-view");
            } else if (tabId === "nav-mypapers") {
                showView("mypapers-view");
                if (window.loadMyPapers) window.loadMyPapers();
            } else if (tabId === "nav-plagiarism") {
                showView("dashboard-workspace");
            } else if (tabId === "nav-aichat") {
                showView("paraphraser-workspace");
            } else if (tabId === "nav-humanizer") {
                showView("humanizer-workspace");
            } else if (tabId === "nav-citations") {
                showView("citations-workspace");
            } else if (tabId === "nav-export") {
                showView("reports-workspace");
                renderReportsHistory();
            } else {
                // Non-functional pages -> show placeholder
                if (placeholderWorkspace) {
                    showView("placeholder-workspace");
                    const pIcon = document.getElementById("placeholder-icon");
                    const pTitle = document.getElementById("placeholder-title");
                    const pDesc = document.getElementById("placeholder-desc");
                    const pSprint = document.getElementById("placeholder-sprint");

                    let title = "Workspace Section";
                    let iconClass = "fa-folder-open";
                    let desc = "This module is currently queued for expansion in a future development sprint.";
                    let sprint = "Sprint 2";

                    if (tabId === "nav-projects") {
                        title = "My Projects";
                        iconClass = "fa-folder-open";
                        desc = "Organize drafts, citations, annotations, and AI threads into local sandboxed projects.";
                        sprint = "Sprint 2";
                    } else if (tabId === "nav-litreview") {
                        title = "Literature Review Workspace";
                        iconClass = "fa-book-open";
                        desc = "Compare research methodologies, identify research gaps, list limitations, and compile theme summaries.";
                        sprint = "Sprint 3";
                    } else if (tabId === "nav-notes") {
                        title = "Academic Note Editor";
                        iconClass = "fa-note-sticky";
                        desc = "Create rich text study notes integrated with LaTeX math support, tables, images, and Markdown.";
                        sprint = "Sprint 2";
                    } else if (tabId === "nav-kb") {
                        title = "Personal Knowledge Base";
                        iconClass = "fa-database";
                        desc = "Organize references, summaries, and notes into collections, folders, and custom tags.";
                        sprint = "Sprint 4";
                    } else if (tabId === "nav-pdfsummary") {
                        title = "PDF AI Summarizer";
                        iconClass = "fa-file-contract";
                        desc = "Summarize academic publications, extracts key formulas, and lists methodologies locally.";
                        sprint = "Sprint 2";
                    } else if (tabId === "nav-settings") {
                        title = "System Settings";
                        iconClass = "fa-gear";
                        desc = "Configure on-device AI model selections, generation parameters (temperature, max tokens), storage paths, and UI theme options.";
                        sprint = "Sprint 1 / 5";
                    } else if (tabId === "nav-support") {
                        title = "Help & Support Center";
                        iconClass = "fa-circle-question";
                        desc = "Troubleshoot local engine setups (Ollama, PostgreSQL, Elasticsearch) and read keyboard shortcuts guides.";
                        sprint = "Sprint 1";
                    }

                    if (pIcon) pIcon.className = `fa-solid ${iconClass}`;
                    if (pTitle) pTitle.textContent = title;
                    if (pDesc) pDesc.textContent = desc;
                    if (pSprint) pSprint.textContent = sprint;
                }
            }
        });
    });


    // Return to dashboard button in placeholder page
    const btnPlaceholderBack = document.getElementById("btn-placeholder-back");
    if (btnPlaceholderBack) {
        btnPlaceholderBack.addEventListener("click", () => {
            const dashNav = document.getElementById("nav-dashboard");
            if (dashNav) dashNav.click();
        });
    }

    // Keyboard Shortcuts for Search Input (Ctrl K or Ctrl /)
    document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey && e.key.toLowerCase() === 'k') || (e.ctrlKey && e.key === '/')) {
            e.preventDefault();
            const searchInput = document.getElementById("global-search-input");
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        }
    });

    // Prompt Box Suggestions Injection
    document.querySelectorAll(".suggestion-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            const promptText = pill.dataset.prompt;
            const promptInput = document.getElementById("dashboard-prompt-input");
            if (promptInput && promptText) {
                promptInput.value = promptText;
                promptInput.focus();
            }
        });
    });

    // Forward Ask AI prompts to AI Chat workspace
    const btnSendPrompt = document.getElementById("btn-send-prompt");
    if (btnSendPrompt) {
        btnSendPrompt.addEventListener("click", () => {
            const promptInput = document.getElementById("dashboard-prompt-input");
            const promptVal = promptInput ? promptInput.value.trim() : "";
            if (!promptVal) {
                showToast("Please enter a research question or rewrite draft.", "error");
                return;
            }

            // Swap to AI Chat (Paraphraser) tab
            const aichatNav = document.getElementById("nav-aichat");
            if (aichatNav) {
                const paraInput = document.getElementById("para-input-text");
                if (paraInput) {
                    paraInput.value = promptVal;
                    paraInput.dispatchEvent(new Event("input"));
                }
                aichatNav.click();

                // Automatically trigger paraphrase run
                const btnRunPara = document.getElementById("btn-run-paraphrase");
                if (btnRunPara) btnRunPara.click();
            }
        });
    }

    // Redirect to Plagiarism workspace on click
    const redirectAndIngest = () => {
        const plagNav = document.getElementById("nav-plagiarism");
        if (plagNav) {
            plagNav.click();
            const fileInput = document.getElementById("file-input");
            if (fileInput) fileInput.click();
        }
    };

    const btnUploadNewDash = document.getElementById("btn-upload-new-dash");
    if (btnUploadNewDash) btnUploadNewDash.addEventListener("click", redirectAndIngest);

    const btnQuickNew = document.getElementById("btn-quick-new");
    if (btnQuickNew) btnQuickNew.addEventListener("click", redirectAndIngest);

    // Setup mobile sidebar drawer backdrop overlay
    const menuToggleBtn = document.getElementById("menu-toggle-btn");
    const sidebarPanel = document.getElementById("sidebar-panel");
    if (menuToggleBtn && sidebarPanel) {
        let overlay = document.querySelector(".sidebar-overlay");
        if (!overlay) {
            overlay = document.createElement("div");
            overlay.className = "sidebar-overlay";
            sidebarPanel.parentNode.appendChild(overlay);
        }

        menuToggleBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            if (window.innerWidth <= 1024) {
                // Tablet/Mobile: slide-in drawer
                sidebarPanel.classList.toggle("open");
                overlay.classList.toggle("active");
            } else {
                // Desktop: collapse sidebar margins
                const appContainer = document.querySelector(".app-container");
                if (appContainer) {
                    appContainer.classList.toggle("collapsed");
                    const isCollapsed = appContainer.classList.contains("collapsed");
                    localStorage.setItem("lemma-sidebar-state", isCollapsed ? "collapsed" : "expanded");
                }
            }
        });

        overlay.addEventListener("click", () => {
            sidebarPanel.classList.remove("open");
            overlay.classList.remove("active");
        });

        // Auto-close sidebar on link navigation on tablet/mobile
        document.querySelectorAll(".sidebar .nav-item a").forEach(link => {
            link.addEventListener("click", () => {
                if (window.innerWidth <= 1024) {
                    sidebarPanel.classList.remove("open");
                    overlay.classList.remove("active");
                }
            });
        });

        // Ensure clean state if window resized past 1024px
        window.addEventListener("resize", () => {
            if (window.innerWidth > 1024) {
                sidebarPanel.classList.remove("open");
                overlay.classList.remove("active");
            }
        });
    }


    /* -------------------------------------------------------------
     * Plagiarism-Free Generator Workspace Logic [NEW]
     * ------------------------------------------------------------- */
    const paraInputText = document.getElementById("para-input-text");
    const paraOutputRender = document.getElementById("para-output-render");
    const btnRunParaphrase = document.getElementById("btn-run-paraphrase");
    const btnCopyParaphrase = document.getElementById("btn-copy-paraphrase");
    const btnClearParaInput = document.getElementById("btn-clear-para-input");
    const btnTransferPlagCheck = document.getElementById("btn-transfer-plag-check");
    const paraTone = document.getElementById("para-tone");
    const paraOrigWords = document.getElementById("para-orig-words");
    const paraNewWords = document.getElementById("para-new-words");

    // Track word counts on input change
    if (paraInputText) {
        paraInputText.addEventListener("input", () => {
            const text = paraInputText.value.trim();
            const wordCount = text ? text.split(/\s+/).length : 0;
            paraOrigWords.textContent = wordCount;
        });
    }

    // Clear input action
    if (btnClearParaInput) {
        btnClearParaInput.addEventListener("click", () => {
            if (paraInputText) paraInputText.value = "";
            if (paraOrigWords) paraOrigWords.textContent = "0";
            if (paraNewWords) paraNewWords.textContent = "0";
            if (paraOutputRender) paraOutputRender.innerHTML = '<span class="placeholder-text" style="color: var(--text-muted); font-style: italic;">Paraphrased text will appear here...</span>';
            if (btnCopyParaphrase) btnCopyParaphrase.disabled = true;
            if (btnTransferPlagCheck) btnTransferPlagCheck.disabled = true;
        });
    }

    // Run Paraphrase Action
    if (btnRunParaphrase) {
        btnRunParaphrase.addEventListener("click", async () => {
            const textToParaphrase = paraInputText ? paraInputText.value.trim() : "";
            if (!textToParaphrase) {
                showToast("Please enter some text to paraphrase.", "error");
                return;
            }

            // Disable button, show loading spinner
            btnRunParaphrase.disabled = true;
            btnRunParaphrase.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Paraphrasing...';
            paraOutputRender.innerHTML = '<span class="placeholder-text" style="color: var(--accent-purple);"><i class="fa-solid fa-spinner fa-spin"></i> Generating 100% original academic phrasing...</span>';
            if (btnCopyParaphrase) btnCopyParaphrase.disabled = true;
            if (btnTransferPlagCheck) btnTransferPlagCheck.disabled = true;
            if (paraNewWords) paraNewWords.textContent = "0";

            showToast(`Paraphrasing text (${paraTone ? paraTone.value : 'academic'} tone)...`, "info");

            try {
                const response = await fetch(API_REWRITE_URL, {
                    method: "POST",
                    headers: {
                        'Authorization': 'Bearer ' + (sessionStorage.getItem('lemma_access_token') || localStorage.getItem('lemma_access_token') || ''),
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        text: textToParaphrase,
                        tone: paraTone ? paraTone.value : "academic"
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || "Paraphrasing failed");
                }

                // Render result
                const rewritten = data.rewritten_text || "";
                paraOutputRender.innerHTML = escapeHtml(rewritten);

                // Calculate new word count
                const wordsNew = rewritten.trim() ? rewritten.trim().split(/\s+/).length : 0;
                if (paraNewWords) paraNewWords.textContent = wordsNew;

                // Enable copy & verify buttons
                if (btnCopyParaphrase) btnCopyParaphrase.disabled = false;
                if (btnTransferPlagCheck) btnTransferPlagCheck.disabled = false;

                showToast("Text paraphrased successfully!", "success");
            } catch (error) {
                console.error("Paraphrase Workspace Error:", error);
                paraOutputRender.innerHTML = `<span class="placeholder-text" style="color: #ef4444; font-style: normal;"><i class="fa-solid fa-circle-exclamation"></i> Error: ${escapeHtml(error.message)}</span>`;
                showToast(error.message, "error");
            } finally {
                // Restore button
                btnRunParaphrase.disabled = false;
                btnRunParaphrase.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Paraphrase Text';
            }
        });
    }

    // Copy to Clipboard Action
    if (btnCopyParaphrase) {
        btnCopyParaphrase.addEventListener("click", () => {
            const textToCopy = paraOutputRender ? paraOutputRender.textContent : "";
            if (!textToCopy || textToCopy.includes("Paraphrased text will appear here")) return;

            navigator.clipboard.writeText(textToCopy).then(() => {
                showToast("Copied paraphrased text to clipboard!", "success");
            }).catch(err => {
                console.error("Clipboard Error:", err);
                showToast("Failed to copy text.", "error");
            });
        });
    }

    // Transfer to Plagiarism Check
    if (btnTransferPlagCheck) {
        btnTransferPlagCheck.addEventListener("click", () => {
            const textToCheck = paraOutputRender ? paraOutputRender.textContent : "";
            if (!textToCheck || textToCheck.includes("Paraphrased text will appear here")) return;

            // Switch to standalone Similarity Check view
            showView("simcheck-view");
            const simTextarea = document.getElementById("simcheck-text-input");
            if (simTextarea) {
                simTextarea.value = textToCheck;
                const tabText = document.querySelector('[data-tab="text"]');
                if (tabText) tabText.click();
            }
            showToast("Transferred paraphrased text to Similarity Check.", "info");
        });
    }

    /* -------------------------------------------------------------
     * AI Humanizer & Stealth Bypass Workspace Logic
     * ------------------------------------------------------------- */
    const humanizeInputText = document.getElementById("humanize-input-text");
    const humanizeOutputRender = document.getElementById("humanize-output-render");
    const btnRunHumanize = document.getElementById("btn-run-humanize");
    const btnCopyHumanize = document.getElementById("btn-copy-humanize");
    const btnClearHumanizeInput = document.getElementById("btn-clear-humanize-input");
    const btnHumanizeTransferPlag = document.getElementById("btn-humanize-transfer-plag");
    const humanizeToneSelect = document.getElementById("humanize-tone-select");
    const humanizeIntensitySelect = document.getElementById("humanize-intensity-select");
    const humanizeAiBefore = document.getElementById("humanize-ai-before");
    const humanizeAiAfter = document.getElementById("humanize-ai-after");

    // Clear action
    if (btnClearHumanizeInput) {
        btnClearHumanizeInput.addEventListener("click", () => {
            if (humanizeInputText) humanizeInputText.value = "";
            if (humanizeOutputRender) humanizeOutputRender.innerHTML = '<span class="placeholder-text" style="color: var(--text-muted); font-style: italic;">Humanized output will appear here with high burstiness and zero AI clichés...</span>';
            if (humanizeAiBefore) humanizeAiBefore.textContent = "--";
            if (humanizeAiAfter) humanizeAiAfter.textContent = "--";
            if (btnCopyHumanize) btnCopyHumanize.disabled = true;
            if (btnHumanizeTransferPlag) btnHumanizeTransferPlag.disabled = true;
        });
    }

    // Run Humanize Action
    if (btnRunHumanize) {
        btnRunHumanize.addEventListener("click", async () => {
            const textToHumanize = humanizeInputText ? humanizeInputText.value.trim() : "";
            if (!textToHumanize) {
                showToast("Please enter AI-generated text to humanize.", "error");
                return;
            }

            btnRunHumanize.disabled = true;
            btnRunHumanize.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Humanizing...';
            humanizeOutputRender.innerHTML = '<span class="placeholder-text" style="color: var(--accent-purple);"><i class="fa-solid fa-spinner fa-spin"></i> Eliminating AI patterns & modulating sentence burstiness...</span>';
            if (btnCopyHumanize) btnCopyHumanize.disabled = true;
            if (btnHumanizeTransferPlag) btnHumanizeTransferPlag.disabled = true;

            showToast("Humanizing text with Turnitin Anti-AI Engine...", "info");

            try {
                const response = await fetch("/api/v1/humanize", {
                    method: "POST",
                    headers: {
                        'Authorization': 'Bearer ' + (sessionStorage.getItem('lemma_access_token') || localStorage.getItem('lemma_access_token') || ''),
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        text: textToHumanize,
                        tone: humanizeToneSelect ? humanizeToneSelect.value : "academic",
                        intensity: humanizeIntensitySelect ? humanizeIntensitySelect.value : "high"
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || "Humanization failed");
                }

                const humanized = data.humanized_text || "";
                humanizeOutputRender.innerHTML = escapeHtml(humanized);

                // Update before/after AI gauges
                const beforePct = Math.round((data.ai_score_before || 0.95) * 100);
                const afterPct = Math.round((data.ai_score_after || 0.08) * 100);
                
                if (humanizeAiBefore) humanizeAiBefore.textContent = `${beforePct}%`;
                if (humanizeAiAfter) humanizeAiAfter.textContent = `${afterPct}%`;

                if (btnCopyHumanize) btnCopyHumanize.disabled = false;
                if (btnHumanizeTransferPlag) btnHumanizeTransferPlag.disabled = false;

                showToast(`Text successfully humanized! AI probability reduced from ${beforePct}% to ${afterPct}%.`, "success");
            } catch (error) {
                console.error("Humanize Workspace Error:", error);
                humanizeOutputRender.innerHTML = `<span class="placeholder-text" style="color: #ef4444; font-style: normal;"><i class="fa-solid fa-circle-exclamation"></i> Error: ${escapeHtml(error.message)}</span>`;
                showToast(error.message, "error");
            } finally {
                btnRunHumanize.disabled = false;
                btnRunHumanize.innerHTML = '<i class="fa-solid fa-sparkles"></i> Humanize Text';
            }
        });
    }

    // Copy Humanized Text
    if (btnCopyHumanize) {
        btnCopyHumanize.addEventListener("click", () => {
            const textToCopy = humanizeOutputRender ? humanizeOutputRender.textContent : "";
            if (!textToCopy || textToCopy.includes("Humanized output will appear here")) return;

            navigator.clipboard.writeText(textToCopy).then(() => {
                showToast("Copied humanized text to clipboard!", "success");
            }).catch(err => {
                console.error("Clipboard Error:", err);
                showToast("Failed to copy text.", "error");
            });
        });
    }

    // Transfer Humanized Text to Plagiarism / Similarity Check
    if (btnHumanizeTransferPlag) {
        btnHumanizeTransferPlag.addEventListener("click", () => {
            const textToCheck = humanizeOutputRender ? humanizeOutputRender.textContent : "";
            if (!textToCheck || textToCheck.includes("Humanized output will appear here")) return;

            showView("simcheck-view");
            const simTextarea = document.getElementById("simcheck-text-input");
            if (simTextarea) {
                simTextarea.value = textToCheck;
                const tabText = document.querySelector('[data-tab="text"]');
                if (tabText) tabText.click();
            }
            showToast("Transferred humanized text to Similarity Check.", "info");
        });
    }

    /* -------------------------------------------------------------
     * Reports History & LocalStorage Persistence [NEW]
     * ------------------------------------------------------------- */
    function saveReportToHistory(filename, jobId, scorePct, resultData) {
        try {
            let history = localStorage.getItem("lemma_reports_history");
            history = history ? JSON.parse(history) : [];

            // Check if this jobId already exists in history to prevent duplicates
            const exists = history.some(item => item.jobId === jobId);
            if (exists) return;

            const newReport = {
                filename: filename,
                jobId: jobId,
                date: new Date().toLocaleString(),
                score: scorePct,
                result: resultData
            };

            history.unshift(newReport); // Add to the beginning

            // Limit history to 20 entries
            if (history.length > 20) {
                history.pop();
            }

            localStorage.setItem("lemma_reports_history", JSON.stringify(history));
        } catch (e) {
            console.error("Error saving report to history:", e);
        }
    }

    function renderReportsHistory() {
        try {
            let history = localStorage.getItem("lemma_reports_history");
            history = history ? JSON.parse(history) : [];

            reportsTableBody.innerHTML = "";

            if (history.length === 0) {
                reportsTable.classList.add("hidden");
                reportsEmptyState.classList.remove("hidden");
                btnClearHistory.disabled = true;
                return;
            }

            reportsTable.classList.remove("hidden");
            reportsEmptyState.classList.add("hidden");
            btnClearHistory.disabled = false;

            history.forEach((item, index) => {
                const tr = document.createElement("tr");

                // Get similarity badge class
                let scoreBadgeClass = "badge-green";
                if (item.score > 50) {
                    scoreBadgeClass = "badge-red";
                } else if (item.score > 20) {
                    scoreBadgeClass = "badge-purple";
                }

                tr.innerHTML = `
                    <td>
                        <i class="fa-solid fa-file-invoice" style="margin-right: 8px; color: var(--text-muted);"></i>
                        <strong>${escapeHtml(item.filename)}</strong>
                    </td>
                    <td>${escapeHtml(item.date)}</td>
                    <td>
                        <span class="badge ${scoreBadgeClass}">
                            ${item.score}% Similarity
                        </span>
                    </td>
                    <td><span class="badge badge-dim">Completed</span></td>
                    <td style="text-align: right;">
                        <button class="btn btn-sm btn-outline btn-restore-report" data-index="${index}" style="padding: 0.35rem 0.75rem; font-size: 0.75rem; margin-right: 0.25rem;">
                            <i class="fa-solid fa-eye"></i> View
                        </button>
                        <button class="btn btn-sm btn-secondary btn-download-report-pdf" data-jobid="${item.jobId}" style="padding: 0.35rem 0.75rem; font-size: 0.75rem;">
                            <i class="fa-solid fa-file-pdf"></i> PDF
                        </button>
                    </td>
                `;
                reportsTableBody.appendChild(tr);
            });

            // Bind view/restore clicks
            document.querySelectorAll(".btn-restore-report").forEach(btn => {
                btn.addEventListener("click", () => {
                    const idx = parseInt(btn.dataset.index);
                    const item = history[idx];
                    if (item && item.result) {
                        restoreReportToViewer(item);
                    }
                });
            });

            // Bind download pdf clicks
            document.querySelectorAll(".btn-download-report-pdf").forEach(btn => {
                btn.addEventListener("click", () => {
                    const jobId = btn.dataset.jobid;
                    showToast("Downloading PDF report...", "info");
                    window.open(`${API_BASE_URL}/api/v1/documents/report/${jobId}`, "_blank");
                });
            });
        } catch (e) {
            console.error("Error rendering reports history:", e);
        }
    }

    function restoreReportToViewer(reportItem) {
        // Switch variables
        uploadResponseData = reportItem.result;
        currentJobId = reportItem.jobId;
        activeFile = { name: reportItem.filename }; // mock active file

        // Render document text structures
        renderDocument(uploadResponseData);

        // Enable PDF download button
        btnDownloadPdf.classList.remove("hidden");

        // Immediately run analysis rendering in UI (without delay since it's already computed)
        const analysis = uploadResponseData.analysis;
        const lexicalChk = document.getElementById("chk-lexical");
        const semanticChk = document.getElementById("chk-semantic");
        const progressScore = document.getElementById("plagiarism-score-text");
        const progressCircle = document.querySelector(".circular-progress");

        lexicalChk.innerHTML = '<i class="fa-regular fa-circle-check"></i> Lexical Match Complete';
        lexicalChk.className = "checklist-item done";
        semanticChk.innerHTML = '<i class="fa-regular fa-circle-check"></i> Semantic Matching Complete';
        semanticChk.className = "checklist-item done";

        const total = analysis.total_sentences;
        const lexicalCount = analysis.lexical_matches_count;
        const hybridCount = analysis.hybrid_matches_count || 0;
        const semanticCount = analysis.semantic_matches_count;

        const pctL = total > 0 ? Math.round((lexicalCount / total) * 100) : 0;
        const pctH = total > 0 ? Math.round((hybridCount / total) * 100) : 0;
        const pctS = total > 0 ? Math.round((semanticCount / total) * 100) : 0;
        const pctO = Math.max(0, 100 - pctL - pctH - pctS);

        const realPlagScore = pctL + pctH + pctS;
        progressScore.textContent = `${realPlagScore}%`;

        const degL = pctL * 3.6;
        const degH = pctH * 3.6;
        const degS = pctS * 3.6;
        progressCircle.style.background = `conic-gradient(#ef4444 0deg ${degL}deg, #f59e0b ${degL}deg ${degL + degH}deg, #8b5cf6 ${degL + degH}deg ${degL + degH + degS}deg, #10b981 ${degL + degH + degS}deg 360deg)`;

        document.getElementById("legend-val-lexical").textContent = `${pctL}%`;
        document.getElementById("legend-val-hybrid").textContent = `${pctH}%`;
        document.getElementById("legend-val-semantic").textContent = `${pctS}%`;
        document.getElementById("legend-val-original").textContent = `${pctO}%`;

        applyPlagiarismHighlights(analysis);
        btnRunAnalysis.disabled = false;

        // Switch view to Plagiarism Check
        navItems.forEach(n => n.classList.remove("active"));
        const plagNav = document.getElementById("nav-plagiarism");
        if (plagNav) plagNav.classList.add("active");

        hideAllWorkspaces();
        if (dashboardWorkspace) dashboardWorkspace.classList.remove("hidden");

        showToast(`Loaded analysis report for ${reportItem.filename}`, "success");
    }

    // Clear History Action
    if (btnClearHistory) {
        btnClearHistory.addEventListener("click", () => {
            if (confirm("Are you sure you want to clear your reports history? This cannot be undone.")) {
                localStorage.removeItem("lemma_reports_history");
                renderReportsHistory();
                showToast("Reports history cleared.", "info");
            }
        });
    }



    /* -------------------------------------------------------------
     * Academic Citation Studio Interactive Logic
     * ------------------------------------------------------------- */
    const citationInput = document.getElementById("citation-input");
    const btnClearCitation = document.getElementById("btn-clear-citation");
    const btnGenerateCitation = document.getElementById("btn-generate-citation");
    const citationResultsPanel = document.getElementById("citation-results-panel");
    const citationHistoryPanel = document.getElementById("citation-history-panel");
    const citationHistoryList = document.getElementById("citation-history-list");
    const btnClearCitationHistory = document.getElementById("btn-clear-citation-history");
    const btnCopyAllCitations = document.getElementById("btn-copy-all-citations");
    const btnDownloadBibtex = document.getElementById("btn-download-bibtex");
    const citationSourceLabel = document.getElementById("citation-source-label");

    // Toggle clear button on input
    if (citationInput && btnClearCitation) {
        citationInput.addEventListener("input", () => {
            if (citationInput.value.trim().length > 0) {
                btnClearCitation.classList.remove("hidden");
            } else {
                btnClearCitation.classList.add("hidden");
            }
        });

        btnClearCitation.addEventListener("click", () => {
            citationInput.value = "";
            btnClearCitation.classList.add("hidden");
            citationInput.focus();
        });

        // Trigger generate on Enter key
        citationInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (btnGenerateCitation) btnGenerateCitation.click();
            }
        });
    }

    // Quick Preset Pills
    document.querySelectorAll(".preset-pill").forEach(pill => {
        pill.addEventListener("click", () => {
            const query = pill.getAttribute("data-query");
            if (citationInput && query) {
                citationInput.value = query;
                if (btnClearCitation) btnClearCitation.classList.remove("hidden");
                if (btnGenerateCitation) btnGenerateCitation.click();
            }
        });
    });

    // Render Citation History from localStorage
    function loadCitationHistory() {
        if (!citationHistoryList || !citationHistoryPanel) return;
        try {
            const history = JSON.parse(localStorage.getItem("lemma_citation_history") || "[]");
            if (!history || history.length === 0) {
                citationHistoryPanel.classList.add("hidden");
                return;
            }

            citationHistoryList.innerHTML = "";
            history.slice(0, 5).forEach((item) => {
                const row = document.createElement("div");
                row.className = "citation-history-item";
                row.innerHTML = `
                    <span style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 85%;">
                        <i class="fa-solid fa-bookmark" style="color: var(--accent-purple); margin-right: 6px;"></i> ${escapeHtml(item.query)}
                    </span>
                    <span style="font-size: 0.75rem; color: var(--text-muted);">${item.date || 'Recent'}</span>
                `;
                row.addEventListener("click", () => {
                    if (citationInput) {
                        citationInput.value = item.query;
                        if (btnClearCitation) btnClearCitation.classList.remove("hidden");
                    }
                    displayCitationResults(item.data, item.query);
                });
                citationHistoryList.appendChild(row);
            });
            citationHistoryPanel.classList.remove("hidden");
        } catch (e) {
            console.warn("Could not load citation history:", e);
        }
    }

    function saveToCitationHistory(query, data) {
        try {
            let history = JSON.parse(localStorage.getItem("lemma_citation_history") || "[]");
            history = history.filter(h => h.query.toLowerCase() !== query.toLowerCase());
            history.unshift({
                query: query,
                data: data,
                date: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            });
            localStorage.setItem("lemma_citation_history", JSON.stringify(history.slice(0, 10)));
            loadCitationHistory();
        } catch (e) {
            console.warn("Could not save citation history:", e);
        }
    }

    if (btnClearCitationHistory) {
        btnClearCitationHistory.addEventListener("click", () => {
            localStorage.removeItem("lemma_citation_history");
            loadCitationHistory();
            showToast("Citation history cleared.", "info");
        });
    }

    // Display formatted results helper
    function displayCitationResults(data, query) {
        const citApa = document.getElementById("cit-apa");
        const citMla = document.getElementById("cit-mla");
        const citChicago = document.getElementById("cit-chicago");
        const citIeee = document.getElementById("cit-ieee");

        if (citApa) citApa.textContent = data.apa || "Citation format unavailable.";
        if (citMla) citMla.textContent = data.mla || "Citation format unavailable.";
        if (citChicago) citChicago.textContent = data.chicago || "Citation format unavailable.";
        if (citIeee) citIeee.textContent = data.ieee || "Citation format unavailable.";

        if (citationSourceLabel) {
            citationSourceLabel.textContent = `Generated for: "${query.length > 50 ? query.substring(0, 50) + '...' : query}"`;
        }

        if (citationResultsPanel) {
            citationResultsPanel.classList.remove("hidden");
            citationResultsPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }
    }

    // Citation Generator Event Listener
    if (btnGenerateCitation) {
        btnGenerateCitation.addEventListener("click", async () => {
            const input = citationInput ? citationInput.value.trim() : "";
            if (!input) {
                showToast("Please enter a source URL, DOI, or title.", "error");
                if (citationInput) citationInput.focus();
                return;
            }
            
            btnGenerateCitation.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Formatting...';
            btnGenerateCitation.disabled = true;
            showToast("Generating standardized citations with AI...", "info");
            
            try {
                const response = await fetch(`${API_BASE_URL}/api/v1/citations/generate`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + (sessionStorage.getItem("lemma_access_token") || localStorage.getItem("lemma_access_token") || "")
                    },
                    body: JSON.stringify({ query: input })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    displayCitationResults(data, input);
                    saveToCitationHistory(input, data);
                    showToast("Citations generated successfully!", "success");
                } else {
                    const errData = await response.json().catch(() => ({}));
                    showToast(errData.detail || "Failed to generate citations. Please check the source.", "error");
                }
            } catch (err) {
                console.error("Citation error:", err);
                showToast("Network error while generating citations.", "error");
            } finally {
                btnGenerateCitation.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Generate Citations';
                btnGenerateCitation.disabled = false;
            }
        });
    }

    // Individual Copy Buttons
    document.querySelectorAll(".citation-copy-action").forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-target");
            const targetEl = document.getElementById(targetId);
            if (!targetEl || !targetEl.textContent) return;

            navigator.clipboard.writeText(targetEl.textContent).then(() => {
                const originalHtml = btn.innerHTML;
                btn.classList.add("copied");
                btn.innerHTML = '<i class="fa-solid fa-check"></i> <span>Copied!</span>';
                showToast(`Copied ${btn.getAttribute("title") || "citation"} to clipboard!`, "success");
                setTimeout(() => {
                    btn.classList.remove("copied");
                    btn.innerHTML = originalHtml;
                }, 2000);
            }).catch(err => {
                console.error("Clipboard error:", err);
                showToast("Failed to copy to clipboard.", "error");
            });
        });
    });

    // Copy All Citations
    if (btnCopyAllCitations) {
        btnCopyAllCitations.addEventListener("click", () => {
            const ieee = document.getElementById("cit-ieee")?.textContent || "";
            const apa = document.getElementById("cit-apa")?.textContent || "";
            const mla = document.getElementById("cit-mla")?.textContent || "";
            const chicago = document.getElementById("cit-chicago")?.textContent || "";

            const combined = `[IEEE Format]\n${ieee}\n\n[APA 7th Edition]\n${apa}\n\n[MLA 9th Edition]\n${mla}\n\n[Chicago / Turabian]\n${chicago}\n`;
            navigator.clipboard.writeText(combined).then(() => {
                showToast("All 4 citation formats copied to clipboard!", "success");
            }).catch(() => {
                showToast("Failed to copy citations.", "error");
            });
        });
    }

    // Export .txt file
    if (btnDownloadBibtex) {
        btnDownloadBibtex.addEventListener("click", () => {
            const query = citationInput ? citationInput.value.trim() : "source";
            const ieee = document.getElementById("cit-ieee")?.textContent || "";
            const apa = document.getElementById("cit-apa")?.textContent || "";
            const mla = document.getElementById("cit-mla")?.textContent || "";
            const chicago = document.getElementById("cit-chicago")?.textContent || "";

            const content = `ACADEMIC CITATIONS REPORT\nSource Inquiry: ${query}\nDate: ${new Date().toLocaleString()}\n\n------------------------------------------------------------\n[IEEE Standard]\n${ieee}\n\n[APA 7th Edition]\n${apa}\n\n[MLA 9th Edition]\n${mla}\n\n[Chicago / Turabian Format]\n${chicago}\n------------------------------------------------------------\nGenerated by Lemma AI Academic Studio\n`;

            const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `citations_${Date.now()}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast("Exported citations text file.", "success");
        });
    }

    // Initial load of citation history
    loadCitationHistory();

    // Initialize user authentication session
    initUserSession();

});

// ---------------------------------------------------------------------------
// Authentication & Session Management
// ---------------------------------------------------------------------------
async function initUserSession() {
    const token = sessionStorage.getItem("lemma_access_token") || localStorage.getItem("lemma_access_token");
    const avatarEl = document.getElementById("nav-user-avatar");
    const nameEl = document.getElementById("nav-user-name");
    const dropAvatarEl = document.getElementById("dropdown-user-avatar");
    const dropNameEl = document.getElementById("dropdown-user-name");
    const dropEmailEl = document.getElementById("dropdown-user-email");
    const dropRoleEl = document.getElementById("dropdown-user-role");
    const welcomeTitle = document.querySelector(".blank-start-title");

    function applyUserData(user) {
        if (!user) return;
        const fullName = user.full_name || user.name || "Researcher";
        const email = user.email || "researcher@lemma.ai";
        const role = (user.role || "student").toUpperCase();
        const initial = fullName.charAt(0).toUpperCase();

        if (avatarEl) avatarEl.textContent = initial;
        if (nameEl) nameEl.textContent = fullName.split(" ")[0];
        if (dropAvatarEl) dropAvatarEl.textContent = initial;
        if (dropNameEl) dropNameEl.textContent = fullName;
        if (dropEmailEl) dropEmailEl.textContent = email;
        if (dropRoleEl) dropRoleEl.textContent = role;
        if (welcomeTitle) {
            welcomeTitle.textContent = `What's next, ${fullName.split(" ")[0]}?`;
        }
    }

    // Check cached profile first for instantaneous UI render
    const cachedUser = JSON.parse(sessionStorage.getItem("lemma_user") || localStorage.getItem("lemma_user") || "null");
    if (cachedUser) {
        applyUserData(cachedUser);
    }

    if (!token) {
        return;
    }

    try {
        const base = typeof APIConfigManager !== 'undefined' 
            ? await APIConfigManager.getApiBaseUrl() 
            : window.location.origin;

        const res = await fetch(`${base}/api/v1/auth/me`, {
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });

        if (res.ok) {
            const user = await res.json();
            sessionStorage.setItem("lemma_user", JSON.stringify(user));
            applyUserData(user);
        } else if (res.status === 401) {
            // Token expired
            sessionStorage.removeItem("lemma_access_token");
            localStorage.removeItem("lemma_access_token");
        }
    } catch (e) {
        console.warn("User profile fetch failed:", e);
    }
}

function toggleProfileDropdown(forceState) {
    const menu = document.getElementById("profile-dropdown");
    if (!menu) return;
    if (typeof forceState === 'boolean') {
        menu.style.display = forceState ? "block" : "none";
    } else {
        menu.style.display = menu.style.display === "block" ? "none" : "block";
    }
}

function handleLogout() {
    sessionStorage.removeItem("lemma_access_token");
    sessionStorage.removeItem("lemma_refresh_token");
    sessionStorage.removeItem("lemma_user");
    localStorage.removeItem("lemma_access_token");
    localStorage.removeItem("lemma_refresh_token");
    localStorage.removeItem("lemma_user");
    window.location.href = "/login.html";
}

// Global click outside listener to close profile dropdown
document.addEventListener("click", (e) => {
    const wrapper = document.querySelector(".header-profile-wrapper");
    const dropdown = document.getElementById("profile-dropdown");
    if (wrapper && dropdown && !wrapper.contains(e.target)) {
        dropdown.style.display = "none";
    }
});


