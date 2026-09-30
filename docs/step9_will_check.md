# Step 9 — SUPERSEDED — 40 least-sure answer-key rows

**Superseded 2026-09-30, before any of these 40 rows were scored.** No
results were seen. This sample was the key's least-sure labels
(`unclear`, `both_classifications`, `barred_with_exception`). Those labels
keep the trial, so a wrong one cannot change any number in the project.
`unclear` is also near-unverifiable from a single quote.

The replacement is `docs/step9_consequential_check.md`: 30 `barred` /
`required` rows, weighted by narrowing. Do not mark this sheet.

---

Reading comprehension only. For each row: does the quoted sentence say
what the **classification** claims, in plain English?

- **agree** — the quote supports that label
- **disagree** — the quote does not say that
- **needs medical knowledge** — you cannot tell without knowing whether
  one medical term falls under another. Record it and move on.

Do not judge whether a patient would qualify. These 40 are the labels the
key was least sure about, not a random sample of the whole key.

Seed **20260930**. All 12 immunotherapy `unclear`, all 7 brain `unclear`,
all 7 brain `both_classifications`, 8 of 22 immunotherapy
`both_classifications`, 3 immunotherapy `barred_with_exception`,
3 brain `barred_with_exception`.

Gate (committed in THRESHOLDS.md): disagreement above **25% of the
checkable ones** (agree + disagree, excluding needs-medical-knowledge)
→ rework the labelling instructions before quoting the key.

## 1. NCT04527419 — prior immunotherapy

_SLND or Not in cT1 GGO Invasive Lung Adenocarcinoma (ECTOP-1009)_

- classification: `unclear`
- quote: Patients who have received radiation, chemotherapy or other treatments previously.
- model note: The trial bars prior radiation, chemotherapy, or other previous treatments, but it does not explicitly say whether immunotherapy is included in “other treatments,” so prior immunotherapy is unclear.

Will: agree / disagree / needs medical knowledge

## 2. NCT05288205 — prior immunotherapy

_Phase 1/2a Study of JAB-21822 Plus JAB-3312 in Patients With Advanced Solid Tumors Harboring KRAS p.G12C Mutation_

- classification: `unclear`
- quote: Patients with previous (≤ 6 months before the initiation of treatment) or current severe autoimmune diseases (including adverse reactions caused by previous anti- tumor immunotherapies), or autoimmune diseases requiring long-term systemic hormone therapy at immunosuppressive dose levels (prednisone > 10 mg/day or equivalent drugs);
- model note: The trial mentions prior anti-tumor immunotherapies only as a source of adverse reactions within an autoimmune-disease exclusion, but it does not state whether prior immunotherapy itself is required, allowed, or barred.

Will: agree / disagree / needs medical knowledge

## 3. NCT05754203 — prior immunotherapy

_Efficacy and Safety of Super-hyperfractionation Pulse Radiotherapy Combined With ICIs for Advanced NSCLC_

- classification: `unclear`
- quote: Participants diagnosed with stage IIIB or above non-small cell lung cancer confirmed by histopathology (whether newly diagnosed or not) meet the requirements of SBRT radiotherapy (mass limited, less than 5 cm) and immune checkpoint inhibitor therapy (according to CSCO guidelines).
- model note: The text mentions immune checkpoint inhibitor therapy as part of eligibility/current treatment planning, but it does not say whether prior receipt of immunotherapy is required, allowed, or excluded. There is no mention of brain metastases or leptomeningeal disease.

Will: agree / disagree / needs medical knowledge

## 4. NCT06303505 — prior immunotherapy

_FiH Study to Investigate Safety, PK and Efficacy of the NaPi2b ADC TUB-040 in Patients With PROC or r/r Adenocarcinoma NSCLC_

- classification: `unclear`
- quote: Resolution of all acute toxic effects of prior therapy or surgical procedures to ≤grade 1 (except alopecia, hyperpigmentation, or discoloration (incl. vitiligo) of the skin and nails, stable immune-related toxicity such as hypothyroidism on hormone replacement, adrenal insufficiency on ≤10 mg daily prednisone [or equivalent], chronic grade 2 peripheral sensory neuropathy after prior taxane therapy or anticancer treatment such as but not limited to IOs).
- model note: Prior immunotherapy is mentioned only indirectly through prior immune-related toxicities and a separate exclusion of current immunotherapy, but the text does not clearly state whether prior immunotherapy itself is required, allowed, or barred at enrollment.

