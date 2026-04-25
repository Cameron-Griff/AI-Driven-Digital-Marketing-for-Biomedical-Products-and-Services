# 2) Platform-Specific Playbooks

Health System Integrations (EHR/Portal)
- Key message: "Reduce avoidable ED visits with an explainable triage layer that augments care navigation while preserving clinician oversight."
- Primary UX elements: portal-embedded symptom flows; clinician handoff summary cards in EHR inbox; co-branded outcome dashboards.
- Content formats: in-portal symptom entry, short explainer microcopy, downloadable clinician summary PDFs.
- Integration checklist:
  - SSO/SAML/OAuth for user authentication; support for SMART on FHIR where possible.
  - Secure PHI transport; HIPAA-compliant BAA and logging.
  - Low-latency API endpoints; offline fallback for intermittent connectivity.
  - Configurable clinical rules and escalation thresholds per site.
- GTM tactics:
  - Executive briefing pack + pilot proposal template.
  - On-site clinician training and simulation sessions.
  - Pilot success scorecards shared weekly.
- KPIs:
  - Pilot: % reduction in non-urgent ED visits (vs baseline), triage completion rate, clinician handoff open rate.
  - Scaling: integration time, cost per active user.
- Messaging snippets:
  - Clinician: "This triage summary is supplemental — please review and confirm next steps."
  - Patient: "If you are experiencing an emergency, call 911 or go to the nearest emergency department."

Clinic Portals & Front-Desk
- Key message: "Streamline triage at check-in and reduce inappropriate ED referrals with fast, explainable guidance."
- Primary UX elements: kiosk/portal pre-check-in flows, front-desk dashboards highlighting suggested disposition.
- Content formats: one-click recommendation cards, printable patient handouts with rationale and follow-up instructions.
- Integration checklist:
  - Simple iframe/SDK embed; minimum latency for in-clinic use.
  - Data minimization: capture only required data fields; consent checkpoint.
  - Local escalation workflows (after-hours routing to on-call).
- GTM tactics:
  - Quick-start embedding guide, plug-and-play script for front-desk workflows.
  - Two-page clinician and staff cheat-sheet.
- KPIs:
  - % of patients routed to same-day primary care instead of ED, front-desk time savings, staff satisfaction.

Telehealth Partners & Clinicians
- Key message: "Provide safer, explainable triage before clinician encounters to prioritize urgent cases and simplify handoffs."
- Primary UX elements: pre-visit symptom triage, clinician-facing summary integrated into telehealth session.
- Content formats: structured clinician handoff, optional audio summary, in-session recommendation overlay.
- Integration checklist:
  - Real-time handoff via API or embedded widget.
  - Support for clinician override and feedback logging.
  - Audit trail for safety monitoring.
- GTM tactics:
  - Integrate with telehealth scheduling to require triage for same-day evaluations.
  - Host clinician webinars demonstrating improved case mix and time-saving.
- KPIs:
  - Reduction in low-acuity telehealth-to-ED escalations, clinician time saved per session, override rate.

Consumer Web & Mobile Apps
- Key message: "Get immediate, clear, and private guidance for your symptoms — with emergency escalation if needed."
- Primary UX elements: concise guided symptom flows (3–7 steps), actionable recommendation cards, clear emergency CTA.
- Content formats: short explainer videos, FAQ, privacy badges, shareable after-action summaries for clinician visits.
- Integration checklist:
  - Mobile-first responsive design; <5s flow completion.
  - Privacy-first consent flows, transparent data use statements.
  - Localization for French/Spanish (planned) and culturally sensitive microcopy.
- GTM tactics:
  - SEO strategy targeting urgent symptom queries and "should I go to ER" queries.
  - App store assets emphasizing safety, explainability, and privacy.
  - Partnerships with urgent care chains to offer co-branded experiences.
- KPIs:
  - Triage completion rate, recommendation acceptance rate, app retention at 7/30 days, referral lift to recommended care types.

Regulatory & Compliance Playbook (cross-platform)
- Mandatory items:
  - HIPAA (US) and PIPEDA (Canada) compliance; BAAs in place for all enterprise partners.
  - Clear non-diagnostic disclaimers inline and in marketing materials.
  - Emergency escalation protocol prominent and unavoidable for red-flag conditions.
  - Logging and audit trails for every recommendation and escalation.
- Clinical governance:
  - Clinical advisory board oversight for rules and AI model behavior.
  - Post-deployment safety audits and reportable incident workflow.
- Messaging/legal:
  - All public-facing content includes a safety-first disclaimer and contact for clinical questions.

Localization & Cultural Sensitivity
- Base launch in English (US/Canada). Plan phased rollout:
  - Phase 1: English (core).
  - Phase 2: French (Canada) and Spanish (US), with adapted microcopy and clinician handoff translations.
- Cultural notes: avoid alarmist phrasing; prefer calm, action-oriented language. Localize examples (clinic names, phone numbers) and emergency contacts.

Clinician Engagement & Adoption Tactics
- Identify clinician champions early and co-create flows.
- Provide one-click feedback inside handoff summaries.
- Quarterly clinician roundtables to iterate content and thresholds.
- Offer dashboards that show reduced low-acuity ED arrivals attributable to triage.

Creative & Copy Guidelines (microcopy examples)
- Onboarding: "This tool helps guide you to the right care. It is not a diagnosis. If you feel your life is at risk, call emergency services now."
- Recommendation card header: "Based on your answers, we recommend: Primary care today"
- Escalation prompt: "This looks potentially serious — please call 911 or go to the emergency department now."