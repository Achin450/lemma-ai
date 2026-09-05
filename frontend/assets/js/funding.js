/**
 * Lemma Research Publishing Incentives & Grants Hub (funding.js)
 * 
 * Features:
 * - Real-time filtering by region (India / International), min payout (>= 10k), journal tier & search
 * - Instant currency conversion toggle (₹ INR / $ USD)
 * - Deep dive modal for tier-by-tier reward matrix & official policy links
 * - Zero memory footprint (<2MB), high-performance client rendering
 */

(function () {
    let allUniversities = [];
    let activeCurrency = "INR"; // "INR" or "USD"
    let selectedRegion = "All";
    let minAmount = 10000;
    let selectedTier = "";
    let searchQuery = "";

    function getApiBaseUrl() {
        if (window.APIConfigManager && typeof window.APIConfigManager.getApiBaseUrl === 'function') {
            return window.APIConfigManager.getApiBaseUrl();
        }
        return window.location.origin.includes('localhost') || window.location.origin.includes('127.0.0.1')
            ? 'http://localhost:8000'
            : window.location.origin;
    }

    function formatAmount(amountInr, amountUsd) {
        if (activeCurrency === "USD") {
            return `$${amountUsd.toLocaleString()}`;
        }
        // Format INR with commas (e.g. ₹1,00,000)
        return `₹${amountInr.toLocaleString('en-IN')}`;
    }

    async function loadFundingDirectory() {
        try {
            const baseUrl = await getApiBaseUrl();
            
            // Parallel fetch for universities and stats
            const [unisRes, statsRes] = await Promise.all([
                fetch(`${baseUrl}/api/v1/funding/universities`),
                fetch(`${baseUrl}/api/v1/funding/stats`)
            ]);

            if (unisRes.ok) {
                allUniversities = await unisRes.json();
                filterAndRender();
            }

            if (statsRes.ok) {
                const stats = await statsRes.json();
                renderStatsRibbon(stats);
            }
        } catch (err) {
            console.error("Error loading funding directory:", err);
            showToastMessage("Could not load publishing grants. Please check network connection.", "error");
        }
    }

    function renderStatsRibbon(stats) {
        const totalEl = document.getElementById("stat-total-unis");
        const maxEl = document.getElementById("stat-max-bounty");
        const regionEl = document.getElementById("stat-region-breakdown");

        if (totalEl) totalEl.textContent = stats.total_institutions;
        if (maxEl) {
            maxEl.textContent = activeCurrency === "USD" 
                ? `$${stats.max_bounty_usd.toLocaleString()}`
                : `₹${stats.max_bounty_inr.toLocaleString('en-IN')}`;
        }
        if (regionEl) {
            regionEl.textContent = `${stats.indian_institutions} 🇮🇳 / ${stats.foreign_institutions} 🌍`;
        }
    }

    function filterAndRender() {
        const filtered = allUniversities.filter(u => {
            // Min amount filter
            if (u.max_amount_inr < minAmount) return false;

            // Region filter
            if (selectedRegion !== "All" && u.region.toLowerCase() !== selectedRegion.toLowerCase()) {
                return false;
            }

            // Journal Tier filter
            if (selectedTier) {
                const q = selectedTier.toLowerCase();
                const matched = u.accepted_indexing.some(idx => idx.toLowerCase().includes(q))
                    || u.reward_tiers.some(t => t.tier_name.toLowerCase().includes(q) || t.criteria.toLowerCase().includes(q));
                if (!matched) return false;
            }

            // Search query filter
            if (searchQuery) {
                const sq = searchQuery.toLowerCase();
                const searchMatched = u.name.toLowerCase().includes(sq)
                    || u.short_name.toLowerCase().includes(sq)
                    || u.country.toLowerCase().includes(sq)
                    || u.city.toLowerCase().includes(sq)
                    || u.accepted_indexing.some(idx => idx.toLowerCase().includes(sq))
                    || u.key_perks.some(p => p.toLowerCase().includes(sq));
                if (!searchMatched) return false;
            }

            return true;
        });

        renderCards(filtered);
    }

    function renderCards(items) {
        const container = document.getElementById("funding-cards-grid");
        const emptyState = document.getElementById("funding-empty-state");

        if (!container) return;
        container.innerHTML = "";

        if (items.length === 0) {
            if (emptyState) emptyState.classList.remove("hidden");
            return;
        }

        if (emptyState) emptyState.classList.add("hidden");

        items.forEach(uni => {
            const card = document.createElement("div");
            card.className = "glass-card funding-card";
            card.style.background = "var(--bg-secondary)";
            card.style.border = "1px solid var(--border-color)";
            card.style.borderRadius = "16px";
            card.style.padding = "1.5rem";
            card.style.display = "flex";
            card.style.flexDirection = "column";
            card.style.justifyContent = "space-between";
            card.style.transition = "transform 0.2s ease, box-shadow 0.2s ease";
            card.style.boxShadow = "0 8px 24px rgba(0,0,0,0.1)";

            const maxBountyDisplay = formatAmount(uni.max_amount_inr, uni.max_amount_usd);
            const minBountyDisplay = formatAmount(uni.min_amount_inr, uni.min_amount_usd);

            const indexingHtml = uni.accepted_indexing.slice(0, 4).map(idx => 
                `<span style="font-size: 0.72rem; padding: 2px 8px; border-radius: 6px; background: rgba(99, 102, 241, 0.12); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.25); font-weight: 600;">${idx}</span>`
            ).join("");

            const perksHtml = uni.key_perks.slice(0, 2).map(p => 
                `<li style="font-size: 0.8rem; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
                    <i class="fa-solid fa-check" style="color: #10b981; font-size: 0.75rem;"></i> ${p}
                </li>`
            ).join("");

            card.innerHTML = `
                <div>
                    <!-- Top Row: Flag + Name + Region Badge -->
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 0.75rem;">
                        <div style="display: flex; align-items: center; gap: 10px;">
                            <span style="font-size: 1.8rem; line-height: 1;">${uni.flag_emoji}</span>
                            <div>
                                <h3 style="margin: 0; font-size: 1.08rem; font-weight: 800; color: var(--text-primary); line-height: 1.25;">
                                    ${uni.name}
                                </h3>
                                <span style="font-size: 0.78rem; color: var(--text-muted);">
                                    <i class="fa-solid fa-location-dot" style="font-size: 0.72rem;"></i> ${uni.city}, ${uni.country}
                                </span>
                            </div>
                        </div>
                        <span style="font-size: 0.72rem; font-weight: 700; padding: 3px 8px; border-radius: 12px; background: ${uni.region === 'India' ? 'rgba(245, 158, 11, 0.12)' : 'rgba(59, 130, 246, 0.12)'}; color: ${uni.region === 'India' ? '#f59e0b' : '#60a5fa'}; border: 1px solid ${uni.region === 'India' ? 'rgba(245, 158, 11, 0.3)' : 'rgba(59, 130, 246, 0.3)'};">
                            ${uni.region}
                        </span>
                    </div>

                    <!-- Bounty Highlight Pill -->
                    <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 10px; padding: 0.75rem 1rem; margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-size: 0.68rem; font-weight: 700; text-transform: uppercase; color: #10b981; letter-spacing: 0.5px; display: block;">Maximum Bounty</span>
                            <span style="font-size: 1.35rem; font-weight: 800; color: #10b981; line-height: 1.2;">Up to ${maxBountyDisplay}</span>
                        </div>
                        <div style="text-align: right;">
                            <span style="font-size: 0.68rem; color: var(--text-muted); display: block;">Base Tier</span>
                            <span style="font-size: 0.85rem; font-weight: 700; color: var(--text-primary);">${minBountyDisplay}</span>
                        </div>
                    </div>

                    <!-- Indexing Tags -->
                    <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 0.85rem;">
                        ${indexingHtml}
                    </div>

                    <!-- Perks List -->
                    <ul style="list-style: none; padding: 0; margin: 0 0 1.25rem 0;">
                        ${perksHtml}
                    </ul>
                </div>

                <!-- Action Button -->
                <button class="btn btn-outline btn-full btn-view-slabs" data-id="${uni.id}" style="width: 100%; padding: 0.6rem; font-size: 0.85rem; font-weight: 700; border-radius: 8px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; border-color: var(--border-color); background: rgba(255,255,255,0.02); color: var(--text-primary);">
                    <i class="fa-solid fa-list-check" style="color: #10b981;"></i> View Reward Slabs &amp; Apply
                </button>
            `;

            // Hover effects
            card.addEventListener("mouseenter", () => {
                card.style.transform = "translateY(-4px)";
                card.style.borderColor = "rgba(16, 185, 129, 0.4)";
                card.style.boxShadow = "0 12px 30px rgba(16, 185, 129, 0.15)";
            });
            card.addEventListener("mouseleave", () => {
                card.style.transform = "translateY(0)";
                card.style.borderColor = "var(--border-color)";
                card.style.boxShadow = "0 8px 24px rgba(0,0,0,0.1)";
            });

            // Wire up slab button
            const btn = card.querySelector(".btn-view-slabs");
            if (btn) {
                btn.addEventListener("click", () => openDetailModal(uni));
            }

            container.appendChild(card);
        });
    }

    function openDetailModal(uni) {
        const modal = document.getElementById("funding-detail-modal");
        if (!modal) return;

        document.getElementById("modal-uni-flag").textContent = uni.flag_emoji;
        document.getElementById("modal-uni-name").textContent = uni.name;
        document.getElementById("modal-uni-location").textContent = `${uni.city}, ${uni.country} • ${uni.region}`;
        document.getElementById("modal-uni-max-bounty").textContent = `Up to ${formatAmount(uni.max_amount_inr, uni.max_amount_usd)}`;
        document.getElementById("modal-uni-eligibility").textContent = uni.eligibility_type;
        document.getElementById("modal-uni-notes").textContent = uni.notes || "Standard institutional affiliation rules apply. Authors must verify indexing before applying.";
        document.getElementById("modal-uni-email").textContent = uni.contact_email || "Contact research dean";

        const linkEl = document.getElementById("modal-uni-link");
        if (linkEl) {
            linkEl.href = uni.official_policy_url || "#";
        }

        // Render Tiers Table
        const tbody = document.getElementById("modal-uni-tiers-tbody");
        if (tbody) {
            tbody.innerHTML = uni.reward_tiers.map(tier => `
                <tr style="border-bottom: 1px solid var(--border-color);">
                    <td style="padding: 10px 14px;">
                        <strong style="color: var(--text-primary); display: block; font-size: 0.88rem;">${tier.tier_name}</strong>
                        <span style="color: var(--text-muted); font-size: 0.78rem;">${tier.criteria}</span>
                    </td>
                    <td style="padding: 10px 14px; font-weight: 800; color: #10b981; font-size: 0.95rem;">
                        ${formatAmount(tier.amount_inr, tier.amount_usd)}
                    </td>
                    <td style="padding: 10px 14px;">
                        <span style="font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; background: rgba(16, 185, 129, 0.12); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.25); font-weight: 600;">
                            ${tier.payout_type}
                        </span>
                    </td>
                </tr>
            `).join("");
        }

        // Render Indexing Tags
        const tagsContainer = document.getElementById("modal-uni-indexing-tags");
        if (tagsContainer) {
            tagsContainer.innerHTML = uni.accepted_indexing.map(idx => 
                `<span style="font-size: 0.75rem; padding: 3px 10px; border-radius: 8px; background: rgba(99, 102, 241, 0.12); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.25); font-weight: 600;">${idx}</span>`
            ).join("");
        }

        modal.classList.remove("hidden");
    }

    function closeDetailModal() {
        const modal = document.getElementById("funding-detail-modal");
        if (modal) modal.classList.add("hidden");
    }

    function initFundingHub() {
        const navFunding = document.getElementById("nav-funding");
        if (navFunding) {
            navFunding.addEventListener("click", (e) => {
                e.preventDefault();
                document.querySelectorAll(".sidebar-nav li").forEach(el => el.classList.remove("active"));
                navFunding.classList.add("active");
                if (typeof window.showView === 'function') {
                    window.showView("funding-view");
                } else {
                    document.querySelectorAll(".workspace-view").forEach(v => v.classList.add("hidden"));
                    const target = document.getElementById("funding-view");
                    if (target) target.classList.remove("hidden");
                }
                loadFundingDirectory();
            });
        }

        // Search Input
        const searchInput = document.getElementById("funding-search-input");
        if (searchInput) {
            searchInput.addEventListener("input", (e) => {
                searchQuery = e.target.value.trim();
                filterAndRender();
            });
        }

        // Currency Toggle
        const btnInr = document.getElementById("btn-curr-inr");
        const btnUsd = document.getElementById("btn-curr-usd");

        if (btnInr && btnUsd) {
            btnInr.addEventListener("click", () => {
                activeCurrency = "INR";
                btnInr.style.background = "#10b981";
                btnInr.style.color = "#fff";
                btnUsd.style.background = "transparent";
                btnUsd.style.color = "var(--text-secondary)";
                filterAndRender();
            });

            btnUsd.addEventListener("click", () => {
                activeCurrency = "USD";
                btnUsd.style.background = "#10b981";
                btnUsd.style.color = "#fff";
                btnInr.style.background = "transparent";
                btnInr.style.color = "var(--text-secondary)";
                filterAndRender();
            });
        }

        // Region Pills
        document.querySelectorAll(".funding-region-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll(".funding-region-btn").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                selectedRegion = btn.getAttribute("data-region") || "All";
                filterAndRender();
            });
        });

        // Min Amount Select
        const minAmountSelect = document.getElementById("funding-min-amount-select");
        if (minAmountSelect) {
            minAmountSelect.addEventListener("change", (e) => {
                minAmount = parseInt(e.target.value, 10) || 10000;
                filterAndRender();
            });
        }

        // Tier Select
        const tierSelect = document.getElementById("funding-tier-select");
        if (tierSelect) {
            tierSelect.addEventListener("change", (e) => {
                selectedTier = e.target.value;
                filterAndRender();
            });
        }

        // Reset Filters Button
        const btnReset = document.getElementById("btn-reset-funding-filters");
        if (btnReset) {
            btnReset.addEventListener("click", () => {
                if (searchInput) searchInput.value = "";
                searchQuery = "";
                selectedRegion = "All";
                minAmount = 10000;
                selectedTier = "";
                if (minAmountSelect) minAmountSelect.value = "10000";
                if (tierSelect) tierSelect.value = "";
                document.querySelectorAll(".funding-region-btn").forEach(b => {
                    b.classList.toggle("active", b.getAttribute("data-region") === "All");
                });
                filterAndRender();
            });
        }

        // Modal Close Button & Backdrop Click
        const btnCloseModal = document.getElementById("btn-close-funding-modal");
        const modalBackdrop = document.getElementById("funding-detail-modal");

        if (btnCloseModal) {
            btnCloseModal.addEventListener("click", closeDetailModal);
        }
        if (modalBackdrop) {
            modalBackdrop.addEventListener("click", (e) => {
                if (e.target === modalBackdrop) closeDetailModal();
            });
        }

        // Expose global loader
        window.loadFundingDirectory = loadFundingDirectory;
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initFundingHub);
    } else {
        initFundingHub();
    }
})();