Will: agree / disagree / needs medical knowledge

## 5. NCT06455917 — prior immunotherapy

_TIL Therapy in Non-small-cell Lung Cancer (NSCLC) Patients_

- classification: `unclear`
- quote: Prior immune-related adverse events that would preclude re-challenge with an immune checkpoint inhibitor or immunomodulatory agent per investigator's judgment.
- model note: The trial text mentions prior immune checkpoint inhibitor exposure only indirectly through prior immune-related adverse events and possible re-challenge, so it does not clearly state whether prior immunotherapy itself is required, allowed, or barred.

Will: agree / disagree / needs medical knowledge

## 6. NCT06743581 — prior immunotherapy

_Study of Neoadjuvant Cemiplimab and Dupilumab in Early-Stage Non-Small Cell Lung Cancer_

- classification: `unclear`
- quote: * History of autoimmune disorders or use of immunomodulatory drugs (including dupilumab) within 2 months prior to treatment initiation.
- model note: The text mentions prior use of an immunomodulatory drug, including dupilumab, but does not clearly address prior immunotherapy as defined here (such as prior immune checkpoint inhibitors or PD-1/PD-L1/CTLA-4-directed treatment). Metastatic disease is mentioned generally, but there is no specific mention of brain or CNS metastases.

Will: agree / disagree / needs medical knowledge

## 7. NCT07116057 — prior immunotherapy

_MOv19-BBz CAR T Cells in FRa+ Cancers_

- classification: `unclear`
- quote: Subjects must be a possible clinical candidate for standard of care treatment with a commercial checkpoint inhibitor, as per physician-investigator assessment.
- model note: The trial mentions checkpoint inhibitors only as a possible standard-of-care option and does not state whether prior receipt of immunotherapy is required, allowed, or excluded. For brain metastases, CNS metastases are only accepted if treated, asymptomatic, off steroids, stable on MRI, with no concurrent CNS treatment and no leptomeningeal disease or cord compression.

Will: agree / disagree / needs medical knowledge

## 8. NCT07175220 — prior immunotherapy

_Phase II Clinical Study of SHR2554 Tablets Combined With Other Anti-tumor Treatments in Non-small Cell Lung Cancer Subjects_

- classification: `unclear`
- quote: 7. Receive other anti-tumor treatments within 4 weeks before the first medication
- model note: Prior immunotherapy is not named specifically, but the exclusion of 'other anti-tumor treatments within 4 weeks before the first medication' could include it, so this is unclear rather than a definite bar. Brain/CNS metastases are excluded only when 'symptomatic or active,' which implies an exception for cases that are not symptomatic or active.

Will: agree / disagree / needs medical knowledge

## 9. NCT07243132 — prior immunotherapy

_Long-Terms Responders in Metastatic Lung Cancer: Better Understanding for Better Management (Lungevity Study)_

- classification: `unclear`
- quote: * Patients alive after more than three years from diagnosis with stage IV or Stage III NSCLC or SCLC, not treated with cytotoxic chemotherapy at the time of inclusion (the patient may be undergoing imunotherapy, targeted therapy or surveillance).
- model note: The trial mentions that a patient may be undergoing immunotherapy at inclusion, which shows immunotherapy is contemplated, but it does not clearly state whether prior immunotherapy is specifically accepted as an eligibility factor independent of current treatment status.

Will: agree / disagree / needs medical knowledge

## 10. NCT07332858 — prior immunotherapy

_First-in-Human Expanded Cohort Study of Intrapleural Administration of TolueneSulfonamide in Patients With Malignant Pleural Effusion_

- classification: `unclear`
- quote: Except for the subject's current stable systemic anti-tumor therapy, any other ongoing tumor-related treatments must be suspended or discontinued after evaluation by the investigator to ensure they do not interfere with the assessment of PTS treatment.
- model note: The trial mentions current stable systemic anti-tumor therapy, which could include immunotherapy, but it does not specifically say whether prior immunotherapy is required, allowed, or excluded. There is no mention of brain metastases or leptomeningeal disease.

