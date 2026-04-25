# 2) Platform-Specific Playbooks

Consumer web app (public triage wizard)
- Objective: high-intent acquisition and triage completions; build trust and convert to app installs or clinic referrals.
- Messaging & UX:
  - Above-the-fold: short value line (“Get safe, explainable care guidance 24/7 — not a diagnosis.”) + CTA: “Start triage”.
  - Show trust signals: HIPAA/PIPEDA badges, clinician-reviewed statement, pilot partner logos.
  - Microcopy: reassuring guidance, immediate emergency banner if any red-flag answers.
- Acquisition tactics: strong SEO symptom pages, branded landing pages for paid SEM, social landing pages for paid social.
- Conversion flows: minimal required fields to get actionable guidance; optional user account to save history and receive referrals.
- Retention: email follow-up with summary and clinic booking links; prompt to download mobile app.
- Compliance & analytics: consent screen before PHI capture; track triage completion rate and source attribution.

Mobile apps (iOS & Android)
- Objective: sustained engagement, recurring triages, easier push notifications for follow-ups.
- App Store Optimization (ASO):
  - Keywords: “symptom checker” (careful with wording—avoid “diagnosis”), “triage”, “ER or urgent care”.
  - Short description with safety-first language and trust badges.
- UX specifics:
  - Fast symptom wizard with progress indicator, emergency escalation CTA always visible.
  - Offline-friendly explanatory snippets; low-latency handling and clear permissions for notifications.
- Retention tactics: push notifications for unfinished triages, aftercare reminders, follow-up satisfaction survey.
- Monetization hooks for B2B: in-app links to partner clinics for bookings or telehealth sessions.
- Compliance: use device-level encryption for stored PHI; clear consent for notifications.

Clinic portals (embedded or co-branded)
- Objective: make clinic intake staff and telehealth providers adopt the tool to reduce non-urgent ED referrals and improve scheduling efficiency.
- Implementation patterns:
  - Embedded widget for clinic websites and intake systems.
  - Single Sign-On (SSO) and role-based access for clinic staff.
- Messaging & UX:
  - Emphasize integration benefits: faster intake, standardized triage, analytics dashboard for patient demand and acuity patterns.
  - Provide a “recommended action” + explainability summary printable/sendable to patients.
- Adoption tactics:
  - On-site training webinars, short explainer videos, cheat-sheet one-pagers for reception and triage nurses.
- KPIs: adoption rate by staff, reduction in unnecessary referrals, average time saved per intake.
- Compliance: data-sharing agreements, audit logs, clinic-level consent flows.

Telehealth integrations
- Objective: integrate into telehealth workflows to streamline visit triage and prep, reducing no-shows and appropriate levels of escalation.
- Integration patterns:
  - Pre-visit triage embed to collect symptoms and produce a clinician-ready summary before session begins.
  - API endpoints for triage result retrieval and booking links.
- UX & ops:
  - Clinician summary: quick bullets of symptom history and risk flags, confidence/explainability notes.
  - Escalation protocol integration with telehealth provider’s scheduling and urgent response flows.
- Value props to telehealth providers: more efficient use of clinician time, better visit appropriateness.
- KPIs: % of telehealth visits pre-populated with triage summary, change in visit acuity mix.

Partner APIs (health systems, payers)
- Objective: enterprise integration enabling bulk referrals, analytics, and co-branded patient routing.
- API play:
  - Authentication: secure OAuth2; scopes for read/write; PHI transmission via encrypted channels.
  - Endpoints: submit-triage, get-triage-result, patient-consent, analytics hooks.
- Commercial motion:
  - Pilot contracts with outcome KPIs (ED avoidance rate) and co-marketing agreements.
  - Offer sandbox and quick-start guides for developer adoption.
- Sales collateral:
  - ROI calculator for ED capacity and cost savings.
  - Case studies from pilot sites with hard metrics.
- Compliance: standardized Business Associate Agreements (BAAs) and data residency options as needed.

Microcopy & clinical tone examples (safety-first)
- Primary CTA: “Start triage — it’s quick and free.”
- Emergency banner: “If you have chest pain, severe difficulty breathing, or are unconscious — call 911 or go to the nearest ER now.”
- Explainability snippet: “We recommend urgent clinic evaluation because your symptoms include X and Y — here’s why: [short reason].”
- Privacy line: “Your data is protected under HIPAA/PIPEDA and is only used to provide care recommendations.”

Measurement & iteration
- Instrument per-platform events aligned with core funnel: view_start, triage_step_completed, triage_completed, referral_clicked, booking_completed, escalation_triggered.
- Weekly dashboard with top-of-funnel (acquisition), mid (completion), and downstream (referral/booking) metrics. Clinical team reviews false negative/positive escalations monthly.

Partnership & channel play
- Quick wins: pilot with 1–2 community clinics and 1 telehealth provider to gather outcome data and testimonial content.
- Mid-term: approach payers for pilots in high-utilization populations (e.g., Medicaid Trust programs).
- PR & thought leadership: position clinical leads to comment on ED overcrowding and explainable AI safety in healthcare journals and local health media.