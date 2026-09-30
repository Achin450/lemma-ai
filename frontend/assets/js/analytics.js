/**
 * Lemma AI — Privacy-Conscious Analytics Engine
 * Strictly configuration-driven. Zero tracking or external script execution
 * occurs unless a valid measurement ID is explicitly configured AND the user
 * has granted cookie consent.
 */
(function(window) {
    'use strict';

    const LemmaAnalytics = {
        _initialized: false,
        _lastPagePath: null,

        /**
         * Get the configured analytics measurement ID
         */
        getMeasurementId() {
            if (window.LEMMA_CONFIG && typeof window.LEMMA_CONFIG.ANALYTICS_ID === 'string') {
                return window.LEMMA_CONFIG.ANALYTICS_ID.trim();
            }
            return '';
        },

        /**
         * Verify if analytics tracking is authorized by user consent and configured
         */
        isAllowed() {
            const id = this.getMeasurementId();
            if (!id) {
                return false; // Disabled: No measurement ID configured
            }

            // Check Cookie Consent
            if (window.LemmaConsent && typeof window.LemmaConsent.isAnalyticsAllowed === 'function') {
                return window.LemmaConsent.isAnalyticsAllowed();
            }

            // Fallback: check localStorage directly
            try {
                const stored = localStorage.getItem('lemma_cookie_consent');
                if (stored) {
                    const parsed = JSON.parse(stored);
                    return Boolean(parsed && parsed.analytics);
                }
            } catch (e) {
                return false;
            }
            return false;
        },

        /**
         * Initialize analytics loader only if permitted
         */
        init() {
            if (this._initialized) return;
            const id = this.getMeasurementId();

            if (!id || !this.isAllowed()) {
                // Keep completely disabled without throwing errors
                return;
            }

            // Load Google Analytics tag asynchronously
            try {
                const script = document.createElement('script');
                script.async = true;
                script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(id);
                document.head.appendChild(script);

                window.dataLayer = window.dataLayer || [];
                function gtag() { window.dataLayer.push(arguments); }
                window.gtag = gtag;
                gtag('js', new Date());
                gtag('config', id, {
                    anonymize_ip: true,
                    send_page_view: false // Managed manually to avoid duplicates
                });

                this._initialized = true;
                this.pageView();
            } catch (err) {
                console.warn('[Lemma Analytics] Initialization note:', err);
            }
        },

        /**
         * Track page view (deduplicated)
         */
        pageView(path, title) {
            if (!this.isAllowed() || !this._initialized) return;
            const currentPath = path || window.location.pathname;
            if (this._lastPagePath === currentPath) return; // Prevent duplicate page views
            this._lastPagePath = currentPath;

            const currentTitle = title || document.title;
            if (typeof window.gtag === 'function') {
                window.gtag('event', 'page_view', {
                    page_path: currentPath,
                    page_title: currentTitle
                });
            }
        },

        /**
         * Track custom action event without personal data
         */
        trackEvent(eventName, params) {
            if (!this.isAllowed() || !this._initialized) return;
            if (typeof window.gtag === 'function') {
                window.gtag('event', eventName, params || {});
            }
        },

        /**
         * Track primary CTA clicks
         */
        trackCta(ctaName, destination) {
            this.trackEvent('cta_click', {
                cta_name: ctaName,
                destination: destination || ''
            });
        },

        /**
         * Track authentication interactions (login/signup)
         */
        trackAuth(action, role) {
            this.trackEvent(action, {
                account_role: role || 'student'
            });
        },

        /**
         * Track form submissions (e.g. contact form)
         */
        trackFormSubmit(formName, isSuccess) {
            this.trackEvent('form_submission', {
                form_name: formName,
                status: isSuccess ? 'success' : 'failed'
            });
        }
    };

    window.LemmaAnalytics = LemmaAnalytics;

    // Listen for consent updates to trigger activation dynamically
    window.addEventListener('lemma-consent-updated', function() {
        if (LemmaAnalytics.isAllowed() && !LemmaAnalytics._initialized) {
            LemmaAnalytics.init();
        }
    });

    // Auto-run initialization check on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { LemmaAnalytics.init(); });
    } else {
        LemmaAnalytics.init();
    }
})(window);
