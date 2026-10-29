# PDF assets

Files used by `guardian/pdf.py` to render the application PDF (`guardian/templates/guardian/application_pdf.html`).
They are inlined into the HTML at render time; WeasyPrint is not allowed to fetch any files or URLs.

## Helsinki logo

- `helsinki-fi-m-black.svg` — Finnish logo (also used for English)
- `helsinki-sv-m-black.svg` — Swedish logo

Downloaded on 2026-10-27 from the Helsinki Design System:
https://hds.hel.fi/foundation/visual-assets/logo/

**Check for the latest version there before updating.** The full logo package is published in the City of Helsinki
visual identity guidelines:
https://www.hel.fi/en/decision-making/information-on-helsinki/design-and-digitalisation/helsinki-brand-and-visual-identity/visual-identity-guidelines/download-elements#helsinki-framed-logos--helsinki-logos-

## Styles

`application_pdf.css` mirrors the frontend styles of the Esikatselu step — keep in sync with
`vety-guardian-portal-front/src/components/summary/Summary.module.css`,
`vety-guardian-portal-front/src/components/divider/Divider.module.css` and
`vety-guardian-portal-front/src/components/application-form/ApplicationForm.module.css`.
