/**
 * ==============================================================================
 * LEMMA AI ADS & SPONSOR CONFIGURATION ENGINE
 * ==============================================================================
 * Edit this file anytime to change sponsors, headlines, links, or toggle ads on/off.
 * ==============================================================================
 */

const LemmaAdsConfig = {
    // Set to false to disable all ads globally (e.g. for Pro subscribers)
    enabled: true,

    // --------------------------------------------------------------------------
    // 1. Landing Page: Sponsored Spotlight Card
    // --------------------------------------------------------------------------
    landingSpotlight: {
        badge: "⭐ Sponsored Academic Partner",
        sponsorName: "Overleaf Cloud LaTeX",
        headline: "Write, Collaborate & Format IEEE Research Papers 3x Faster",
        description: "The gold standard collaborative LaTeX cloud editor for university researchers, labs, and students. Auto-sync bibliographies with Zotero and Mendeley.",
        ctaText: "Claim Student Pro Plan →",
        ctaUrl: "https://www.overleaf.com",
        iconClass: "fa-solid fa-graduation-cap"
    },

    // --------------------------------------------------------------------------
    // 2. In-Workspace: Loading State Ad (Shown during Paper Generation & Scans)
    // --------------------------------------------------------------------------
    workspaceLoading: {
        badge: "📢 Sponsored Computing Partner",
        sponsorName: "RunPod Cloud GPUs",
        headline: "Need high-speed GPU compute for your ML research models?",
        description: "On-demand A100 & H100 cloud clusters starting at $0.20/hr with instant PyTorch & Jupyter environments.",
        ctaText: "Get $10 Free Credits →",
        ctaUrl: "https://www.runpod.io",
        iconClass: "fa-solid fa-server"
    },

    // --------------------------------------------------------------------------
    // 3. Freemium "Lemma Pro" Upgrade Modal
    // --------------------------------------------------------------------------
    proPricing: {
        title: "Upgrade to Lemma Pro",
        subtitle: "Unlock a distraction-free research studio with dedicated compute power.",
        monthlyPrice: "₹199 / month",
        annualPrice: "₹1,999 / year (Save 20%)",
        features: [
            "🚫 100% Ad-Free Research Experience",
            "⚡ Priority GPU & Generator Queue (3x faster compile)",
            "📄 Unlimited IEEE & Springer Paper Restructuring",
            "🔍 Unlimited Plagiarism & Dual-Tier Similarity Scans",
            "💾 Direct Camera-Ready PDF, DOCX & BibTeX Exports",
            "🔒 Strict Enterprise Data Isolation & Privacy"
        ]
    }
};