Will: agree / disagree / needs medical knowledge

## 11. NCT07498933 — prior immunotherapy

_FAP-targeted PET/NIR in Lung Malignant Tumors_

- classification: `unclear`
- quote: * Previously combined with other malignant tumors or received other anti-tumor treatments;
- model note: The trial mentions prior anti-tumor treatments, but it does not specifically say whether prior immunotherapy, immune checkpoint inhibitors, or PD-1/PD-L1/CTLA-4-directed therapy were received or how they are handled separately.

Will: agree / disagree / needs medical knowledge

## 12. NCT07637474 — prior immunotherapy

_Immune Metabolism Dysregulation and Efficacy to Anti-PD-1 PD-L1 Agents in Non Small Cell Lung Cancer Patients_

- classification: `unclear`
- quote: * Contraindications to immunotherapy
- model note: The trial mentions immunotherapy only as a contraindication, which does not state whether prior immunotherapy is required, allowed, or barred; there is no mention of brain metastases or central nervous system involvement.

Will: agree / disagree / needs medical knowledge

## 13. NCT06218914 — brain metastases

_Phase 1 Study to Investigate TCRTs KRAS Mutation in Unresectable, Advanced, and/or Metastatic Solid Tumors_

- classification: `unclear`
- quote: * Known, active primary central nervous system (CNS) malignancy
- model note: The trial text does not mention prior immunotherapy, immune checkpoint inhibitors, PD-1, PD-L1, or CTLA-4 treatment history. It mentions CNS malignancy, but that is a primary CNS cancer and does not clearly state whether brain metastases or leptomeningeal disease are allowed or excluded.

Will: agree / disagree / needs medical knowledge

## 14. NCT06616584 — brain metastases

_Adding the Immunotherapy Drug Cemiplimab to Usual Treatment for People With Advanced Non-Small Cell Lung Cancer Who Had Previous Treatment With Platinum Chemotherapy and Immunotherapy (An Expanded Lung-MAP Treatment Trial)_

- classification: `unclear`
- quote: Participants must have a CT or MRI scan of the brain to evaluate for central nervous system (CNS) disease within 42 days prior to randomization
- model note: Prior immunotherapy is explicitly required. Brain/CNS disease is mentioned only as something to be evaluated on imaging, but the text does not say whether participants with brain metastases are eligible or ineligible.

Will: agree / disagree / needs medical knowledge

## 15. NCT06712316 — brain metastases

_Safety, Efficacy, and Pharmacokinetics of BNT327 in Combination With Chemotherapy and Other Investigational Agents for Lung Cancer_

- classification: `unclear`
- quote: If the lesion with prior local treatment is the only targeted lesion, evidence-based radiology must be provided to demonstrate disease progression (the single bone metastasis or the single central nervous system metastasis should not be considered as a measurable lesion).
- model note: Prior immunotherapy is explicitly excluded through prior PD(L)-1 and PD(L)-1/VEGF bispecific therapy. Brain/CNS metastasis is mentioned only in the context of measurable lesion assessment, not clearly as an inclusion or exclusion rule.

Will: agree / disagree / needs medical knowledge

## 16. NCT06829459 — brain metastases

_A Study to Evaluate the Efficacy and Safety of Glumetinib Combined With Osimertinib Mesylate Versus Platinum-based Doublet Chemotherapy in Non-Small Cell Lung Cancer Patients After Resistance to EGFR-TKIs_

- classification: `unclear`
- quote: Brain metastases will not be considered as target lesions.
- model note: The trial explicitly excludes prior immunotherapy for advanced NSCLC other than EGFR-TKIs. Brain metastases are mentioned only in the context of target lesion assessment, not as an eligibility inclusion or exclusion criterion.

Will: agree / disagree / needs medical knowledge

## 17. NCT07241039 — brain metastases

_A Study to Assess the Adverse Events, Change in Disease Activity, and How Oral ABBV-711 Tablets Move Through the Body as a Monotherapy and in Combination With Intravenously Infused Budigalimab (ABBV-181), in Adults With Advanced Squamous Tumors_

