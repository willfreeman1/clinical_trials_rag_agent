# Step 8 — Will check: 20 extra exclusions the six-fact key missed

Reading comprehension only. For each row: does the quoted sentence plainly
say what the model claims? Not a medical judgment. Mark agree / disagree /
cannot tell from the quote.

Drawn with seed 20260930 from the expensive model (`gpt-5.4`).
20 of 352 extra exclusions on kept trials.

**Will, 2026-09-30: 20 of 20 agree.** Quote says what the model claims. Not a
medical judgment. Mini's extra exclusions were not in this sheet.

## 1. P01 / NCT06839105

_A Clinical Study to Evaluate the Safety and Tolerability of AWT020 in Patients With Advanced Malignancies_

- fact: `cancer spread to the brain`
- claim: excludes_this_patient
- quote: There is active central nervous system metastasis. If the patient has received radiotherapy or surgery in the past, imaging examination within 4 weeks before the first medication indicates stable brain metastases without aggravation or new neurological symptoms, hormone therapy has been discontinued 2 weeks before the first medication, and screening is allowed; For meningeal and brainstem metastases, screening is not allowed regardless of treatment.
- reasoning: The note says new cerebral lesions were found last week and nothing has been done about them yet, so active CNS metastasis is present.

Will: agree / disagree / cannot tell

## 2. P02 / NCT04486833

_Quaratusugene Ozeplasmid (Reqorsa) and Osimertinib in Patients With Advanced Lung Cancer Who Progressed on Osimertinib_

- fact: `renal function`
- claim: excludes_this_patient
- quote: Adequate renal function documented by serum creatinine of ≤1.5 mg/dL or calculated creatinine clearance >50 ml/min within ≤28 days.
- reasoning: The patient’s creatinine clearance is 37, which is below the required threshold.

- fact: `HIV infection`
- claim: excludes_this_patient
- quote: Known human immunodeficiency virus (HIV) infection or has active hepatitis infection.
- reasoning: The patient is described as HIV positive.

Will: agree / disagree / cannot tell

## 3. V01 / NCT07680764

_A Study To Assess the Safety, Tolerability, and Efficacy of Imzokitug in Combination With Pumitamig and Platinum-Doublet Chemotherapy (PDCT) Versus Pumitamig and PDCT as First-line Treatment for Participants With Locally Advanced or Metastatic Non-Small Cell Lung Cancer (NSCLC)_

- fact: `previous systemic anticancer treatment (any kind)`
- claim: excludes_this_patient
- quote: Participants must have no prior systemic anti-cancer therapy given as primary therapy for advanced or metastatic disease.
- reasoning: The patient has stage IV lung adenocarcinoma and was previously treated with chemotherapy.

Will: agree / disagree / cannot tell

## 4. V01 / NCT05394831

_A Phase 1/2 Study to Evaluate the Safety, Tolerability and PK of JIN-A02 in Patients With EGFR Mutant Advanced NSCLC_

- fact: `tumour genetic marker`
- claim: excludes_this_patient
- quote: Subjects with pathologically confirmed and finally diagnosed advanced and/or metastatic NSCLC with active EGFR mutant
- reasoning: The patient is described as wild type on NGS, so this required EGFR mutation is absent.

- fact: `tumour genetic marker`
- claim: excludes_this_patient
- quote: Subjects with a test result of locally confirmed EGFR mutant obtained through a test method approved by the sponsor using either a tumor tissue and/or plasma ctDNA.
- reasoning: The trial requires a confirmed EGFR mutation, but the patient note says wild type on NGS.

Will: agree / disagree / cannot tell

## 5. P12 / NCT05005403

_Study to Assess Adverse Events and Pharmacokinetics in Adult Participants With Non-Small Cell Lung Cancer, Head and Neck Squamous Cell Carcinoma and Other Solid Tumors, Receiving Intravenous Infusion of Azirkitug Alone or in Combination(s) With Budigalimab, Bevacizumab, or Telisotuzumab Adizutecan_

- fact: `autoimmune disease`
- claim: excludes_this_patient
- quote: No active autoimmune/immunodeficiency disease with limited exceptions
- reasoning: The patient has rheumatoid arthritis on methotrexate, which is an active autoimmune condition.

