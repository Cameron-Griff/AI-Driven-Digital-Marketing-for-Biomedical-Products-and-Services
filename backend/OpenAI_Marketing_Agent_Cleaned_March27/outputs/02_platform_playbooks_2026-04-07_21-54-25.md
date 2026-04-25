# 2) Platform-Specific Playbooks

Patient Web App
- Goal: rapid self-triage, reduce ED anxiety, convert to appropriate care pathway.
- Key UX elements: one-click symptom start, progressive disclosure questionnaire, visual risk meter, explainable recommendation card (why recommendation made), clear escalation CTA (call 911 / go to ED / contact clinic), option to share summary with clinician.
- Messaging: reassuring, concise, safety-first; plain-language explanations and clear disclaimers; bilingual EN/FR toggle.
- Content & assets: symptom landing pages, short explainer videos, trust badges (clinically validated, HIPAA/PIPEDA), patient FAQs, privacy summary.
- Conversion points: clinic booking link, telehealth appointment link, printable/emailed handoff summary.
- Privacy/security: cookies minimized, encrypted session, explicit consent screens for sharing info with clinicians.
- Success metrics: completion rate of triage flows, time-to-recommendation, conversion to recommended action, user-reported confidence.

Mobile App (iOS/Android)
- Goal: on-demand, 24/7 accessible triage with push-based follow-ups.
- App-specific features: offline-friendly UI, push notification triage reminders, symptom history, caregiver mode (manage multiple profiles), ASO-optimized metadata.
- Onboarding: quick privacy & safety overview, permission gating (notifications), guided first-triage walkthrough.
- Engagement: contextual nudges (e.g., seasonal symptom pushes), in-app educational micro-content, appointment integration with calendar.
- Security: biometric sign-in option, device-level encryption, session timeouts.
- Success metrics: daily/weekly active users (DAU/WAU), retention at 7/30/90 days, push opt-in rates, referral activation.

Clinic Portals & In-Clinic Activation
- Goal: integrate at point-of-care to influence patient behavior before ED visits and improve clinic workflows.
- Implementation: lightweight widget or link embedded in patient portal, waitroom tablets/QR codes, SMS links post-teletriage.
- Clinician workflow: one-button send of patient's triage summary to clinician inbox; standardized clinician handoff summaries that map to clinic intake fields.
- Messaging to clinics: emphasize decreased non-urgent ED visits, reduced phone triage burden, faster patient routing.
- Training assets: quick-reference cards, 15–30 minute clinician demo, cheat sheets for interpreting recommendation cards.
- Success metrics: uptake of portal widget, number of patient-initiated triages from portal, clinician use of handoff summaries.

Telehealth Integrations
- Goal: reduce phone burden and support remote triage ahead of clinician assessment.
- Integration points: embed triage link in telehealth intake, pre-visit symptom capture, and clinician dashboard within telehealth platform.
- UX: pre-visit triage prompts sent via SMS/email; telehealth provider sees structured summary and confidence/urgency signals.
- Safety features: real-time escalation flags for high-acuity symptoms with recommended immediate action.
- Success metrics: % telehealth appointments with triage summary available, reduction in no-shows for appropriate care, reduced unnecessary scheduled urgent visits.

EHR Integrations
- Goal: seamless clinician handoff, audit trails, and system reporting.
- Technical approach: FHIR-based APIs, HL7 where required, OAuth2 for auth, SMART on FHIR app capabilities for embedding.
- Data to exchange: structured symptom data, recommendation card, timestamps, patient consent metadata, clinician notes (if any).
- Compliance: ensure audit logging, encrypted transit/storage, role-based access lists.
- Implementation playbook: developer sandbox, mapping templates, sample handoff payloads, integration checklist for security review.
- Success metrics: number of integrated clinics, time-to-live integration, number of handoffs per week.

Content & Creative Playbook (cross-platform)
- Tone: empathetic, clear, concise, authoritative.
- Primary assets:
  - Interactive symptom questionnaires tailored to common urgent and non-urgent conditions.
  - Explainable recommendation cards with “Why this recommendation?” toggles showing reasoning and next-steps.
  - Escalation templates: scripts for “call 911” and “seek urgent care” that meet local regulatory language.
  - Clinician handoff summaries designed to pre-populate EHR intake fields.
  - Patient education microcontent: short text + icon-based explainers and 30–60s videos for common triage outcomes.
- Localization: professional translation and clinical review in French (Canada), adapt wording to local idioms and regulatory phrasing.
- A/B testing: start with variations of reassurance language and escalation wording to measure impact on compliance with recommendations and patient confidence.

Trust & Risk-Communication Playbook
- Always include: clinical validation highlights, clear disclaimer “not a diagnosis,” data privacy summary, clinician oversight details.
- Visual trust signals: clinical partner logos (with permission), certification badges, clinician quotes and short video testimonials from pilots.
- Crisis messaging: pre-approved emergency wording templates that default to conservative escalation when red-flag symptoms are detected.

Sales & Partnership Playbook
- Target partners: integrated health systems, primary care networks, telehealth vendors, EHR vendors, regional health authorities, payers.
- Value-based pilots: offer outcomes-based pilots (e.g., shared savings on avoided ED visits), subject to measurement agreements.
- Sales collateral: pilot one-pagers, ROI calculator (based on ED visit cost savings), clinical validation brief, technical integration deck.
- Implementation support: clinical onboarding, technical onboarding, privacy/legal checklist, and a pilot success dashboard.

Measurement & Optimization Playbook
- Required analytic events: triage started/completed, recommendation type, time-to-recommendation, escalation invoked, patient action taken, share-to-clinic used.
- Safety monitoring: incident reporting workflow, weekly safety reviews, and rapid rollback capability for any change flagged by clinicians.
- Iteration cadence: bi-weekly product/content sprints informed by pilot data, monthly clinician advisory board calls.