- classification: `unclear`
- quote: Radiation therapy for central nervous system metastases within 14 days prior to first dose.
- model note: Prior PD-1/PD-L1 therapy is explicitly permitted. Brain/CNS metastases are mentioned only in the context of recent radiation washout, which does not clearly state whether having brain metastases themselves is allowed or excluded.

Will: agree / disagree / needs medical knowledge

## 18. NCT07309952 — brain metastases

_Neoadjuvant SBRT Followed by Sintilimab Plus Chemotherapy for N3-Positive NSCLC_

- classification: `unclear`
- quote: Baseline staging must be performed with either PET/CT or a combination of contrast-enhanced CT of chest/abdomen + bone scan + brain MRI.
- model note: Prior immunotherapy is explicitly excluded. Brain MRI is mentioned only as part of staging, and the trial excludes “distant metastasis,” but it does not explicitly state whether brain/CNS metastases are specifically allowed or barred.

Will: agree / disagree / needs medical knowledge

## 19. NCT07613723 — brain metastases

_A Study to Test the Safety, Tolerability and Effect of ZI-MA4-1 for Patients With Locally Advanced or Metastatic Solid Malignancies_

- classification: `unclear`
- quote: * Significant CNS disorders.
- model note: Prior immunotherapy is not excluded in general, but it is excluded if recent within up to 4 weeks prior to lymphodepletion. The trial mentions CNS involvement only as 'Significant CNS disorders,' which does not clearly state whether brain metastases are included.

Will: agree / disagree / needs medical knowledge

## 20. NCT05379803 — brain metastases

_High-dose Furmonertinib for First-line Treatment of EGFR Mutated NSCLC With Central Nervous System (CNS) Metastases_

- classification: `both_classifications`
- quote: According to RECIST 1.1, patients must have at least one central nervous system (CNS) metastatic tumor lesion at baseline that meets the following requirements: accurately and repeatably measurable at baseline, have no radiotherapy or biopsy.

Spinal cord compression; symptomatic and unstable brain metastases, except for those patients who have completed definitive therapy, are not on steroids, and have a stable neurological status for at least 2 weeks after completion of the definitive therapy and steroids.
- model note: Brain/CNS metastases are required for enrollment, but a subset with symptomatic and unstable brain metastases is excluded unless specific stabilization criteria are met.

Will: agree / disagree / needs medical knowledge

## 21. NCT05394831 — brain metastases

_A Phase 1/2 Study to Evaluate the Safety, Tolerability and PK of JIN-A02 in Patients With EGFR Mutant Advanced NSCLC_

- classification: `both_classifications`
- quote: subjects who are positive for any EGFR mutations and stable brain metastasis in Cohort 4

and

Subjects requiring steroid escalation within 28 days before start of the study due to spinal cord compression with uncontrolled symptoms or Central Nervous System (CNS) metastasis or for CNS disease treatment; patients requiring local CNS disease treatment; and subjects with leptomeningeal disease. However, these subjects may be included in the study if they are systemically asymptomatic and stable 2 weeks after gamma knife therapy or 4 weeks after whole-brain irradiation

and

For Part Part C: all Cohorts except for Cohort 4

- Subjects without CNS metastasis
- model note: Prior immunotherapy is not categorically excluded, only if given within 28 days before first dose. Brain metastases/CNS metastases are required for Cohort 4, barred unless stable/treated in Parts A, B, and Cohort 4 of Part C, and absence of CNS metastasis is excluded in other Part C cohorts, so the protocol gives conflicting eligibility rules across cohorts.

Will: agree / disagree / needs medical knowledge

## 22. NCT05948813 — brain metastases

_TY-9591 in the Patients With EGFR Mutations in Advanced NSCLC With Brain Metastases_

- classification: `both_classifications`
- quote: Patients diagnosed with NSCLC by histology or cytology, with brain metastases.
Patients with primary malignant brain tumors and unstable brain metastases.
- model note: Prior immunotherapy is barred because prior systemic antitumor therapy including immunodrug therapy is excluded. Brain metastases are required, but unstable brain metastases are excluded, so the trial both wants brain metastases and refuses a subset of them.

Will: agree / disagree / needs medical knowledge

## 23. NCT05967689 — brain metastases

_A Study of Zipalertinib in Patients With Advanced Non-Small Cell Lung Cancer With Epidermal Growth Factor Receptor (EGFR) Exon 20 Insertions or Other Uncommon Mutation._

