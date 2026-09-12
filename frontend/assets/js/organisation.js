/**
 * Lemma Organisation Management & Funding Scheme Engine (organisation.js)
 * 
 * Features:
 * - Organisation Registration & Official Domain Authentication
 * - Organisation Dashboard (Profile, Analytics, Scheme Management)
 * - Interactive Funding Scheme Modal (Q1, Q2, Q3, Q4, Conference, Book Chapter, Patent payouts)
 * - Scheme CRUD operations synced with Lemma Public Publishing Grants directory
 */

(function () {
    let currentOrgProfile = null;
    let currentOrgSchemes = [];
    let editingSchemeId = null;

    function getApiBaseUrl() {
        if (window.APIConfigManager && typeof window.APIConfigManager.getApiBaseUrl === 'function') {
            return window.APIConfigManager.getApiBaseUrl();
        }
        return window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
            ? 'http://localhost:8000'
            : window.location.origin;
    }

    function getAuthToken() {
        return sessionStorage.getItem("lemma_access_token") || localStorage.getItem("lemma_access_token") || "";
    }

    function getUserData() {
        try {
            return JSON.parse(sessionStorage.getItem("lemma_user") || localStorage.getItem("lemma_user") || "{}");
        } catch {
            return {};
        }
    }

    function showToast(msg, type = "info") {
        if (typeof window.showToastMessage === 'function') {
            window.showToastMessage(msg, type);
        } else if (typeof window.showToast === 'function') {
            window.showToast(msg, type);
        } else {
            console.log(`[${type}] ${msg}`);
        }
    }

    // ==========================================
    // ORGANISATION DASHBOARD INITIALIZATION
    // ==========================================
    async function initOrganisationDashboard() {
        const navOrg = document.getElementById("nav-org-dashboard");
        if (navOrg) {
            navOrg.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".sidebar-nav li").forEach(el => el.classList.remove("active"));
                navOrg.classList.add("active");
                if (typeof window.showView === 'function') {
                    window.showView("org-dashboard-view");
                } else {
                    document.querySelectorAll(".workspace-view").forEach(v => v.classList.add("hidden"));
                    const target = document.getElementById("org-dashboard-view");
                    if (target) target.classList.remove("hidden");
                }
                loadOrgData();
            });
        }

        // Add Scheme Button
        const btnAddScheme = document.getElementById("btn-add-scheme-modal");
        if (btnAddScheme) {
            btnAddScheme.addEventListener("click", () => openSchemeModal());
        }

        // Edit Profile Button
        const btnEditProfile = document.getElementById("btn-edit-org-profile");
        if (btnEditProfile) {
            btnEditProfile.addEventListener("click", () => openOrgProfileModal());
        }

        // Scheme Modal Close & Save Buttons
        const btnCloseSchemeModal = document.getElementById("btn-close-scheme-modal");
        const btnCancelSchemeModal = document.getElementById("btn-cancel-scheme-modal");
        const modalSchemeEl = document.getElementById("org-scheme-modal");
        const formScheme = document.getElementById("org-scheme-form");

        if (btnCloseSchemeModal) btnCloseSchemeModal.addEventListener("click", closeSchemeModal);
        if (btnCancelSchemeModal) btnCancelSchemeModal.addEventListener("click", closeSchemeModal);
        if (modalSchemeEl) {
            modalSchemeEl.addEventListener("click", (e) => {
                if (e.target === modalSchemeEl) closeSchemeModal();
            });
        }
        
        // Enterprise Forms
        const poForm = document.getElementById("org-po-form");
        if (poForm) poForm.addEventListener("submit", handlePoSubmit);

        const wireForm = document.getElementById("org-wire-form");
        if (wireForm) wireForm.addEventListener("submit", handleWireSubmit);

        const allocForm = document.getElementById("org-allocate-seat-form");
        if (allocForm) allocForm.addEventListener("submit", handleAllocateSeatSubmit);

        if (formScheme) {
            formScheme.addEventListener("submit", handleSaveScheme);
        }

        // Profile Modal Close & Save Buttons
        const btnCloseProfileModal = document.getElementById("btn-close-org-profile-modal");
        const btnCancelProfileModal = document.getElementById("btn-cancel-org-profile-modal");
        const modalProfileEl = document.getElementById("org-profile-modal");
        const formProfile = document.getElementById("org-profile-form");

        if (btnCloseProfileModal) btnCloseProfileModal.addEventListener("click", closeOrgProfileModal);
        if (btnCancelProfileModal) btnCancelProfileModal.addEventListener("click", closeOrgProfileModal);
        if (modalProfileEl) {
            modalProfileEl.addEventListener("click", (e) => {
                if (e.target === modalProfileEl) closeOrgProfileModal();
            });
        }
        if (formProfile) {
            formProfile.addEventListener("submit", handleSaveOrgProfile);
        }

        // If user is already logged in as organisation, display badge in topbar
        const user = getUserData();
        if (user && (user.role === "organisation_admin" || user.is_organisation)) {
            const roleBadge = document.getElementById("dropdown-user-role");
            if (roleBadge) {
                roleBadge.textContent = "Organisation Admin";
                roleBadge.style.background = "rgba(16, 185, 129, 0.15)";
                roleBadge.style.color = "#10b981";
                roleBadge.style.borderColor = "rgba(16, 185, 129, 0.3)";
            }
        }
    }

    // ==========================================
    // LOAD ORG DATA & SCHEMES
    // ==========================================
    async function loadOrgData() {
        const token = getAuthToken();
        const baseUrl = await getApiBaseUrl();

        const notLoggedContainer = document.getElementById("org-not-logged-in-state");
        const loggedContainer = document.getElementById("org-logged-in-state");

        if (!token) {
            if (notLoggedContainer) notLoggedContainer.classList.remove("hidden");
            if (loggedContainer) loggedContainer.classList.add("hidden");
            return;
        }

        try {
            // Fetch profile
            const profileRes = await fetch(`${baseUrl}/api/v1/organisations/me`, {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!profileRes.ok) {
                if (notLoggedContainer) notLoggedContainer.classList.remove("hidden");
                if (loggedContainer) loggedContainer.classList.add("hidden");
                return;
            }

            currentOrgProfile = await profileRes.json();

            if (notLoggedContainer) notLoggedContainer.classList.add("hidden");
            if (loggedContainer) loggedContainer.classList.remove("hidden");

            renderOrgProfile(currentOrgProfile);

            // Fetch Schemes
            await loadOrgSchemes();
        } catch (err) {
            console.error("Error loading organisation data:", err);
            showToast("Failed to load organisation dashboard.", "error");
        }
    }

    function renderOrgProfile(org) {
        const nameEl = document.getElementById("org-profile-name");
        const typeEl = document.getElementById("org-profile-type");
        const emailEl = document.getElementById("org-profile-email");
        const domainEl = document.getElementById("org-profile-domain");
        const contactEl = document.getElementById("org-profile-contact");
        const websiteEl = document.getElementById("org-profile-website");
        const descEl = document.getElementById("org-profile-desc");
        const logoAvatarEl = document.getElementById("org-profile-avatar");

        if (nameEl) nameEl.textContent = org.name;
        if (typeEl) typeEl.textContent = org.organisation_type || "University";
        if (emailEl) emailEl.textContent = org.official_email;
        if (domainEl) domainEl.textContent = `@${org.domain}`;
        if (contactEl) contactEl.textContent = `${org.contact_person || 'N/A'}${org.contact_phone ? ` • ${org.contact_phone}` : ''}`;
        if (websiteEl) {
            websiteEl.textContent = org.website || "Not provided";
            if (org.website) websiteEl.href = org.website.startsWith('http') ? org.website : `https://${org.website}`;
        }
        if (descEl) descEl.textContent = org.description || "Leading academic & research institution providing comprehensive publication incentives for faculty, researchers, and global co-authors.";
        if (logoAvatarEl) {
            logoAvatarEl.textContent = (org.short_name || org.name.substring(0, 2)).toUpperCase();
        }
    }

    async function loadOrgSchemes() {
        const token = getAuthToken();
        const baseUrl = await getApiBaseUrl();

        try {
            const res = await fetch(`${baseUrl}/api/v1/organisations/me/schemes`, {
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (res.ok) {
                currentOrgSchemes = await res.json();
                renderOrgSchemes(currentOrgSchemes);
                updateOrgStatsRibbon(currentOrgSchemes);
            }
        } catch (err) {
            console.error("Error loading organisation schemes:", err);
        }
    }

    function updateOrgStatsRibbon(schemes) {
        const totalSchemesEl = document.getElementById("stat-org-total-schemes");
        const activeSchemesEl = document.getElementById("stat-org-active-schemes");
        const maxBountyEl = document.getElementById("stat-org-max-bounty");
        const totalPayoutTypesEl = document.getElementById("stat-org-criteria-count");

        if (totalSchemesEl) totalSchemesEl.textContent = schemes.length;
        if (activeSchemesEl) activeSchemesEl.textContent = schemes.filter(s => s.status === 'active').length;

        let maxBounty = 0;
        let totalCriteria = 0;
        schemes.forEach(s => {
            if (s.criteria && Array.isArray(s.criteria)) {
                totalCriteria += s.criteria.length;
                s.criteria.forEach(c => {
                    if (c.amount_inr && c.amount_inr > maxBounty) maxBounty = c.amount_inr;
                });
            }
        });

        if (maxBountyEl) maxBountyEl.textContent = maxBounty > 0 ? `₹${maxBounty.toLocaleString('en-IN')}` : "₹0";
        if (totalPayoutTypesEl) totalPayoutTypesEl.textContent = totalCriteria;
    }

    function renderOrgSchemes(schemes) {
        const grid = document.getElementById("org-schemes-grid");
        const emptyState = document.getElementById("org-schemes-empty");

        if (!grid) return;
        grid.innerHTML = "";

        if (!schemes || schemes.length === 0) {
            if (emptyState) emptyState.classList.remove("hidden");
            return;
        }

        if (emptyState) emptyState.classList.add("hidden");

        schemes.forEach(scheme => {
            const card = document.createElement("div");
            card.className = "glass-card org-scheme-card";
            card.style.cssText = "background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: 16px; padding: 1.5rem; display: flex; flex-direction: column; justify-content: space-between; position: relative; transition: transform 0.2s, box-shadow 0.2s;";

            let schemeMax = 0;
            if (scheme.criteria && Array.isArray(scheme.criteria)) {
                scheme.criteria.forEach(c => {
                    if (c.amount_inr > schemeMax) schemeMax = c.amount_inr;
                });
            }

            const criteriaBadges = (scheme.criteria || []).map(c => {
                let badgeClass = "badge-gray";
                let icon = "fa-bookmark";
                if (c.criteria_type.includes("q1") || c.criteria_type.includes("sci")) {
                    icon = "fa-crown";
                    badgeClass = "color: #10b981; background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.3);";
                } else if (c.criteria_type.includes("q2")) {
                    icon = "fa-star";
                    badgeClass = "color: #6366f1; background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.3);";
                } else if (c.criteria_type.includes("conference")) {
                    icon = "fa-microphone";
                    badgeClass = "color: #3b82f6; background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.3);";
                } else if (c.criteria_type.includes("book")) {
                    icon = "fa-book";
                    badgeClass = "color: #f59e0b; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.3);";
                } else if (c.criteria_type.includes("patent")) {
                    icon = "fa-certificate";
                    badgeClass = "color: #ec4899; background: rgba(236, 72, 153, 0.12); border: 1px solid rgba(236, 72, 153, 0.3);";
                } else {
                    badgeClass = "color: var(--text-secondary); background: rgba(255, 255, 255, 0.05); border: 1px solid var(--border-color);";
                }

                return `
                    <div style="font-size: 0.76rem; font-weight: 600; padding: 4px 10px; border-radius: 8px; display: inline-flex; align-items: center; gap: 6px; ${badgeClass}">
                        <i class="fa-solid ${icon}"></i>
                        <span>${c.criteria_name}: <strong>₹${(c.amount_inr || 0).toLocaleString('en-IN')}</strong></span>
                    </div>
                `;
            }).join("");

            card.innerHTML = `
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 0.75rem;">
                        <div>
                            <span style="font-size: 0.72rem; font-weight: 700; color: #10b981; text-transform: uppercase; letter-spacing: 0.5px;">
                                <i class="fa-solid fa-graduation-cap"></i> ${scheme.academic_year || 'Active Policy'}
                            </span>
                            <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-primary); margin: 2px 0 0 0;">
                                ${escapeHtml(scheme.scheme_title)}
                            </h3>
                        </div>
                        <span style="padding: 3px 10px; border-radius: 12px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; ${scheme.status === 'active' ? 'background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid rgba(16,185,129,0.3);' : 'background: rgba(100,116,139,0.15); color: #94a3b8; border: 1px solid rgba(100,116,139,0.3);'}">
                            <i class="fa-solid ${scheme.status === 'active' ? 'fa-circle-check' : 'fa-pause'}"></i> ${scheme.status}
                        </span>
                    </div>

                    <p style="font-size: 0.83rem; color: var(--text-secondary); line-height: 1.5; margin-bottom: 1rem;">
                        ${escapeHtml(scheme.description || 'Institutional research incentive scheme covering verified journal and conference publications.')}
                    </p>

                    <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.2); border-radius: 10px; padding: 10px 14px; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; font-weight: 700; display: block;">Max Reward</span>
                            <span style="font-size: 1.25rem; font-weight: 800; color: #10b981;">₹${schemeMax.toLocaleString('en-IN')}</span>
                        </div>
                        <div style="text-align: right;">
                            <span style="font-size: 0.72rem; color: var(--text-muted); display: block;">Eligibility</span>
                            <span style="font-size: 0.8rem; font-weight: 600; color: var(--text-primary);">${escapeHtml(scheme.eligibility_scope || 'Faculty, Students, Co-Authors')}</span>
                        </div>
                    </div>

                    <div style="margin-bottom: 1.25rem;">
                        <span style="font-size: 0.75rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; display: block; margin-bottom: 8px;">
                            Configured Payout Slabs (${(scheme.criteria || []).length}):
                        </span>
                        <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                            ${criteriaBadges || '<span style="font-size: 0.8rem; color: var(--text-muted);">No criteria configured</span>'}
                        </div>
                    </div>
                </div>

                <div style="border-top: 1px solid var(--border-color); padding-top: 1rem; display: flex; justify-content: space-between; align-items: center;">
                    <div style="font-size: 0.75rem; color: var(--text-muted);">
                        <i class="fa-solid fa-clock"></i> Updated: ${new Date(scheme.updated_at || scheme.created_at).toLocaleDateString()}
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn btn-sm btn-outline btn-edit-scheme" data-id="${scheme.id}" style="font-size: 0.78rem; padding: 5px 12px; border-radius: 6px;">
                            <i class="fa-solid fa-pen-to-square"></i> Edit
                        </button>
                        <button class="btn btn-sm btn-danger btn-delete-scheme" data-id="${scheme.id}" style="font-size: 0.78rem; padding: 5px 12px; border-radius: 6px; background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);">
                            <i class="fa-solid fa-trash"></i> Delete
                        </button>
                    </div>
                </div>
            `;

            card.querySelector(".btn-edit-scheme").addEventListener("click", () => openSchemeModal(scheme));
            card.querySelector(".btn-delete-scheme").addEventListener("click", () => handleDeleteScheme(scheme.id, scheme.scheme_title));

            grid.appendChild(card);
        });
    }

    // ==========================================
    // ADD / EDIT SCHEME MODAL LOGIC
    // ==========================================
    function openSchemeModal(schemeToEdit = null) {
        editingSchemeId = schemeToEdit ? schemeToEdit.id : null;
        const modal = document.getElementById("org-scheme-modal");
        const titleEl = document.getElementById("modal-scheme-title-text");

        if (titleEl) {
            titleEl.textContent = editingSchemeId ? "Edit Funding Scheme" : "Create New Research Funding Scheme";
        }

        const safeSet = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.value = val;
        };

        safeSet("input-scheme-title", schemeToEdit ? schemeToEdit.scheme_title : "");
        safeSet("input-scheme-desc", schemeToEdit ? (schemeToEdit.description || "") : "");
        safeSet("input-scheme-year", schemeToEdit ? (schemeToEdit.academic_year || "2026-2027") : "2026-2027");
        safeSet("input-scheme-status", schemeToEdit ? schemeToEdit.status : "active");
        safeSet("input-scheme-scope", schemeToEdit ? (schemeToEdit.eligibility_scope || "Faculty, Students, Global Co-Authors") : "Faculty, Students, Global Co-Authors");
        safeSet("input-scheme-guidelines-url", schemeToEdit ? (schemeToEdit.guidelines_url || "") : "");
        safeSet("input-scheme-contact-email", schemeToEdit ? (schemeToEdit.contact_email || (currentOrgProfile ? currentOrgProfile.official_email : "")) : (currentOrgProfile ? currentOrgProfile.official_email : ""));

        const defaultCriteriaMap = {
            "q1_sci": { enabled: true, amount: 100000, name: "Scopus Q1 / SCI Journal" },
            "q2": { enabled: true, amount: 45000, name: "Scopus Q2 Journal" },
            "q3": { enabled: true, amount: 20000, name: "Scopus Q3 Journal" },
            "q4": { enabled: false, amount: 10000, name: "Scopus Q4 Journal" },
            "conference_ieee": { enabled: true, amount: 25000, name: "IEEE / ACM Conference" },
            "book_chapter": { enabled: true, amount: 15000, name: "Scopus Book Chapter" },
            "patent_granted": { enabled: false, amount: 50000, name: "Granted Patent" }
        };

        if (schemeToEdit && schemeToEdit.criteria && Array.isArray(schemeToEdit.criteria)) {
            Object.keys(defaultCriteriaMap).forEach(k => {
                defaultCriteriaMap[k].enabled = false;
            });
            schemeToEdit.criteria.forEach(c => {
                if (defaultCriteriaMap[c.criteria_type]) {
                    defaultCriteriaMap[c.criteria_type].enabled = true;
                    defaultCriteriaMap[c.criteria_type].amount = c.amount_inr || 0;
                    if (c.criteria_name) defaultCriteriaMap[c.criteria_type].name = c.criteria_name;
                }
            });
        }

        Object.keys(defaultCriteriaMap).forEach(key => {
            const chk = document.getElementById(`chk-crit-${key}`);
            const inp = document.getElementById(`amt-crit-${key}`);
            if (chk) chk.checked = defaultCriteriaMap[key].enabled;
            if (inp) {
                inp.value = defaultCriteriaMap[key].amount;
                inp.disabled = !defaultCriteriaMap[key].enabled;
            }
        });

        Object.keys(defaultCriteriaMap).forEach(key => {
            const chk = document.getElementById(`chk-crit-${key}`);
            const inp = document.getElementById(`amt-crit-${key}`);
            if (chk && inp) {
                chk.onchange = () => {
                    inp.disabled = !chk.checked;
                    if (chk.checked && (!inp.value || inp.value === "0")) {
                        inp.value = defaultCriteriaMap[key].amount || 25000;
                    }
                };
            }
        });

        if (modal) {
            modal.style.display = "flex";
            modal.classList.remove("hidden");
        }
    }

    function closeSchemeModal() {
        const modal = document.getElementById("org-scheme-modal");
        if (modal) {
            modal.style.display = "none";
            modal.classList.add("hidden");
        }
        editingSchemeId = null;
    }

    async function handleSaveScheme(e) {
        e.preventDefault();
        const token = getAuthToken();
        const baseUrl = await getApiBaseUrl();

        const btnSave = document.getElementById("btn-save-scheme");
        if (btnSave) {
            btnSave.disabled = true;
            btnSave.textContent = "Saving Scheme...";
        }

        try {
            const criteria = [];
            const criteriaKeys = [
                { key: "q1_sci", name: "Scopus Q1 / SCI Journal", indexing: "Scopus Q1, SCI" },
                { key: "q2", name: "Scopus Q2 Journal", indexing: "Scopus Q2" },
                { key: "q3", name: "Scopus Q3 Journal", indexing: "Scopus Q3" },
                { key: "q4", name: "Scopus Q4 Journal", indexing: "Scopus Q4" },
                { key: "conference_ieee", name: "IEEE / ACM Conference Paper", indexing: "IEEE Xplore, ACM Digital Library" },
                { key: "book_chapter", name: "Scopus Indexed Book Chapter", indexing: "Scopus Book Series, Springer" },
                { key: "patent_granted", name: "Granted National / International Patent", indexing: "Patent Office" }
            ];

            criteriaKeys.forEach(item => {
                const chk = document.getElementById(`chk-crit-${item.key}`);
                const inp = document.getElementById(`amt-crit-${item.key}`);
                if (chk && chk.checked) {
                    const amount = parseInt(inp.value, 10) || 10000;
                    criteria.push({
                        criteria_type: item.key,
                        criteria_name: item.name,
                        amount_inr: amount,
                        amount_usd: Math.round(amount / 85),
                        min_indexing: item.indexing,
                        payout_form: "Direct Cash Bounty & APC Reimbursement"
                    });
                }
            });

            if (criteria.length === 0) {
                showToast("Please select at least one publication criteria (e.g. Scopus Q1, Q2, Conference).", "error");
                if (btnSave) {
                    btnSave.disabled = false;
                    btnSave.textContent = "Save Scheme";
                }
                return;
            }

            const statusEl = document.getElementById("input-scheme-status");
            const payload = {
                scheme_title: document.getElementById("input-scheme-title").value.trim(),
                description: document.getElementById("input-scheme-desc").value.trim(),
                academic_year: document.getElementById("input-scheme-year").value.trim(),
                status: statusEl ? statusEl.value : "active",
                eligibility_scope: document.getElementById("input-scheme-scope").value.trim(),
                guidelines_url: document.getElementById("input-scheme-guidelines-url").value.trim(),
                contact_email: document.getElementById("input-scheme-contact-email").value.trim(),
                criteria: criteria
            };

            const url = editingSchemeId
                ? `${baseUrl}/api/v1/organisations/me/schemes/${editingSchemeId}`
                : `${baseUrl}/api/v1/organisations/me/schemes`;
            const method = editingSchemeId ? "PUT" : "POST";

            const res = await fetch(url, {
                method: method,
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || "Failed to save funding scheme.");
            }

            showToast(editingSchemeId ? "Funding scheme updated successfully!" : "New funding scheme published to directory!", "success");
            closeSchemeModal();
            await loadOrgSchemes();

            if (typeof window.loadFundingDirectory === 'function') {
                window.loadFundingDirectory();
            }
        } catch (err) {
            console.error("Error saving scheme:", err);
            showToast(err.message || "Failed to save scheme.", "error");
        } finally {
            if (btnSave) {
                btnSave.disabled = false;
                btnSave.textContent = "Save Scheme";
            }
        }
    }

    async function handleDeleteScheme(schemeId, title) {
        if (!confirm(`Are you sure you want to delete scheme: "${title}"?\nThis will remove it from your dashboard and the public Grants Directory.`)) {
            return;
        }

        const token = getAuthToken();
        const baseUrl = await getApiBaseUrl();

        try {
            const res = await fetch(`${baseUrl}/api/v1/organisations/me/schemes/${schemeId}`, {
                method: "DELETE",
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Failed to delete scheme.");
            }

            showToast("Funding scheme deleted successfully.", "success");
            await loadOrgSchemes();

            if (typeof window.loadFundingDirectory === 'function') {
                window.loadFundingDirectory();
            }
        } catch (err) {
            console.error("Error deleting scheme:", err);
            showToast(err.message || "Could not delete scheme.", "error");
        }
    }

    // ==========================================
    // EDIT ORGANISATION PROFILE MODAL
    // ==========================================
    function openOrgProfileModal() {
        if (!currentOrgProfile) return;
        const modal = document.getElementById("org-profile-modal");

        document.getElementById("input-org-name").value = currentOrgProfile.name || "";
        document.getElementById("input-org-short-name").value = currentOrgProfile.short_name || "";
        document.getElementById("input-org-type").value = currentOrgProfile.organisation_type || "University";
        document.getElementById("input-org-website").value = currentOrgProfile.website || "";
        document.getElementById("input-org-contact-name").value = currentOrgProfile.contact_person || "";
        document.getElementById("input-org-contact-phone").value = currentOrgProfile.contact_phone || "";
        document.getElementById("input-org-desc").value = currentOrgProfile.description || "";
        document.getElementById("input-org-country").value = currentOrgProfile.country || "India";
        document.getElementById("input-org-city").value = currentOrgProfile.city || "";

        if (modal) {
            modal.style.display = "flex";
            modal.classList.remove("hidden");
        }
    }

    function closeOrgProfileModal() {
        const modal = document.getElementById("org-profile-modal");
        if (modal) {
            modal.style.display = "none";
            modal.classList.add("hidden");
        }
    }

    async function handleSaveOrgProfile(e) {
        e.preventDefault();
        const token = getAuthToken();
        const baseUrl = await getApiBaseUrl();

        const btnSave = document.getElementById("btn-save-org-profile");
        if (btnSave) {
            btnSave.disabled = true;
            btnSave.textContent = "Updating Profile...";
        }

        try {
            const payload = {
                name: document.getElementById("input-org-name").value.trim(),
                short_name: document.getElementById("input-org-short-name").value.trim(),
                organisation_type: document.getElementById("input-org-type").value,
                website: document.getElementById("input-org-website").value.trim(),
                contact_person: document.getElementById("input-org-contact-name").value.trim(),
                contact_phone: document.getElementById("input-org-contact-phone").value.trim(),
                description: document.getElementById("input-org-desc").value.trim(),
                country: document.getElementById("input-org-country").value.trim(),
                city: document.getElementById("input-org-city").value.trim()
            };

            const res = await fetch(`${baseUrl}/api/v1/organisations/me`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || "Failed to update profile.");
            }

            currentOrgProfile = data;
            renderOrgProfile(currentOrgProfile);
            showToast("Organisation profile updated successfully!", "success");
            closeOrgProfileModal();

            if (typeof window.loadFundingDirectory === 'function') {
                window.loadFundingDirectory();
            }
        } catch (err) {
            console.error("Error updating organisation profile:", err);
            showToast(err.message || "Failed to update profile.", "error");
        } finally {
            if (btnSave) {
                btnSave.disabled = false;
                btnSave.textContent = "Save Changes";
            }
        }
    }

    function escapeHtml(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }


    // ============================================================================
    // ENTERPRISE EDITION: BILLING, PO, GST INVOICES & CAMPUS SEAT MANAGEMENT
    // ============================================================================

    let allAllocatedSeats = [];

    window.switchOrgSubTab = function(tabName) {
        document.querySelectorAll(".org-subtab-btn").forEach(btn => {
            btn.classList.remove("active");
            btn.style.color = "var(--text-muted)";
            btn.style.borderBottomColor = "transparent";
        });
        
        const activeBtn = document.getElementById(`tab-btn-${tabName}`);
        if (activeBtn) {
            activeBtn.classList.add("active");
            activeBtn.style.color = "var(--text-primary)";
            activeBtn.style.borderBottomColor = "#6366f1";
        }

        const panes = ["schemes", "billing", "seats", "po"];
        panes.forEach(p => {
            const el = document.getElementById(`org-tab-pane-${p}`);
            if (el) {
                if (p === tabName) {
                    el.classList.remove("hidden");
                } else {
                    el.classList.add("hidden");
                }
            }
        });

        if (tabName === "billing") loadEnterpriseBilling();
        if (tabName === "seats") loadCampusSeats();
    };

    // 1. Load Enterprise Billing & Invoices
    async function loadEnterpriseBilling() {
        const token = getAuthToken();
        const baseUrl = getApiBaseUrl();
        const tbody = document.getElementById("billing-invoices-tbody");

        try {
            // Fetch contracts
            const ctrRes = await fetch(`${baseUrl}/api/v1/enterprise/contracts/me`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (ctrRes.ok) {
                const contracts = await ctrRes.json();
                if (contracts && contracts.length > 0) {
                    const activeCtr = contracts[0];
                    const planTitleEl = document.getElementById("billing-plan-title");
                    const statusBadgeEl = document.getElementById("billing-contract-status-badge");
                    const ctrNumEl = document.getElementById("billing-contract-num");
                    const ctrPoEl = document.getElementById("billing-contract-po");
                    const ctrPeriodEl = document.getElementById("billing-contract-period");

                    if (planTitleEl) planTitleEl.textContent = `${activeCtr.plan_name} (${activeCtr.total_seats === -1 ? 'Unlimited' : activeCtr.total_seats} Seats)`;
                    if (statusBadgeEl) {
                        statusBadgeEl.textContent = `${activeCtr.status.toUpperCase()} (${activeCtr.payment_terms || 'NET-30'})`;
                        statusBadgeEl.style.background = activeCtr.payment_status === 'paid' ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)';
                        statusBadgeEl.style.color = activeCtr.payment_status === 'paid' ? '#10b981' : '#f59e0b';
                    }
                    if (ctrNumEl) ctrNumEl.textContent = activeCtr.contract_number;
                    if (ctrPoEl) ctrPoEl.textContent = activeCtr.po_number || "Direct PO";
                    if (ctrPeriodEl) ctrPeriodEl.textContent = `${activeCtr.start_date ? activeCtr.start_date.split('T')[0] : '2026'} to ${activeCtr.end_date ? activeCtr.end_date.split('T')[0] : '2027'}`;
                }
            }

            // Fetch Invoices
            const invRes = await fetch(`${baseUrl}/api/v1/enterprise/invoices`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (invRes.ok) {
                const invoices = await invRes.json();
                renderInvoicesTable(invoices);
            }
        } catch (err) {
            console.error("Error loading enterprise billing:", err);
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="7" style="padding: 24px; text-align: center; color: #ef4444;">Failed to load invoices. Please ensure you are logged in.</td></tr>`;
            }
        }
    }

    window.refreshOrgInvoices = loadEnterpriseBilling;

    function renderInvoicesTable(invoices) {
        const tbody = document.getElementById("billing-invoices-tbody");
        if (!tbody) return;

        if (!invoices || invoices.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="padding: 30px; text-align: center; color: var(--text-muted);">No invoices generated yet. Submit a Purchase Order to create proforma tax invoice.</td></tr>`;
            return;
        }

        const baseUrl = getApiBaseUrl();
        const token = getAuthToken();

        tbody.innerHTML = invoices.map(inv => {
            const isPaid = inv.status === 'paid';
            const isPendingVerif = inv.status === 'pending_verification';
            const statusBg = isPaid ? 'rgba(16,185,129,0.15)' : (isPendingVerif ? 'rgba(99,102,241,0.15)' : 'rgba(245,158,11,0.15)');
            const statusColor = isPaid ? '#10b981' : (isPendingVerif ? '#818cf8' : '#f59e0b');
            const statusText = isPaid ? 'PAID & SETTLED' : (isPendingVerif ? 'UTR SUBMITTED (VERIFYING)' : 'PROFORMA / UNPAID');

            return `
                <tr style="border-bottom: 1px solid var(--border-color);">
                    <td style="padding: 12px 8px; font-family: monospace; font-weight: 700; color: var(--text-primary);">${escapeHtml(inv.invoice_number)}</td>
                    <td style="padding: 12px 8px; color: var(--text-secondary);">${inv.created_at ? inv.created_at.split('T')[0] : 'Today'}</td>
                    <td style="padding: 12px 8px; font-family: monospace; color: var(--text-secondary);">${escapeHtml(inv.po_reference || '-')}</td>
                    <td style="padding: 12px 8px; font-weight: 600; color: var(--text-primary);">₹${inv.subtotal_inr.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
                    <td style="padding: 12px 8px; color: var(--text-muted);">₹${inv.tax_inr.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
                    <td style="padding: 12px 8px;">
                        <span style="padding: 3px 10px; border-radius: 12px; font-size: 0.72rem; font-weight: 700; background: ${statusBg}; color: ${statusColor};">
                            ${statusText}
                        </span>
                    </td>
                    <td style="padding: 12px 8px; text-align: right; white-space: nowrap;">
                        <a href="${baseUrl}/api/v1/enterprise/invoices/${inv.id}/download?token=${token}" target="_blank" class="btn btn-outline" style="padding: 4px 10px; font-size: 0.78rem; border-radius: 6px; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; margin-right: 6px;">
                            <i class="fa-solid fa-file-pdf" style="color: #ef4444;"></i> Tax Invoice
                        </a>
                        ${!isPaid ? `
                            <button class="btn btn-primary" onclick="window.openWireModal('${inv.id}', '${inv.invoice_number}')" style="padding: 4px 10px; font-size: 0.78rem; border-radius: 6px; background: linear-gradient(135deg, #6366f1, #4f46e5);">
                                <i class="fa-solid fa-receipt"></i> Submit UTR
                            </button>
                        ` : ''}
                    </td>
                </tr>
            `;
        }).join('');
    }

    // 2. Load Campus Seats Management
    async function loadCampusSeats() {
        const token = getAuthToken();
        const baseUrl = getApiBaseUrl();

        try {
            const res = await fetch(`${baseUrl}/api/v1/enterprise/seats`, {
                headers: { "Authorization": `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                allAllocatedSeats = data.seats || [];
                
                // Update gauge
                const total = data.total_seats;
                const allocated = data.allocated_seats;
                const percent = total > 0 ? Math.min(100, Math.round((allocated / total) * 100)) : 0;

                const allocEl = document.getElementById("seat-gauge-allocated");
                const totalEl = document.getElementById("seat-gauge-total");
                const pctEl = document.getElementById("seat-gauge-percent");
                const barEl = document.getElementById("seat-gauge-bar");
                const badgeEl = document.getElementById("tab-seat-count-badge");

                if (allocEl) allocEl.textContent = allocated;
                if (totalEl) totalEl.textContent = total === -1 ? 'Unlimited' : total;
                if (pctEl) pctEl.textContent = total === -1 ? 'Unlimited' : `${percent}%`;
                if (barEl) barEl.style.width = total === -1 ? '100%' : `${percent}%`;
                if (badgeEl) badgeEl.textContent = allocated;

                renderSeatsTable(allAllocatedSeats);
            }
        } catch (err) {
            console.error("Error loading campus seats:", err);
        }
    }

    function renderSeatsTable(seats) {
        const tbody = document.getElementById("campus-seats-tbody");
        if (!tbody) return;

        if (!seats || seats.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="padding: 30px; text-align: center; color: var(--text-muted);">No faculty or scholars allocated yet. Use the form above to grant seats.</td></tr>`;
            return;
        }

        tbody.innerHTML = seats.map(s => {
            const roleLabels = {
                "faculty": "Faculty Member",
                "phd_scholar": "PhD Scholar",
                "researcher": "Researcher",
                "student": "Student"
            };

            return `
                <tr style="border-bottom: 1px solid var(--border-color);">
                    <td style="padding: 12px 8px; font-weight: 700; color: var(--text-primary);">${escapeHtml(s.user_name || 'Scholar')}</td>
                    <td style="padding: 12px 8px; font-family: monospace; color: #818cf8;">${escapeHtml(s.user_email)}</td>
                    <td style="padding: 12px 8px; color: var(--text-secondary);">${escapeHtml(s.department)}</td>
                    <td style="padding: 12px 8px;"><span style="padding: 2px 8px; border-radius: 10px; font-size: 0.72rem; font-weight: 700; background: rgba(99,102,241,0.1); color: #818cf8;">${roleLabels[s.seat_role] || s.seat_role}</span></td>
                    <td style="padding: 12px 8px; color: var(--text-muted); font-size: 0.8rem;">${s.assigned_at ? s.assigned_at.split('T')[0] : 'Active'}</td>
                    <td style="padding: 12px 8px;"><span style="color: #10b981; font-weight: 700; font-size: 0.78rem;"><i class="fa-solid fa-circle-check"></i> PRO Active</span></td>
                    <td style="padding: 12px 8px; text-align: right;">
                        <button class="btn btn-outline" onclick="window.revokeCampusSeat('${s.id}', '${escapeHtml(s.user_email)}')" style="padding: 4px 10px; font-size: 0.78rem; border-radius: 6px; color: #ef4444; border-color: rgba(239,68,68,0.3);">
                            <i class="fa-solid fa-user-xmark"></i> Revoke
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    window.filterSeatsTable = function(query) {
        const q = (query || "").toLowerCase().trim();
        if (!q) {
            renderSeatsTable(allAllocatedSeats);
            return;
        }
        const filtered = allAllocatedSeats.filter(s => 
            (s.user_email && s.user_email.toLowerCase().includes(q)) ||
            (s.user_name && s.user_name.toLowerCase().includes(q)) ||
            (s.department && s.department.toLowerCase().includes(q))
        );
        renderSeatsTable(filtered);
    };

    // 3. Purchase Order Modal & Submission
    window.openPoModal = function(planId, planName, price, seats) {
        const modal = document.getElementById("org-po-modal");
        document.getElementById("input-po-plan-id").value = planId;
        document.getElementById("input-po-plan-name").value = `${planName} - ₹${price.toLocaleString('en-IN')} / yr`;
        
        if (currentOrgProfile) {
            document.getElementById("input-po-contact-name").value = currentOrgProfile.contact_person || "";
            document.getElementById("input-po-contact-email").value = currentOrgProfile.domain_email || "";
            document.getElementById("input-po-billing-address").value = `${currentOrgProfile.name}, ${currentOrgProfile.city || ''} ${currentOrgProfile.country || 'India'}`.trim();
        }
        
        if (modal) {
            modal.style.display = "flex";
            modal.classList.remove("hidden");
        }
    };

    window.closePoModal = function() {
        const modal = document.getElementById("org-po-modal");
        if (modal) {
            modal.style.display = "none";
            modal.classList.add("hidden");
        }
    };

    async function handlePoSubmit(e) {
        e.preventDefault();
        const token = getAuthToken();
        const baseUrl = getApiBaseUrl();
        const btnSubmit = document.getElementById("btn-submit-po");

        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating Contract & Invoice...';
        }

        try {
            const payload = {
                plan_id: document.getElementById("input-po-plan-id").value,
                po_number: document.getElementById("input-po-number").value.trim(),
                gstin_tax_id: document.getElementById("input-po-gstin").value.trim() || null,
                billing_contact_name: document.getElementById("input-po-contact-name").value.trim(),
                billing_contact_email: document.getElementById("input-po-contact-email").value.trim(),
                billing_address: document.getElementById("input-po-billing-address").value.trim(),
                payment_terms: document.getElementById("select-po-payment-terms").value,
                currency: "INR"
            };

            const res = await fetch(`${baseUrl}/api/v1/enterprise/contracts/create-po`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || "Failed to create Purchase Order contract.");
            }

            showToast("Purchase Order approved! Institutional contract & GST Tax invoice generated.", "success");
            window.closePoModal();
            window.switchOrgSubTab("billing");
        } catch (err) {
            console.error("Error submitting PO:", err);
            showToast(err.message || "Failed to submit Purchase Order.", "error");
        } finally {
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = '<i class="fa-solid fa-check"></i> Generate Contract & Invoices';
            }
        }
    }

    // 4. Wire UTR Modal & Submission
    window.openWireModal = function(invId, invNum) {
        const modal = document.getElementById("org-wire-modal");
        document.getElementById("input-wire-inv-id").value = invId;
        const lbl = document.getElementById("wire-modal-inv-num");
        if (lbl) lbl.textContent = `Invoice #: ${invNum}`;

        if (modal) {
            modal.style.display = "flex";
            modal.classList.remove("hidden");
        }
    };

    window.closeWireModal = function() {
        const modal = document.getElementById("org-wire-modal");
        if (modal) {
            modal.style.display = "none";
            modal.classList.add("hidden");
        }
    };

    async function handleWireSubmit(e) {
        e.preventDefault();
        const token = getAuthToken();
        const baseUrl = getApiBaseUrl();
        const btnSubmit = document.getElementById("btn-submit-wire");
        const invId = document.getElementById("input-wire-inv-id").value;

        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Submitting...';
        }

        try {
            const payload = {
                payment_reference: document.getElementById("input-wire-ref").value.trim(),
                payment_notes: document.getElementById("input-wire-notes").value.trim()
            };

            const res = await fetch(`${baseUrl}/api/v1/enterprise/invoices/${invId}/submit-offline-payment`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || "Failed to submit wire reference.");
            }

            showToast("Bank Wire UTR reference submitted successfully! Invoice is pending verification.", "success");
            window.closeWireModal();
            loadEnterpriseBilling();
        } catch (err) {
            console.error("Error submitting wire reference:", err);
            showToast(err.message || "Failed to submit wire reference.", "error");
        } finally {
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = '<i class="fa-solid fa-check"></i> Submit Reference';
            }
        }
    }

    // 5. Seat Allocation & Revocation
    async function handleAllocateSeatSubmit(e) {
        e.preventDefault();
        const token = getAuthToken();
        const baseUrl = getApiBaseUrl();
        const btnSubmit = document.getElementById("btn-submit-seat-alloc");

        if (btnSubmit) {
            btnSubmit.disabled = true;
            btnSubmit.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Allocating...';
        }

        try {
            const payload = {
                user_email: document.getElementById("input-seat-email").value.trim(),
                user_name: document.getElementById("input-seat-name").value.trim() || null,
                department: document.getElementById("input-seat-dept").value.trim() || "Academic Faculty",
                seat_role: document.getElementById("select-seat-role").value
            };

            const res = await fetch(`${baseUrl}/api/v1/enterprise/seats/allocate`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify(payload)
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || "Failed to allocate seat.");
            }

            showToast(`Enterprise Pro seat successfully granted to ${payload.user_email}!`, "success");
            document.getElementById("input-seat-email").value = "";
            document.getElementById("input-seat-name").value = "";
            loadCampusSeats();
        } catch (err) {
            console.error("Error allocating seat:", err);
            showToast(err.message || "Could not allocate seat.", "error");
        } finally {
            if (btnSubmit) {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = '<i class="fa-solid fa-plus"></i> Grant Seat';
            }
        }
    }

    window.revokeCampusSeat = async function(seatId, email) {
        if (!confirm(`Are you sure you want to revoke the Enterprise license from ${email}? The license will return to your institutional pool.`)) {
            return;
        }

        const token = getAuthToken();
        const baseUrl = getApiBaseUrl();

        try {
            const res = await fetch(`${baseUrl}/api/v1/enterprise/seats/${seatId}`, {
                method: "DELETE",
                headers: { "Authorization": `Bearer ${token}` }
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Failed to revoke seat.");
            }

            showToast(`License revoked for ${email} and returned to pool.`, "info");
            loadCampusSeats();
        } catch (err) {
            console.error("Error revoking seat:", err);
            showToast(err.message || "Failed to revoke seat.", "error");
        }
    };

    
    window.enterOrgDemoMode = function() {
        const demoOrg = {
            id: "demo-chitkara-univ",
            name: "Chitkara University",
            short_name: "CU",
            domain_email: "research.dean@chitkara.edu.in",
            domain: "chitkara.edu.in",
            organisation_type: "University",
            website: "https://www.chitkara.edu.in",
            contact_person: "Dr. Research Director",
            contact_phone: "+91 9876543210",
            description: "Premier NAAC A+ Accredited University promoting high-impact research, Scopus Q1/Q2 journal publications, and innovation patents.",
            country: "India",
            city: "Punjab"
        };
        currentOrgProfile = demoOrg;
        
        const notLoggedContainer = document.getElementById("org-not-logged-in-state");
        const loggedContainer = document.getElementById("org-logged-in-state");
        if (notLoggedContainer) notLoggedContainer.classList.add("hidden");
        if (loggedContainer) loggedContainer.classList.remove("hidden");
        
        renderOrgProfile(demoOrg);
        loadOrgSchemes();
        loadEnterpriseBilling();
        loadCampusSeats();
        showToast("Switched to Chitkara University Organisation Portal!", "success");
    };

    window.openSchemeModal = openSchemeModal;
    window.closeSchemeModal = closeSchemeModal;
    window.loadOrgData = loadOrgData;
    window.initOrganisationDashboard = initOrganisationDashboard;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initOrganisationDashboard);
    } else {
        initOrganisationDashboard();
    }
})();
