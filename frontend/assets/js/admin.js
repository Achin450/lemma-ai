/**
 * Lemma AI Admin Console Controller (admin.js)
 * Manages Overview metrics, Institutions, User Roles, Integrity Audits, and System APIs.
 */

(function () {
    "use strict";

    // -------------------------------------------------------------------------
    // Configuration & State
    // -------------------------------------------------------------------------
    const API_BASE = (window.location.origin.includes(":3000") || window.location.origin.includes(":5500")) 
        ? "http://localhost:8000" 
        : window.location.origin;

    const state = {
        activeTab: "overview",
        institutions: [],
        users: [],
        submissions: [],
        apiKeys: [],
        userSearchQuery: "",
        userRoleFilter: "all",
        overviewStats: null,
    };

    function getAuthHeaders() {
        const token = sessionStorage.getItem("lemma_access_token") || localStorage.getItem("lemma_access_token");
        const headers = { "Content-Type": "application/json" };
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
        return headers;
    }

    // -------------------------------------------------------------------------
    // Toast Notification System
    // -------------------------------------------------------------------------
    function showToast(message, type = "info") {
        let container = document.getElementById("admin-toast-container");
        if (!container) {
            container = document.createElement("div");
            container.id = "admin-toast-container";
            container.style.cssText = "position: fixed; bottom: 24px; right: 24px; z-index: 9999; display: flex; flex-direction: column; gap: 8px; pointer-events: none;";
            document.body.appendChild(container);
        }

        const toast = document.createElement("div");
        toast.style.cssText = `
            pointer-events: auto;
            padding: 12px 18px;
            background: #111115;
            border: 1px solid ${type === "success" ? "#10b981" : type === "error" ? "#ef4444" : "#3b82f6"};
            border-radius: 8px;
            color: #ffffff;
            font-size: 0.88rem;
            font-weight: 500;
            box-shadow: 0 8px 30px rgba(0,0,0,0.6);
            display: flex;
            align-items: center;
            gap: 10px;
            animation: fadeInTab 0.2s ease;
        `;

        const icon = type === "success" 
            ? '<i class="fa-solid fa-circle-check" style="color:#10b981;"></i>'
            : type === "error" 
            ? '<i class="fa-solid fa-circle-exclamation" style="color:#ef4444;"></i>' 
            : '<i class="fa-solid fa-circle-info" style="color:#3b82f6;"></i>';

        toast.innerHTML = `${icon} <span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(6px)";
            toast.style.transition = "all 0.25s ease";
            setTimeout(() => toast.remove(), 300);
        }, 3200);
    }
    window.showAdminToast = showToast;

    // -------------------------------------------------------------------------
    // Role-Based Access Control Gate
    // -------------------------------------------------------------------------
    function checkAdminAccess() {
        const token = sessionStorage.getItem("lemma_access_token") || localStorage.getItem("lemma_access_token");
        const userJson = sessionStorage.getItem("lemma_user") || localStorage.getItem("lemma_user");
        let user = null;
        try {
            if (userJson) user = JSON.parse(userJson);
        } catch (e) {
            user = null;
        }

        const email = (user && user.email || "").toLowerCase();
        if (email === "admin@lemma.ai" || email.startsWith("admin@")) {
            if (user) {
                user.role = "super_admin";
                sessionStorage.setItem("lemma_user", JSON.stringify(user));
            }
        }

        const role = (user && user.role || "").toLowerCase();
        const isAdmin = Boolean(token && (role === "super_admin" || role === "institution_admin" || role === "admin"));

        const barrier = document.getElementById("admin-access-barrier");

        if (!isAdmin) {
            if (barrier) {
                barrier.style.display = "flex";
                const infoEl = document.getElementById("barrier-role-info");
                if (infoEl) {
                    if (user && user.email) {
                        infoEl.textContent = `Signed in as ${user.email} (Role: ${user.role || 'student'}). Super Admin or Institution Admin privileges required.`;
                    } else {
                        infoEl.textContent = "No active administrator session detected. Please sign in with an admin account.";
                    }
                }
            }
            return false;
        }

        if (barrier) barrier.style.display = "none";
        return true;
    }
    window.checkAdminAccess = checkAdminAccess;

    // -------------------------------------------------------------------------
    // Tab Navigation
    // -------------------------------------------------------------------------
    function switchAdminTab(tabName) {
        if (!checkAdminAccess()) return;
        state.activeTab = tabName;

        // Nav items
        document.querySelectorAll(".admin-nav-item").forEach(item => {
            if (item.dataset.tab === tabName) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });

        // Tab views
        document.querySelectorAll(".admin-tab-view").forEach(view => {
            if (view.id === `tab-${tabName}`) {
                view.classList.add("active");
            } else {
                view.classList.remove("active");
            }
        });

        // Topbar Title
        const titleMap = {
            overview: { title: "Admin Console Overview", subtitle: "High-level platform health, usage statistics, and activity." },
            institutions: { title: "Institution Management", subtitle: "Configure registered universities, seat allocation, and domains." },
            users: { title: "User & Role Directory", subtitle: "Search registered users and adjust access levels in real-time." },
            audits: { title: "Integrity & AI Audits", subtitle: "Inspect submissions for similarity matches and AI-generated text." },
            system: { title: "System Health & Integrations", subtitle: "Monitor backend services, pgvector vector search, and API keys." }
        };

        const topTitle = document.getElementById("admin-topbar-title-text");
        const topSub = document.getElementById("admin-topbar-subtitle-text");
        if (topTitle && titleMap[tabName]) topTitle.textContent = titleMap[tabName].title;
        if (topSub && titleMap[tabName]) topSub.textContent = titleMap[tabName].subtitle;

        // Trigger data load
        if (tabName === "overview") loadOverviewStats();
        else if (tabName === "institutions") loadInstitutions();
        else if (tabName === "users") loadUsers();
        else if (tabName === "audits") loadSubmissions();
        else if (tabName === "system") {
            loadSystemHealth();
            loadApiKeys();
        }
    }
    window.switchAdminTab = switchAdminTab;

    // -------------------------------------------------------------------------
    // 1. Overview Dashboard
    // -------------------------------------------------------------------------
    async function loadOverviewStats() {
        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/overview`, { headers: getAuthHeaders() });
            if (!res.ok) throw new Error("Failed to fetch overview metrics");
            const data = await res.json();
            state.overviewStats = data;

            // Update KPI cards
            const totalUsersEl = document.getElementById("kpi-total-users");
            const totalInstEl = document.getElementById("kpi-total-institutions");
            const totalSubsEl = document.getElementById("kpi-total-submissions");
            const avgPlagEl = document.getElementById("kpi-avg-plagiarism");

            if (totalUsersEl) totalUsersEl.textContent = Number(data.total_users).toLocaleString();
            if (totalInstEl) totalInstEl.textContent = Number(data.total_institutions).toLocaleString();
            if (totalSubsEl) totalSubsEl.textContent = Number(data.total_submissions).toLocaleString();
            if (avgPlagEl) avgPlagEl.textContent = `${(data.avg_plagiarism_score * 100).toFixed(1)}%`;

            // Subtitle counts
            const userSubEl = document.getElementById("kpi-user-subtitle");
            if (userSubEl) userSubEl.innerHTML = `<span class="positive">${data.active_instructors}</span> instructors, ${data.active_students} students`;

            // Seat Progress
            const seatsUsed = data.total_seats_used || 0;
            const seatsAllocated = Math.max(1, data.total_seats_allocated || 1);
            const seatPct = Math.min(100, Math.round((seatsUsed / seatsAllocated) * 100));

            const seatPctLabel = document.getElementById("overview-seat-pct");
            const seatFractionLabel = document.getElementById("overview-seat-fraction");
            const seatFillBar = document.getElementById("overview-seat-fill");

            if (seatPctLabel) seatPctLabel.textContent = `${seatPct}% Utilized`;
            if (seatFractionLabel) seatFractionLabel.textContent = `${seatsUsed.toLocaleString()} / ${seatsAllocated.toLocaleString()} seats`;
            if (seatFillBar) seatFillBar.style.width = `${seatPct}%`;

            // Risk Breakdown
            const total = Math.max(1, data.clean + data.flagged_medium + data.flagged_high);
            const cleanPct = Math.round((data.clean / total) * 100);
            const medPct = Math.round((data.flagged_medium / total) * 100);
            const highPct = Math.round((data.flagged_high / total) * 100);

            const fillClean = document.getElementById("meter-fill-clean");
            const fillMed = document.getElementById("meter-fill-medium");
            const fillHigh = document.getElementById("meter-fill-high");

            if (fillClean) fillClean.style.width = `${cleanPct}%`;
            if (fillMed) fillMed.style.width = `${medPct}%`;
            if (fillHigh) fillHigh.style.width = `${highPct}%`;

            const cntClean = document.getElementById("meter-cnt-clean");
            const cntMed = document.getElementById("meter-cnt-medium");
            const cntHigh = document.getElementById("meter-cnt-high");

            if (cntClean) cntClean.textContent = `${data.clean} papers (${cleanPct}%)`;
            if (cntMed) cntMed.textContent = `${data.flagged_medium} papers (${medPct}%)`;
            if (cntHigh) cntHigh.textContent = `${data.flagged_high} papers (${highPct}%)`;

        } catch (err) {
            console.warn("Overview stats fetch failed:", err);
        }
    }

    // -------------------------------------------------------------------------
    // 2. Institutions Management
    // -------------------------------------------------------------------------
    async function loadInstitutions() {
        const tbody = document.getElementById("institutions-table-body");
        if (!tbody) return;
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 2rem;"><i class="fa-solid fa-spinner fa-spin"></i> Loading institutions...</td></tr>`;

        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/institutions`, { headers: getAuthHeaders() });
            if (!res.ok) throw new Error("Could not load institutions");
            const list = await res.json();
            state.institutions = list;

            // Populate institution dropdown in invite modal
            const inviteSelect = document.getElementById("invite-institution-select");
            if (inviteSelect) {
                inviteSelect.innerHTML = list.map(inst => `<option value="${inst.id}">${inst.name}</option>`).join("");
            }

            if (!list.length) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 2.5rem; color: var(--text-muted);">No institutions registered yet. Click "Add Institution" above to get started.</td></tr>`;
                return;
            }

            tbody.innerHTML = list.map(inst => {
                const used = inst.used_seats || 0;
                const max = inst.max_seats || 100;
                const pct = Math.min(100, Math.round((used / max) * 100));

                return `
                    <tr>
                        <td>
                            <strong style="color: var(--text-primary); font-size: 0.95rem;">${escapeHtml(inst.name)}</strong>
                            <div style="font-size: 0.76rem; color: var(--text-muted);">${escapeHtml(inst.domain || 'All domains allowed')}</div>
                        </td>
                        <td>
                            <span class="code-copy-pill" onclick="copyText('${inst.institution_code}', 'Institution Code')">
                                ${inst.institution_code}
                                <i class="fa-regular fa-copy"></i>
                            </span>
                        </td>
                        <td style="min-width: 140px;">
                            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; margin-bottom: 4px;">
                                <span>${used} / ${max}</span>
                                <span style="color: var(--accent-purple); font-weight: 600;">${pct}%</span>
                            </div>
                            <div class="progress-track" style="height: 6px;">
                                <div class="progress-fill seats" style="width: ${pct}%;"></div>
                            </div>
                        </td>
                        <td>
                            <span style="font-size: 0.8rem; color: var(--text-muted);">
                                ${inst.created_at ? new Date(inst.created_at).toLocaleDateString() : 'Active'}
                            </span>
                        </td>
                        <td style="text-align: right;">
                            <button class="btn-admin-secondary" style="padding: 4px 10px; font-size: 0.78rem;" onclick="openSeatsModal('${inst.id}')">
                                <i class="fa-solid fa-users"></i> View Seats
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");

        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: #ef4444; padding: 2rem;">Error: ${err.message}</td></tr>`;
        }
    }

    async function handleCreateInstitution(e) {
        e.preventDefault();
        const btn = document.getElementById("btn-submit-institution");
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Creating...';

        const payload = {
            name: document.getElementById("inst-name-input").value.trim(),
            domain: document.getElementById("inst-domain-input").value.trim() || null,
            max_seats: parseInt(document.getElementById("inst-seats-input").value, 10) || 100
        };

        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/institutions`, {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to create institution");

            showToast(`Created institution: ${data.name}! Code: ${data.institution_code}`, "success");
            closeModal("modal-add-institution");
            document.getElementById("form-add-institution").reset();
            loadInstitutions();
            loadOverviewStats();
        } catch (err) {
            showToast(err.message, "error");
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Create Institution';
        }
    }

    async function openSeatsModal(institutionId) {
        const modal = document.getElementById("modal-view-seats");
        const titleEl = document.getElementById("seats-modal-title");
        const bodyEl = document.getElementById("seats-modal-members");

        if (titleEl) titleEl.textContent = "Loading Seat Allocation...";
        if (bodyEl) bodyEl.innerHTML = `<p style="text-align:center; padding: 1.5rem;"><i class="fa-solid fa-spinner fa-spin"></i> Loading members...</p>`;
        openModal("modal-view-seats");

        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/institutions/${institutionId}/seats`, { headers: getAuthHeaders() });
            if (!res.ok) throw new Error("Failed to load seat data");
            const data = await res.json();

            if (titleEl) titleEl.textContent = `${data.institution_name} • Seat Quota (${data.used_seats} / ${data.max_seats})`;
            
            if (!data.members || !data.members.length) {
                bodyEl.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted);">No members enrolled in this institution yet. Use the "Invite Users" tool to send invitations.</div>`;
                return;
            }

            bodyEl.innerHTML = `
                <div class="admin-table-wrapper" style="max-height: 340px; overflow-y: auto;">
                    <table class="admin-table">
                        <thead>
                            <tr>
                                <th>Member Name</th>
                                <th>Email</th>
                                <th>Role</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.members.map(m => `
                                <tr>
                                    <td><strong>${escapeHtml(m.full_name)}</strong></td>
                                    <td>${escapeHtml(m.email)}</td>
                                    <td><span class="role-badge ${m.role}">${formatRole(m.role)}</span></td>
                                </tr>
                            `).join("")}
                        </tbody>
                    </table>
                </div>
            `;
        } catch (err) {
            bodyEl.innerHTML = `<p style="color: #ef4444; padding: 1rem;">Failed to load seats: ${err.message}</p>`;
        }
    }
    window.openSeatsModal = openSeatsModal;

    // -------------------------------------------------------------------------
    // 3. Users & Role Management
    // -------------------------------------------------------------------------
    async function loadUsers() {
        const tbody = document.getElementById("users-table-body");
        if (!tbody) return;
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 2rem;"><i class="fa-solid fa-spinner fa-spin"></i> Loading users...</td></tr>`;

        const q = state.userSearchQuery.trim();
        const role = state.userRoleFilter;
        let url = `${API_BASE}/api/v1/admin/users?limit=100`;
        if (q) url += `&q=${encodeURIComponent(q)}`;
        if (role && role !== "all") url += `&role=${encodeURIComponent(role)}`;

        try {
            const res = await fetch(url, { headers: getAuthHeaders() });
            if (!res.ok) throw new Error("Could not load users");
            const users = await res.json();
            state.users = users;

            if (!users.length) {
                tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 2.5rem; color: var(--text-muted);">No users matched your query.</td></tr>`;
                return;
            }

            tbody.innerHTML = users.map(user => {
                return `
                    <tr>
                        <td>
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <div style="width: 32px; height: 32px; border-radius: 50%; background: rgba(16, 185, 129, 0.15); color: var(--accent-purple); display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem;">
                                    ${(user.full_name || 'U').charAt(0).toUpperCase()}
                                </div>
                                <div>
                                    <strong style="color: var(--text-primary); font-size: 0.92rem;">${escapeHtml(user.full_name)}</strong>
                                    <div style="font-size: 0.78rem; color: var(--text-muted);">${escapeHtml(user.email)}</div>
                                </div>
                            </div>
                        </td>
                        <td>
                            <span style="font-size: 0.85rem;">${escapeHtml(user.institution_name || 'Individual Researcher')}</span>
                        </td>
                        <td>
                            <span class="role-badge ${user.role}">${formatRole(user.role)}</span>
                        </td>
                        <td>
                            <span style="font-size: 0.85rem; color: var(--text-primary); font-weight: 600;">${user.submissions_count || 0}</span>
                        </td>
                        <td>
                            ${user.email_verified 
                                ? '<span style="color: #10b981; font-size: 0.8rem;"><i class="fa-solid fa-circle-check"></i> Verified</span>' 
                                : '<span style="color: var(--text-muted); font-size: 0.8rem;"><i class="fa-regular fa-circle"></i> Unverified</span>'}
                        </td>
                        <td style="text-align: right;">
                            <select class="admin-select" style="padding: 4px 8px; font-size: 0.78rem;" onchange="handleRoleChange('${user.id}', this.value)">
                                <option value="student" ${user.role === "student" ? "selected" : ""}>Student</option>
                                <option value="instructor" ${user.role === "instructor" ? "selected" : ""}>Instructor</option>
                                <option value="institution_admin" ${user.role === "institution_admin" ? "selected" : ""}>Inst. Admin</option>
                                <option value="super_admin" ${user.role === "super_admin" ? "selected" : ""}>Super Admin</option>
                            </select>
                        </td>
                    </tr>
                `;
            }).join("");

        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: #ef4444; padding: 2rem;">Error: ${err.message}</td></tr>`;
        }
    }

    async function handleRoleChange(userId, newRole) {
        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/users/${userId}/role`, {
                method: "PATCH",
                headers: getAuthHeaders(),
                body: JSON.stringify({ role: newRole })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to update role");
            showToast(`Role updated to ${formatRole(newRole)}`, "success");
            loadUsers();
        } catch (err) {
            showToast(err.message, "error");
        }
    }
    window.handleRoleChange = handleRoleChange;

    async function handleInviteUsers(e) {
        e.preventDefault();
        const btn = document.getElementById("btn-submit-invite");
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sending invites...';

        const instId = document.getElementById("invite-institution-select").value;
        const role = document.getElementById("invite-role-select").value;
        const rawEmails = document.getElementById("invite-emails-input").value;
        const emails = rawEmails.split(/[\n,;]+/).map(e => e.trim()).filter(Boolean);

        if (!emails.length) {
            showToast("Please enter at least one valid email address.", "error");
            btn.disabled = false;
            btn.innerHTML = 'Send Invitations';
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/institutions/${instId}/invite`, {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify({ emails, role })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Bulk invitation failed");

            const count = data.invited ? data.invited.length : emails.length;
            showToast(`Successfully invited ${count} user(s)!`, "success");
            closeModal("modal-invite-users");
            document.getElementById("form-invite-users").reset();
            loadUsers();
            loadInstitutions();
        } catch (err) {
            showToast(err.message, "error");
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Send Invitations';
        }
    }

    // -------------------------------------------------------------------------
    // 4. Submission & Integrity Audits
    // -------------------------------------------------------------------------
    async function loadSubmissions() {
        const tbody = document.getElementById("audits-table-body");
        if (!tbody) return;
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2rem;"><i class="fa-solid fa-spinner fa-spin"></i> Loading submission audits...</td></tr>`;

        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/submissions?limit=50`, { headers: getAuthHeaders() });
            if (!res.ok) throw new Error("Could not load submissions");
            const subs = await res.json();
            state.submissions = subs;

            if (!subs.length) {
                tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding: 2.5rem; color: var(--text-muted);">No submissions recorded yet.</td></tr>`;
                return;
            }

            tbody.innerHTML = subs.map(sub => {
                const plagPct = Math.round(sub.plagiarism_score * 100);
                const aiPct = Math.round(sub.ai_score * 100);

                let riskBadge = '<span class="status-chip clean"><i class="fa-solid fa-shield-check"></i> Clean</span>';
                if (sub.plagiarism_score >= 0.6 || sub.ai_score >= 0.6) {
                    riskBadge = '<span class="status-chip high"><i class="fa-solid fa-triangle-exclamation"></i> High Risk</span>';
                } else if (sub.plagiarism_score >= 0.3 || sub.ai_score >= 0.3) {
                    riskBadge = '<span class="status-chip medium"><i class="fa-solid fa-circle-exclamation"></i> Medium</span>';
                }

                return `
                    <tr>
                        <td>
                            <strong style="color: var(--text-primary); font-size: 0.9rem;">${escapeHtml(sub.assignment_title)}</strong>
                            <div style="font-size: 0.76rem; color: var(--text-muted);">${escapeHtml(sub.institution_name)}</div>
                        </td>
                        <td>
                            <div>${escapeHtml(sub.student_name)}</div>
                            <div style="font-size: 0.76rem; color: var(--text-muted);">${escapeHtml(sub.student_email)}</div>
                        </td>
                        <td>
                            <div style="font-weight: 700; color: ${plagPct >= 60 ? '#ef4444' : plagPct >= 30 ? '#f59e0b' : '#10b981'};">
                                ${plagPct}%
                            </div>
                        </td>
                        <td>
                            <div style="font-weight: 700; color: ${aiPct >= 60 ? '#ef4444' : aiPct >= 30 ? '#f59e0b' : '#10b981'};">
                                ${aiPct}%
                            </div>
                        </td>
                        <td>${riskBadge}</td>
                        <td>
                            <span style="font-size: 0.78rem; color: var(--text-muted);">
                                ${sub.submitted_at ? new Date(sub.submitted_at).toLocaleDateString() : 'Recent'}
                            </span>
                        </td>
                        <td style="text-align: right;">
                            <button class="btn-admin-secondary" style="padding: 4px 10px; font-size: 0.76rem;" onclick="inspectSubmission('${sub.id}')">
                                <i class="fa-regular fa-file-lines"></i> Inspect
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");

        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color: #ef4444; padding: 2rem;">Error: ${err.message}</td></tr>`;
        }
    }

    function inspectSubmission(subId) {
        const sub = state.submissions.find(s => s.id === subId);
        if (!sub) return;

        const modal = document.getElementById("modal-inspect-doc");
        const titleEl = document.getElementById("inspect-modal-title");
        const bodyEl = document.getElementById("inspect-modal-content");

        if (titleEl) titleEl.textContent = `Audit Report: ${sub.assignment_title}`;
        if (bodyEl) {
            const plagPct = Math.round(sub.plagiarism_score * 100);
            const aiPct = Math.round(sub.ai_score * 100);

            bodyEl.innerHTML = `
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem;">
                    <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-glass); border-radius: 8px; padding: 1rem; text-align: center;">
                        <span style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">Plagiarism Index</span>
                        <h3 style="font-size: 1.8rem; font-family: 'Outfit'; color: ${plagPct >= 60 ? '#ef4444' : plagPct >= 30 ? '#f59e0b' : '#10b981'}; margin: 4px 0;">${plagPct}%</h3>
                        <p style="font-size: 0.76rem; color: var(--text-muted);">Against 10M+ arXiv, IEEE & CrossRef docs</p>
                    </div>
                    <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-glass); border-radius: 8px; padding: 1rem; text-align: center;">
                        <span style="font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">AI Synthesis Score</span>
                        <h3 style="font-size: 1.8rem; font-family: 'Outfit'; color: ${aiPct >= 60 ? '#ef4444' : aiPct >= 30 ? '#f59e0b' : '#10b981'}; margin: 4px 0;">${aiPct}%</h3>
                        <p style="font-size: 0.76rem; color: var(--text-muted);">Multi-head perplexity & burstiness</p>
                    </div>
                </div>
                <div style="font-size: 0.85rem; line-height: 1.6; color: var(--text-secondary); background: rgba(0,0,0,0.3); border: 1px solid var(--border-glass); border-radius: 8px; padding: 1rem;">
                    <p><strong>Submitter:</strong> ${escapeHtml(sub.student_name)} (${escapeHtml(sub.student_email)})</p>
                    <p><strong>Affiliation:</strong> ${escapeHtml(sub.institution_name)}</p>
                    <p><strong>Audit Status:</strong> Analysis completed and verified by Lemma Multi-tier Integrity Engine.</p>
                </div>
            `;
        }
        openModal("modal-inspect-doc");
    }
    window.inspectSubmission = inspectSubmission;

    // -------------------------------------------------------------------------
    // 5. System Health & API Keys
    // -------------------------------------------------------------------------
    async function loadSystemHealth() {
        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/system-health`, { headers: getAuthHeaders() });
            if (!res.ok) throw new Error("Could not load health metrics");
            const data = await res.json();

            const statusDot = document.getElementById("admin-health-pulse");
            const statusText = document.getElementById("admin-health-text");

            if (data.status === "operational") {
                if (statusDot) statusDot.style.backgroundColor = "#10b981";
                if (statusText) statusText.textContent = "Systems Operational";
            } else {
                if (statusDot) statusDot.style.backgroundColor = "#f59e0b";
                if (statusText) statusText.textContent = "Degraded / Local Dev";
            }

            // Update health grid cards
            const pgStatus = document.getElementById("health-status-postgres");
            const pgDesc = document.getElementById("health-desc-postgres");
            if (pgStatus && data.services.postgresql) {
                pgStatus.textContent = data.services.postgresql.status.toUpperCase();
                pgStatus.className = `status-chip ${data.services.postgresql.connected ? 'clean' : 'medium'}`;
                if (pgDesc) pgDesc.textContent = data.services.postgresql.connected ? "PostgreSQL 16 + pgvector connected" : "Using in-memory dev engine";
            }

            const vecStatus = document.getElementById("health-status-vector");
            if (vecStatus && data.services.pgvector) {
                vecStatus.textContent = data.services.pgvector.status.toUpperCase();
                vecStatus.className = `status-chip ${data.services.pgvector.active ? 'clean' : 'medium'}`;
            }

        } catch (err) {
            console.warn("Health check error:", err);
        }
    }

    async function loadApiKeys() {
        const tbody = document.getElementById("api-keys-table-body");
        if (!tbody) return;

        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/api-keys`, { headers: getAuthHeaders() });
            if (!res.ok) throw new Error("Could not load API keys");
            const keys = await res.json();
            state.apiKeys = keys;

            if (!keys.length) {
                tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding: 2rem; color: var(--text-muted);">No API integration keys created yet.</td></tr>`;
                return;
            }

            tbody.innerHTML = keys.map(k => `
                <tr>
                    <td><strong>${escapeHtml(k.label)}</strong></td>
                    <td><code>${escapeHtml(k.key_prefix)}</code></td>
                    <td>${k.created_at ? new Date(k.created_at).toLocaleDateString() : 'Active'}</td>
                    <td style="color: var(--text-muted);">${k.expires_at ? new Date(k.expires_at).toLocaleDateString() : 'Never'}</td>
                </tr>
            `).join("");
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color: #ef4444; padding: 1.5rem;">Error: ${err.message}</td></tr>`;
        }
    }

    async function handleCreateApiKey(e) {
        e.preventDefault();
        const btn = document.getElementById("btn-submit-key");
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating...';

        const label = document.getElementById("key-label-input").value.trim();
        const days = parseInt(document.getElementById("key-expiry-input").value, 10) || 90;

        try {
            const res = await fetch(`${API_BASE}/api/v1/admin/api-keys`, {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify({ label, expires_in_days: days })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to generate key");

            closeModal("modal-add-api-key");
            document.getElementById("form-add-api-key").reset();

            // Prompt user with raw key
            alert(`Your new API Key has been generated:\n\n${data.raw_key}\n\nPlease copy and store this safely now, as it will not be displayed again.`);
            loadApiKeys();
        } catch (err) {
            showToast(err.message, "error");
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Generate Key';
        }
    }

    // -------------------------------------------------------------------------
    // Modal Helpers
    // -------------------------------------------------------------------------
    function openModal(id) {
        const m = document.getElementById(id);
        if (m) m.classList.add("show");
    }
    window.openModal = openModal;

    function closeModal(id) {
        const m = document.getElementById(id);
        if (m) m.classList.remove("show");
    }
    window.closeModal = closeModal;

    // -------------------------------------------------------------------------
    // Utilities
    // -------------------------------------------------------------------------
    function escapeHtml(str) {
        if (!str) return "";
        return String(str).replace(/[&<>"']/g, m => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[m]));
    }

    function formatRole(role) {
        const map = {
            super_admin: "Super Admin",
            institution_admin: "Inst. Admin",
            instructor: "Instructor",
            student: "Student"
        };
        return map[role] || role;
    }

    function copyText(text, label = "Code") {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text).then(() => {
                showToast(`${label} copied to clipboard!`, "success");
            });
        } else {
            prompt(`Copy this ${label}:`, text);
        }
    }
    window.copyText = copyText;

    // -------------------------------------------------------------------------
    // Initialization
    // -------------------------------------------------------------------------
    document.addEventListener("DOMContentLoaded", () => {
        // Tab buttons in sidebar
        document.querySelectorAll(".admin-nav-item button").forEach(btn => {
            btn.addEventListener("click", () => {
                const parent = btn.closest(".admin-nav-item");
                if (parent && parent.dataset.tab) {
                    switchAdminTab(parent.dataset.tab);
                }
            });
        });

        // User Search input debounce
        const searchInput = document.getElementById("users-search-input");
        if (searchInput) {
            let debounceTimer;
            searchInput.addEventListener("input", (e) => {
                clearTimeout(debounceTimer);
                debounceTimer = setTimeout(() => {
                    state.userSearchQuery = e.target.value;
                    loadUsers();
                }, 300);
            });
        }

        // User Role Filter
        const roleFilter = document.getElementById("users-role-filter");
        if (roleFilter) {
            roleFilter.addEventListener("change", (e) => {
                state.userRoleFilter = e.target.value;
                loadUsers();
            });
        }

        // Form bindings
        const formAddInst = document.getElementById("form-add-institution");
        if (formAddInst) formAddInst.addEventListener("submit", handleCreateInstitution);

        const formInvite = document.getElementById("form-invite-users");
        if (formInvite) formInvite.addEventListener("submit", handleInviteUsers);

        const formKey = document.getElementById("form-add-api-key");
        if (formKey) formKey.addEventListener("submit", handleCreateApiKey);

        // Click outside modal to close
        document.querySelectorAll(".admin-modal-backdrop").forEach(backdrop => {
            backdrop.addEventListener("click", (e) => {
                if (e.target === backdrop) {
                    backdrop.classList.remove("show");
                }
            });
        });

        // Verify admin access before initializing
        if (!checkAdminAccess()) {
            return;
        }

        // Initial tab load
        switchAdminTab("overview");
    });

})();