- classification: `both_classifications`
- quote: Participants with brain metastasis must be neurologically stable. Participants must have received central nervous system (CNS)-directed therapy and have no evidence of progression for at least 4 weeks after CNS-directed treatment, as ascertained by clinical examination and brain imaging (magnetic resonance imaging [MRI] or computed tomography [CT] scan) during the Screening Period. Additionally, they must be on a stable or decreasing dose of corticosteroids and/or anti-convulsant medications for at least 2 weeks prior to the first dose of study treatment. Participants with a history of uncontrolled seizures or LMD are not eligible.

Presence of brain metastasis(es) characterized as at least one of the following:

* Newly diagnosed and/or progressive brain metastasis(es) measurable by Response Assessment in Neuro-oncology Brain Metastases (RANO-BM) criteria and not subjected to CNS-directed therapy, AND/OR
* LMD measurable or non-measurable by RANO-BM criteria and confirmed by a positive cerebrospinal fluid cytology, or unequivocal radiographic and/or clinical determination.
- model note: Prior immunotherapy is permitted if it was not within 28 days before first dose, so it is allowed with a time-based exception. Brain metastases are handled differently across cohorts/substudies: some cohorts require or allow stable treated brain metastases, while Cohort C specifically requires brain metastases including LMD, so the trial text both wants and restricts this condition depending on cohort.

Will: agree / disagree / needs medical knowledge

## 24. NCT07264569 — brain metastases

_Evaluate the Safety, Tolerability, Biodistribution Characteristics and Preliminary Efficacy of BioTTT001_

- classification: `both_classifications`
- quote: Patients diagnosed with NSCLC through pathological histology, who have experienced recurrence or progression after standard treatment, and have tumor cells found in cerebrospinal fluid or MRI diagnosis of leptomeningeal metastasis;
22. Patients with intracranial brainstem metastases or rapidly progressing diffuse cerebral parenchymal metastases;
- model note: Prior immunotherapy is excluded if it was given within 6 weeks before first dose, implying earlier prior immunotherapy may be allowed, but prior immunotherapy is also excluded if it caused irAE grade ≥3. Brain/CNS metastasis is required via leptomeningeal metastasis, while certain other intracranial metastases are excluded.

Will: agree / disagree / needs medical knowledge

## 25. NCT07562581 — brain metastases

_A Phase 2 Study of Luvometinib Combined With Anlotinib in KRAS-mutated NSCLC_

- classification: `both_classifications`
- quote: 6．At least one intracranial measurable lesion according to RECIST v1.1 criteria.

2．Active CNS metastases; brainstem, leptomeningeal, spinal cord metastases or spinal cord compression.
- model note: Prior immunotherapy is permitted because prior stage IV treatment may include PD-(L)1, but it is not required; however, immunotherapy within 28 days before first dose is excluded. Brain/CNS involvement appears required by the inclusion criterion for an intracranial measurable lesion, while active CNS metastases and certain CNS sites are excluded.

Will: agree / disagree / needs medical knowledge

## 26. NCT07659782 — brain metastases

_A Phase 2 Study of VS-7375 in Patients With KRAS G12D-Mutated Non-Small Cell Lung Cancer_

- classification: `both_classifications`
- quote: Inclusion Criteria:

Patients with 2L-4L with brain metastases:

* Have asymptomatic and untreated brain metastases
* At least 1 untreated measurable brain lesion per mRECIST v1.1 with a long axis ≥ 0.5 cm and ≤ 3 cm.

Exclusion Criteria:

* Untreated or symptomatic CNS metastasis
- model note: Prior immunotherapy is explicitly required because the inclusion criteria require a prior immune checkpoint inhibitor. Brain metastases are both required for a subgroup ('Patients with 2L-4L with brain metastases') and also excluded in another passage ('Untreated or symptomatic CNS metastasis'), creating conflicting statements about the same fact.

Will: agree / disagree / needs medical knowledge

## 27. NCT04777084 — prior immunotherapy

_The Efficacy and Safety of the Bispecific Anti-PD-1/PD-L1 Antibody IBI318 Combined with Lenvatinib in NSCLC._

