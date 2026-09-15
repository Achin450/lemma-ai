/**
 * ==============================================================================
 * LEMMA AI PERSONAL ACCOUNT PAYMENT & BILLING STUDIO
 * ==============================================================================
 * Handles subscriptions, quota tracking, checkout, Stripe/Razorpay gateways,
 * and academic tax receipts.
 * ==============================================================================
 */

const LemmaPaymentApp = {
    plans: [],
    subscription: null,
    usage: null,
    invoices: [],

    selectedCycle: "monthly",
    selectedCurrency: "INR",
    checkoutPlanId: "pro_monthly",
    selectedGateway: "razorpay",
    selectedPaymentMethod: "upi",

    getApiBase() {
        if (typeof API_BASE_URL !== "undefined" && API_BASE_URL) {
            return API_BASE_URL;
        }
        return window.location.origin;
    },

    getAuthHeaders() {
        const token = localStorage.getItem("lemma_access_token") || localStorage.getItem("token");
        const headers = { "Content-Type": "application/json" };
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }
        return headers;
    },

    async init() {
        await this.loadPlans();
        await this.loadBillingData();

        // Listen for workspace tab activations
        const navBilling = document.getElementById("nav-billing");
        if (navBilling) {
            navBilling.addEventListener("click", (e) => {
                e.preventDefault();
                this.showBillingStudio();
            });
        }

        // Check if URL hash or session requested billing
        const hash = (window.location.hash || "").toLowerCase();
        const pendingView = sessionStorage.getItem("lemma_active_view");
        if (hash === "#billing" || hash === "#pricing" || hash === "#plans" || pendingView === "billing-view") {
            sessionStorage.removeItem("lemma_active_view");
            setTimeout(() => {
                this.showBillingStudio();
            }, 150);
        }
    },

    showBillingStudio(targetPlanId = null) {
        if (typeof showView === "function") {
            showView("billing-view");
        } else {
            document.querySelectorAll(".workspace-view").forEach(v => v.classList.add("hidden"));
            const bv = document.getElementById("billing-view");
            if (bv) bv.classList.remove("hidden");
        }

        // Highlight sidebar active tab
        document.querySelectorAll(".sidebar-nav .nav-item").forEach(item => item.classList.remove("active"));
        const navBilling = document.getElementById("nav-billing");
        if (navBilling) navBilling.classList.add("active");

        this.loadBillingData();

        if (targetPlanId) {
            setTimeout(() => {
                this.scrollToPlans();
                this.openCheckout(targetPlanId);
            }, 200);
        }
    },

    scrollToPlans() {
        const anchor = document.getElementById("pricing-plans-anchor");
        if (anchor) {
            anchor.scrollIntoView({ behavior: "smooth" });
        }
    },

    async loadPlans() {
        try {
            const res = await fetch(`${this.getApiBase()}/api/v1/payment/plans`);
            if (res.ok) {
                const data = await res.json();
                this.plans = data.plans || [];
                this.renderPlans();
            }
        } catch (e) {
            console.error("Failed to load pricing plans:", e);
        }
    },

    async loadBillingData() {
        const token = localStorage.getItem("lemma_access_token") || localStorage.getItem("token");
        if (!token) {
            this.renderGuestState();
            return;
        }

        try {
            const headers = this.getAuthHeaders();

            // Parallel fetch
            const [subRes, usageRes, invRes] = await Promise.all([
                fetch(`${this.getApiBase()}/api/v1/payment/subscription`, { headers }),
                fetch(`${this.getApiBase()}/api/v1/payment/usage`, { headers }),
                fetch(`${this.getApiBase()}/api/v1/payment/invoices`, { headers })
            ]);

            if (subRes.ok) {
                this.subscription = await subRes.json();
                this.updateSubscriptionUI();
            }

            if (usageRes.ok) {
                this.usage = await usageRes.json();
                this.updateUsageUI();
            }

            if (invRes.ok) {
                const invData = await invRes.json();
                this.invoices = invData.invoices || [];
                this.renderInvoices();
            }
        } catch (err) {
            console.error("Error fetching billing details:", err);
        }
    },

    renderGuestState() {
        const badge = document.getElementById("sidebar-plan-badge");
        if (badge) badge.textContent = "GUEST";

        const planName = document.getElementById("current-plan-name");
        if (planName) planName.textContent = "Free Guest Session";

        const planDesc = document.getElementById("current-plan-desc");
        if (planDesc) planDesc.textContent = "Sign in to activate permanent quotas and subscribe to Lemma Pro.";

        this.renderPlans();
    },

    updateSubscriptionUI() {
        if (!this.subscription) return;

        const sub = this.subscription;
        const isPro = sub.is_pro;

        // Update sidebar badge
        const sideBadge = document.getElementById("sidebar-plan-badge");
        if (sideBadge) {
            sideBadge.textContent = isPro ? (sub.plan_id.includes("annual") ? "PRO ANNUAL" : "PRO") : "FREE";
            sideBadge.style.background = isPro ? "rgba(16, 185, 129, 0.2)" : "rgba(99, 102, 241, 0.2)";
            sideBadge.style.color = isPro ? "#10b981" : "var(--accent-purple)";
            sideBadge.style.borderColor = isPro ? "rgba(16, 185, 129, 0.4)" : "rgba(99, 102, 241, 0.4)";
        }

        // Update User Role Tag in Header Dropdown if Pro
        const dropdownRole = document.getElementById("dropdown-user-role");
        if (dropdownRole && isPro) {
            dropdownRole.textContent = "Scholar Pro";
            dropdownRole.style.background = "linear-gradient(135deg, #10b981, #059669)";
            dropdownRole.style.color = "#ffffff";
        }

        // Active Plan Card
        const planName = document.getElementById("current-plan-name");
        if (planName) planName.textContent = sub.plan_name;

        const planBadge = document.getElementById("current-plan-badge");
        if (planBadge) {
            planBadge.textContent = isPro ? "LEMMA PRO" : "FREE EXPLORER";
            planBadge.className = isPro ? "plan-badge-tag pro" : "plan-badge-tag";
        }

        const cycleVal = document.getElementById("current-billing-cycle");
        if (cycleVal) {
            cycleVal.textContent = sub.billing_cycle === "annual" ? "Annual Commitment (Save 20%)" : (sub.billing_cycle === "monthly" ? "Monthly Billing" : "Free Forever");
        }

        const periodEndVal = document.getElementById("current-period-end");
        if (periodEndVal) {
            if (sub.current_period_end) {
                const d = new Date(sub.current_period_end);
                periodEndVal.textContent = d.toLocaleDateString("en-US", { year: 'numeric', month: 'short', day: 'numeric' });
            } else {
                periodEndVal.textContent = "Permanent";
            }
        }

        const renewStatus = document.getElementById("current-renewal-status");
        const cancelBtn = document.getElementById("btn-cancel-sub-action");
        if (renewStatus) {
            if (sub.cancel_at_period_end) {
                renewStatus.textContent = "Cancels at period end";
                renewStatus.style.color = "#ef4444";
                if (cancelBtn) {
                    cancelBtn.style.display = "inline-block";
                    cancelBtn.textContent = "Reactivate Auto-Renew";
                    cancelBtn.className = "btn btn-outline";
                }
            } else if (isPro) {
                renewStatus.textContent = "Active (Auto-renews)";
                renewStatus.style.color = "#10b981";
                if (cancelBtn) {
                    cancelBtn.style.display = "inline-block";
                    cancelBtn.textContent = "Cancel Auto-Renew";
                    cancelBtn.className = "btn btn-ghost";
                }
            } else {
                renewStatus.textContent = "Standard Free Tier";
                renewStatus.style.color = "var(--text-secondary)";
                if (cancelBtn) cancelBtn.style.display = "none";
            }
        }

        // Quick action button
        const primaryBtn = document.getElementById("btn-plan-primary-action");
        if (primaryBtn) {
            if (isPro) {
                primaryBtn.innerHTML = '<i class="fa-solid fa-gear"></i> Manage Tier';
            } else {
                primaryBtn.innerHTML = '<i class="fa-solid fa-arrow-up-right-dots"></i> Upgrade to Pro';
            }
        }

        // If Pro, automatically disable ads engine and hide ad containers
        if (isPro) {
            if (window.LemmaAdsConfig) {
                LemmaAdsConfig.enabled = false;
            }
            const adSidebar = document.getElementById("dashboard-ad-sidebar");
            if (adSidebar) adSidebar.style.display = "none";
            const landingAd = document.getElementById("landing-vertical-ad");
            if (landingAd) landingAd.style.display = "none";
        }

        this.renderPlans();
    },

    updateUsageUI() {
        if (!this.usage) return;
        const u = this.usage;

        const proTag = document.getElementById("pro-unlimited-tag");
        if (proTag) proTag.style.display = u.is_pro ? "inline-flex" : "none";

        const updateMeter = (textId, barId, item, unit) => {
            const txt = document.getElementById(textId);
            const bar = document.getElementById(barId);
            if (!txt || !bar) return;

            if (item.limit === -1) {
                txt.textContent = `${item.used} ${unit} used (Unlimited)`;
                bar.style.width = "100%";
                bar.style.background = "linear-gradient(90deg, #10b981, #059669)";
            } else {
                txt.textContent = `${item.used} / ${item.limit} ${unit} (${item.remaining} left)`;
                bar.style.width = `${Math.min(100, item.percentage)}%`;
                bar.style.background = item.percentage >= 90 ? "#ef4444" : "linear-gradient(90deg, #6366f1, #818cf8)";
            }
        };

        updateMeter("quota-scans-text", "quota-scans-bar", u.plagiarism_scans, "checks");
        updateMeter("quota-gens-text", "quota-gens-bar", u.paper_generations, "papers");
        updateMeter("quota-restruct-text", "quota-restruct-bar", u.restructures, "docs");
        updateMeter("quota-novelty-text", "quota-novelty-bar", u.novelty_checks, "checks");
        updateMeter("quota-words-text", "quota-words-bar", u.humanizer_words, "words");
    },

    setCycle(cycle) {
        this.selectedCycle = cycle;
        const btnM = document.getElementById("btn-cycle-monthly");
        const btnA = document.getElementById("btn-cycle-annual");
        if (btnM && btnA) {
            btnM.classList.toggle("active", cycle === "monthly");
            btnA.classList.toggle("active", cycle === "annual");
        }
        this.renderPlans();
    },

    setCurrency(curr) {
        this.selectedCurrency = curr;
        const btnI = document.getElementById("btn-curr-inr");
        const btnU = document.getElementById("btn-curr-usd");
        if (btnI && btnU) {
            btnI.classList.toggle("active", curr === "INR");
            btnU.classList.toggle("active", curr === "USD");
        }
        this.renderPlans();
    },

    renderPlans() {
        const container = document.getElementById("pricing-cards-container");
        if (!container) return;

        const isAnnual = this.selectedCycle === "annual";
        const isINR = this.selectedCurrency === "INR";
        const sym = isINR ? "₹" : "$";

        // Current user plan id
        const userPlanId = (this.subscription && this.subscription.plan_id) || "free";

        // Find plans or fallback
        const findPlan = (id) => (this.plans || []).find(p => p.id === id) || null;
        const freePlan = findPlan("free") || {
            name: "Free Explorer",
            headline: "Essential academic writing and basic integrity verification for students.",
            features: [
                "5 Plagiarism & similarity checks / month",
                "3 IEEE Paper Restructurings / month",
                "3 AI Paper Generations / month",
                "Standard queue processing speed",
                "Ad-supported research workspace",
                "Basic text & Markdown exports"
            ]
        };

        const proPlan = findPlan(isAnnual ? "pro_annual" : "pro_monthly") || {
            name: "Lemma Pro",
            headline: "Dedicated GPU compute and unrestricted research tools for active scholars.",
            features: isAnnual ? [
                "🚫 100% Ad-Free Research Studio",
                "⚡ Top Priority GPU & Multi-Agent Queue",
                "📄 350 IEEE & Springer Restructures / month",
                "🔍 500 Plagiarism & Similarity Scans / month",
                "💾 Unlimited Camera-Ready PDF, DOCX & BibTeX Exports",
                "🛡️ Cryptographically Signed Integrity Certificates",
                "🌟 Early Access to Next-Gen Deep Reasoning Models",
                "✉️ Priority 1-on-1 Researcher Support"
            ] : [
                "🚫 100% Ad-Free Research Studio",
                "⚡ 3x Faster Priority GPU & LLM Queue",
                "📄 100 Monthly IEEE & Springer Paper Restructures",
                "🔍 150 Dual-Tier Similarity & Plagiarism Scans",
                "💾 Unlimited Camera-Ready PDF, DOCX & BibTeX Exports",
                "💡 Novelty Claim Analysis & Rebuttal Advisor",
                "✉️ Priority Researcher Email Support"
            ]
        };

        const ultraPlan = findPlan("scholar_ultra") || {
            name: "Scholar Ultra",
            headline: "High-throughput synthesis, unlimited checks, and API keys for faculty and labs.",
            features: [
                "♾️ Unlimited Scans, Restructures & Generations",
                "🔑 Developer REST API Key Included (10k req/mo)",
                "⚡ Dedicated High-Speed Compute Instance",
                "🚫 100% Zero-Telemetry Enterprise Privacy",
                "📚 Automated Grant & Publication Venue Matching",
                "🎓 Multi-author Lab Collaboration (Up to 5 seats)"
            ]
        };

        // Pricing calculations
        const freePriceDisplay = "0";
        const proPriceNum = isAnnual ? (isINR ? "1,999" : "79.99") : (isINR ? "199" : "9.99");
        const ultraPriceNum = isINR ? "4,999" : "199";

        const targetProKey = isAnnual ? "pro_annual" : "pro_monthly";

        // Current status flags
        const isFreeCurrent = userPlanId === "free";
        const isProCurrent = userPlanId === targetProKey;
        const isUltraCurrent = userPlanId === "scholar_ultra";

        // Helper to format feature item
        const renderFeatureLi = (text, tierClass) => {
            const formatted = text.replace(/(\d+%?|\bUnlimited\b|\bTop Priority\b|\b3x Faster\b|\bREST API\b)/g, '<strong>$1</strong>');
            return `
                <li>
                    <span class="feature-check-icon ${tierClass}"><i class="fa-solid fa-check"></i></span>
                    <span>${formatted}</span>
                </li>
            `;
        };

        const cardsHtml = `
            <!-- Card 1: Free Explorer -->
            <div class="pricing-card ${isFreeCurrent ? 'current-active' : ''}">
                <div class="pricing-card-header">
                    <div class="plan-tier-icon-wrap free-icon">
                        <i class="fa-solid fa-seedling"></i>
                    </div>
                    <h4 class="plan-title">${freePlan.name}</h4>
                    <p class="plan-headline">${freePlan.headline}</p>
                    <div class="price-wrap">
                        <span class="price-currency">${sym}</span>
                        <span class="price-num">${freePriceDisplay}</span>
                        <span class="price-cycle">/ forever</span>
                    </div>
                    <div class="card-guarantee-note" style="justify-content: flex-start; margin-top: 4px;">
                        <i class="fa-solid fa-shield-halved"></i> No credit card required
                    </div>
                </div>

                <div class="pricing-card-body">
                    <div class="features-header-tag">Included Capacities</div>
                    <ul class="plan-features-ul">
                        ${(freePlan.features || []).map(f => renderFeatureLi(f, 'free')).join('')}
                    </ul>
                </div>

                <div class="pricing-card-footer">
                    ${isFreeCurrent ? `
                        <button class="plan-cta-btn disabled" disabled>
                            <i class="fa-solid fa-circle-check"></i> Current Plan
                        </button>
                    ` : `
                        <button class="plan-cta-btn outline-btn" onclick="LemmaPaymentApp.handlePlanSelect('free')">
                            Downgrade to Free
                        </button>
                    `}
                    <div class="card-guarantee-note">Essential tools for students</div>
                </div>
            </div>

            <!-- Card 2: Lemma Pro (Most Popular) -->
            <div class="pricing-card popular-card ${isProCurrent ? 'current-active' : ''}">
                <div class="pricing-badge-ribbon">
                    <i class="fa-solid fa-fire"></i> ${isAnnual ? 'SAVE 20% · BEST VALUE' : 'MOST POPULAR'}
                </div>
                <div class="pricing-card-header">
                    <div class="plan-tier-icon-wrap pro-icon">
                        <i class="fa-solid fa-bolt"></i>
                    </div>
                    <h4 class="plan-title">Lemma Pro</h4>
                    <p class="plan-headline">${proPlan.headline}</p>
                    <div class="price-wrap">
                        <span class="price-currency">${sym}</span>
                        <span class="price-num">${proPriceNum}</span>
                        <span class="price-cycle">${isAnnual ? '/ year' : '/ month'}</span>
                    </div>
                    ${isAnnual ? `
                        <div class="annual-savings-pill">
                            <i class="fa-solid fa-sparkles"></i> Save 20% · ${sym}${isINR ? '166' : '6.67'}/mo equivalent
                        </div>
                    ` : `
                        <div class="card-guarantee-note" style="justify-content: flex-start; margin-top: 4px;">
                            <i class="fa-solid fa-rotate"></i> Billed monthly · Cancel anytime
                        </div>
                    `}
                </div>

                <div class="pricing-card-body">
                    <div class="features-header-tag">Pro Research Arsenal</div>
                    <ul class="plan-features-ul">
                        ${(proPlan.features || []).map(f => renderFeatureLi(f, 'pro')).join('')}
                    </ul>
                </div>

                <div class="pricing-card-footer">
                    ${isProCurrent ? `
                        <button class="plan-cta-btn disabled" disabled>
                            <i class="fa-solid fa-circle-check"></i> Current Plan
                        </button>
                    ` : `
                        <button class="plan-cta-btn pro-primary-btn" onclick="LemmaPaymentApp.handlePlanSelect('${targetProKey}')">
                            <i class="fa-solid fa-bolt"></i> Upgrade to Pro <i class="fa-solid fa-arrow-right" style="font-size: 0.8rem;"></i>
                        </button>
                    `}
                    <div class="card-guarantee-note">
                        <i class="fa-solid fa-lock"></i> Instant activation • Cancel anytime • 100% secure
                    </div>
                </div>
            </div>

            <!-- Card 3: Scholar Ultra (Lab & Faculty) -->
            <div class="pricing-card ${isUltraCurrent ? 'current-active' : ''}">
                <div class="pricing-badge-ribbon ultra-ribbon">
                    <i class="fa-solid fa-graduation-cap"></i> LAB &amp; FACULTY
                </div>
                <div class="pricing-card-header">
                    <div class="plan-tier-icon-wrap ultra-icon">
                        <i class="fa-solid fa-building-columns"></i>
                    </div>
                    <h4 class="plan-title">${ultraPlan.name}</h4>
                    <p class="plan-headline">${ultraPlan.headline}</p>
                    <div class="price-wrap">
                        <span class="price-currency">${sym}</span>
                        <span class="price-num">${ultraPriceNum}</span>
                        <span class="price-cycle">/ year</span>
                    </div>
                    <div class="card-guarantee-note" style="justify-content: flex-start; margin-top: 4px;">
                        <i class="fa-solid fa-users"></i> Up to 5 lab seats included
                    </div>
                </div>

                <div class="pricing-card-body">
                    <div class="features-header-tag">Enterprise Research Power</div>
                    <ul class="plan-features-ul">
                        ${(ultraPlan.features || []).map(f => renderFeatureLi(f, 'ultra')).join('')}
                    </ul>
                </div>

                <div class="pricing-card-footer">
                    ${isUltraCurrent ? `
                        <button class="plan-cta-btn disabled" disabled>
                            <i class="fa-solid fa-circle-check"></i> Current Plan
                        </button>
                    ` : `
                        <button class="plan-cta-btn ultra-btn" onclick="LemmaPaymentApp.handlePlanSelect('scholar_ultra')">
                            <i class="fa-solid fa-rocket"></i> Get Scholar Ultra <i class="fa-solid fa-arrow-right" style="font-size: 0.8rem;"></i>
                        </button>
                    `}
                    <div class="card-guarantee-note">
                        <i class="fa-solid fa-file-invoice"></i> Official GST invoices for grants
                    </div>
                </div>
            </div>
        `;

        container.innerHTML = cardsHtml;
    },

    handlePlanSelect(planId) {
        if (planId === "free") {
            if (confirm("Are you sure you want to downgrade to the Free Explorer tier? Pro benefits will terminate at the end of your billing cycle.")) {
                this.toggleCancelAutoRenew();
            }
            return;
        }

        const token = localStorage.getItem("lemma_access_token") || localStorage.getItem("token");
        if (!token) {
            if (typeof openAuthModal === "function") {
                openAuthModal();
            } else {
                window.location.href = "/login.html";
            }
            return;
        }

        this.openCheckout(planId);
    },

    openCheckout(planId) {
        this.checkoutPlanId = planId;
        const modal = document.getElementById("lemma-checkout-modal");
        if (!modal) return;

        const isAnnual = planId.includes("annual") || planId.includes("ultra");
        const isINR = this.selectedCurrency === "INR";
        const sym = isINR ? "₹" : "$";

        let title = "Lemma Pro (Monthly)";
        let amount = isINR ? 199 : 9.99;
        let showDiscount = false;

        if (planId === "pro_annual") {
            title = "Lemma Pro (Annual Commitment)";
            amount = isINR ? 1999 : 79.99;
            showDiscount = true;
        } else if (planId === "scholar_ultra") {
            title = "Scholar Ultra (Annual Lab Access)";
            amount = isINR ? 4999 : 199;
            showDiscount = true;
        }

        document.getElementById("checkout-plan-title").textContent = `Upgrade to ${title}`;
        document.getElementById("checkout-item-title").textContent = title;
        document.getElementById("checkout-item-price").textContent = `${sym}${amount}`;
        document.getElementById("checkout-total-price").textContent = `${sym}${amount}`;
        document.getElementById("checkout-pay-btn-label").textContent = `Pay ${sym}${amount} & Activate Access`;

        const discountRow = document.getElementById("checkout-discount-row");
        if (discountRow) discountRow.style.display = showDiscount ? "flex" : "none";

        modal.style.display = "flex";
        this.setupCardFormatters();
    },

    closeCheckout() {
        const modal = document.getElementById("lemma-checkout-modal");
        if (modal) modal.style.display = "none";
    },

    selectGateway(gw) {
        this.selectedGateway = gw;
        const tabRzp = document.getElementById("tab-gw-razorpay");
        const tabStr = document.getElementById("tab-gw-stripe");
        const paneRzp = document.getElementById("pane-razorpay");
        const paneStr = document.getElementById("pane-stripe");

        if (tabRzp && tabStr) {
            tabRzp.classList.toggle("active", gw === "razorpay");
            tabStr.classList.toggle("active", gw === "stripe");
        }
        if (paneRzp && paneStr) {
            paneRzp.classList.toggle("hidden", gw !== "razorpay");
            paneStr.classList.toggle("hidden", gw !== "stripe");
        }

        // Auto-switch default method based on gateway
        if (gw === "stripe") {
            this.selectedPaymentMethod = "card";
        } else {
            this.selectedPaymentMethod = "upi";
        }
    },

    setPaymentMethod(method, labelEl) {
        this.selectedPaymentMethod = method;
        document.querySelectorAll(".payment-method-selector .pay-option-radio").forEach(el => el.classList.remove("active"));
        if (labelEl) labelEl.classList.add("active");

        const upiBox = document.getElementById("upi-interactive-box");
        if (upiBox) {
            upiBox.style.display = method === "upi" ? "block" : "none";
        }
    },

    selectUpiApp(app, btnEl) {
        document.querySelectorAll(".upi-app-chips .upi-chip").forEach(el => el.classList.remove("active"));
        if (btnEl) btnEl.classList.add("active");

        const vpaInput = document.getElementById("upi-vpa-input");
        if (!vpaInput) return;

        const handles = {
            gpay: "user@okhdfcbank",
            phonepe: "user@ybl",
            paytm: "user@paytm",
            bhim: "user@upi"
        };
        if (!vpaInput.value || Object.values(handles).includes(vpaInput.value)) {
            vpaInput.value = handles[app] || "scholar@upi";
        }
    },

    toggleUpiQr() {
        const qrBox = document.getElementById("upi-qr-display-box");
        const qrImg = document.getElementById("upi-qr-code-img");
        const toggleBtn = document.getElementById("btn-toggle-upi-qr");
        if (!qrBox || !qrImg) return;

        if (qrBox.style.display === "none" || !qrBox.style.display) {
            const amount = this.selectedCurrency === "INR" ? (this.checkoutPlanId.includes("annual") ? (this.checkoutPlanId.includes("ultra") ? 4999 : 1999) : 199) : 9.99;
            const upiString = `upi://pay?pa=lemmaai@icici&pn=Lemma%20AI&am=${amount}&cu=INR&tn=Lemma%20Pro%20Upgrade`;
            const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(upiString)}`;
            qrImg.src = qrUrl;
            qrBox.style.display = "block";
            if (toggleBtn) toggleBtn.innerHTML = '<i class="fa-solid fa-eye-slash"></i> Hide QR';
        } else {
            qrBox.style.display = "none";
            if (toggleBtn) toggleBtn.innerHTML = '<i class="fa-solid fa-qrcode"></i> Show QR';
        }
    },

    detectCardBrand(num) {
        const clean = num.replace(/\D/g, "");
        if (/^4/.test(clean)) return { name: "Visa", icon: "fa-brands fa-cc-visa", color: "#1a1f71" };
        if (/^5[1-5]/.test(clean) || /^2[2-7]/.test(clean)) return { name: "MasterCard", icon: "fa-brands fa-cc-mastercard", color: "#eb001b" };
        if (/^(60|65|81|82)/.test(clean) || /^508/.test(clean)) return { name: "RuPay", icon: "fa-solid fa-credit-card", color: "#097939" };
        if (/^3[47]/.test(clean)) return { name: "Amex", icon: "fa-brands fa-cc-amex", color: "#006fcf" };
        return { name: "Card", icon: "fa-solid fa-credit-card", color: "var(--accent-purple)" };
    },

    setupCardFormatters() {
        const cardNumInput = document.getElementById("stripe-card-number");
        const cardBrandBadge = document.getElementById("card-brand-badge");
        const cardExpInput = document.getElementById("stripe-card-expiry");
        const cardCvcInput = document.getElementById("stripe-card-cvc");

        if (cardNumInput && !cardNumInput.dataset.bound) {
            cardNumInput.dataset.bound = "true";
            cardNumInput.addEventListener("input", (e) => {
                let val = e.target.value.replace(/\D/g, "").substring(0, 16);
                let formatted = val.match(/.{1,4}/g)?.join(" ") || val;
                e.target.value = formatted;

                if (cardBrandBadge) {
                    const brand = LemmaPaymentApp.detectCardBrand(val);
                    cardBrandBadge.innerHTML = `<i class="${brand.icon}" style="color: ${brand.color};"></i> ${brand.name}`;
                }
            });
        }

        if (cardExpInput && !cardExpInput.dataset.bound) {
            cardExpInput.dataset.bound = "true";
            cardExpInput.addEventListener("input", (e) => {
                let val = e.target.value.replace(/\D/g, "").substring(0, 4);
                if (val.length >= 3) {
                    e.target.value = `${val.substring(0, 2)}/${val.substring(2, 4)}`;
                } else {
                    e.target.value = val;
                }
            });
        }

        if (cardCvcInput && !cardCvcInput.dataset.bound) {
            cardCvcInput.dataset.bound = "true";
            cardCvcInput.addEventListener("input", (e) => {
                e.target.value = e.target.value.replace(/\D/g, "").substring(0, 4);
            });
        }
    },

    async processPayment() {
        const payBtn = document.getElementById("btn-execute-payment");
        if (payBtn) {
            payBtn.disabled = true;
            payBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing Transaction...';
        }

        try {
            const headers = this.getAuthHeaders();
            const payload = {
                plan_id: this.checkoutPlanId,
                currency: this.selectedCurrency,
                gateway: this.selectedGateway,
                billing_cycle: this.checkoutPlanId.includes("annual") ? "annual" : "monthly"
            };

            // Step 1: Initiate Checkout on backend
            const orderRes = await fetch(`${this.getApiBase()}/api/v1/payment/checkout`, {
                method: "POST",
                headers,
                body: JSON.stringify(payload)
            });

            if (!orderRes.ok) {
                const errData = await orderRes.json();
                throw new Error(errData.detail || "Checkout failed to initialize.");
            }

            const order = await orderRes.json();

            // Extract UPI or Card specifics
            let upiId = null;
            let cardLast4 = null;
            let cardNetwork = null;
            let cardholderName = null;

            if (this.selectedPaymentMethod === "upi") {
                const vpaInput = document.getElementById("upi-vpa-input");
                upiId = (vpaInput && vpaInput.value.trim()) || "researcher@okhdfcbank";
            } else if (this.selectedPaymentMethod === "card" || this.selectedGateway === "stripe") {
                const cardNumInput = document.getElementById("stripe-card-number");
                const cardholderInput = document.getElementById("stripe-cardholder-name");
                const cleanDigits = ((cardNumInput && cardNumInput.value) || "4242").replace(/\D/g, "");
                cardLast4 = cleanDigits.slice(-4) || "4242";
                cardNetwork = this.detectCardBrand(cleanDigits).name;
                cardholderName = (cardholderInput && cardholderInput.value.trim()) || "Scholar Researcher";
            }

            // Step 2: Verification and subscription activation
            const verifyPayload = {
                gateway: this.selectedGateway,
                order_id: order.order_id,
                payment_id: `pay_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`,
                signature: "verified_signature",
                plan_id: this.checkoutPlanId,
                currency: this.selectedCurrency,
                payment_method: this.selectedPaymentMethod,
                upi_id: upiId,
                card_last4: cardLast4,
                card_network: cardNetwork,
                cardholder_name: cardholderName
            };

            const verifyRes = await fetch(`${this.getApiBase()}/api/v1/payment/verify`, {
                method: "POST",
                headers,
                body: JSON.stringify(verifyPayload)
            });

            if (!verifyRes.ok) {
                const vErr = await verifyRes.json();
                throw new Error(vErr.detail || "Payment verification failed.");
            }

            const verifyData = await verifyRes.json();

            // Success feedback
            this.closeCheckout();
            if (typeof showToast === "function") {
                showToast(verifyData.message || "Upgraded to Lemma Pro!", "success");
            } else {
                alert(verifyData.message);
            }

            // Immediately reload billing data to show Pro badges and refreshed quota
            await this.loadBillingData();

        } catch (err) {
            console.error("Payment error:", err);
            alert(`Payment Error: ${err.message}`);
        } finally {
            if (payBtn) {
                payBtn.disabled = false;
                payBtn.innerHTML = '<i class="fa-solid fa-lock"></i> <span>Complete Payment</span>';
            }
        }
    },

    async toggleCancelAutoRenew() {
        if (!this.subscription) return;
        const sub = this.subscription;
        const headers = this.getAuthHeaders();

        if (sub.cancel_at_period_end) {
            // Reactivate
            try {
                const res = await fetch(`${this.getApiBase()}/api/v1/payment/reactivate`, {
                    method: "POST",
                    headers
                });
                if (res.ok) {
                    const data = await res.json();
                    alert(data.message || "Auto-renew reactivated!");
                    await this.loadBillingData();
                }
            } catch (e) {
                alert("Failed to reactivate subscription.");
            }
        } else {
            // Cancel
            if (!confirm("Are you sure you wish to disable auto-renewal? You will keep Pro privileges until the end of the current period.")) {
                return;
            }
            try {
                const res = await fetch(`${this.getApiBase()}/api/v1/payment/cancel`, {
                    method: "POST",
                    headers
                });
                if (res.ok) {
                    const data = await res.json();
                    alert(data.message || "Subscription set to cancel.");
                    await this.loadBillingData();
                }
            } catch (e) {
                alert("Failed to cancel auto-renewal.");
            }
        }
    },

    renderInvoices() {
        const tbody = document.getElementById("invoices-table-body");
        if (!tbody) return;

        if (!this.invoices || this.invoices.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 2.5rem 1rem;">
                        <i class="fa-solid fa-receipt" style="font-size: 1.8rem; opacity: 0.4; margin-bottom: 0.5rem; display: block;"></i>
                        No transaction receipts yet. Your active subscription is free.
                    </td>
                </tr>
            `;
            return;
        }

        const rowsHtml = this.invoices.map(inv => {
            const sym = inv.currency === "INR" ? "₹" : "$";
            const dateStr = inv.created_at ? new Date(inv.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" }) : "—";
            return `
                <tr>
                    <td><strong style="font-family: monospace; color: var(--accent-purple);">${inv.invoice_number}</strong></td>
                    <td>${dateStr}</td>
                    <td>${inv.description}</td>
                    <td><strong>${sym}${inv.amount.toFixed(2)}</strong></td>
                    <td><span class="method-tag">${inv.payment_method.toUpperCase()}</span></td>
                    <td><span class="status-pill paid"><i class="fa-solid fa-circle-check"></i> ${inv.status.toUpperCase()}</span></td>
                    <td style="text-align: right;">
                        <button class="btn btn-sm btn-ghost" onclick="LemmaPaymentApp.downloadInvoiceReceipt('${inv.invoice_number}')" title="Download Academic Receipt">
                            <i class="fa-solid fa-download"></i> Receipt
                        </button>
                    </td>
                </tr>
            `;
        }).join("");

        tbody.innerHTML = rowsHtml;
    },

    downloadInvoiceReceipt(invoiceNumber) {
        const token = localStorage.getItem("lemma_access_token") || localStorage.getItem("token");
        const url = `${this.getApiBase()}/api/v1/payment/invoices/${invoiceNumber}/download?token=${encodeURIComponent(token || "")}`;
        window.open(url, "_blank");
    }
};

// Auto-initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
    LemmaPaymentApp.init();
});
