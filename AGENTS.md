# Persistent product requirements

- Keep the interface in Traditional Chinese.
- Preserve the original score's eighth-note beam groups. Do not replace beamed eighth notes with individually flagged notes. Store explicit beam boundaries when importing MusicXML; use beat grouping only as a fallback.
- Do not show accidentals already implied by the current key signature. Render temporary accidentals and naturals only when required, respecting measure-local accidental state and bar resets.
- Preserve melody, rhythms, Chinese lyrics, slash-chord basses, ties, measures, repeats and first/second endings through transposition and export.
- Normal use must not call ChatGPT or an LLM API. Keep transposition, engraving and PDF export in-browser, and OMR local to the user's computer. Do not introduce AI API charges without the user's explicit request.
- Distinguish the manually corrected sample fixture from raw automated OMR. Never represent a matching sample lookup as fresh recognition or claim general accuracy based on this fixture.