- classification: `both_classifications`
- quote: Cohort A: histological or cytological confirmed locally advanced (IIIB-IIIC) or metastatic (stage IV) NSCLC (International Association for the Study of Lung Cancer and Joint Committee on the American Classification of Cancer, TNM Lung cancer stage 8) without EGFR gene sensitive mutations, ALK gene fusion or ROS1 gene fusion confirmed by histological specimens, Relapse after failure of first-line anti-PD-1 /PD-L1 antibody therapy, as follows:

1. Only one anti-PD-1/PD-L1 antibody monotherapy or combination therapy is accepted in the advanced stage of the disease, and other immunotherapy is not allowed;
...
To cohort B and C: Prior treatment: anti-PD-1, anti-PD-L1, or anti-PD-L2 drugs or drugs that target another stimulating or co-inhibiting T-cell receptor (including but not limited to CTLA-4, OX-40, CD137, etc.);
- model note: Prior immunotherapy differs by cohort: it is required for cohort A but barred for cohorts B and C, so the overall trial text contains conflicting eligibility directions for the same fact.

Will: agree / disagree / needs medical knowledge

## 28. NCT04389632 — prior immunotherapy

_A Study of Sigvotatug Vedotin in Advanced Solid Tumors_

- classification: `both_classifications`
- quote: Part B only: Participants must have disease that is relapsed or refractory or be intolerant to standard-of-care therapies. Participants must have received platinum-based therapy and a PD-1/PD-(L)1 inhibitor, if applicable and available.

Part C and D: Prior therapy with a PD-1 inhibitor, anti-PD-(L)1, or anti PD-L2 agent or with an agent directed to another stimulatory or co-inhibitory T-cell receptor and was discontinued from that treatment due to a Grade 3 or higher immune-mediated adverse event (IMAE).
- model note: Prior immunotherapy is required in Part B when applicable and available, but a subset of prior immunotherapy is also excluded in Parts C and D if it was stopped for a Grade 3 or higher immune-mediated adverse event.

Will: agree / disagree / needs medical knowledge

## 29. NCT07638891 — prior immunotherapy

_A Study of HDM2020 in Patients With Advanced Sq-NSCLC_

- classification: `both_classifications`
- quote: Participants must have histologically or cytologically confirmed locally advanced (Stage IIIB/IIIC) or metastatic (Stage IV) squamous non-small cell lung cancer (sqNSCLC) that is not amenable to curative surgical resection, staged according to the 8th edition of the Union for International Cancer Control (UICC) and American Joint Committee on Cancer (AJCC) TNM staging system for lung cancer, and must have experienced treatment failure or intolerance to adequate prior standard-of-care therapy, including platinum-based chemotherapy and anti-PD-1/PD-L1 therapy. ... Participants received standard chemotherapy, biological therapy, immunotherapies, any investigational medicinal product (IMP) and other systemic anti-tumor treatments within 4 weeks before the first dose.
- model note: Prior immunotherapy is required as part of prior standard-of-care failure/intolerance, but immunotherapies are also excluded if received within 4 weeks before the first dose. Brain metastases are excluded only when they are active CNS metastases, so CNS/brain metastases are barred with an activity-based exception.

Will: agree / disagree / needs medical knowledge

## 30. NCT05473156 — prior immunotherapy

_A Study to Investigate the Safety, Pharmacokinetics, and Clinical Activity of AP203 in Patients with Locally Advanced or Metastatic Solid Tumors, and Expansion to Selected Malignancies_

- classification: `both_classifications`
- quote: Participants who have histologically or cytologically confirmed diagnosis of relapsed or refractory, locally unresectable advanced or metastatic NSCLC, HNSCC, ESCC, who received at least one line of systemic treatment including anti-PD-1 or anti-PD-L1 therapy.

Participants who have received concurrent antitumor treatment or investigational products within 28 days or 5 half lives, whichever is shorter before the start of study intervention (e.g., chemotherapy, radiotherapy [with the exception of palliative bone directed radiotherapy], immunotherapy, targeted therapy, hormonal therapy, or cytokine therapy except for erythropoietin).
- model note: Prior immunotherapy is required for the dose expansion NSCLC/HNSCC/ESCC cohorts, but immunotherapy received within 28 days or 5 half-lives before study treatment is excluded, so the trial text contains both a requirement and a bar about the same fact at different time limits.