- fact: `interstitial lung disease`
- claim: excludes_this_patient
- quote: Combination treatment excludes participants treated with anti-programmed cell death protein 1(PD-1)/Programmed cell death ligand 1 (PD-L1) who had immune mediated toxicity G3 or greater, interstitial lung disease, or hypersensitivity Combination treatment may also require no significant cardiac deficiencies and/or events
- reasoning: The patient previously received atezolizumab and has CT changes consistent with ILD.

Will: agree / disagree / cannot tell

## 6. P03 / NCT06481813

_Prospective, Longitudinal Biocollection in Thoracic Oncology, Including Newly Diagnosed Lung Cancer Patients_

- fact: `previous immunotherapy`
- claim: excludes_this_patient
- quote: Previous anticancer treatment for Lung cancer
- reasoning: The patient had pembrolizumab, which is prior anticancer treatment for lung cancer.

Will: agree / disagree / cannot tell

## 7. P12 / NCT06758401

_This is a Study to Learn About How the Combination of the Study Medicines Sigvotatug Vedotin Plus Pembrolizumab Works in People With Non-small Cell Lung Cancer With High Levels of PD-L1._

- fact: `tumour genetic marker`
- claim: excludes_this_patient
- quote: Participants with known AGAs including EGFR, ALK, ROS1, NTRK, BRAF, RET, and MET, for which there are approved and available first-line therapies per local SOC are ineligible.
- reasoning: The patient has EGFR L858R, a known actionable alteration with approved first-line therapy.

- fact: `autoimmune disease`
- claim: excludes_this_patient
- quote: History of autoimmune disease that has required systemic treatment in the past 2 years
- reasoning: The patient has rheumatoid arthritis on methotrexate, which is systemic treatment.

- fact: `interstitial lung disease`
- claim: excludes_this_patient
- quote: Evidence of noninfectious or drug-induced ILD or pneumonitis
- reasoning: The note says CT shows interstitial changes consistent with ILD.

- fact: `previous immunotherapy`
- claim: excludes_this_patient
- quote: Prior systemic therapy, including anti-PD-(L)1 therapy, for locally advanced, unresectable, or metastatic NSCLC.
- reasoning: The patient previously received atezolizumab for stage IV NSCLC.

- fact: `previous systemic anticancer treatment (any kind)`
- claim: excludes_this_patient
- quote: Prior systemic therapy, including anti-PD-(L)1 therapy, for locally advanced, unresectable, or metastatic NSCLC.
- reasoning: The patient had prior carboplatin plus atezolizumab for metastatic NSCLC.

Will: agree / disagree / cannot tell

## 8. P03 / NCT06494540

_NIS to Examine the Effectiveness of TDC in Patients With Metastatic Non-squamous NSCLC and High-risk Genetic Alterations_

- fact: `previous immunotherapy`
- claim: excludes_this_patient
- quote: Decision to start first-line (1L) treatment with TDC according to the current SmPCs
- reasoning: The trial is for starting first-line treatment, and the patient already had pembrolizumab.

- fact: `previous systemic anticancer treatment (any kind)`
- claim: excludes_this_patient
- quote: Decision to start first-line (1L) treatment with TDC according to the current SmPCs
- reasoning: Having already received pembrolizumab means the patient is not starting first-line systemic therapy.

Will: agree / disagree / cannot tell

## 9. V01 / NCT07586826

_Romiplostim N01 Plus ATRA for Persistent Isolated Chemotherapy-Induced Thrombocytopenia After Complete Remission of Gynecologic, Breast, or Lung Solid Tumors_

- fact: `disease stage`
- claim: excludes_this_patient
- quote: Complete remission of the underlying tumor after chemotherapy or antitumor treatment, with tumor-related treatment discontinued for at least 12 weeks before enrollment, no evidence of recurrence or progression by specialist assessment, and no current need for additional tumor-directed therapy.
- reasoning: The patient has stage IV lung adenocarcinoma and is not described as being in complete remission.

- fact: `tumour status`
- claim: excludes_this_patient
- quote: Active recurrence or progression of the underlying tumor, or evidence of bone marrow metastasis or tumor cell infiltration on bone marrow examination.
- reasoning: Stage IV lung adenocarcinoma is active metastatic cancer rather than a post-remission setting.

Will: agree / disagree / cannot tell

## 10. P12 / NCT07440290

