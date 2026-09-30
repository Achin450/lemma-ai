/**
 * Lemma AI — Honest Cookie & Privacy Consent Banner
 * Implements simple, transparent cookie choices:
 * 1. Essential (Always Active - JWT session, theme, UI state)
 * 2. Analytics (Optional - usage telemetry)
 */
(function(window) {
    'use strict';

    const STORAGE_KEY = 'lemma_cookie_consent';

    const LemmaConsent = {
        getConsent() {
            try {
                const item = localStorage.getItem(STORAGE_KEY);
                return item ? JSON.parse(item) : null;
            } catch (e) {
                return null;
            }
        },

        saveConsent(analyticsAllowed) {
            const consentData = {
                essential: true,
                analytics: Boolean(analyticsAllowed),
                timestamp: new Date().toISOString()
            };
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(consentData));
            } catch (e) {
                console.warn('[Lemma Consent] Storage error:', e);
            }
            this.hideBanner();
            window.dispatchEvent(new CustomEvent('lemma-consent-updated', { detail: consentData }));
        },

        isAnalyticsAllowed() {
            const consent = this.getConsent();
            return Boolean(consent && consent.analytics);
        },

        hideBanner() {
            const el = document.getElementById('lemma-cookie-banner');
            if (el) {
                el.style.opacity = '0';
                el.style.transform = 'translateY(20px)';
                setTimeout(() => el.remove(), 250);
            }
        },

        showPreferencesModal() {
            let modal = document.getElementById('lemma-consent-modal');
            if (modal) {
                modal.style.display = 'flex';
                return;
            }

            modal = document.createElement('div');
            modal.id = 'lemma-consent-modal';
            modal.style.cssText = `
                position: fixed; inset: 0; z-index: 100000;
                background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(8px);
                display: flex; align-items: center; justify-content: center; padding: 16px;
            `;

            const current = this.getConsent() || { essential: true, analytics: false };

            modal.innerHTML = `
                <div style="background: var(--bg-secondary, #0a0a0c); border: 1px solid var(--border-color, #27272a); border-radius: 16px; max-width: 500px; width: 100%; padding: 24px; box-shadow: 0 16px 40px rgba(0,0,0,0.6); color: var(--text-primary, #ffffff); font-family: 'Inter', sans-serif;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                        <h3 style="margin: 0; font-size: 1.15rem; font-weight: 700;">Privacy & Cookie Preferences</h3>
                        <button type="button" id="lemma-close-pref-modal" style="background: transparent; border: none; color: var(--text-muted, #71717a); font-size: 1.25rem; cursor: pointer; padding: 4px;">&times;</button>
                    </div>
                    <p style="font-size: 0.88rem; color: var(--text-secondary, #a1a1aa); margin-bottom: 18px; line-height: 1.5;">
                        We believe in complete transparency. Manage the categories of cookies and local storage items used during your session.
                    </p>

                    <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color, #27272a); border-radius: 10px; padding: 14px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-weight: 600; font-size: 0.9rem;">Strictly Essential</div>
                            <div style="font-size: 0.78rem; color: var(--text-muted, #71717a); margin-top: 2px;">Authentication tokens, interface theme, and workspace state.</div>
                        </div>
                        <span style="font-size: 0.75rem; font-weight: 700; color: #10b981; background: rgba(16,185,129,0.12); padding: 3px 8px; border-radius: 6px;">Always Active</span>
                    </div>

                    <div style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color, #27272a); border-radius: 10px; padding: 14px; margin-bottom: 22px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-weight: 600; font-size: 0.9rem;">Anonymous Analytics</div>
                            <div style="font-size: 0.78rem; color: var(--text-muted, #71717a); margin-top: 2px;">Helps us measure feature usage and optimize application performance.</div>
                        </div>
                        <label style="position: relative; display: inline-block; width: 44px; height: 24px; cursor: pointer;">
                            <input type="checkbox" id="lemma-analytics-toggle" ${current.analytics ? 'checked' : ''} style="opacity: 0; width: 0; height: 0;">
                            <span id="lemma-analytics-slider" style="position: absolute; cursor: pointer; inset: 0; background-color: ${current.analytics ? '#10b981' : '#3f3f46'}; border-radius: 24px; transition: .2s;">
                                <span style="position: absolute; height: 18px; width: 18px; left: ${current.analytics ? '22px' : '3px'}; bottom: 3px; background-color: white; border-radius: 50%; transition: .2s;"></span>
                            </span>
                        </label>
                    </div>

                    <div style="display: flex; gap: 10px; justify-content: flex-end;">
                        <button type="button" id="lemma-save-pref-btn" class="btn btn-primary" style="padding: 9px 18px; font-size: 0.88rem; font-weight: 600; border-radius: 8px; background: #10b981; border: none; color: #fff; cursor: pointer;">Save Preferences</button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);

            const toggle = modal.querySelector('#lemma-analytics-toggle');
            const slider = modal.querySelector('#lemma-analytics-slider');
            const knob = slider.querySelector('span');

            toggle.addEventListener('change', () => {
                if (toggle.checked) {
                    slider.style.backgroundColor = '#10b981';
                    knob.style.left = '22px';
                } else {
                    slider.style.backgroundColor = '#3f3f46';
                    knob.style.left = '3px';
                }
            });

            modal.querySelector('#lemma-close-pref-modal').addEventListener('click', () => {
                modal.style.display = 'none';
            });

            modal.querySelector('#lemma-save-pref-btn').addEventListener('click', () => {
                LemmaConsent.saveConsent(toggle.checked);
                modal.style.display = 'none';
            });
        },

        initBanner() {
            // If user already expressed preference, don't show
            if (this.getConsent() !== null) {
                return;
            }

            const banner = document.createElement('div');
            banner.id = 'lemma-cookie-banner';
            banner.setAttribute('role', 'region');
            banner.setAttribute('aria-label', 'Cookie and privacy consent');
            banner.style.cssText = `
                position: fixed; bottom: 20px; left: 20px; right: 20px; max-width: 580px; margin: 0 auto;
                background: rgba(10, 10, 12, 0.94); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
                border: 1px solid var(--border-color, #27272a); border-radius: 14px; padding: 18px 22px;
                box-shadow: 0 16px 40px rgba(0,0,0,0.65); z-index: 99999;
                color: var(--text-primary, #ffffff); font-family: 'Inter', sans-serif;
                display: flex; flex-direction: column; gap: 14px;
                transition: opacity 0.25s ease, transform 0.25s ease;
            `;

            banner.innerHTML = `
                <div style="display: flex; align-items: flex-start; gap: 12px;">
                    <i class="fa-solid fa-cookie-bite" style="color: #10b981; font-size: 1.25rem; margin-top: 2px;"></i>
                    <div style="font-size: 0.88rem; line-height: 1.5; color: var(--text-secondary, #a1a1aa);">
                        <strong style="color: #fff; font-weight: 600;">Your Privacy on Lemma AI</strong><br>
                        We use essential storage to maintain your workspace session and optional anonymous telemetry to optimize research performance. 
                        Read our <a href="privacy.html" style="color: #10b981; text-decoration: underline;">Privacy Policy</a>.
                    </div>
                </div>
                <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; align-items: center;">
                    <button type="button" id="lemma-cookie-pref" style="background: transparent; border: 1px solid var(--border-color, #27272a); color: var(--text-secondary, #a1a1aa); padding: 7px 14px; border-radius: 8px; font-size: 0.82rem; cursor: pointer; font-weight: 500;">Preferences</button>
                    <button type="button" id="lemma-cookie-decline" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border-color, #27272a); color: #fff; padding: 7px 14px; border-radius: 8px; font-size: 0.82rem; cursor: pointer; font-weight: 500;">Decline Non-Essential</button>
                    <button type="button" id="lemma-cookie-accept" style="background: #10b981; border: none; color: #fff; padding: 7px 16px; border-radius: 8px; font-size: 0.82rem; cursor: pointer; font-weight: 600;">Accept All</button>
                </div>
            `;

            document.body.appendChild(banner);

            document.getElementById('lemma-cookie-accept').addEventListener('click', () => {
                LemmaConsent.saveConsent(true);
            });

            document.getElementById('lemma-cookie-decline').addEventListener('click', () => {
                LemmaConsent.saveConsent(false);
            });

            document.getElementById('lemma-cookie-pref').addEventListener('click', () => {
                LemmaConsent.showPreferencesModal();
            });
        }
    };

    window.LemmaConsent = LemmaConsent;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => LemmaConsent.initBanner());
    } else {
        LemmaConsent.initBanner();
    }
})(window);