Will: agree / disagree / needs medical knowledge

## 31. NCT04977791 — prior immunotherapy

_Analysis of Drug Resistance in Immune Checkpoint Inhibitors of Non-small Cell Lung Cancer_

- classification: `both_classifications`
- quote: Inclusion Criteria:

* Patients receiving immune checkpoint inhibitor treatment represented by anti-PD-1/PD-L1 monoclonal antibody;

Exclusion Criteria:

* Have received any approved systemic anti-tumor immunotherapy before starting the research treatment;
- model note: The trial text explicitly includes patients receiving anti-PD-1/PD-L1 immune checkpoint inhibitor treatment, but also excludes patients who have received approved systemic anti-tumor immunotherapy before starting research treatment; these passages conflict for prior immunotherapy.

Will: agree / disagree / needs medical knowledge

## 32. NCT06498635 — prior immunotherapy

_Immunotherapy After Surgery for People Who Have No Remaining Cancer Cells After Standard Treatment for Early-Stage Non-Small Cell Lung Cancer, INSIGHT Trial_

- classification: `both_classifications`
- quote: * Participants must have received at least two cycles of neoadjuvant platinum-based chemotherapy and anti-PD-1 or anti-PD-L1 therapy. The neoadjuvant treatment must be Food and Drug Administration (FDA) approved and standard of care as listed in NCCN guidelines
* Participants must not have received any prior systemic therapy (systemic chemotherapy, immunotherapy or investigational drug) within 28 days prior to randomization
- model note: The trial explicitly requires prior anti-PD-1/PD-L1 therapy, but it also separately says participants must not have received prior systemic immunotherapy within 28 days before randomization, creating conflicting statements about prior immunotherapy.

Will: agree / disagree / needs medical knowledge

## 33. NCT06069570 — prior immunotherapy

_Safety Study for a Gamma Delta T Cell Product Used With Low Dose Radiotherapy in Patients With Locally Advanced or Metastatic NSCLC or Solid Tumors With Bone Metastases_

- classification: `both_classifications`
- quote: * Progressed on SOC therapy including platinum-based chemotherapy and immune checkpoint inhibitors (NSCLC), and are not a candidate for further standard anti-neoplastic therapy and/or have exhibited intolerance to and/or declined clinically applicable salvage therapies, and/or have declined therapy.
* Chemotherapy, investigational, and/or check-point inhibitor therapy within the 30 days prior to study Day 1.
- model note: The trial requires prior immune checkpoint inhibitors for NSCLC participants, but also excludes checkpoint inhibitor therapy within 30 days prior to Day 1, so prior immunotherapy is both required and barred depending on timing. The text does not mention brain metastases, CNS metastases, or leptomeningeal disease.

Will: agree / disagree / needs medical knowledge

## 34. NCT07751042 — prior immunotherapy

_Phase 1/2 Study of Intravenous Injection of STX-003 in Advanced Solid Tumors as Monotherapy or in Combination With Pembrolizumab_

- classification: `both_classifications`
- quote: Prior treatment (for advanced, metastatic or [neo]adjuvant) should have included a platinum-based therapy and a PD-1/L1 pathway checkpoint inhibitor, unless the patient is not a candidate for or has refused viable therapies due to inability to tolerate treatment (i.e. cell therapy) or potential side effects (i.e. checkpoint inhibitor toxicity).

Received an anti-PD-1/PD-L1 inhibitor as monotherapy or in combination with anti-CTLA-4 inhibitor and have either primary or secondary checkpoint inhibitor resistance asper SITC consensus definition, unless deemed intolerable by the Investigator.

Prior IL-12 therapy.
- model note: Prior immunotherapy is required in Phase 2 NSCLC and melanoma, but a different immunotherapy ("Prior IL-12 therapy") is excluded, so the protocol contains both requiring and barring statements within the broader immunotherapy category.

Will: agree / disagree / needs medical knowledge

## 35. NCT06452277 — prior immunotherapy

_A Study to Learn More About How Well Sevabertinib Works and How Safe it is Compared With Standard Treatment, in Participants Who Have Advanced Non-small Cell Lung Cancer (NSCLC) With Mutations of the Human Epidermal Growth Factor Receptor 2 (HER2)_