_DETERMINE Trial Treatment Arm 07: Dabrafenib in Combination With Trametinib in Adult, Paediatric and Teenage/Young Adult Patients With BRAF V600 Mutation-Positive Cancers._

- fact: `tumour genetic marker`
- claim: excludes_this_patient
- quote: A. Confirmed diagnosis of a malignancy harbouring an oncogenic alteration in BRAF V600, including Langerhans cell histiocytosis, using an analytically validated next-generation sequencing method.
- reasoning: The patient note reports EGFR L858R, not a BRAF V600 alteration.

- fact: `disease stage`
- claim: excludes_this_patient
- quote: A. Diagnosis of one of the following BRAF V600E mutation-positive cancers:

* Colorectal cancer in adult (≥18 years) patients;
* Unresectable or metastatic melanoma in adult (≥18 years) patients;
* Advanced non-small cell lung cancer in adult (≥18 years) patients;
* Gliomas harbouring a BRAF V600E mutation in paediatric (1 to <16 years) or TYA (16 to <18 years) patients.
- reasoning: The patient has stage IV adenocarcinoma of the lung, which is advanced non-small cell lung cancer.

Will: agree / disagree / cannot tell

## 11. P02 / NCT05194982

_A Study of BL-B01D1 in Patients With Locally Advanced or Metastatic Solid Tumor_

- fact: `kidney function`
- claim: excludes_this_patient
- quote: 11. The organ function level must meet the following requirements: a) bone marrow function: absolute neutrophilic granulocyte count (ANC) ≥1.5×109/L, platelet count ≥90×109/L, hemoglobin ≥90 g/L; b) Liver function: total bilirubin (TBIL≤1.5 ULN), AST and ALT ≤2.5 ULN in patients without liver metastasis, AST and ALT ≤5.0 ULN in patients with liver metastasis; c) Kidney function: creatinine (Cr) ≤1.5 ULN, or creatinine clearance (Ccr) ≥50 mL/min (according to Cockcroft and Gault formula).
- reasoning: The patient has creatinine clearance 37, which is below the required Ccr ≥50 mL/min unless creatinine is ≤1.5 ULN.

- fact: `HIV infection`
- claim: excludes_this_patient
- quote: 13. Positive human immunodeficiency virus antibody (HIVAb), active tuberculosis, active hepatitis B virus infection (HBV-DNA copy number > 103 IU/ml) or active hepatitis C virus infection (HCV antibody positive and HCV-RNA > lower limit of detection).
- reasoning: The patient is HIV positive, and the trial excludes positive HIV antibody.

Will: agree / disagree / cannot tell

## 12. P12 / NCT06043973

_Almonertinib Combined With Anlotinib as First-line Treatment for Advanced Non-small Cell Lung Cance_

- fact: `previous chemotherapy (any kind)`
- claim: excludes_this_patient
- quote: Patients who had not previously received systemic radiotherapy and chemotherapy or who had relapsed for more than 6 months of follow-up after onset of adjuvant chemotherapy.
- reasoning: The patient has already received carboplatin, which is prior chemotherapy.

- fact: `previous systemic anticancer treatment (any kind)`
- claim: excludes_this_patient
- quote: Patients who had not previously received systemic radiotherapy and chemotherapy or who had relapsed for more than 6 months of follow-up after onset of adjuvant chemotherapy.
- reasoning: The patient has had one prior systemic treatment line including carboplatin and atezolizumab.

- fact: `autoimmune disease`
- claim: excludes_this_patient
- quote: Active pulmonary tuberculosis; Active autoimmune disease requiring systemic therapy (such as the use of disease-modifying drugs, glucocorticoids, or immunosuppressants) within 2 years prior to the first dose.
- reasoning: The patient has rheumatoid arthritis on methotrexate, a disease-modifying systemic therapy.

Will: agree / disagree / cannot tell

## 13. P02 / NCT07225036

_Promoting Immunotherapy Efficacy With Low-Dose Liver RT_

- fact: `tumour genetic marker`
- claim: excludes_this_patient
- quote: Patients with NSCLC are ineligible for enrollment in cohort 1 if the presence of the following driver mutations are noted: EGFR, ALK, ROS1, RET.
- reasoning: The patient is L858R positive, which is an EGFR mutation named in this exclusion for cohort 1.

