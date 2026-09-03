/**
 * research.js — Frontend module for Lemma AI Research Paper Assistant
 * Handles all three workflows:
 *   1. Generate Research Paper
 *   2. Restructure to IEEE
 *   3. Similarity Check
 *
 * Also handles:
 *   - Paper Editor/Review view
 *   - My Papers list
 *   - Export (PDF/DOCX)
 *   - Section improvement
 *
 * Depends on: app.js (for showView, showToast, API_BASE, getAuthHeaders)
 */

(function () {
    'use strict';

    // ---------------------------------------------------------------------------
    // State
    // ---------------------------------------------------------------------------
    const state = {
        currentPaperId: null,
        currentPaper: null,
        currentJobId: null,
        pollingTimer: null,
        pollingJobType: null, // 'generate' | 'restructure' | 'simcheck'
        simJobId: null,
        restructureFile: null,
        simcheckFile: null,
        currentSection: null,
    };

    // ---------------------------------------------------------------------------
    // Utilities
    // ---------------------------------------------------------------------------
    function getToken() {
        return localStorage.getItem('lemma_access_token') || localStorage.getItem('lemma_token') || sessionStorage.getItem('lemma_token') || '';
    }

    function authHeaders() {
        const token = getToken();
        const headers = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        return headers;
    }

    function authHeadersFormData() {
        const token = getToken();
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        return headers;
    }

    function apiBase() {
        if (window.LEMMA_API_BASE) return window.LEMMA_API_BASE;
        if (window.API_BASE) return window.API_BASE;
        if (window.location.protocol === 'file:') return 'http://localhost:8000';
        if (window.location.port === '8000') return window.location.origin;
        return 'http://localhost:8000';
    }

    function showToast(msg, type = 'info') {
        if (window.showToast) {
            window.showToast(msg, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${msg}`);
        }
    }

    function showViewGlobal(viewId) {
        if (viewId === 'paper-editor-view') {
            document.body.classList.add('in-paper-editor');
        } else {
            document.body.classList.remove('in-paper-editor');
        }

        if (window.showView) {
            window.showView(viewId);
            return;
        }
        // Fallback: hide all workspace-view elements, show target
        document.querySelectorAll('.workspace-view').forEach(el => {
            el.classList.add('hidden');
            el.style.display = 'none';
        });
        const target = document.getElementById(viewId);
        if (target) {
            target.classList.remove('hidden');
            target.style.display = target.classList.contains('content-grid') ? 'grid' : 'flex';
        }

        // Update active sidebar item
        document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
        const viewNavMap = {
            'dashboard-home-view': 'nav-dashboard',
            'generate-paper-view': 'nav-generate',
            'restructure-view': 'nav-restructure',
            'simcheck-view': 'nav-simcheck',
            'simresults-view': 'nav-simcheck',
            'mypapers-view': 'nav-mypapers',
        };
        const navId = viewNavMap[viewId];
        if (navId) {
            const navEl = document.getElementById(navId);
            if (navEl) navEl.classList.add('active');
        }
    }


    function scoreColor(score) {
        // score is 0.0-1.0
        const pct = Math.round(score * 100);
        if (pct < 20) return '#10b981';  // green
        if (pct < 40) return '#f59e0b';  // amber
        return '#ef4444';               // red
    }

    // ---------------------------------------------------------------------------
    // Sidebar Navigation — attach research nav items
    // ---------------------------------------------------------------------------
    function initNavigation() {
        const navMap = {
            'nav-generate': 'generate-paper-view',
            'nav-restructure': 'restructure-view',
            'nav-simcheck': 'simcheck-view',
            'nav-mypapers': 'mypapers-view',
        };

        Object.entries(navMap).forEach(([navId, viewId]) => {
            const el = document.getElementById(navId);
            if (el) {
                el.addEventListener('click', (e) => {
                    e.preventDefault();
                    showViewGlobal(viewId);
                    if (viewId === 'mypapers-view') loadMyPapers();
                });
            }
        });
    }

    // ---------------------------------------------------------------------------
    // WORKFLOW 1: Generate Research Paper
    // ---------------------------------------------------------------------------
    function formatApiErrorMessage(errData, status) {
        if (!errData) return `Server error: ${status}`;
        if (typeof errData === 'string') return errData;
        if (typeof errData.detail === 'string') return errData.detail;
        if (Array.isArray(errData.detail)) {
            return errData.detail.map(d => (d.loc ? d.loc.slice(1).join('.') + ': ' : '') + (d.msg || JSON.stringify(d))).join('; ');
        }
        if (typeof errData.message === 'string') return errData.message;
        return `Server error: ${status}`;
    }

    function initGeneratePaper() {
        const btnGenerate = document.getElementById('btn-generate-paper');
        if (!btnGenerate) return;

        btnGenerate.addEventListener('click', async () => {
            const topic = document.getElementById('gen-topic')?.value?.trim();
            if (!topic || topic.length < 3) {
                showToast('Please enter a research topic (at least 3 characters).', 'error');
                return;
            }

            const domain = document.getElementById('gen-domain')?.value?.trim() || null;
            const length = document.getElementById('gen-length')?.value || 'medium';
            const numRefs = parseInt(document.getElementById('gen-refs')?.value || '10');
            const ieeeFormat = document.getElementById('gen-ieee')?.checked ?? true;

            try {
                btnGenerate.disabled = true;
                btnGenerate.textContent = 'Starting...';

                const res = await fetch(`${apiBase()}/api/v1/research/generate`, {
                    method: 'POST',
                    headers: authHeaders(),
                    body: JSON.stringify({
                        topic,
                        domain,
                        length,
                        num_references: numRefs,
                        ieee_format: ieeeFormat,
                    }),
                });

                if (!res.ok) {
                    const errData = await res.json().catch(() => ({}));
                    throw new Error(formatApiErrorMessage(errData, res.status));
                }

                const data = await res.json();
                state.currentJobId = data.job_id;
                state.pollingJobType = 'generate';

                showProgressView(`Generating: "${topic}"`, 'Your research paper is being generated...');
                startPolling(data.job_id, 'research');

            } catch (e) {
                showToast(`Failed to start generation: ${e.message}`, 'error');
            } finally {
                btnGenerate.disabled = false;
                btnGenerate.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg> Generate Research Paper`;
            }
        });
    }

    // ---------------------------------------------------------------------------
    // WORKFLOW 2: Restructure to IEEE
    // ---------------------------------------------------------------------------
    function initRestructure() {
        const fileInput = document.getElementById('restructure-file-input');
        const dropZone = document.getElementById('restructure-drop-zone');
        const browseBtn = document.getElementById('btn-restructure-browse');
        const clearBtn = document.getElementById('btn-restructure-clear');
        const fileSelected = document.getElementById('restructure-file-selected');
        const filenameDisplay = document.getElementById('restructure-filename-display');
        const startBtn = document.getElementById('btn-start-restructure');

        if (!fileInput) return;

        function setFile(file) {
            state.restructureFile = file;
            if (filenameDisplay) filenameDisplay.textContent = file.name;
            if (fileSelected) fileSelected.classList.remove('hidden');
            if (dropZone) dropZone.style.display = 'none';
            if (startBtn) startBtn.disabled = false;
        }

        function clearFile() {
            state.restructureFile = null;
            if (fileInput) fileInput.value = '';
            if (fileSelected) fileSelected.classList.add('hidden');
            if (dropZone) dropZone.style.display = '';
            if (startBtn) startBtn.disabled = true;
        }

        if (browseBtn) browseBtn.addEventListener('click', (e) => { e.preventDefault(); fileInput.click(); });
        if (clearBtn) clearBtn.addEventListener('click', clearFile);

        if (fileInput) {
            fileInput.addEventListener('change', () => {
                if (fileInput.files[0]) setFile(fileInput.files[0]);
            });
        }

        if (dropZone) {
            dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
            dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('drag-over');
                const file = e.dataTransfer.files[0];
                if (file) setFile(file);
            });
            dropZone.addEventListener('click', () => fileInput.click());
        }

        if (startBtn) {
            startBtn.addEventListener('click', async () => {
                if (!state.restructureFile) {
                    showToast('Please select a file to restructure.', 'error');
                    return;
                }

                try {
                    startBtn.disabled = true;
                    startBtn.textContent = 'Uploading...';

                    const formData = new FormData();
                    formData.append('file', state.restructureFile);
                    formData.append('preserve_citations',
                        String(document.getElementById('restructure-preserve-citations')?.checked ?? true));

                    const res = await fetch(`${apiBase()}/api/v1/research/restructure`, {
                        method: 'POST',
                        headers: authHeadersFormData(),
                        body: formData,
                    });

                    if (!res.ok) {
                        const err = await res.json().catch(() => ({}));
                        throw new Error(err.detail || `Upload failed: ${res.status}`);
                    }

                    const data = await res.json();
                    state.currentJobId = data.job_id;
                    state.pollingJobType = 'restructure';

                    showProgressView(
                        `Restructuring: "${state.restructureFile.name}"`,
                        'Detecting sections and applying IEEE formatting...'
                    );
                    startPolling(data.job_id, 'research');

                } catch (e) {
                    showToast(`Restructure failed: ${e.message}`, 'error');
                } finally {
                    startBtn.disabled = false;
                    startBtn.textContent = 'Restructure to IEEE';
                }
            });
        }
    }

    // ---------------------------------------------------------------------------
    // WORKFLOW 3: Similarity Check
    // ---------------------------------------------------------------------------
    function initSimilarityCheck() {
        // Mode tabs
        const tabFile = document.getElementById('sim-tab-file');
        const tabText = document.getElementById('sim-tab-text');
        const fileMode = document.getElementById('sim-file-mode');
        const textMode = document.getElementById('sim-text-mode');

        if (tabFile) {
            tabFile.addEventListener('click', () => {
                tabFile.classList.add('active');
                if (tabText) tabText.classList.remove('active');
                if (fileMode) fileMode.classList.remove('hidden');
                if (textMode) textMode.classList.add('hidden');
            });
        }

        if (tabText) {
            tabText.addEventListener('click', () => {
                tabText.classList.add('active');
                if (tabFile) tabFile.classList.remove('active');
                if (textMode) textMode.classList.remove('hidden');
                if (fileMode) fileMode.classList.add('hidden');
            });
        }

        // File drop zone
        const fileInput = document.getElementById('simcheck-file-input');
        const dropZone = document.getElementById('simcheck-drop-zone');
        const browseBtn = document.getElementById('btn-simcheck-browse');
        const clearBtn = document.getElementById('btn-simcheck-clear');
        const fileSelected = document.getElementById('simcheck-file-selected');
        const filenameDisplay = document.getElementById('simcheck-filename-display');

        function setSimFile(file) {
            state.simcheckFile = file;
            if (filenameDisplay) filenameDisplay.textContent = file.name;
            if (fileSelected) fileSelected.classList.remove('hidden');
            if (dropZone) dropZone.style.display = 'none';
        }

        function clearSimFile() {
            state.simcheckFile = null;
            if (fileInput) fileInput.value = '';
            if (fileSelected) fileSelected.classList.add('hidden');
            if (dropZone) dropZone.style.display = '';
        }

        if (browseBtn) browseBtn.addEventListener('click', (e) => { e.preventDefault(); fileInput.click(); });
        if (clearBtn) clearBtn.addEventListener('click', clearSimFile);
        if (fileInput) fileInput.addEventListener('change', () => { if (fileInput.files[0]) setSimFile(fileInput.files[0]); });

        if (dropZone) {
            dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('drag-over'); });
            dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('drag-over');
                const file = e.dataTransfer.files[0];
                if (file) setSimFile(file);
            });
            dropZone.addEventListener('click', () => fileInput.click());
        }

        // Run button
        const runBtn = document.getElementById('btn-run-simcheck');
        if (runBtn) {
            runBtn.addEventListener('click', async () => {
                const isTextMode = tabText && tabText.classList.contains('active');
                const text = isTextMode ? (document.getElementById('simcheck-text-input')?.value?.trim() || '') : '';

                if (isTextMode && text.length < 50) {
                    showToast('Please enter at least 50 characters of text to analyze.', 'error');
                    return;
                }

                if (!isTextMode && !state.simcheckFile) {
                    showToast('Please select a file to analyze.', 'error');
                    return;
                }

                try {
                    runBtn.disabled = true;
                    runBtn.textContent = 'Uploading...';

                    let res;
                    if (isTextMode) {
                        const formData = new FormData();
                        formData.append('text', text);
                        res = await fetch(`${apiBase()}/api/v1/plagiarism/check`, {
                            method: 'POST',
                            headers: authHeadersFormData(),
                            body: formData,
                        });
                    } else {
                        const formData = new FormData();
                        formData.append('file', state.simcheckFile);
                        res = await fetch(`${apiBase()}/api/v1/plagiarism/check`, {
                            method: 'POST',
                            headers: authHeadersFormData(),
                            body: formData,
                        });
                    }

                    if (!res.ok) {
                        const err = await res.json().catch(() => ({}));
                        throw new Error(err.detail || `Check failed: ${res.status}`);
                    }

                    const data = await res.json();
                    state.simJobId = data.job_id;

                    showProgressView('Analyzing Similarity...', 'Checking against academic sources...');
                    startPolling(data.job_id, 'similarity');

                } catch (e) {
                    showToast(`Similarity check failed: ${e.message}`, 'error');
                } finally {
                    runBtn.disabled = false;
                    runBtn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 12 11 14 15 10"></polyline></svg> Run Similarity Check`;
                }
            });
        }

        // Results view buttons
        const backBtn = document.getElementById('btn-simresults-back');
        if (backBtn) backBtn.addEventListener('click', () => showViewGlobal('simcheck-view'));

        const pdfBtn = document.getElementById('btn-simresults-pdf');
        if (pdfBtn) {
            pdfBtn.addEventListener('click', async () => {
                if (!state.simJobId) return;
                const url = `${apiBase()}/api/v1/plagiarism/report/${state.simJobId}`;
                downloadFile(url, `similarity_report.pdf`);
            });
        }
    }

    // ---------------------------------------------------------------------------
    // Polling
    // ---------------------------------------------------------------------------
    // Live Background Paper Stream & Typewriter Engine
    // ---------------------------------------------------------------------------
    const liveStreamState = {
        active: false,
        renderedLengths: {}, // id -> character length rendered so far
        pendingTyping: [],   // items queue: { targetEl, fullText, currentLen, onComplete }
        typingInterval: null,
        isMinimized: false,
        activeSectionId: null,
    };

    function startTypewriterLoop() {
        if (liveStreamState.typingInterval) return;
        liveStreamState.typingInterval = setInterval(() => {
            if (!liveStreamState.pendingTyping.length) {
                clearInterval(liveStreamState.typingInterval);
                liveStreamState.typingInterval = null;
                return;
            }

            const item = liveStreamState.pendingTyping[0];
            const targetEl = item.targetEl;
            if (!targetEl || !document.body.contains(targetEl)) {
                liveStreamState.pendingTyping.shift();
                return;
            }

            const targetText = item.fullText || '';
            const remaining = targetText.length - item.currentLen;
            const step = Math.max(3, Math.min(22, Math.ceil(remaining / 8)));
            item.currentLen = Math.min(targetText.length, item.currentLen + step);

            const slice = targetText.slice(0, item.currentLen);
            const isDone = item.currentLen >= targetText.length;

            targetEl.innerHTML = formatContent(slice) + (isDone ? '' : '<span class="typing-caret"></span>');

            if (isDone) {
                liveStreamState.pendingTyping.shift();
                if (typeof item.onComplete === 'function') item.onComplete();
            }
        }, 25);
    }

    function queueTyping(targetEl, fullText, onComplete) {
        if (!targetEl || !fullText) return;
        const existingIdx = liveStreamState.pendingTyping.findIndex(p => p.targetEl === targetEl);
        if (existingIdx >= 0) {
            liveStreamState.pendingTyping[existingIdx].fullText = fullText;
        } else {
            liveStreamState.pendingTyping.push({
                targetEl,
                fullText,
                currentLen: 0,
                onComplete,
            });
        }
        startTypewriterLoop();
    }

    function initLivePaperCanvas(topic) {
        liveStreamState.active = true;
        liveStreamState.renderedLengths = {};
        liveStreamState.pendingTyping = [];
        liveStreamState.activeSectionId = null;

        const inner = document.getElementById('live-paper-inner');
        if (!inner) return;

        const defaultAffils = [
            { dept: 'Dept. of Computer Science &amp; Eng.', org: 'Lemma AI Research Laboratory', loc: 'New York, USA', email: 'author1@lemma.ai' },
            { dept: 'Dept. of Electrical &amp; Data Systems', org: 'Lemma AI Research Laboratory', loc: 'Boston, USA', email: 'author2@lemma.ai' },
            { dept: 'Dept. of Information Intelligence', org: 'Lemma AI Research Laboratory', loc: 'San Francisco, USA', email: 'author3@lemma.ai' }
        ];

        let html = `
            <div class="paper-journal-meta">IEEE TRANSACTIONS ON COMPUTATIONAL INTELLIGENCE &amp; DATA RESEARCH — OFFICIAL CONFERENCE TEMPLATE</div>
            <h1 class="paper-title-preview" id="live-paper-title">${escHtml(topic || 'Synthesizing Research Topic...')}</h1>
            <div class="paper-authors-grid">
        `;

        for (let i = 0; i < 3; i++) {
            const aff = defaultAffils[i];
            html += `
                <div class="paper-author-card">
                    <div class="author-name">Author ${i+1}</div>
                    <div class="author-dept">${aff.dept}</div>
                    <div class="author-org">(${aff.org})</div>
                    <div class="author-loc">${aff.loc}</div>
                    <div class="author-email">${aff.email}</div>
                </div>`;
        }

        html += `</div>
            <div class="paper-two-column-body" id="live-paper-two-col">
                <div class="paper-abstract-preview" id="live-abstract-block" style="display: none;"></div>
                <div class="paper-keywords-preview" id="live-keywords-block" style="display: none;"></div>
                <div id="live-sections-stream"></div>
                <div class="paper-section-preview" id="live-references-block" style="display: none;"></div>
            </div>
        `;

        inner.innerHTML = html;
    }

    function updateLivePaperPreview(paper, step, pct) {
        if (!paper) return;

        // 1. Title
        if (paper.title) {
            const titleEl = document.getElementById('live-paper-title');
            if (titleEl && titleEl.textContent !== paper.title && !paper.title.startsWith('Generating:')) {
                titleEl.textContent = paper.title;
            }
        }

        // 2. Keywords
        if (paper.keywords && paper.keywords.length) {
            const kwBlock = document.getElementById('live-keywords-block');
            if (kwBlock && kwBlock.style.display === 'none') {
                kwBlock.style.display = 'block';
                kwBlock.innerHTML = '<span class="ieee-run-in">Index Terms—</span>' + escHtml(paper.keywords.join(', '));
            }
        }

        // 3. Abstract
        if (paper.abstract && paper.abstract.trim().length > 0) {
            const absBlock = document.getElementById('live-abstract-block');
            if (absBlock) {
                if (absBlock.style.display === 'none') absBlock.style.display = 'block';
                const key = 'abstract';
                const prevLen = liveStreamState.renderedLengths[key] || 0;
                if (paper.abstract.length > prevLen) {
                    liveStreamState.renderedLengths[key] = paper.abstract.length;
                    queueTyping(absBlock, 'Abstract—' + paper.abstract);
                }
            }
        }

        // 4. Sections & Live Outline Structure
        if (paper.sections && paper.sections.length) {
            const secContainer = document.getElementById('live-sections-stream');
            if (secContainer) {
                let activeSecFound = null;

                paper.sections.forEach((sec, idx) => {
                    let secEl = document.getElementById(`live-sec-${sec.number}`);
                    if (!secEl) {
                        secEl = document.createElement('div');
                        secEl.className = 'paper-section-preview';
                        secEl.id = `live-sec-${sec.number}`;
                        secEl.innerHTML = `
                            <h2 class="paper-section-heading-preview">
                                ${escHtml(sec.number)}. ${escHtml((sec.title || '').toUpperCase())}
                                <span class="sec-status-badge" id="sec-badge-${sec.number}"></span>
                            </h2>
                            <div class="paper-section-content-preview" id="live-sec-content-${sec.number}">
                                <div class="skeleton-text-block">
                                    <div class="skeleton-text-line" style="width: 95%;"></div>
                                    <div class="skeleton-text-line" style="width: 82%;"></div>
                                    <div class="skeleton-text-line" style="width: 88%;"></div>
                                </div>
                            </div>
                        `;
                        secContainer.appendChild(secEl);
                    }

                    const contentEl = document.getElementById(`live-sec-content-${sec.number}`);
                    const badgeEl = document.getElementById(`sec-badge-${sec.number}`);
                    const secKey = `sec_${sec.number}`;
                    const prevLen = liveStreamState.renderedLengths[secKey] || 0;

                    if (sec.content && sec.content.trim().length > 0) {
                        if (sec.content.length > prevLen) {
                            liveStreamState.renderedLengths[secKey] = sec.content.length;
                            activeSecFound = secEl;
                            if (badgeEl) {
                                badgeEl.innerHTML = '<span class="writing-active-badge"><span class="live-pulsing-dot"></span> Typing Now...</span>';
                            }
                            queueTyping(contentEl, sec.content, () => {
                                if (badgeEl) badgeEl.innerHTML = '';
                            });
                        } else if (!badgeEl?.innerHTML.includes('Typing Now')) {
                            if (badgeEl) badgeEl.innerHTML = '';
                        }
                    } else {
                        // Pending in outline
                        if (badgeEl && !badgeEl.innerHTML) {
                            badgeEl.innerHTML = '<span style="font-size:0.7rem; color:#94a3b8; font-weight:normal; text-transform:none; margin-left:6px;">[Pending outline]</span>';
                        }
                    }
                });

                if (activeSecFound && activeSecFound !== liveStreamState.activeSectionId) {
                    document.querySelectorAll('.section-writing-active').forEach(el => el.classList.remove('section-writing-active'));
                    activeSecFound.classList.add('section-writing-active');
                    liveStreamState.activeSectionId = activeSecFound;
                    // Auto-scroll inside live-paper-stage on the right
                    const paperStage = document.getElementById('live-paper-stage');
                    if (paperStage) {
                        const offsetTop = activeSecFound.offsetTop - 120;
                        paperStage.scrollTo({ top: Math.max(0, offsetTop), behavior: 'smooth' });
                    }
                }
            }
        }

        // 5. References
        if (paper.citations && paper.citations.length) {
            const refsBlock = document.getElementById('live-references-block');
            if (refsBlock) {
                refsBlock.style.display = 'block';
                let refsHtml = '<h2 class="paper-section-heading-preview">REFERENCES</h2><div class="paper-references-list">';
                paper.citations.forEach(cit => {
                    refsHtml += `<p class="paper-ref-preview">[${cit.number}] ${escHtml(buildRefString(cit))}</p>`;
                });
                refsHtml += '</div>';
                refsBlock.innerHTML = refsHtml;
            }
        }
    }

    // ---------------------------------------------------------------------------
    // Polling
    // ---------------------------------------------------------------------------
    function startPolling(jobId, type) {
        stopPolling();
        state.pollingTimer = setInterval(() => pollJobStatus(jobId, type), 2000);
        // Poll immediately
        pollJobStatus(jobId, type);
    }

    function stopPolling() {
        if (state.pollingTimer) {
            clearInterval(state.pollingTimer);
            state.pollingTimer = null;
        }
        if (liveStreamState.typingInterval) {
            clearInterval(liveStreamState.typingInterval);
            liveStreamState.typingInterval = null;
        }
    }

    async function pollJobStatus(jobId, type) {
        try {
            const endpoint = type === 'similarity'
                ? `${apiBase()}/api/v1/plagiarism/status/${jobId}`
                : `${apiBase()}/api/v1/research/status/${jobId}`;

            const res = await fetch(endpoint, { headers: authHeaders() });
            if (!res.ok) return;

            const data = await res.json();
            updateProgressUI(data, type);

            // Stream background paper live if paper object is attached
            if (data.paper && type !== 'similarity') {
                updateLivePaperPreview(data.paper, data.progress_step || 'Processing...', data.progress_pct || 0);
            }

            if (data.status === 'completed') {
                stopPolling();
                if (type === 'similarity') {
                    showSimResults(data.report, jobId);
                } else {
                    // Hide generation box and center the paper
                    const progressView = document.getElementById('paper-progress-view');
                    if (progressView) progressView.classList.add('generation-completed');

                    // Small delay to let user see completed paper centered before opening editor
                    setTimeout(async () => {
                        await loadAndShowPaper(data.paper_id || jobId);
                    }, 1400);
                }
            } else if (data.status === 'failed') {
                stopPolling();
                showToast(`Process failed: ${data.error || 'Unknown error'}`, 'error');
                showViewGlobal('dashboard-home-view');
            }
        } catch (e) {
            console.error('Polling error:', e);
        }
    }

    function updateProgressUI(data, type) {
        const pct = data.progress_pct || 0;
        const step = data.progress_step || 'Processing...';

        const fill = document.getElementById('progress-bar-fill');
        const pctText = document.getElementById('progress-pct-text');
        const stepText = document.getElementById('progress-step-text');

        if (fill) fill.style.width = `${pct}%`;
        if (pctText) pctText.textContent = `${pct}%`;
        if (stepText) stepText.textContent = step;

        // Update stage dots based on percentage
        updateStageDots(pct, type);
    }

    function updateStageDots(pct, type) {
        const stages = ['analyze', 'sources', 'outline', 'write', 'citations', 'similarity', 'done'];
        const thresholds = [5, 30, 40, 80, 85, 88, 100];

        stages.forEach((stage, idx) => {
            const dot = document.getElementById(`stage-${stage}-dot`);
            if (!dot) return;
            if (pct >= thresholds[idx]) {
                dot.className = 'stage-dot done';
            } else if (pct >= (thresholds[idx - 1] || 0)) {
                dot.className = 'stage-dot active';
            } else {
                dot.className = 'stage-dot pending';
            }
        });
    }

    function showProgressView(title, subtitle) {
        const titleEl = document.getElementById('progress-title');
        const subtitleEl = document.getElementById('progress-subtitle');
        if (titleEl) titleEl.textContent = title;
        if (subtitleEl) subtitleEl.textContent = subtitle;

        // Reset progress
        const fill = document.getElementById('progress-bar-fill');
        const pctText = document.getElementById('progress-pct-text');
        const stepText = document.getElementById('progress-step-text');
        if (fill) fill.style.width = '0%';
        if (pctText) pctText.textContent = '0%';
        if (stepText) stepText.textContent = 'Starting...';

        // Reset dots
        document.querySelectorAll('.stage-dot').forEach(d => d.className = 'stage-dot pending');

        // Reset split layout state (show box on left, paper on right)
        const progressView = document.getElementById('paper-progress-view');
        if (progressView) progressView.classList.remove('generation-completed');
        const pCard = document.getElementById('progress-view-card');
        if (pCard) pCard.style.display = '';

        // Initialize Background Paper Canvas with topic
        initLivePaperCanvas(title);

        showViewGlobal('paper-progress-view');
    }

    // ---------------------------------------------------------------------------
    // Load & Show Paper Editor
    // ---------------------------------------------------------------------------
    async function loadAndShowPaper(paperId) {
        try {
            const res = await fetch(`${apiBase()}/api/v1/research/${paperId}`, {
                headers: authHeaders(),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Failed to load paper: ${res.status}`);
            }

            const paper = await res.json();
            state.currentPaper = paper;
            state.currentPaperId = paperId;

            renderPaperEditor(paper);
            showViewGlobal('paper-editor-view');
            showToast('Paper ready!', 'success');

        } catch (e) {
            showToast(`Could not load paper: ${e.message}`, 'error');
            showViewGlobal('dashboard-home-view');
        }
    }

    function renderPaperEditor(paper) {
        // Update header
        const titleEl = document.getElementById('paper-editor-title');
        const metaEl = document.getElementById('paper-editor-meta');
        if (titleEl) titleEl.textContent = paper.title || 'Research Paper';

        const typeLabel = paper.paper_type === 'generated' ? 'Generated' : 'Restructured';
        const refsCount = (paper.citations || []).length;
        if (metaEl) metaEl.textContent = `${typeLabel} • ${refsCount} references`;

        // Similarity badge
        const simScore = paper.similarity_score;
        const simBadge = document.getElementById('paper-similarity-score');
        if (simBadge) {
            if (simScore !== null && simScore !== undefined) {
                const pct = Math.round(simScore * 100);
                simBadge.textContent = `${pct}%`;
                simBadge.style.color = scoreColor(simScore);
            } else {
                simBadge.textContent = '—';
            }
        }

        // Paper info sidebar
        const infoType = document.getElementById('paper-info-type');
        const infoSections = document.getElementById('paper-info-sections');
        const infoRefs = document.getElementById('paper-info-refs');
        const infoSim = document.getElementById('paper-info-similarity');
        if (infoType) infoType.textContent = typeLabel;
        if (infoSections) infoSections.textContent = (paper.sections || []).length;
        if (infoRefs) infoRefs.textContent = refsCount;
        if (infoSim) {
            infoSim.textContent = simScore !== null && simScore !== undefined
                ? `${Math.round(simScore * 100)}%`
                : '—';
        }

        // Build section nav
        const navEl = document.getElementById('paper-section-nav');
        if (navEl) {
            navEl.innerHTML = `<div class="paper-nav-header">Sections</div>
                <div class="paper-nav-item active" data-section="abstract">Abstract</div>`;

            (paper.sections || []).forEach(sec => {
                const item = document.createElement('div');
                item.className = 'paper-nav-item';
                item.dataset.section = sec.number;
                item.textContent = `${sec.number}. ${sec.title}`;

                if (sec.similarity_score !== null && sec.similarity_score !== undefined) {
                    const dot = document.createElement('span');
                    dot.style.cssText = `width: 8px; height: 8px; border-radius: 50%; background: ${scoreColor(sec.similarity_score)}; display: inline-block; margin-left: 6px;`;
                    item.appendChild(dot);
                }
                navEl.appendChild(item);
            });

            const divider = document.createElement('div');
            divider.className = 'paper-nav-divider';
            navEl.appendChild(divider);

            const refsItem = document.createElement('div');
            refsItem.className = 'paper-nav-item';
            refsItem.dataset.section = 'references';
            refsItem.textContent = 'References';
            navEl.appendChild(refsItem);

            // Section nav clicks
            navEl.querySelectorAll('.paper-nav-item').forEach(item => {
                item.addEventListener('click', () => {
                    navEl.querySelectorAll('.paper-nav-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                    const section = item.dataset.section;
                    scrollToSection(section, paper);
                    showSectionDetails(section, paper);
                });
            });
        }

        // Render the paper content
        renderPaperContent(paper);
    }

    function renderPaperContent(paper) {
        const wrapper = document.getElementById('paper-preview-wrapper');
        if (!wrapper) return;

        let html = `<div class="paper-preview-inner">`;

        // Journal Meta Header Banner
        html += `<div class="paper-journal-meta">IEEE TRANSACTIONS ON COMPUTATIONAL INTELLIGENCE &amp; DATA RESEARCH • OFFICIAL CONFERENCE TEMPLATE</div>`;

        // Title (Full Width)
        html += `<h1 class="paper-title-preview" id="paper-editable-title">${escHtml(paper.title || 'Research Paper Title')}</h1>`;

        // Author Affiliations (3-Column Grid matching IEEE Template)
        const authors = (paper.authors && paper.authors.length) ? paper.authors : [
            '1st Given Name Surname',
            '2nd Given Name Surname',
            '3rd Given Name Surname'
        ];

        html += `<div class="paper-authors-grid">`;
        const defaultAffils = [
            { dept: 'dept. of computer science &amp; eng.', org: 'Lemma AI Research Laboratory', loc: 'New York, USA', email: 'author1@lemma.ai' },
            { dept: 'dept. of electrical &amp; data systems', org: 'Lemma AI Research Laboratory', loc: 'Boston, USA', email: 'author2@lemma.ai' },
            { dept: 'dept. of information intelligence', org: 'Lemma AI Research Laboratory', loc: 'San Francisco, USA', email: 'author3@lemma.ai' }
        ];

        for (let i = 0; i < 3; i++) {
            const authorName = authors[i] || `Author ${i+1}`;
            const aff = defaultAffils[i];
            html += `
                <div class="paper-author-card">
                    <div class="author-name">${escHtml(authorName)}</div>
                    <div class="author-dept">${aff.dept}</div>
                    <div class="author-org">(${aff.org})</div>
                    <div class="author-loc">${aff.loc}</div>
                    <div class="author-email">${aff.email}</div>
                </div>`;
        }
        html += `</div>`;

        // 2-Column Body Container
        html += `<div class="paper-two-column-body">`;

        // Abstract (Left column start)
        if (paper.abstract) {
            html += `<div class="paper-abstract-preview" id="section-abstract">
                <span class="ieee-run-in">Abstract—</span><span class="abstract-content-editable" id="paper-editable-abstract">${escHtml(paper.abstract)}</span>
            </div>`;
        }

        // Keywords / Index Terms
        if (paper.keywords && paper.keywords.length) {
            html += `<div class="paper-keywords-preview">
                <span class="ieee-run-in">Index Terms—</span><span class="keywords-content-editable" id="paper-editable-keywords">${escHtml(paper.keywords.join(', '))}</span>
            </div>`;
        }

        // Sections (2-Column flow)
        (paper.sections || []).forEach((sec, idx) => {
            const simLabel = sec.similarity_score !== null && sec.similarity_score !== undefined
                ? `<span class="section-sim-indicator" style="color: ${scoreColor(sec.similarity_score)}; font-size: 0.75rem; font-weight: normal; margin-left: 8px;">(${Math.round(sec.similarity_score * 100)}% match)</span>`
                : '';

            html += `<div class="paper-section-preview" id="section-${sec.number}" data-sec-idx="${idx}">
                <h2 class="paper-section-heading-preview">
                    <span class="sec-num-label">${escHtml(sec.number)}. </span>
                    <span class="sec-title-editable">${escHtml(sec.title.toUpperCase())}</span>
                    ${simLabel}
                </h2>
                <div class="paper-section-content-preview sec-content-editable">${formatContent(sec.content)}</div>`;

            (sec.subsections || []).forEach(sub => {
                html += `<h3 class="paper-subsection-heading-preview"><i>${escHtml(sub.label)}. ${escHtml(sub.title)}</i></h3>
                    <div class="paper-section-content-preview">${formatContent(sub.content)}</div>`;
            });

            html += `</div>`;
        });

        // References (in 2-column flow)
        if (paper.citations && paper.citations.length) {
            html += `<div class="paper-section-preview" id="section-references">
                <h2 class="paper-section-heading-preview">REFERENCES</h2>
                <div class="paper-references-list">`;
            paper.citations.forEach(cit => {
                const refStr = buildRefString(cit);
                html += `<p class="paper-ref-preview" id="ref-${cit.number}">${escHtml(refStr)}</p>`;
            });
            html += `</div></div>`;
        }

        html += `</div></div>`;
        wrapper.innerHTML = html;
    }

    function scrollToSection(sectionId, paper) {
        const el = document.getElementById(`section-${sectionId}`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function showSectionDetails(sectionId, paper) {
        const detailEl = document.getElementById('section-detail-info');
        const improveCard = document.getElementById('section-improve-card');
        const improveBtn = document.getElementById('btn-improve-section');

        if (!detailEl) return;

        const sec = (paper.sections || []).find(s => s.number === sectionId);

        if (sectionId === 'abstract') {
            detailEl.innerHTML = `<p style="font-size: 0.82rem; color: var(--text-secondary);">Abstract — ${(paper.abstract || '').length} characters</p>`;
            if (improveCard) improveCard.style.display = 'none';
            return;
        }

        if (sectionId === 'references') {
            detailEl.innerHTML = `<p style="font-size: 0.82rem; color: var(--text-secondary);">${(paper.citations || []).length} references</p>`;
            if (improveCard) improveCard.style.display = 'none';
            return;
        }

        if (!sec) return;

        const simPct = sec.similarity_score !== null && sec.similarity_score !== undefined
            ? `${Math.round(sec.similarity_score * 100)}%`
            : '—';

        detailEl.innerHTML = `
            <div class="paper-info-row"><span>Section</span><span>${escHtml(sec.number)}. ${escHtml(sec.title)}</span></div>
            <div class="paper-info-row"><span>Similarity</span><span style="color: ${sec.similarity_score !== null ? scoreColor(sec.similarity_score) : 'inherit'};">${simPct}</span></div>
            <div class="paper-info-row"><span>Words</span><span>~${Math.round((sec.content || '').split(/\s+/).length)}</span></div>
        `;

        state.currentSection = sec.number;

        // Show improve button if similarity is high
        if (sec.similarity_score !== null && sec.similarity_score > 0.30) {
            if (improveCard) improveCard.style.display = 'block';
        } else {
            if (improveCard) improveCard.style.display = 'none';
        }

        // Wire improve button
        if (improveBtn) {
            improveBtn.onclick = () => improveSection(state.currentPaperId, sec.number);
        }
    }

    async function improveSection(paperId, sectionNumber) {
        const improveBtn = document.getElementById('btn-improve-section');
        if (!improveBtn) return;

        try {
            improveBtn.disabled = true;
            improveBtn.textContent = 'Rewriting...';

            const res = await fetch(`${apiBase()}/api/v1/research/${paperId}/improve`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({
                    paper_id: paperId,
                    section_number: sectionNumber,
                }),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || 'Improvement failed');
            }

            const data = await res.json();
            showToast('Section rewritten successfully!', 'success');

            // Reload paper
            await loadAndShowPaper(paperId);

        } catch (e) {
            showToast(`Could not improve section: ${e.message}`, 'error');
        } finally {
            if (improveBtn) {
                improveBtn.disabled = false;
                improveBtn.textContent = 'Rewrite Section';
            }
        }
    }

    // ---------------------------------------------------------------------------
    // In-Place Manual Paper Editing & Persistence
    // ---------------------------------------------------------------------------
    let isEditMode = false;

    function initPaperEditing() {
        const editBtn = document.getElementById('btn-edit-paper');
        const saveBtn = document.getElementById('btn-save-paper');
        const cancelBtn = document.getElementById('btn-cancel-edit');

        if (editBtn) {
            editBtn.addEventListener('click', () => {
                setEditMode(true);
            });
        }

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                setEditMode(false);
                if (state.currentPaper) {
                    renderPaperContent(state.currentPaper);
                }
            });
        }

        if (saveBtn) {
            saveBtn.addEventListener('click', async () => {
                await savePaperEdits();
            });
        }
    }

    function setEditMode(active) {
        isEditMode = active;
        const editBtn = document.getElementById('btn-edit-paper');
        const saveBtn = document.getElementById('btn-save-paper');
        const cancelBtn = document.getElementById('btn-cancel-edit');
        const banner = document.getElementById('paper-edit-banner');
        const inner = document.querySelector('.paper-preview-inner');

        if (editBtn) editBtn.classList.toggle('hidden', active);
        if (saveBtn) saveBtn.classList.toggle('hidden', !active);
        if (cancelBtn) cancelBtn.classList.toggle('hidden', !active);
        if (banner) banner.classList.toggle('hidden', !active);

        if (inner) {
            inner.classList.toggle('editing-active', active);
        }

        // Toggle contenteditable on target elements
        const titleEl = document.getElementById('paper-editable-title');
        const abstractEl = document.getElementById('paper-editable-abstract');
        const keywordsEl = document.getElementById('paper-editable-keywords');
        const secTitles = document.querySelectorAll('.sec-title-editable');
        const secContents = document.querySelectorAll('.sec-content-editable');

        if (titleEl) titleEl.contentEditable = active ? "true" : "false";
        if (abstractEl) abstractEl.contentEditable = active ? "true" : "false";
        if (keywordsEl) keywordsEl.contentEditable = active ? "true" : "false";

        secTitles.forEach(el => el.contentEditable = active ? "true" : "false");
        secContents.forEach(el => el.contentEditable = active ? "true" : "false");

        if (active && titleEl) {
            titleEl.focus();
            showToast('Editing mode active. Click any text to edit.', 'info');
        }
    }

    async function savePaperEdits() {
        if (!state.currentPaperId || !state.currentPaper) return;

        const saveBtn = document.getElementById('btn-save-paper');
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> <span>Saving...</span>';
        }

        try {
            const titleEl = document.getElementById('paper-editable-title');
            const abstractEl = document.getElementById('paper-editable-abstract');
            const keywordsEl = document.getElementById('paper-editable-keywords');

            const newTitle = titleEl ? titleEl.innerText.trim() : state.currentPaper.title;
            const newAbstract = abstractEl ? abstractEl.innerText.trim() : state.currentPaper.abstract;
            const newKeywords = keywordsEl 
                ? keywordsEl.innerText.split(',').map(k => k.trim()).filter(Boolean)
                : state.currentPaper.keywords;

            // Collect sections
            const secPreviews = document.querySelectorAll('.paper-section-preview[data-sec-idx]');
            const newSections = [];

            secPreviews.forEach((secEl) => {
                const idx = parseInt(secEl.getAttribute('data-sec-idx'), 10);
                const titleSpan = secEl.querySelector('.sec-title-editable');
                const contentDiv = secEl.querySelector('.sec-content-editable');

                const origSec = (state.currentPaper.sections || [])[idx] || {};
                newSections.push({
                    number: origSec.number || `SECTION_${idx+1}`,
                    title: titleSpan ? titleSpan.innerText.trim() : origSec.title,
                    content: contentDiv ? contentDiv.innerText.trim() : origSec.content
                });
            });

            const payload = {
                title: newTitle,
                abstract: newAbstract,
                keywords: newKeywords,
                sections: newSections.length ? newSections : undefined
            };

            const res = await fetch(`${apiBase()}/api/v1/research/${state.currentPaperId}`, {
                method: 'PUT',
                headers: authHeaders(),
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Save failed: ${res.status}`);
            }

            const updated = await res.json();
            state.currentPaper = updated;

            // Update header title in workspace
            const topTitle = document.getElementById('paper-editor-title');
            if (topTitle) topTitle.textContent = updated.title || 'Research Paper';

            setEditMode(false);
            showToast('Paper changes saved successfully! Ready to export.', 'success');

        } catch (e) {
            showToast(`Save error: ${e.message}`, 'error');
        } finally {
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> <span>Save Changes</span>';
            }
        }
    }

    // ---------------------------------------------------------------------------
    // Export
    // ---------------------------------------------------------------------------
    function initExport() {
        const pdfBtn = document.getElementById('btn-export-pdf');
        const docxBtn = document.getElementById('btn-export-docx');

        if (pdfBtn) {
            pdfBtn.addEventListener('click', async () => {
                if (!state.currentPaperId) return;
                if (isEditMode) {
                    await savePaperEdits();
                }
                downloadFile(
                    `${apiBase()}/api/v1/research/export/${state.currentPaperId}?format=pdf`,
                    `paper.pdf`
                );
            });
        }

        if (docxBtn) {
            docxBtn.addEventListener('click', async () => {
                if (!state.currentPaperId) return;
                if (isEditMode) {
                    await savePaperEdits();
                }
                downloadFile(
                    `${apiBase()}/api/v1/research/export/${state.currentPaperId}?format=docx`,
                    `paper.docx`
                );
            });
        }
    }

    async function downloadFile(url, filename) {
        try {
            showToast('Generating export...', 'info');
            const res = await fetch(url, { headers: authHeadersFormData() });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Export failed: ${res.status}`);
            }

            let downloadName = filename;
            const disposition = res.headers.get('content-disposition');
            if (disposition && disposition.includes('filename=')) {
                const match = disposition.match(/filename=["']?([^"';]+)["']?/i);
                if (match && match[1]) {
                    downloadName = match[1].trim();
                }
            }

            const blob = await res.blob();
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = downloadName;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(a.href);
            showToast(`Downloaded ${downloadName}!`, 'success');
        } catch (e) {
            showToast(`Export error: ${e.message}`, 'error');
        }
    }

    // Back button in paper editor
    function initPaperBack() {
        const backBtn = document.getElementById('btn-paper-back');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                showViewGlobal('mypapers-view');
                loadMyPapers();
            });
        }
    }

    // ---------------------------------------------------------------------------
    // Similarity Results
    // ---------------------------------------------------------------------------
    function showSimResults(report, jobId) {
        if (!report) {
            showToast('No results available.', 'error');
            return;
        }

        state.simJobId = jobId;

        const overallScore = report.overall_score || 0;
        const pct = Math.round(overallScore * 100);

        // Score circle
        const scoreNumber = document.getElementById('sim-score-number');
        const scoreCircle = document.getElementById('sim-score-circle');
        if (scoreNumber) scoreNumber.textContent = `${pct}%`;
        if (scoreCircle) scoreCircle.style.borderColor = scoreColor(overallScore);

        // Stats
        const origPct = document.getElementById('sim-original-pct');
        const matchPct = document.getElementById('sim-matched-pct');
        const totalSents = document.getElementById('sim-total-sents');
        const matchSents = document.getElementById('sim-matched-sents');
        const lexCount = document.getElementById('sim-lexical-count');
        const semCount = document.getElementById('sim-semantic-count');

        if (origPct) origPct.textContent = `${Math.round((report.original_pct || 0) * 100)}%`;
        if (matchPct) matchPct.textContent = `${pct}%`;
        if (totalSents) totalSents.textContent = report.total_sentences || 0;
        if (matchSents) matchSents.textContent = report.matched_sentences || 0;
        if (lexCount) lexCount.textContent = report.lexical_matches || 0;
        if (semCount) semCount.textContent = report.semantic_matches || 0;

        // Subtitle
        const subtitle = document.getElementById('simresults-subtitle');
        if (subtitle) {
            const verdict = pct < 20 ? '✓ Low similarity — content appears mostly original.' :
                            pct < 40 ? '⚠ Moderate similarity detected.' :
                            '⚠ High similarity — significant matches found.';
            subtitle.textContent = verdict;
        }

        // Match cards
        const matchList = document.getElementById('sim-matches-list');
        const noMatches = document.getElementById('sim-no-matches');
        if (matchList) {
            matchList.innerHTML = '';
            const matches = report.matches || [];
            if (matches.length === 0) {
                if (noMatches) noMatches.style.display = 'block';
            } else {
                if (noMatches) noMatches.style.display = 'none';
                matches.forEach(match => {
                    const card = buildMatchCard(match);
                    matchList.appendChild(card);
                });
            }
        }

        showViewGlobal('simresults-view');
    }

    function buildMatchCard(match) {
        const card = document.createElement('div');
        card.className = 'sim-match-card';

        const scoreColor_ = scoreColor(match.similarity_score || 0);
        const pct = Math.round((match.similarity_score || 0) * 100);

        card.innerHTML = `
            <div class="sim-match-header">
                <span class="sim-match-type badge-${match.match_type || 'lexical'}">${(match.match_type || 'lexical').toUpperCase()}</span>
                <span class="sim-match-score" style="color: ${scoreColor_}; font-weight: 700;">${pct}% match</span>
                <span class="sim-match-confidence">${match.confidence || 'Low'}</span>
            </div>
            <div class="sim-match-body">
                <div class="sim-match-query">
                    <label>Your text:</label>
                    <p>"${escHtml((match.query_text || '').substring(0, 200))}${match.query_text && match.query_text.length > 200 ? '...' : ''}"</p>
                </div>
                <div class="sim-match-ref">
                    <label>Matched source:</label>
                    <p>"${escHtml((match.matched_text || '').substring(0, 200))}${match.matched_text && match.matched_text.length > 200 ? '...' : ''}"</p>
                    <div class="sim-source-info">
                        <strong>${escHtml(match.source_title || 'Unknown')}</strong>
                        ${match.source_author ? `<span> — ${escHtml(match.source_author)}</span>` : ''}
                        ${match.source_url ? `<a href="${match.source_url}" target="_blank" rel="noopener noreferrer" class="source-link">View Source</a>` : ''}
                    </div>
                </div>
            </div>`;
        return card;
    }

    function matchBadgeClass(type) {
        if (!type) return 'badge-secondary';
        const t = type.toLowerCase();
        if (t.includes('exact') || t.includes('verbatim')) return 'badge-danger';
        if (t.includes('paraphrase') || t.includes('semantic')) return 'badge-warning';
        return 'badge-info';
    }

    // ---------------------------------------------------------------------------
    // ---------------------------------------------------------------------------
    // My Research Library (Generated Papers, Restructured, Similarity Checks)
    // ---------------------------------------------------------------------------
    let libraryItems = [];
    let currentLibraryFilter = 'all';

    async function loadMyPapers() {
        const grid = document.getElementById('papers-grid');
        const empty = document.getElementById('mypapers-empty') || document.getElementById('papers-empty');
        if (!grid) return;

        try {
            const res = await fetch(`${apiBase()}/api/v1/research/papers`, {
                headers: authHeaders(),
            });
            if (!res.ok) throw new Error('Failed to load papers');

            const rawData = await res.json();
            libraryItems = Array.isArray(rawData) ? rawData : (rawData.papers || []);

            updateLibraryBadgeCounts();
            renderFilteredLibrary();
        } catch (e) {
            console.error('Failed to load library items:', e);
            if (empty) empty.style.display = 'block';
            if (grid) grid.style.display = 'none';
        }
    }

    function updateLibraryBadgeCounts() {
        const total = libraryItems.length;
        const genCount = libraryItems.filter(i => i.paper_type === 'generated').length;
        const restructCount = libraryItems.filter(i => i.paper_type === 'restructured').length;
        const simCount = libraryItems.filter(i => i.paper_type === 'similarity_check').length;

        const bAll = document.getElementById('badge-all-count');
        const bGen = document.getElementById('badge-gen-count');
        const bRes = document.getElementById('badge-restruct-count');
        const bSim = document.getElementById('badge-sim-count');

        if (bAll) bAll.textContent = total;
        if (bGen) bGen.textContent = genCount;
        if (bRes) bRes.textContent = restructCount;
        if (bSim) bSim.textContent = simCount;
    }

    function renderFilteredLibrary() {
        const grid = document.getElementById('papers-grid');
        const empty = document.getElementById('mypapers-empty') || document.getElementById('papers-empty');
        if (!grid) return;

        let filtered = libraryItems;
        if (currentLibraryFilter !== 'all') {
            filtered = libraryItems.filter(i => i.paper_type === currentLibraryFilter);
        }

        if (!filtered.length) {
            if (empty) empty.style.display = 'block';
            grid.style.display = 'none';
            grid.innerHTML = '';
            return;
        }

        if (empty) empty.style.display = 'none';
        grid.style.display = 'grid';
        grid.innerHTML = '';

        filtered.forEach(item => {
            grid.appendChild(buildPaperCard(item));
        });
    }

    function buildPaperCard(item) {
        const card = document.createElement('div');
        card.className = 'paper-card';

        const isSim = item.paper_type === 'similarity_check';
        const isRestruct = item.paper_type === 'restructured';

        let typeLabel = 'Generated Paper';
        let typeClass = 'type-generated';

        if (isSim) {
            typeLabel = 'Plagiarism Check';
            typeClass = 'type-similarity_check';
        } else if (isRestruct) {
            typeLabel = 'Restructured IEEE';
            typeClass = 'type-restructured';
        }

        const simPct = item.similarity_score !== null && item.similarity_score !== undefined
            ? `${Math.round(item.similarity_score * 100)}%`
            : '—';
        const simColor_ = item.similarity_score !== null ? scoreColor(item.similarity_score) : 'var(--text-muted)';

        const statusClass = item.status === 'completed' ? 'status-completed' :
                           item.status === 'failed' ? 'status-failed' : 'status-pending';

        const itemKey = item.job_id || item.paper_id || item.id;

        // Stats line based on type
        let statsHtml = '';
        if (isSim) {
            const totalSents = item.sections_count || 0;
            const matchedSents = item.citations_count || 0;
            statsHtml = `
                <span>Similarity: <strong style="color: ${simColor_};">${simPct}</strong></span>
                ${totalSents ? `<span style="color: var(--text-muted); font-size: 0.78rem;"> • ${totalSents} Sentences (${matchedSents} matched)</span>` : ''}
            `;
        } else {
            const secCount = item.sections_count || (item.sections ? item.sections.length : 0) || 8;
            const citCount = item.citations_count || (item.citations ? item.citations.length : 0) || 10;
            let dateStr = '';
            if (item.created_at) {
                try {
                    const d = new Date(item.created_at);
                    dateStr = ` • ${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
                } catch (_) {}
            }
            statsHtml = `
                <span style="color: #e2e8f0; font-weight: 500;">${secCount} Sections</span>
                <span style="color: var(--text-muted); font-size: 0.8rem;"> • </span>
                <span style="color: #e2e8f0; font-weight: 500;">${citCount} References</span>
                ${dateStr ? `<span style="color: var(--text-muted); font-size: 0.78rem;">${dateStr}</span>` : ''}
            `;
        }

        // Action buttons based on type
        let actionsHtml = '';
        if (isSim) {
            actionsHtml = `
                <button class="btn btn-sm btn-primary paper-view-sim-btn">View Report</button>
                <button class="btn btn-sm btn-outline paper-export-simpdf-btn">Report PDF</button>
                <button class="paper-card-delete-btn" title="Delete record">Delete</button>
            `;
        } else {
            actionsHtml = `
                ${item.status === 'completed' ? `<button class="btn btn-sm btn-primary paper-open-btn">Open Paper</button>` : ''}
                ${item.status === 'completed' ? `<button class="btn btn-sm btn-outline paper-export-pdf-btn">PDF</button>` : ''}
                ${item.status === 'completed' ? `<button class="btn btn-sm btn-outline paper-export-docx-btn">DOCX</button>` : ''}
                <button class="paper-card-delete-btn" title="Delete paper">Delete</button>
            `;
        }

        card.innerHTML = `
            <div class="paper-card-header">
                <span class="paper-card-type ${typeClass}">${typeLabel}</span>
                <span class="paper-card-status ${statusClass}">${item.status || 'completed'}</span>
            </div>
            <div class="paper-card-title">${escHtml(item.title || 'Untitled Document')}</div>
            ${item.topic ? `<div class="paper-card-topic">${escHtml(item.topic)}</div>` : ''}
            <div class="paper-card-stats">
                ${statsHtml}
            </div>
            <div class="paper-card-actions">
                ${actionsHtml}
            </div>
        `;

        // Wire buttons
        const openBtn = card.querySelector('.paper-open-btn');
        if (openBtn) {
            openBtn.addEventListener('click', async () => {
                await loadAndShowPaper(itemKey);
            });
        }

        const viewSimBtn = card.querySelector('.paper-view-sim-btn');
        if (viewSimBtn) {
            viewSimBtn.addEventListener('click', async () => {
                try {
                    const res = await fetch(`${apiBase()}/api/v1/research/similarity-report/${itemKey}`, {
                        headers: authHeaders(),
                    });
                    if (!res.ok) throw new Error('Could not load report');
                    const data = await res.json();
                    showSimResults(data.report, itemKey);
                } catch (err) {
                    showToast('Failed to load similarity report: ' + err.message, 'error');
                }
            });
        }

        const exportSimPdfBtn = card.querySelector('.paper-export-simpdf-btn');
        if (exportSimPdfBtn) {
            exportSimPdfBtn.addEventListener('click', () => {
                downloadFile(
                    `${apiBase()}/api/v1/plagiarism/report/${itemKey}`,
                    `similarity_report_${itemKey.slice(0,8)}.pdf`
                );
            });
        }

        const exportPdfBtn = card.querySelector('.paper-export-pdf-btn');
        if (exportPdfBtn) {
            exportPdfBtn.addEventListener('click', () => {
                downloadFile(
                    `${apiBase()}/api/v1/research/export/${itemKey}?format=pdf`,
                    `paper.pdf`
                );
            });
        }

        const exportDocxBtn = card.querySelector('.paper-export-docx-btn');
        if (exportDocxBtn) {
            exportDocxBtn.addEventListener('click', () => {
                downloadFile(
                    `${apiBase()}/api/v1/research/export/${itemKey}?format=docx`,
                    `paper.docx`
                );
            });
        }

        const deleteBtn = card.querySelector('.paper-card-delete-btn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', async () => {
                if (!confirm(`Are you sure you want to delete "${item.title || 'this item'}"?`)) return;
                try {
                    const res = await fetch(`${apiBase()}/api/v1/research/papers/${itemKey}`, {
                        method: 'DELETE',
                        headers: authHeaders(),
                    });
                    if (res.ok) {
                        showToast('Item deleted successfully.', 'info');
                        libraryItems = libraryItems.filter(i => (i.job_id || i.paper_id || i.id) !== itemKey);
                        updateLibraryBadgeCounts();
                        renderFilteredLibrary();
                    } else {
                        showToast('Failed to delete item.', 'error');
                    }
                } catch (e) {
                    showToast('Delete error: ' + e.message, 'error');
                }
            });
        }

        return card;
    }

    function initMyPapers() {
        const newPaperBtn = document.getElementById('btn-new-paper');
        if (newPaperBtn) {
            newPaperBtn.addEventListener('click', () => showViewGlobal('generate-paper-view'));
        }

        // Wire Filter Tabs
        const filterContainer = document.getElementById('mypapers-filter-tabs');
        if (filterContainer) {
            filterContainer.querySelectorAll('.filter-tab').forEach(tab => {
                tab.addEventListener('click', (e) => {
                    e.preventDefault();
                    filterContainer.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');
                    currentLibraryFilter = tab.dataset.filter || 'all';
                    renderFilteredLibrary();
                });
            });
        }
    }

    // ---------------------------------------------------------------------------
    // Progress cancel
    // ---------------------------------------------------------------------------
    function initProgressCancel() {
        const cancelBtn = document.getElementById('btn-progress-cancel');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                stopPolling();
                showViewGlobal('dashboard-home-view');
                showToast('Cancelled.', 'info');
            });
        }
    }

    // ---------------------------------------------------------------------------
    // Core Workflow Launchers (Callable from anywhere)
    // ---------------------------------------------------------------------------
    async function startGenerateFromTopic(topic, domain = null, length = 'medium', numRefs = 10, ieeeFormat = true) {
        if (!topic || topic.trim().length < 3) {
            showToast('Please enter a valid research topic (at least 3 characters).', 'error');
            return;
        }

        try {
            showProgressView(`Generating: "${topic.trim()}"`, 'Analyzing research topic and finding academic sources...');

            const res = await fetch(`${apiBase()}/api/v1/research/generate`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({
                    topic: topic.trim(),
                    domain: domain,
                    length: length,
                    num_references: numRefs,
                    ieee_format: ieeeFormat,
                }),
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(formatApiErrorMessage(errData, res.status));
            }

            const data = await res.json();
            state.currentJobId = data.job_id;
            state.pollingJobType = 'generate';

            startPolling(data.job_id, 'research');

        } catch (e) {
            showToast(`Failed to start generation: ${e.message}`, 'error');
            showViewGlobal('dashboard-home-view');
        }
    }

    async function startRestructureFromFile(file, preserveCitations = true) {
        if (!file) {
            showToast('Please select a file to restructure.', 'error');
            return;
        }

        try {
            showProgressView(`Restructuring: "${file.name}"`, 'Extracting sections and mapping to IEEE structure...');

            const formData = new FormData();
            formData.append('file', file);
            formData.append('preserve_citations', preserveCitations ? 'true' : 'false');

            const res = await fetch(`${apiBase()}/api/v1/research/restructure`, {
                method: 'POST',
                headers: authHeadersFormData(),
                body: formData,
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Server error: ${res.status}`);
            }

            const data = await res.json();
            state.currentJobId = data.job_id;
            state.pollingJobType = 'restructure';

            startPolling(data.job_id, 'research');

        } catch (e) {
            showToast(`Restructuring failed to start: ${e.message}`, 'error');
            showViewGlobal('dashboard-home-view');
        }
    }

    // ---------------------------------------------------------------------------
    // Dashboard Home: Search Bar & Plus Button Handler
    // ---------------------------------------------------------------------------
    function initHomePromptBar() {
        const promptInput = document.getElementById('blank-prompt-input');
        const generateBtn = document.getElementById('btn-blank-generate');
        const plusBtn = document.getElementById('btn-blank-new');
        const fileInput = document.getElementById('home-restructure-file-input');

        function handleGenerateSubmit() {
            const topic = promptInput ? promptInput.value.trim() : '';
            if (!topic) {
                showToast('Please enter a research topic to generate a paper.', 'error');
                if (promptInput) promptInput.focus();
                return;
            }
            startGenerateFromTopic(topic);
        }

        if (promptInput) {
            promptInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleGenerateSubmit();
                }
            });
        }

        if (generateBtn) {
            generateBtn.addEventListener('click', (e) => {
                e.preventDefault();
                handleGenerateSubmit();
            });
        }

        if (plusBtn && fileInput) {
            plusBtn.addEventListener('click', (e) => {
                e.preventDefault();
                fileInput.click();
            });

            fileInput.addEventListener('change', () => {
                if (fileInput.files && fileInput.files[0]) {
                    const file = fileInput.files[0];
                    startRestructureFromFile(file);
                    fileInput.value = '';
                }
            });
        }

        // Suggestion pills
        document.querySelectorAll('.suggestion-tag-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const topic = btn.getAttribute('data-topic') || btn.textContent.trim();
                if (promptInput) promptInput.value = topic;
                startGenerateFromTopic(topic);
            });
        });
    }


    // ---------------------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------------------
    function escHtml(text) {
        if (!text) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function formatContent(text) {
        if (!text) return '';
        let escaped = escHtml(text);
        // Convert inline citations [N] to styled citation markers
        escaped = escaped.replace(/\[(\d+)\]/g, '<span class="paper-cit-marker"><a href="#ref-$1" title="Reference [$1]">[$1]</a></span>');
        
        // Split paragraphs
        return escaped.split(/\n\n+/).map(p => {
            const trimmed = p.trim();
            if (!trimmed) return '';
            
            // Check for explicit equation lines: e.g. a + b = \gamma (1) or $$ ... (1) $$
            if (trimmed.includes('(1)') || trimmed.includes('(2)') || trimmed.startsWith('$$') || trimmed.includes('\\min_')) {
                const cleanEq = trimmed.replace(/\$\$/g, '').trim();
                return `<div class="paper-equation"><span class="eq-body">${cleanEq}</span></div>`;
            }
            if (trimmed.startsWith('TABLE ') || trimmed.startsWith('Table ')) {
                return `<div class="paper-table-box"><div class="paper-table-header">${trimmed}</div><div class="paper-table-placeholder">[Comparative Metric Evaluation Matrix — Validated across Benchmarks]</div></div>`;
            }
            return `<p class="paper-paragraph">${trimmed.replace(/\n/g, ' ')}</p>`;
        }).join('');
    }

    function buildRefString(cit) {
        if (!cit || !cit.source) return '';
        const src = cit.source;
        const authors = (src.authors || []);
        let authorStr = 'Author(s) unknown';
        if (authors.length === 1) authorStr = authors[0];
        else if (authors.length > 1) authorStr = authors[0] + ' et al.';

        const year = src.year || 'n.d.';
        const title = src.title || '';
        const venue = src.source || '';
        const url = src.url ? ` [Online]. Available: ${src.url}` : '';

        return `[${cit.number}] ${authorStr}, "${title}," ${venue}, ${year}.${url}`;
    }

    // ---------------------------------------------------------------------------
    // Bootstrap on DOMContentLoaded
    // ---------------------------------------------------------------------------
    function init() {
        initNavigation();
        initGeneratePaper();
        initRestructure();
        initSimilarityCheck();
        initExport();
        initPaperEditing();
        initPaperBack();
        initMyPapers();
        initProgressCancel();
        initHomePromptBar();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose to window for global access
    window.loadMyPapers = loadMyPapers;
    window.startGenerateFromTopic = startGenerateFromTopic;
    window.startRestructureFromFile = startRestructureFromFile;
    window.lemmaResearch = { state, loadAndShowPaper, loadMyPapers, startGenerateFromTopic, startRestructureFromFile };

})();

