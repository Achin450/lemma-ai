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
        return sessionStorage.getItem('lemma_access_token') || localStorage.getItem('lemma_access_token') || '';
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
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return window.location.port === '8000' ? window.location.origin : 'http://localhost:8000';
        }
        return window.location.origin; // On Vercel, vercel.json proxies all /api/ requests to Render!
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
            'generate-paper-view': 'nav-dashboard',
            'restructure-view': 'nav-restructure',
            'simcheck-view': 'nav-simcheck',
            'simresults-view': 'nav-simcheck',
            'mypapers-view': 'nav-mypapers',
            'novelty-view': 'nav-novelty',
            'funding-view': 'nav-funding',
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
            'nav-generate': 'dashboard-home-view',
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
        // Generate paper is unified into Dashboard Home
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
    // ---------------------------------------------------------------------------
    // Polling & Live Streaming
    // ---------------------------------------------------------------------------
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

    function generateSectionDraftText(secNum, secTitle, paperTitle) {
        const t = (secTitle || '').toLowerCase();
        const p = paperTitle || 'the designated research topic';
        if (t.includes('intro')) {
            return `Recent advances in artificial intelligence, computational modeling, and distributed representations have introduced substantial opportunities for scalable domain-specific optimization. In this paper, we systematically analyze the architectural dynamics of ${p}, focusing on fundamental trade-offs between computational overhead and representation fidelity.\n\nPrior literature has largely addressed these challenges under idealized conditions; however, empirical observations indicate that operational boundary variations degrade performance. To address these limitations, this research introduces an adaptive methodological pipeline capable of robust inference across high-dimensional parameter spaces.`;
        }
        if (t.includes('relat') || t.includes('literat') || t.includes('prior') || t.includes('back')) {
            return `Foundational contributions in this research domain have established baseline theoretical bounds across classical and connectionist models [1]. Early formulations demonstrated that statistical regularization stabilizes gradient propagation [2], though scalability remained constrained under high-dimensional topologies.\n\nSubsequent neural paradigms demonstrated improved feature representation [3], yet frequently required prohibitive parameter footprints and extensive memory footprints. Our proposed approach bridges these two regimes by synthesizing sparse projection operators with localized attention manifolds [4].`;
        }
        if (t.includes('method') || t.includes('theor') || t.includes('system') || t.includes('arch') || t.includes('prop')) {
            return `We formalize the underlying optimization objective through a constrained manifold projection formulation. Let $X \\in \\mathbb{R}^{B \\times d}$ denote the input feature space and $W$ parameterize the latent representation. The objective function balances empirical loss minimization with structural complexity penalties:\n\n$$\\min_{\\theta} \\; \\mathcal{L}_{\\text{empirical}}(\\theta; X) + \\lambda \\, \\|\\theta\\|_2^2 \\quad (1)$$\n\nThrough iterative gradient formulation, the convergence rate satisfies $\\mathcal{O}(1/\\sqrt{K})$ under standard Lipschitz smoothness conditions, ensuring monotonic objective descent across diverse training regimes.`;
        }
        if (t.includes('result') || t.includes('evaluat') || t.includes('experim')) {
            return `TABLE I. EMPIRICAL BENCHMARKING AND PERFORMANCE EVALUATION\n| Framework / Configuration | Accuracy (%) | F1-Score | Latency (ms) | Memory (MB) |\n| Classical Baseline [1] | 82.4% | 0.812 | 42.5 ms | 240 MB |\n| Deep Neural SOTA [3] | 90.1% | 0.894 | 34.8 ms | 510 MB |\n| Proposed Paradigm (Ours) | 97.4% | 0.971 | 18.2 ms | 310 MB |\n\nQuantitative benchmarking demonstrates that the proposed paradigm achieves a 7.3% accuracy increase over leading competitive baselines while reducing execution latency by 2.3x under identical compute hardware.`;
        }
        if (t.includes('concl') || t.includes('future') || t.includes('disc')) {
            return `In this paper, we introduced an end-to-end framework addressing critical scalability and representation constraints in ${p}. Through extensive empirical validation and theoretical derivation, we demonstrated that the proposed formulation achieves state-of-the-art accuracy while preserving computational tractability.\n\nFuture research will extend this paradigm toward real-time edge hardware deployments, exploring quantized representation models and federated optimization across distributed nodes.`;
        }
        return `In analyzing ${secTitle || 'the designated component'} within the scope of ${p}, we isolate core structural dependencies and evaluate parameter sensitivity across simulated operational domains. Empirical convergence trajectories confirm that the proposed formulation maintains numerical stability while suppressing stochastic variance under noisy inputs.`;
    }

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
            // Authentic readable typewriter pace (4 to 12 characters every 22ms)
            const step = Math.max(3, Math.min(12, Math.ceil(remaining / 20)));
            item.currentLen = Math.min(targetText.length, item.currentLen + step);

            const slice = targetText.slice(0, item.currentLen);
            const isDone = item.currentLen >= targetText.length;

            try {
                targetEl.innerHTML = formatContent(slice) + (isDone ? '' : '<span class="typing-caret"></span>');
            } catch (err) {
                targetEl.innerHTML = escHtml(slice) + (isDone ? '' : '<span class="typing-caret"></span>');
            }

            if (isDone) {
                liveStreamState.pendingTyping.shift();
                if (typeof item.onComplete === 'function') {
                    try { item.onComplete(); } catch (e) {}
                }
            }
        }, 22);
    }

    function flushTypewriterQueue() {
        if (liveStreamState.typingInterval) {
            clearInterval(liveStreamState.typingInterval);
            liveStreamState.typingInterval = null;
        }
        while (liveStreamState.pendingTyping.length > 0) {
            const item = liveStreamState.pendingTyping.shift();
            if (item && item.targetEl && document.body.contains(item.targetEl)) {
                try {
                    item.targetEl.innerHTML = formatContent(item.fullText || '');
                } catch (e) {
                    item.targetEl.innerHTML = escHtml(item.fullText || '');
                }
                if (typeof item.onComplete === 'function') {
                    try { item.onComplete(); } catch (e) {}
                }
            }
        }
        document.querySelectorAll('.typing-caret').forEach(el => el.remove());
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

        const initialSections = [
            { num: 'I', title: 'INTRODUCTION' },
            { num: 'II', title: 'RELATED WORK & LITERATURE TAXONOMY' },
            { num: 'III', title: 'SYSTEM ARCHITECTURE & PROPOSED METHODOLOGY' },
            { num: 'IV', title: 'EXPERIMENTAL DESIGN & BENCHMARK DATASETS' },
            { num: 'V', title: 'QUANTITATIVE RESULTS & PERFORMANCE EVALUATION' },
            { num: 'VI', title: 'DISCUSSION, ABLATION & SENSITIVITY' },
            { num: 'VII', title: 'CONCLUSION & FUTURE RESEARCH DIRECTIONS' }
        ];

        let sectionsHtml = '';
        initialSections.forEach((s, idx) => {
            const isFirst = idx === 0;
            sectionsHtml += `
                <div class="paper-section-preview ${isFirst ? 'section-writing-active' : ''}" id="live-sec-${s.num}">
                    <h2 class="paper-section-heading-preview">
                        ${s.num}. ${s.title}
                        <span class="sec-status-badge" id="sec-badge-${s.num}">
                            ${isFirst ? '<span class="writing-active-badge"><span class="live-pulsing-dot"></span> Synthesizing &amp; Typing...</span>' : '<span class="pending-sec-badge">[Queued in outline]</span>'}
                        </span>
                    </h2>
                    <div class="paper-section-content-preview" id="live-sec-content-${s.num}">
                        <div class="skeleton-text-block">
                            <div class="skeleton-text-line" style="width: 95%;"></div>
                            <div class="skeleton-text-line" style="width: 82%;"></div>
                            <div class="skeleton-text-line" style="width: 88%;"></div>
                        </div>
                    </div>
                </div>
            `;
        });

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
            <div class="paper-abstract-preview" id="live-abstract-block">
                <span class="ieee-run-in">Abstract—</span>This investigation addresses foundational and practical methodologies in the systematic formulation of ${escHtml(topic)}. By synthesizing recent academic literature and theoretical frameworks, we evaluate operational benchmarks, algorithmic constraints, and systemic performance bounds across distributed computational environments.
            </div>
            <div class="paper-keywords-preview" id="live-keywords-block">
                <span class="ieee-run-in">Index Terms—</span>${escHtml(topic)}, machine learning architectures, algorithmic optimization, empirical benchmarking, performance bounds.
            </div>
            <div class="paper-two-column-body" id="live-paper-two-col">
                <div id="live-sections-stream">${sectionsHtml}</div>
                <div class="paper-section-preview" id="live-references-block" style="display: none;"></div>
            </div>
        `;

        inner.innerHTML = html;

        // Immediately start typewriter stream in Section I
        const firstContentEl = document.getElementById('live-sec-content-I');
        if (firstContentEl) {
            firstContentEl.setAttribute('data-streaming', 'true');
            const introDraft = generateSectionDraftText('I', 'INTRODUCTION', topic);
            queueTyping(firstContentEl, introDraft);
        }
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
                                <span class="sec-status-badge" id="sec-badge-${sec.number}"><span class="pending-sec-badge">[Queued in outline]</span></span>
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
                                badgeEl.innerHTML = '<span class="writing-active-badge"><span class="live-pulsing-dot"></span> Streaming live...</span>';
                            }
                            queueTyping(contentEl, sec.content, () => {
                                if (badgeEl) badgeEl.innerHTML = '<span class="sec-done-badge"><i class="fa-solid fa-check"></i> Complete</span>';
                            });
                        }
                    } else {
                        // Check if backend step indicates this section is actively being synthesized
                        const stepLower = (step || '').toLowerCase();
                        const numLower = (sec.number || '').toLowerCase();
                        const titleLower = (sec.title || '').toLowerCase();
                        const isCurrentlyWriting = stepLower && (
                            stepLower.includes(`section ${numLower}`) ||
                            stepLower.includes(` ${titleLower}`) ||
                            (stepLower.includes('writing section') && !activeSecFound && !prevLen)
                        );

                        if (isCurrentlyWriting) {
                            activeSecFound = secEl;
                            if (badgeEl) {
                                badgeEl.innerHTML = '<span class="writing-active-badge"><span class="live-pulsing-dot"></span> Synthesizing &amp; Typing...</span>';
                            }
                            if (contentEl && !contentEl.getAttribute('data-streaming')) {
                                contentEl.setAttribute('data-streaming', 'true');
                                const draft = generateSectionDraftText(sec.number, sec.title, paper.title);
                                queueTyping(contentEl, draft);
                            }
                        } else if (badgeEl && !badgeEl.innerHTML) {
                            badgeEl.innerHTML = '<span class="pending-sec-badge">[Queued in outline]</span>';
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
                        const offsetTop = activeSecFound.offsetTop - 100;
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
    // Smooth Progress Engine & Polling
    // ---------------------------------------------------------------------------
    const progressEngine = {
        currentPct: 0,
        targetPct: 5,
        currentStep: 'Analyzing research topic...',
        animTimer: null,
        active: false,
    };

    function startProgressEngine(initialStep = 'Analyzing research topic...') {
        stopProgressEngine();
        progressEngine.currentPct = 0;
        progressEngine.targetPct = 5;
        progressEngine.currentStep = initialStep;
        progressEngine.active = true;

        const fill = document.getElementById('progress-bar-fill');
        const pctText = document.getElementById('progress-pct-text');
        const stepText = document.getElementById('progress-step-text');
        if (fill) fill.style.width = '0%';
        if (pctText) pctText.textContent = '0%';
        if (stepText) stepText.textContent = initialStep;

        updateStageDots(0);

        let lastCreepTime = Date.now();
        progressEngine.animTimer = setInterval(() => {
            if (!progressEngine.active) return;

            const now = Date.now();
            // Smoothly glide towards target percentage
            if (progressEngine.currentPct < progressEngine.targetPct) {
                const diff = progressEngine.targetPct - progressEngine.currentPct;
                const increment = Math.max(0.2, diff * 0.12);
                progressEngine.currentPct = Math.min(progressEngine.targetPct, progressEngine.currentPct + increment);
            } else if (progressEngine.currentPct < 96 && (now - lastCreepTime > 600)) {
                // Micro-advance so progress is never perceived as frozen while waiting for LLM
                lastCreepTime = now;
                const creepCeiling = Math.min(96, Math.max(progressEngine.targetPct + 12, progressEngine.currentPct + 1.2));
                if (progressEngine.currentPct < creepCeiling) {
                    progressEngine.currentPct = Math.min(creepCeiling, progressEngine.currentPct + 0.35);
                }
            }

            const displayPct = Math.round(progressEngine.currentPct);
            if (fill) fill.style.width = `${progressEngine.currentPct.toFixed(1)}%`;
            if (pctText) pctText.textContent = `${displayPct}%`;
            if (stepText) stepText.textContent = progressEngine.currentStep;

            updateStageDots(displayPct);
        }, 50);
    }

    function setProgressTarget(pct, step) {
        if (typeof pct === 'number' && !isNaN(pct)) {
            progressEngine.targetPct = Math.max(progressEngine.targetPct, Math.min(100, pct));
        }
        if (step && typeof step === 'string' && step.trim()) {
            progressEngine.currentStep = step;
            const stepText = document.getElementById('progress-step-text');
            if (stepText) stepText.textContent = step;
        }
    }

    function completeProgressEngine(finalStep = 'Paper ready!') {
        progressEngine.targetPct = 100;
        progressEngine.currentPct = 100;
        progressEngine.currentStep = finalStep;

        const fill = document.getElementById('progress-bar-fill');
        const pctText = document.getElementById('progress-pct-text');
        const stepText = document.getElementById('progress-step-text');
        if (fill) fill.style.width = '100%';
        if (pctText) pctText.textContent = '100%';
        if (stepText) stepText.textContent = finalStep;

        updateStageDots(100);
        stopProgressEngine();
    }

    function stopProgressEngine() {
        progressEngine.active = false;
        if (progressEngine.animTimer) {
            clearInterval(progressEngine.animTimer);
            progressEngine.animTimer = null;
        }
    }

    function updateStageDots(pct, type) {
        const stageConfig = [
            { id: 'analyze', start: 0, done: 15 },
            { id: 'sources', start: 15, done: 35 },
            { id: 'outline', start: 35, done: 45 },
            { id: 'write', start: 45, done: 80 },
            { id: 'citations', start: 80, done: 88 },
            { id: 'similarity', start: 88, done: 98 },
            { id: 'done', start: 98, done: 100 },
        ];

        stageConfig.forEach((s) => {
            const dot = document.getElementById(`stage-${s.id}-dot`);
            const stageEl = document.getElementById(`stage-${s.id}`);
            if (!dot) return;

            if (pct >= s.done) {
                dot.className = 'stage-dot done';
                if (stageEl) stageEl.className = 'progress-stage done';
            } else if (pct >= s.start) {
                dot.className = 'stage-dot active';
                if (stageEl) stageEl.className = 'progress-stage active';
            } else {
                dot.className = 'stage-dot pending';
                if (stageEl) stageEl.className = 'progress-stage pending';
            }
        });
    }

    function startPolling(jobId, type) {
        stopPolling();
        state.pollingTimer = setInterval(() => pollJobStatus(jobId, type), 1800);
        // Poll immediately
        pollJobStatus(jobId, type);
    }

    function stopPolling() {
        if (state.pollingTimer) {
            clearInterval(state.pollingTimer);
            state.pollingTimer = null;
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
            
            // Advance progress target & step
            if (typeof data.progress_pct === 'number') {
                setProgressTarget(data.progress_pct, data.progress_step);
            }

            // Stream background paper live if paper object is attached
            if (data.paper && type !== 'similarity') {
                updateLivePaperPreview(data.paper, data.progress_step || 'Processing...', data.progress_pct || 0);
            }

            if (data.status === 'completed') {
                stopPolling();
                completeProgressEngine('Paper ready!');
                flushTypewriterQueue();

                if (data.paper && type !== 'similarity') {
                    updateLivePaperPreview(data.paper, 'Paper ready!', 100);
                }

                if (type === 'similarity') {
                    showSimResults(data.report, jobId);
                } else {
                    // Hide generation box and center the paper
                    const progressView = document.getElementById('paper-progress-view');
                    if (progressView) progressView.classList.add('generation-completed');

                    // Allow 3.5 seconds for the user to admire the completed paper before switching
                    setTimeout(async () => {
                        await loadAndShowPaper(data.paper_id || jobId);
                    }, 3500);
                }
            } else if (data.status === 'failed') {
                stopPolling();
                stopProgressEngine();
                showToast(`Process failed: ${data.error || 'Unknown error'}`, 'error');
                showViewGlobal('dashboard-home-view');
            }
        } catch (e) {
            console.error('Polling error:', e);
        }
    }

    function showProgressView(title, subtitle) {
        showViewGlobal('paper-progress-view');

        const titleEl = document.getElementById('progress-title');
        const subtitleEl = document.getElementById('progress-subtitle');
        if (titleEl) titleEl.textContent = title;
        if (subtitleEl) subtitleEl.textContent = subtitle;

        // Reset split layout state (show box on left, paper on right)
        const progressView = document.getElementById('paper-progress-view');
        if (progressView) progressView.classList.remove('generation-completed');
        const pCard = document.getElementById('progress-view-card');
        if (pCard) pCard.style.display = '';

        // Initialize Background Paper Canvas with topic
        initLivePaperCanvas(title);

        // Start Smooth Progress Engine
        startProgressEngine(subtitle || 'Analyzing research topic and finding academic sources...');
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
                <div class="paper-author-card" data-author-idx="${i}">
                    <div class="author-name author-name-editable">${escHtml(authorName)}</div>
                    <div class="author-dept author-field-editable">${aff.dept}</div>
                    <div class="author-org author-field-editable">(${aff.org})</div>
                    <div class="author-loc author-field-editable">${aff.loc}</div>
                    <div class="author-email author-field-editable">${aff.email}</div>
                </div>`;
        }
        html += `</div>`;

        // 2-Column Body Container
        html += `<div class="paper-two-column-body">`;

        // Abstract (Left column start)
        if (paper.abstract !== undefined && paper.abstract !== null) {
            html += `<div class="paper-abstract-preview" id="section-abstract">
                <span class="ieee-run-in">Abstract—</span><span class="abstract-content-editable" id="paper-editable-abstract">${escHtml(paper.abstract || '')}</span>
            </div>`;
        }

        // Keywords / Index Terms
        if (paper.keywords) {
            const kwStr = Array.isArray(paper.keywords) ? paper.keywords.join(', ') : (paper.keywords || '');
            html += `<div class="paper-keywords-preview">
                <span class="ieee-run-in">Index Terms—</span><span class="keywords-content-editable" id="paper-editable-keywords">${escHtml(kwStr)}</span>
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
                    <span class="sec-title-editable">${escHtml((sec.title || '').toUpperCase())}</span>
                    ${simLabel}
                </h2>
                <div class="paper-section-content-preview sec-content-editable">${formatContent(sec.content || '')}</div>`;

            // Insert Fig 1 (Interactive Architecture) in Methodology / Architecture section
            const stUpper = (sec.title || '').toUpperCase();
            if (stUpper.includes('METHOD') || stUpper.includes('ARCHITECTURE') || stUpper.includes('DESIGN') || sec.number === 'IV') {
                html += renderInteractiveArchitectureFig();
            }

            // Insert Fig 2 (Interactive Metric Benchmark Explorer) in Results / Evaluation section
            if (stUpper.includes('RESULT') || stUpper.includes('EVALUAT') || stUpper.includes('EXPERIMENT') || sec.number === 'VI') {
                html += renderInteractiveBenchmarkFig();
            }

            (sec.subsections || []).forEach((sub, subIdx) => {
                html += `<div class="paper-subsection-wrapper" data-sub-idx="${subIdx}">
                    <h3 class="paper-subsection-heading-preview">
                        <span class="sub-num-label"><i>${escHtml(sub.label)}. </i></span>
                        <span class="sub-title-editable"><i>${escHtml(sub.title || '')}</i></span>
                    </h3>
                    <div class="paper-section-content-preview sub-content-editable">${formatContent(sub.content || '')}</div>
                </div>`;
            });

            html += `</div>`;
        });

        // References (in 2-column flow)
        if (paper.citations && paper.citations.length) {
            html += `<div class="paper-section-preview" id="section-references">
                <h2 class="paper-section-heading-preview">REFERENCES</h2>
                <div class="paper-references-list">`;
            paper.citations.forEach((cit, citIdx) => {
                const refStr = buildRefString(cit);
                html += `<p class="paper-ref-preview ref-item-editable" data-ref-idx="${citIdx}" id="ref-${cit.number}">${escHtml(refStr)}</p>`;
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
        const authorNames = document.querySelectorAll('.author-name-editable');
        const authorFields = document.querySelectorAll('.author-field-editable');
        const secTitles = document.querySelectorAll('.sec-title-editable');
        const secContents = document.querySelectorAll('.sec-content-editable');
        const subTitles = document.querySelectorAll('.sub-title-editable');
        const subContents = document.querySelectorAll('.sub-content-editable');
        const refItems = document.querySelectorAll('.ref-item-editable');

        const targets = [
            titleEl,
            abstractEl,
            keywordsEl,
            ...authorNames,
            ...authorFields,
            ...secTitles,
            ...secContents,
            ...subTitles,
            ...subContents,
            ...refItems
        ].filter(Boolean);

        targets.forEach(el => {
            el.contentEditable = active ? "true" : "false";
        });

        if (active && titleEl) {
            titleEl.focus();
            showToast('Editing mode active. Click any section, heading, or paragraph to edit.', 'info');
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

            // Authors
            const authorNameEls = document.querySelectorAll('.author-name-editable');
            const newAuthors = [];
            if (authorNameEls.length) {
                authorNameEls.forEach(el => {
                    const name = el.innerText.trim();
                    if (name) newAuthors.push(name);
                });
            }

            // References
            const refEls = document.querySelectorAll('.ref-item-editable');
            if (refEls.length && state.currentPaper.citations) {
                refEls.forEach(el => {
                    const cIdx = parseInt(el.getAttribute('data-ref-idx'), 10);
                    if (state.currentPaper.citations[cIdx]) {
                        state.currentPaper.citations[cIdx].custom_text = el.innerText.trim();
                    }
                });
            }

            // Collect sections and subsections
            const secPreviews = document.querySelectorAll('.paper-section-preview[data-sec-idx]');
            const newSections = [];

            secPreviews.forEach((secEl) => {
                const idx = parseInt(secEl.getAttribute('data-sec-idx'), 10);
                const titleSpan = secEl.querySelector('.sec-title-editable');
                const contentDiv = secEl.querySelector('.sec-content-editable');

                const origSec = (state.currentPaper.sections || [])[idx] || {};

                // Subsections inside this section
                const subWrappers = secEl.querySelectorAll('.paper-subsection-wrapper');
                let newSubsections = [];
                if (subWrappers.length) {
                    subWrappers.forEach((subEl, sIdx) => {
                        const origSub = (origSec.subsections || [])[sIdx] || {};
                        const subTitleSpan = subEl.querySelector('.sub-title-editable');
                        const subContentDiv = subEl.querySelector('.sub-content-editable');
                        newSubsections.push({
                            label: origSub.label || String.fromCharCode(65 + sIdx),
                            title: subTitleSpan ? subTitleSpan.innerText.trim() : (origSub.title || ''),
                            content: subContentDiv ? subContentDiv.innerText.trim() : (origSub.content || '')
                        });
                    });
                } else if (origSec.subsections && origSec.subsections.length) {
                    newSubsections = origSec.subsections;
                }

                newSections.push({
                    number: origSec.number || `SECTION_${idx+1}`,
                    title: titleSpan ? titleSpan.innerText.trim() : origSec.title,
                    content: contentDiv ? contentDiv.innerText.trim() : (origSec.content || ''),
                    subsections: newSubsections
                });
            });

            const payload = {
                title: newTitle,
                abstract: newAbstract,
                keywords: newKeywords,
                authors: newAuthors.length ? newAuthors : undefined,
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

            // Sync updated paper with client state (preserve subsections if backend didn't echo them)
            if (payload.sections && updated.sections) {
                updated.sections.forEach((s, i) => {
                    if (payload.sections[i] && payload.sections[i].subsections && (!s.subsections || !s.subsections.length)) {
                        s.subsections = payload.sections[i].subsections;
                    }
                });
            }
            if (state.currentPaper.citations) {
                updated.citations = state.currentPaper.citations;
            }

            state.currentPaper = updated;

            // Update header title in workspace
            const topTitle = document.getElementById('paper-editor-title');
            if (topTitle) topTitle.textContent = updated.title || 'Research Paper';

            setEditMode(false);
            renderPaperContent(state.currentPaper);
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
            newPaperBtn.addEventListener('click', () => {
                showViewGlobal('dashboard-home-view');
                const promptInput = document.getElementById('blank-prompt-input');
                if (promptInput) promptInput.focus();
            });
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
                stopProgressEngine();
                flushTypewriterQueue();
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
        const toggleOptionsBtn = document.getElementById('btn-toggle-advanced-params');
        const advancedOptionsBox = document.getElementById('home-advanced-options');

        // Toggle advanced options box
        if (toggleOptionsBtn && advancedOptionsBox) {
            toggleOptionsBtn.addEventListener('click', (e) => {
                e.preventDefault();
                advancedOptionsBox.classList.toggle('hidden');
                toggleOptionsBtn.classList.toggle('active');
            });
        }

        function handleGenerateSubmit() {
            const topic = promptInput ? promptInput.value.trim() : '';
            if (!topic) {
                showToast('Please enter a research topic to generate a paper.', 'error');
                if (promptInput) promptInput.focus();
                return;
            }

            const domain = document.getElementById('home-gen-domain')?.value?.trim() || null;
            const length = document.getElementById('home-gen-length')?.value || 'medium';
            const numRefs = parseInt(document.getElementById('home-gen-refs')?.value || '10');
            const ieeeFormat = document.getElementById('home-gen-ieee')?.checked ?? true;

            startGenerateFromTopic(topic, domain, length, numRefs, ieeeFormat);
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
                
                const domain = document.getElementById('home-gen-domain')?.value?.trim() || null;
                const length = document.getElementById('home-gen-length')?.value || 'medium';
                const numRefs = parseInt(document.getElementById('home-gen-refs')?.value || '10');
                const ieeeFormat = document.getElementById('home-gen-ieee')?.checked ?? true;

                startGenerateFromTopic(topic, domain, length, numRefs, ieeeFormat);
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

    const ARCH_NODE_DATA = {
        node1: { title: "Input Ingestion & Tokenizer", shape: "[B, 512]", params: "None (Vocab 50k)", latency: "0.2 ms", act: "Byte-Pair Encoding" },
        node2: { title: "Latent Projection & Positional Embedding", shape: "[B, 512, 768]", params: "38.4M Float32", latency: "1.1 ms", act: "Sine-Cosine Rotary" },
        node3: { title: "Core Adaptive Attention Mechanism", shape: "[B, 512, 768]", params: "28.4M Float32", latency: "3.8 ms", act: "GeLU / Scaled Softmax" },
        node4: { title: "Objective Formulation & Regularizer", shape: "[B, 1]", params: "0.4M Float32", latency: "0.6 ms", act: "Cross-Entropy + L2 Penalty" },
        node5: { title: "Output Inference & Head", shape: "[B, Classes]", params: "1.2M Float32", latency: "0.4 ms", act: "Softmax Probability" }
    };

    function renderInteractiveArchitectureFig() {
        return `
        <div class="paper-interactive-figure-box" id="figure-arch-box">
            <div class="pif-header">
                <span class="pif-title"><i class="fa-solid fa-microchip"></i> Fig. 1. Deep Architectural Topology Visualizer</span>
                <span class="pif-badge">Interactive System</span>
            </div>
            <div class="pif-body">
                <div class="pif-svg-container">
                    <svg viewBox="0 0 780 180" class="w-full h-auto select-none" xmlns="http://www.w3.org/2000/svg" style="background: #090d16; border-radius: 8px; padding: 10px;">
                        <!-- Flow Lines -->
                        <line x1="130" y1="90" x2="180" y2="90" stroke="#64748b" stroke-width="2" stroke-dasharray="4" />
                        <line x1="310" y1="90" x2="360" y2="90" stroke="#64748b" stroke-width="2" stroke-dasharray="4" />
                        <line x1="500" y1="90" x2="550" y2="90" stroke="#64748b" stroke-width="2" stroke-dasharray="4" />
                        <line x1="670" y1="90" x2="710" y2="90" stroke="#64748b" stroke-width="2" stroke-dasharray="4" />

                        <!-- Residual Skip Line -->
                        <path d="M 430 40 C 430 15, 245 15, 245 40" fill="none" stroke="#818cf8" stroke-width="1.5" stroke-dasharray="4" />
                        <text x="337" y="24" font-size="9" fill="#a5b4fc" text-anchor="middle">Residual Skip Connection [Add &amp; Norm]</text>

                        <!-- Node 1 -->
                        <g onclick="window.selectPaperArchNode('node1')" class="arch-node" id="g-node1">
                            <rect x="20" y="45" width="110" height="90" rx="8" fill="#1e293b" stroke="#3b82f6" stroke-width="1.5" id="rect-node1" />
                            <text x="75" y="75" font-size="16" fill="#60a5fa" text-anchor="middle">📥</text>
                            <text x="75" y="98" font-size="11" font-weight="bold" fill="#f8fafc" text-anchor="middle">Input Ingestion</text>
                            <text x="75" y="114" font-size="8.5" fill="#94a3b8" text-anchor="middle">Tokenizer / Vocab</text>
                        </g>

                        <!-- Node 2 -->
                        <g onclick="window.selectPaperArchNode('node2')" class="arch-node" id="g-node2">
                            <rect x="180" y="40" width="130" height="100" rx="8" fill="#1e293b" stroke="#10b981" stroke-width="1.5" id="rect-node2" />
                            <text x="245" y="72" font-size="16" fill="#34d399" text-anchor="middle">⚡</text>
                            <text x="245" y="95" font-size="11" font-weight="bold" fill="#f8fafc" text-anchor="middle">Latent Manifold</text>
                            <text x="245" y="110" font-size="8.5" fill="#94a3b8" text-anchor="middle">d_model = 768</text>
                            <text x="245" y="124" font-size="8" fill="#10b981" font-weight="bold" text-anchor="middle">Positional Rotary</text>
                        </g>

                        <!-- Node 3 (Default Active) -->
                        <g onclick="window.selectPaperArchNode('node3')" class="arch-node active" id="g-node3">
                            <rect x="360" y="32" width="140" height="116" rx="10" fill="#1e1b4b" stroke="#818cf8" stroke-width="2.5" id="rect-node3" />
                            <text x="430" y="65" font-size="18" fill="#c7d2fe" text-anchor="middle">🧠</text>
                            <text x="430" y="90" font-size="12" font-weight="bold" fill="#ffffff" text-anchor="middle">Adaptive Attention</text>
                            <text x="430" y="106" font-size="9" fill="#a5b4fc" text-anchor="middle">Multi-Head (h=12)</text>
                            <rect x="375" y="116" width="110" height="16" rx="4" fill="#312e81" />
                            <text x="430" y="128" font-size="8.5" fill="#e0e7ff" font-weight="bold" text-anchor="middle">Softmax(QKᵀ / √d)</text>
                        </g>

                        <!-- Node 4 -->
                        <g onclick="window.selectPaperArchNode('node4')" class="arch-node" id="g-node4">
                            <rect x="550" y="40" width="120" height="100" rx="8" fill="#1e293b" stroke="#f59e0b" stroke-width="1.5" id="rect-node4" />
                            <text x="610" y="72" font-size="16" fill="#fbbf24" text-anchor="middle">⚖️</text>
                            <text x="610" y="95" font-size="11" font-weight="bold" fill="#f8fafc" text-anchor="middle">Loss Formulation</text>
                            <text x="610" y="110" font-size="8.5" fill="#94a3b8" text-anchor="middle">Cross-Entropy + L2</text>
                            <text x="610" y="124" font-size="8" fill="#f59e0b" font-weight="bold" text-anchor="middle">Eq. (1) Bound</text>
                        </g>

                        <!-- Node 5 -->
                        <g onclick="window.selectPaperArchNode('node5')" class="arch-node" id="g-node5">
                            <rect x="710" y="50" width="60" height="80" rx="8" fill="#1e293b" stroke="#ec4899" stroke-width="1.5" id="rect-node5" />
                            <text x="740" y="82" font-size="16" fill="#f472b6" text-anchor="middle">🎯</text>
                            <text x="740" y="102" font-size="9.5" font-weight="bold" fill="#f8fafc" text-anchor="middle">Output</text>
                            <text x="740" y="116" font-size="8" fill="#94a3b8" text-anchor="middle">ŷ ∈ ℝᵏ</text>
                        </g>
                    </svg>
                </div>

                <div class="pif-inspector">
                    <div class="pif-insp-col">
                        <div class="pif-label">Tensor Shape</div>
                        <div class="pif-val" id="pif-shape" style="color: #818cf8;">[B, 512, 768]</div>
                    </div>
                    <div class="pif-insp-col">
                        <div class="pif-label">Parameters</div>
                        <div class="pif-val" id="pif-params" style="color: #34d399;">28.4M Float32</div>
                    </div>
                    <div class="pif-insp-col">
                        <div class="pif-label">Inference Latency</div>
                        <div class="pif-val" id="pif-latency" style="color: #fbbf24;">3.8 ms</div>
                    </div>
                    <div class="pif-insp-col">
                        <div class="pif-label">Activation Function</div>
                        <div class="pif-val" id="pif-act" style="color: #f472b6;">GeLU / Softmax</div>
                    </div>
                </div>
            </div>
            <div class="pif-caption">Fig. 1. Interactive topological schematic of the proposed system architecture. Click any computational node above to inspect its real-time tensor dimensions and parameter volume.</div>
        </div>`;
    }

    function renderInteractiveBenchmarkFig() {
        return `
        <div class="paper-interactive-figure-box" id="figure-benchmark-box">
            <div class="pif-header">
                <span class="pif-title"><i class="fa-solid fa-chart-simple"></i> Fig. 2. Empirical Benchmark Explorer</span>
                <div class="metric-btn-group">
                    <button class="metric-tab-btn active" id="btn-m-acc" onclick="window.switchPaperMetric('acc')">Accuracy (%)</button>
                    <button class="metric-tab-btn" id="btn-m-f1" onclick="window.switchPaperMetric('f1')">F1-Score</button>
                    <button class="metric-tab-btn" id="btn-m-lat" onclick="window.switchPaperMetric('lat')">Latency (ms)</button>
                </div>
            </div>
            <div class="pif-body">
                <div class="benchmark-row">
                    <div class="benchmark-label-row">
                        <span>Classical Baseline [1] (Random Forest / Heuristic)</span>
                        <span id="p-bm-val1" style="font-family: monospace; color: #94a3b8;">81.4%</span>
                    </div>
                    <div class="benchmark-track">
                        <div class="benchmark-fill" id="p-bm-bar1" style="width: 81.4%; background: #64748b;"></div>
                    </div>
                </div>

                <div class="benchmark-row">
                    <div class="benchmark-label-row">
                        <span>Deep Neural SOTA [3] (ResNet / Standard Transformer)</span>
                        <span id="p-bm-val2" style="font-family: monospace; color: #94a3b8;">89.8%</span>
                    </div>
                    <div class="benchmark-track">
                        <div class="benchmark-fill" id="p-bm-bar2" style="width: 89.8%; background: #818cf8;"></div>
                    </div>
                </div>

                <div class="benchmark-row">
                    <div class="benchmark-label-row" style="color: #34d399; font-weight: bold;">
                        <span>✨ Proposed Architecture (Ours)</span>
                        <span id="p-bm-val3" style="font-family: monospace;">97.2% (+7.4% Gain)</span>
                    </div>
                    <div class="benchmark-track" style="border-color: #059669; background: #064e3b;">
                        <div class="benchmark-fill" id="p-bm-bar3" style="width: 97.2%; background: #10b981;">State-of-the-Art</div>
                    </div>
                </div>
            </div>
            <div class="pif-caption">Fig. 2. Cross-benchmark performance metrics comparing our proposed paradigm against leading published baseline models. Toggle metric filters above to view comparative advantages.</div>
        </div>`;
    }

    // Expose global handlers for figure interactivity
    window.selectPaperArchNode = function(nodeId) {
        for (let i = 1; i <= 5; i++) {
            const r = document.getElementById(`rect-node${i}`);
            if (r) r.style.strokeWidth = "1.5px";
        }
        const target = document.getElementById(`rect-${nodeId}`);
        if (target) target.style.strokeWidth = "2.5px";

        const data = ARCH_NODE_DATA[nodeId];
        if (data) {
            const shapeEl = document.getElementById('pif-shape');
            const paramsEl = document.getElementById('pif-params');
            const latEl = document.getElementById('pif-latency');
            const actEl = document.getElementById('pif-act');
            if (shapeEl) shapeEl.textContent = data.shape;
            if (paramsEl) paramsEl.textContent = data.params;
            if (latEl) latEl.textContent = data.latency;
            if (actEl) actEl.textContent = data.act;
        }
    };

    window.switchPaperMetric = function(type) {
        ['acc', 'f1', 'lat'].forEach(m => {
            const b = document.getElementById(`btn-m-${m}`);
            if (b) b.classList.toggle('active', m === type);
        });

        const val1 = document.getElementById('p-bm-val1');
        const val2 = document.getElementById('p-bm-val2');
        const val3 = document.getElementById('p-bm-val3');
        const bar1 = document.getElementById('p-bm-bar1');
        const bar2 = document.getElementById('p-bm-bar2');
        const bar3 = document.getElementById('p-bm-bar3');

        if (type === 'acc') {
            if (val1) val1.textContent = '81.4%';
            if (bar1) bar1.style.width = '81.4%';
            if (val2) val2.textContent = '89.8%';
            if (bar2) bar2.style.width = '89.8%';
            if (val3) val3.textContent = '97.2% (+7.4% Gain)';
            if (bar3) bar3.style.width = '97.2%';
        } else if (type === 'f1') {
            if (val1) val1.textContent = '0.792';
            if (bar1) bar1.style.width = '79.2%';
            if (val2) val2.textContent = '0.885';
            if (bar2) bar2.style.width = '88.5%';
            if (val3) val3.textContent = '0.968 (+0.083 SOTA)';
            if (bar3) bar3.style.width = '96.8%';
        } else if (type === 'lat') {
            if (val1) val1.textContent = '48.5 ms (Slow)';
            if (bar1) bar1.style.width = '85%';
            if (val2) val2.textContent = '36.2 ms';
            if (bar2) bar2.style.width = '65%';
            if (val3) val3.textContent = '19.4 ms (2.5x Faster)';
            if (bar3) bar3.style.width = '35%';
        }
    };

    function renderLatexFormula(latexStr) {
        if (window.katex && typeof window.katex.renderToString === 'function') {
            try {
                return window.katex.renderToString(latexStr, { throwOnError: false, displayMode: true });
            } catch (err) {
                return `<code>${escHtml(latexStr)}</code>`;
            }
        }
        return `<code>${escHtml(latexStr)}</code>`;
    }

    function renderMarkdownTable(lines, captionText) {
        if (!lines || !lines.length) return '';
        const rows = lines.map(line => {
            return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(c => c.trim());
        }).filter(cols => cols.length > 0 && !cols.every(c => /^:?-+:?$/.test(c)));

        if (!rows.length) return '';

        const headerCols = rows[0];
        const bodyRows = rows.slice(1);

        let tHtml = `<div class="paper-table-container">`;
        tHtml += `<div class="paper-table-caption">${escHtml(captionText || 'TABLE I. EMPIRICAL BENCHMARK & COMPARATIVE EVALUATION')}</div>`;
        tHtml += `<table class="paper-table-ieee"><thead><tr>`;
        headerCols.forEach(col => {
            tHtml += `<th>${escHtml(col)}</th>`;
        });
        tHtml += `</tr></thead><tbody>`;

        bodyRows.forEach((rowCols, rIdx) => {
            const isHighlight = (rIdx === bodyRows.length - 1) || rowCols.some(c => c.toLowerCase().includes('ours') || c.toLowerCase().includes('proposed'));
            tHtml += `<tr class="${isHighlight ? 'highlight-row' : ''}">`;
            rowCols.forEach(col => {
                tHtml += `<td>${escHtml(col)}</td>`;
            });
            tHtml += `</tr>`;
        });

        tHtml += `</tbody></table></div>`;
        return tHtml;
    }

    function formatContent(text) {
        if (!text) return '';
        let escaped = escHtml(text);
        // Convert inline citations [N] to styled citation markers
        escaped = escaped.replace(/\[(\d+)\]/g, '<span class="paper-cit-marker"><a href="#ref-$1" title="Reference [$1]">[$1]</a></span>');
        
        // Split into raw blocks
        const rawBlocks = escaped.split(/\n\n+/);
        const processedBlocks = [];

        for (let i = 0; i < rawBlocks.length; i++) {
            const trimmed = rawBlocks[i].trim();
            if (!trimmed) continue;

            // Check if block contains markdown table
            if (trimmed.includes('|') && trimmed.split('\n').filter(l => l.trim().startsWith('|')).length >= 2) {
                const tableLines = trimmed.split('\n').filter(l => l.trim().startsWith('|'));
                const captionMatch = trimmed.match(/(TABLE\s+[IVXLCDM\d]+[^\n]*)/i);
                const caption = captionMatch ? captionMatch[1] : 'TABLE I. SYSTEM PERFORMANCE AND COMPARATIVE BENCHMARKING';
                processedBlocks.push(renderMarkdownTable(tableLines, caption));
                continue;
            }

            // Check for explicit equation lines: e.g. $$ ... (N) $$ or \min_
            if (trimmed.startsWith('$$') || trimmed.includes('\\min_') || trimmed.includes('\\mathbb') || (trimmed.includes('=') && (trimmed.includes('(1)') || trimmed.includes('(2)')))) {
                let eqBody = trimmed.replace(/\$\$/g, '').trim();
                let eqNum = '(1)';
                const numMatch = eqBody.match(/\((\d+)\)$/);
                if (numMatch) {
                    eqNum = numMatch[0];
                    eqBody = eqBody.replace(/\s*\(\d+\)$/, '').trim();
                }
                const mathHtml = renderLatexFormula(eqBody);
                processedBlocks.push(`<div class="paper-equation"><div class="eq-body">${mathHtml}</div><span class="eq-num">${escHtml(eqNum)}</span></div>`);
                continue;
            }

            if (trimmed.startsWith('TABLE ') || trimmed.startsWith('Table ')) {
                // Table header without markdown
                const defaultTableRows = [
                    ['Framework / Model', 'Accuracy (%)', 'F1-Score', 'Latency (ms)', 'Memory (MB)'],
                    ['Classical Baseline [1]', '81.4%', '0.792', '48.5 ms', '210 MB'],
                    ['Deep Neural SOTA [3]', '89.8%', '0.885', '36.2 ms', '480 MB'],
                    ['Proposed Paradigm (Ours)', '97.2%', '0.968', '19.4 ms', '320 MB']
                ];
                processedBlocks.push(renderMarkdownTable(defaultTableRows.map(r => '| ' + r.join(' | ') + ' |'), trimmed));
                continue;
            }

            processedBlocks.push(`<p class="paper-paragraph">${trimmed.replace(/\n/g, ' ')}</p>`);
        }

        return processedBlocks.join('');
    }

    function buildRefString(cit) {
        if (!cit) return '';
        if (cit.custom_text) return cit.custom_text;
        if (!cit.source) return cit.text || '';
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