Will: agree / disagree / cannot tell

## 14. P12 / NCT07085091

_A First in Human Study of ALX2004 With Advanced or Metastatic Selected Solid Tumors_

- fact: `tumour genetic marker`
- claim: excludes_this_patient
- quote: NSCLC - For participants with a targetable molecular alteration: received appropriate standard targeted therapy and no more than 2 prior lines of systemic chemotherapy in the advanced/metastatic setting.
- reasoning: The patient has EGFR L858R, a targetable alteration, and the note does not show prior appropriate standard targeted therapy.

Will: agree / disagree / cannot tell

## 15. V01 / NCT06705465

_Cross-sectorial Rehabilitation of Patients with Lung Cancer_

- fact: `previous systemic anticancer treatment (any kind)`
- claim: excludes_this_patient
- quote: 1. line systemic treatment
- reasoning: The trial is for patients in first-line systemic treatment, and this patient was previously treated with chemotherapy.

Will: agree / disagree / cannot tell

## 16. P09 / NCT05991193

_A Study With Central Nervous System Metastatic EGFR Mutation Positive Non-small Cell Lung Cancer_

- fact: `previous immunotherapy`
- claim: excludes_this_patient
- quote: Patients must have untreated advanced Non-Small Cell Lung Cancer (NSCLC).
- reasoning: The patient already received pembrolizumab, so the advanced NSCLC is not untreated.

- fact: `previous platinum chemotherapy`
- claim: excludes_this_patient
- quote: Patients must have untreated advanced Non-Small Cell Lung Cancer (NSCLC).
- reasoning: The patient already received carboplatin, so the advanced NSCLC is not untreated.

- fact: `previous systemic anticancer treatment (any kind)`
- claim: excludes_this_patient
- quote: Patients must have untreated advanced Non-Small Cell Lung Cancer (NSCLC).
- reasoning: The patient has had one prior line of systemic treatment, so the disease is not untreated.

Will: agree / disagree / cannot tell

## 17. P02 / NCT07359040

_Mechanism of Enhanced Efficacy of Ivonescimab in Neoadjuvant Therapy for Non-Small Cell Lung Cancer_

- fact: `disease stage`
- claim: excludes_this_patient
- quote: Unresectable advanced disease (Stage IV) or locally advanced unresectable (Stage IIIC);
- reasoning: The patient is described as metastatic, which is Stage IV disease.

Will: agree / disagree / cannot tell

## 18. P09 / NCT07229729

_A Study of SHR-A2102 in Combination With Other Anti-tumor Therapies for Resectable Non-small Cell Lung Cancer_

- fact: `HIV infection`
- claim: excludes_this_patient
- quote: Has a known history of human immunodeficiency virus (HIV) infection;
- reasoning: The patient is HIV positive, so this exclusion applies.

Will: agree / disagree / cannot tell

## 19. P12 / NCT06618287

_A Study to Evaluate the Safety, Tolerability, Drug Levels, and Preliminary Efficacy of BMS-986507 Combinations in Adult Participants With Advanced Solid Tumors_

- fact: `tumour genetic marker`
- claim: excludes_this_patient
- quote: Participants with known mutations in EGFR will be excluded (Group A,B and E).
- reasoning: The patient has an EGFR L858R mutation, which is a known EGFR mutation.

Will: agree / disagree / cannot tell

## 20. P03 / NCT05059444

_ORACLE: Observation of ResiduAl Cancer With Liquid Biopsy Evaluation_

- fact: `disease stage`
- claim: excludes_this_patient
- quote: * Cohort 2: Cohort 2: Non-small cell lung cancer (stage IB-III):
- reasoning: The patient has stage IV lung adenocarcinoma, not stage IB-III.

- fact: `treatment intent`
- claim: excludes_this_patient
- quote: * Initial treatment is given with curative/radical intent AND
- reasoning: The patient has metastatic stage IV disease, so this note does not match curative/radical-intent initial treatment.

- fact: `metastatic disease at enrollment`
- claim: excludes_this_patient
- quote: * Known distant metastasis at time of enrollment (with the exception of participants with limited/resectable stage IV cutaneous melanoma or RCC)
- reasoning: The patient has brain metastases from lung cancer, which are distant metastases and not one of the listed exceptions.

Will: agree / disagree / cannot tell