// ------------------------------------------------------------------------------
// Ads Engine Rendering & Modal Controller
// ------------------------------------------------------------------------------
const LemmaAdsEngine = {
    init() {
        if (!LemmaAdsConfig.enabled) return;

        // Render landing ad if container exists
        const landingContainer = document.getElementById("landing-ad-container");
        if (landingContainer) {
            this.renderLandingAd(landingContainer);
        }

        // Render workspace ad if container exists
        const workspaceContainer = document.getElementById("workspace-ad-box");
        if (workspaceContainer) {
            this.renderWorkspaceAd(workspaceContainer);
        }
    },

    renderLandingAd(container) {
        const ad = LemmaAdsConfig.landingSpotlight;
        container.innerHTML = `
            <div class="vertical-ad-card" id="landing-vertical-ad">
                <div class="ad-top-bar">
                    <span class="ad-badge">${ad.badge}</span>
                    <div class="ad-actions-row">
                        <button class="ad-remove-btn" onclick="LemmaAdsEngine.openProModal()" title="Remove Ads with Pro">
                            <i class="fa-solid fa-bolt"></i> Remove
                        </button>
                        <button class="ad-close-btn" onclick="document.getElementById('landing-vertical-ad').style.display='none'" title="Dismiss">
                            &times;
                        </button>
                    </div>
                </div>
                
                <div class="ad-sponsor-header">
                    <div class="ad-icon-box">
                        <i class="${ad.iconClass}"></i>
                    </div>
                    <div class="ad-sponsor-details">
                        <div class="ad-sponsor-label">Featured Partner</div>
                        <div class="ad-sponsor-name">${ad.sponsorName}</div>
                    </div>
                </div>

                <div class="ad-body-vertical">
                    <h3 class="ad-headline-vert">${ad.headline}</h3>
                    <p class="ad-desc-vert">${ad.description}</p>
                    
                    <div class="ad-perks-list">
                        <div class="ad-perk-item"><i class="fa-solid fa-check"></i> IEEE & Springer Templates</div>
                        <div class="ad-perk-item"><i class="fa-solid fa-check"></i> 1-Click LaTeX & PDF Export</div>
                        <div class="ad-perk-item"><i class="fa-solid fa-check"></i> Real-time Team Writing</div>
                    </div>

                    <a href="${ad.ctaUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-primary ad-cta-btn-vert">
                        ${ad.ctaText}
                    </a>
                </div>
            </div>
        `;
    },

    renderWorkspaceAd(container) {
        const ad = LemmaAdsConfig.workspaceLoading;
        container.innerHTML = `
            <div class="workspace-ad-card">
                <div class="ws-ad-header">
                    <span class="ws-ad-badge">${ad.badge}</span>
                    <button class="ws-ad-remove-btn" onclick="LemmaAdsEngine.openProModal()" title="Remove Ads">
                        Remove Ads ⚡
                    </button>
                </div>
                <div class="ws-ad-main">
                    <div class="ws-ad-icon"><i class="${ad.iconClass}"></i></div>
                    <div class="ws-ad-info">
                        <div class="ws-ad-sponsor">${ad.sponsorName}</div>
                        <div class="ws-ad-title">${ad.headline}</div>
                        <div class="ws-ad-desc">${ad.description}</div>
                    </div>
                </div>
                <div class="ws-ad-footer">
                    <a href="${ad.ctaUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline ws-ad-cta">
                        ${ad.ctaText}
                    </a>
                </div>
            </div>
        `;
    },

    openProModal() {
        let modal = document.getElementById("lemma-pro-modal");
        if (!modal) {
            this.createProModal();
            modal = document.getElementById("lemma-pro-modal");
        }
        if (modal) modal.classList.add("show");
    },

    closeProModal() {
        const modal = document.getElementById("lemma-pro-modal");
        if (modal) modal.classList.remove("show");
    },

    createProModal() {
        const pro = LemmaAdsConfig.proPricing;
        const featuresHtml = pro.features.map(f => `<li><i class="fa-solid fa-circle-check"></i> ${f}</li>`).join("");

        const modalDiv = document.createElement("div");
        modalDiv.id = "lemma-pro-modal";
        modalDiv.className = "pro-modal-backdrop";
        modalDiv.innerHTML = `
            <div class="pro-modal-card">
                <button class="pro-modal-close" onclick="LemmaAdsEngine.closeProModal()">&times;</button>
                <div class="pro-modal-header">
                    <div class="pro-badge-pill">LEMMA PRO</div>
                    <h2>${pro.title}</h2>
                    <p>${pro.subtitle}</p>
                </div>
                <div class="pro-pricing-box">
                    <div class="pricing-option active">
                        <div class="price-val">${pro.monthlyPrice}</div>
                        <div class="price-lbl">Monthly Plan</div>
                    </div>
                    <div class="pricing-option">
                        <div class="price-val">${pro.annualPrice}</div>
                        <div class="price-lbl">Annual Commitment</div>
                    </div>
                </div>
                <ul class="pro-features-list">
                    ${featuresHtml}
                </ul>
                <button class="btn btn-primary pro-upgrade-btn" onclick="alert('Payment Gateway Integration: Ready for Razorpay / Stripe checkout!'); LemmaAdsEngine.closeProModal();">
                    Upgrade to Lemma Pro Now
                </button>
                <p class="pro-modal-footer">Cancel anytime. 7-day academic money-back guarantee.</p>
            </div>
        `;

        document.body.appendChild(modalDiv);

        // Close on outside backdrop click
        modalDiv.addEventListener("click", (e) => {
            if (e.target === modalDiv) {
                LemmaAdsEngine.closeProModal();
            }
        });
    }
};

// Auto-initialize when DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    LemmaAdsEngine.init();
});