- classification: `barred_with_exception`
- quote: No prior systemic therapy for locally advanced or metastatic disease. No prior treatment with a HER2 ex20ins-targeted therapy (e.g. poziotinib, trastuzumab deruxtecan). Participants who received adjuvant or neoadjuvant therapy are eligible if the adjuvant/neoadjuvant therapy was completed at least 12 months prior to the start of screening.
- model note: Prior immunotherapy falls under the broader ban on prior systemic therapy for locally advanced or metastatic disease, with an exception for prior adjuvant or neoadjuvant therapy completed at least 12 months before screening; brain metastases are not addressed.

Will: agree / disagree / needs medical knowledge

## 36. NCT04499053 — prior immunotherapy

_Durvalumab and Tremelimumab in Combination With Chemotherapy in HIV-infected Patients With Non-small Cell Lung Cancer_

- classification: `barred_with_exception`
- quote: Patients who have received prior anti-PD-1, anti PD-L1 or anti CTLA-4 within 12 months of the first dose of durvalumab.
- model note: Prior immunotherapy is excluded only if it was anti-PD-1/PD-L1/CTLA-4 within 12 months, so earlier use outside that window is not explicitly excluded. Brain metastases are excluded when previously untreated CNS metastases or leptomeningeal disease are present, implying treated CNS metastases may be allowed, with an added timing limit for recent WBRT.

Will: agree / disagree / needs medical knowledge

## 37. NCT06439914 — prior immunotherapy

_First-in-human Study of Interferon-y PET Imaging to Assess Response to Immunotherapy_

- classification: `barred_with_exception`
- quote: No prior immunotherapy for current stage of NSCLC (Non Small Cell Lung Cancer). Immunotherapy in neoadjuvant or adjuvant setting and have recurrence at least 12 months following completion of immunotherapy are eligible after discussion with the principle investigator.
- model note: Prior immunotherapy is generally excluded for the current stage, with a stated exception for certain prior neoadjuvant or adjuvant immunotherapy cases; brain metastases are not addressed in the provided text.

Will: agree / disagree / needs medical knowledge

## 38. NCT06518057 — brain metastases

_Hippocampal Avoidance in Craniospinal Irradiation for the Treatment of Leptomeningeal Metastases From Breast Cancer or Non-small Cell Lung Cancer_

- classification: `barred_with_exception`
- quote: Brain metastases within 5 mm of the hippocampal contours not previously treated
- model note: Prior immunotherapy is not addressed in the provided eligibility text. Brain metastases are excluded only in the specific case where they are within 5 mm of the hippocampal contours and not previously treated, so this is barred with an exception rather than a complete bar.

Will: agree / disagree / needs medical knowledge

## 39. NCT07253142 — brain metastases

_A Phase II Clinical Study to Evaluate HLX43 in Combination With Serplulimab in Subjects With Advanced Lung Cancer_

- classification: `barred_with_exception`
- quote: Presence of spinal cord compression or clinically active central nervous system metastases (referring to untreated or symptomatic metastases, or metastases requiring corticosteroids or anticonvulsants to control related symptoms), or meningitis carcinomatosa. Subjects who have previously received treatment for brain metastases (e.g., whole-brain radiotherapy or stereotactic brain radiotherapy) may participate in the study, provided they have been clinically stable for at least 4 weeks with no imaging evidence of brain metastasis progression;
- model note: Prior anti-PD-1/L1 therapy is explicitly required as part of prior treatment. Brain/CNS metastases are excluded when clinically active, with an exception for previously treated, clinically stable brain metastases.

Will: agree / disagree / needs medical knowledge

## 40. NCT06896890 — brain metastases

_Cisplatin (CIS) Administered As Dry Powder for Inhalation (DPI) in Patients with Stage IV Non-Small Cell Lung Cancer_

- classification: `barred_with_exception`
- quote: Patients with carcinomatous meningitis or CNS metastases, except where such metastases are stable and already irradiated.
- model note: Prior immunotherapy is explicitly excluded via prior immune checkpoint inhibitor therapy. Brain/CNS involvement is excluded except for stable, already irradiated metastases.

Will: agree / disagree / needs medical knowledge
