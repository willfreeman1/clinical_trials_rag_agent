# scispaCy bundled UMLS — hierarchy check

Checked 2026-09-30 against the public scispaCy source
(`linking_utils.py`, README EntityLinker, `UmlsKnowledgeBase`).
Not installed. Ten-minute check. No download.

**It has no concept-to-concept is-a.** Unused.

What the bundled KB actually stores:

- `cui_to_entity`: CUI → canonical name, aliases, definition, **TUIs**
- `alias_to_cuis`: string → CUIs
- `semantic_type_tree`: the UMLS **Semantic Network** (T047 Disease
  is a kind of T047-parent *type*), not Metathesaurus PAR/RB links
  between carboplatin and platinum chemotherapy

The linker is character-3gram nearest neighbours onto that name list.
`HyponymDetector` is Hearst patterns over **running text**, not the
UMLS hierarchy.

Containment is load-bearing on day one. Without is-a, scispaCy cannot
replace the hand-written therapy ladder. Do not install it for this
project. Vintage (~3M concepts, UMLS levels 0/1/2/9 in current
README) is irrelevant once the hierarchy is missing.

Next: UMLS REST API for the lung-slice gate. No Metathesaurus file.
