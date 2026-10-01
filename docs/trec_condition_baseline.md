# TREC condition-field baseline (2021/2022 only)

**No. The free `conditions` field does not already do the retrieval step's job.**

Gates committed in `9ffa03b` before any match rate or matched-depth recall.
2023 was not run. No six-name code. No trial text to an LLM. No reranker.

Disease term is the first already-generated keyword. Strict is normalised equality.
Loose is strict, or substring either way, or token overlap.
Keyword hybrid is the same BM25 + MedCPT + RRF as `docs/trec_hybrid_retrieval.md`,
ranked over the whole judged pool (that is why hybrid at 6% is 91.1% / 91.2% here
instead of 91.6% / 91.4% on the top-1000 lists). Combination is the loose filter
first, then that hybrid inside the survivors.

The empty-field failure mode is not the problem. 7 of 26,162 pool trials (2021)
and 3 of 26,585 (2022) have an empty `conditions` field. One eligible trial in
2021 is empty; none in 2022. Loose matching retained at least one trial for
every patient (Wilson upper bound 4.9% / 7.1% on 75 and 50 topics). The field
is populated. It still misses too many eligible trials.

## Empty or unmatchable

| Year | Pool trials with empty conditions | Eligible trials with empty conditions | Patients with zero loose matches |
|---|---:|---:|---:|
| 2021 | 7/26162 (0.0%) | 1 (0.0%) | 0/75 (0.0%–4.9%) |
| 2022 | 3/26585 (0.0%) | 0 (0.0%) | 0/50 (0.0%–7.1%) |

## Filter vs keyword hybrid at matched depth

Per patient, *k* is how many trials the filter kept. Hybrid is scored at that same *k*.
Headline reading is from **loose**.

| Year | Strength | Mean *k* | Mean share of pool | Filter eligible recall | Hybrid @ *k* | Gap | Reading |
|---|---|---:|---:|---:|---:|---:|---|
| 2021 | strict | 74.4 | 0.3% | 23.7% | 20.9% | -2.9 pts | within_3 |
| 2021 | loose | 994.0 | 3.8% | 62.3% | 73.3% | 11.0 pts | more_than_10_worse |
| 2022 | strict | 48.5 | 0.2% | 24.0% | 20.5% | -3.5 pts | within_3 |
| 2022 | loose | 580.9 | 2.2% | 49.2% | 62.2% | 13.0 pts | more_than_10_worse |

## Combination (loose filter, then keyword hybrid)

| Year | Hybrid @ 6% of pool | Combo @ 6% of pool | Loose filter recall (all survivors) |
|---|---:|---:|---:|
| 2021 | 91.1% | 62.2% | 62.3% |
| 2022 | 91.2% | 49.2% | 49.2% |

## Combination and hybrid at fixed depths (eligible recall)

| Year | System | @10 | @20 | @50 | @100 | @200 | @500 | @6% |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2021 | hybrid | 5.7% | 10.4% | 22.1% | 36.4% | 52.7% | 75.8% | 91.1% |
| 2021 | combo | 5.7% | 10.8% | 20.8% | 31.5% | 43.1% | 57.2% | 62.2% |
| 2022 | hybrid | 7.4% | 13.4% | 26.8% | 40.5% | 58.5% | 79.3% | 91.2% |
| 2022 | combo | 8.3% | 14.0% | 24.2% | 34.9% | 43.4% | 48.5% | 49.2% |

## Reading

Retrieval is doing real work beyond disease matching. The committed table is
read from **loose**. 2021: 62.3% vs 73.3% at matched depth (**11.0 points**
worse). 2022: 49.2% vs 62.2% (**13.0 points** worse). Both years are past the
10-point line.

That gap is not an empty field. It is what the first keyword cannot see.

The 604,566 → 1,308 NSCLC query at the start of this project is a
single-disease cut. TREC 2021/2022 notes are not. Eligible trials are often
for a second problem in the same note, for a parent or sibling heading, or
for a synonym the first keyword does not share a token with. Keyword
retrieval reads the rest of the note. The conditions field, given one
disease string, does not.

Strict looks "within 3 points" of hybrid at matched depth (23.7% vs 20.9% in
2021; 24.0% vs 20.5% in 2022). That is not a win. Strict keeps a mean of 74
and 48 trials and only about a quarter of the eligible set. Hybrid is equally
weak at those tiny depths. Equality at 24% is not the retrieval job.

Loose token overlap also inflates *k* on generic words. `coronary artery
disease` keeps 2,766 trials because `disease` hits every "X disease" row.
`Kallmann syndrome` and `Turner syndrome` keep ~1,500 because `syndrome`
does the same. That gives hybrid a larger matched-depth budget. It does not
create the 62% / 49% filter recalls: those eligible trials are gone no
matter how hybrid is scored. Micro-average is the same story (64.3% of 5,570
eligible in 2021; 57.0% of 3,939 in 2022).

The combination does not beat both. At 6% of the pool it is 62.2% / 49.2% —
the filter's ceiling — against hybrid 91.1% / 91.2%. At depth 10 the two
are level. Hybrid then pulls away as it keeps finding trials the field
dropped.

Do not replace the first stage with this field. Do not start a reranker from
this measurement; it only decides that a reranker, if built, would sit on
keyword retrieval, not on a conditions query.

## Why the loose filter loses

29 of 75 topics in 2021 and 23 of 50 in 2022 are more than 10 points behind
hybrid at that topic's own *k*. The misses fall into three piles. A topic
can sit in more than one.

**The first keyword is not the judged condition.** The note lists several
problems; the keyword prompt put one first. TREC eligible trials are often
for another one.

- 2021 topic 5 / 19: first keyword `coronary artery disease`. The notes also
  have carotid stenosis and prior stroke. Missed eligible rows are Carotid
  Stenosis, Stroke, Cerebral Infarction.
- 2021 topic 6: first keyword `end-stage renal disease`. The admission is
  recurrent *C. difficile*. Missed rows are Clostridium Infections,
  Pseudomembranous Colitis.
- 2021 topic 9: `severe intellectual disability`. The admission is a
  seizure. Missed rows are Epilepsy.
- 2021 topic 12: `Marfan's syndrome`. The admission is mitral-valve repair.
  Missed rows are Mitral Valve Insufficiency.
- 2021 topics 21 / 26 / 53 and 2022 topics 2 / 12: first keyword is a
  symptom (`abdominal pain`, `bone pain`, `vaginal spotting`, `chronic
  cough`). Trials name the disease (cholecystitis, vitamin D deficiency,
  incomplete abortion, pulmonary fibrosis).

**Same condition, different string.** Loose still fails when there is no
shared token.

- `major depressive disorder` misses trials labelled only `Depression`.
- `Cerebrovascular Accident` misses `Stroke`.
- `neonatal jaundice` misses `Hyperbilirubinemia`.
- `Hashimoto disease` misses `Hashimotos Thyroiditis` (the extra `s`, and
  `disease` / `thyroiditis` do not overlap).
- `cataracts` (plural) misses `Cataract`.
- `stage 1B cervical cancer` misses `Cervix Neoplasms`.
- `chronic lymphocytic leukemia` misses `B-CLL`, `Leukaemia`, `Richter's
  Syndrome`.

**Parent or sibling heading.** Kallmann → Hypogonadism. Hepatitis C →
Cirrhosis / Liver Fibrosis. Turner → Growth Disorders. Acute urinary
retention → Benign Prostatic Hyperplasia. *C. difficile* infection →
Enterocolitis / Antibiotic-Associated Colitis.

None of these are empty-field misses. The field has a condition; it is not
the first keyword.

## Patients the loose filter loses by more than 10 points

### 2021 (29 topics)

- **Topic 5** `coronary artery disease`: filter 62.2% vs hybrid 93.3% at k=2766; 119 eligible, 0 with empty conditions.
  - NCT00000469: Cardiovascular Diseases; Carotid Stenosis; Cerebral Arteriosclerosis; Cerebrovascular Disorders; Heart Diseases; Vascular Diseases
  - NCT00004732: Atherosclerosis; Stroke; Carotid Stenosis; Cerebral Infarction; Myocardial Infarction
  - NCT00011258: Carotid Stenosis
  - NCT00119041: Diabetes Mellitus Type 2; Diabetes Mellitus, Type 1; Primary Care Provider
- **Topic 6** `end-stage renal disease`: filter 27.4% vs hybrid 97.4% at k=3133; 117 eligible, 0 with empty conditions.
  - NCT00269399: Clostridium Infections; Diarrhea
  - NCT00304369: Clostridium Enterocolitis; Pseudomembranous Colitis; Antibiotic-Associated Colitis
  - NCT00304863: Enterocolitis; Pseudomembranous Colitis; Antibiotic-associated Colitis
  - NCT00304876: Enterocolitis; Pseudomembranous Colitis; Antibiotic-Associated Colitis
- **Topic 8** `chronic lymphocytic leukemia`: filter 80.4% vs hybrid 98.9% at k=1739; 92 eligible, 0 with empty conditions.
  - NCT00162851: B-CLL
  - NCT00290498: Lymphoma
  - NCT01171378: Richter's Syndrome
  - NCT01313689: Leukaemia
- **Topic 9** `severe intellectual disability`: filter 15.4% vs hybrid 53.8% at k=208; 13 eligible, 0 with empty conditions.
  - NCT00013845: Epilepsy
  - NCT00231556: Epilepsy; Seizures; Epilepsies, Partial; Epilepsy, Generalized; Epilepsy, Tonic-Clonic
  - NCT00510783: Tonic-clonic Seizure
  - NCT01663545: Epilepsies, Partial
- **Topic 12** `Marfan's syndrome`: filter 9.6% vs hybrid 97.1% at k=1136; 104 eligible, 0 with empty conditions.
  - NCT00001314: Aortic Valve Insufficiency; Mitral Valve Insufficiency
  - NCT00209274: Mitral Valve Insufficiency; Mitral Valve Regurgitation; Mitral Valve Incompetence; Mitral Regurgitation; Mitral Insufficiency
  - NCT00209339: Mitral Valve Insufficiency; Mitral Valve Regurgitation; Mitral Valve Incompetence; Mitral Regurgitation; Mitral Insufficiency
  - NCT00587899: Atrial Fibrillation
- **Topic 13** `Cerebrovascular Accident`: filter 0.0% vs hybrid 18.5% at k=81; 54 eligible, 0 with empty conditions.
  - NCT00005985: Lymphoma
  - NCT00195286: Urinary Infections
  - NCT00210990: Urinary Tract Infections; Pyelonephritis
  - NCT00229021: Urinary Tract Infections; Pyelonephritis
- **Topic 16** `chronic hypoxemia`: filter 38.7% vs hybrid 75.8% at k=1528; 62 eligible, 0 with empty conditions.
  - NCT00303004: Eisenmenger Syndrome
  - NCT00309790: Congestive Heart Failure
  - NCT00614900: COPD; Pulmonary Hypertension
  - NCT00628082: Heart Failure, Diastolic
- **Topic 18** `benign prostatic hyperplasia`: filter 14.3% vs hybrid 71.4% at k=319; 14 eligible, 0 with empty conditions.
  - NCT00662064: Urologic Diseases
  - NCT00978991: Prostate Cancer; Bladder Cancer; Erectile Dysfunction; Incontinence
  - NCT01196572: Urethral Strictures
  - NCT01388348: Bladder Outlet Obstruction
- **Topic 19** `coronary artery disease`: filter 9.6% vs hybrid 95.7% at k=2766; 115 eligible, 1 with empty conditions.
  - NCT00000531: Arrhythmia; Cardiovascular Diseases; Death, Sudden, Cardiac; Heart Diseases; Tachycardia, Ventricular; Ventricular Fibrillation
  - NCT00005202: Cardiovascular Diseases; Arrhythmia; Death, Sudden, Cardiac; Heart Diseases; Syncope
  - NCT00005243: Cardiovascular Diseases; Arrhythmia; Myocardial Infarction; Heart Diseases
  - NCT00006501: Heart Diseases; Ventricular Arrhythmia; Ventricular Fibrillation; Death, Sudden, Cardiac; Heart Arrest
- **Topic 21** `abdominal pain`: filter 6.1% vs hybrid 67.3% at k=985; 49 eligible, 0 with empty conditions.
  - NCT00075205: Healthy; Alcohol Drinking
  - NCT00483912: Pancreatitis; Multiple Organ Failure
  - NCT00490386: Pancreatitis, Acute; Helicobacter Infections
  - NCT00699933: Acute Pancreatitis
- **Topic 22** `acute appendicitis`: filter 77.5% vs hybrid 98.6% at k=975; 71 eligible, 0 with empty conditions.
  - NCT00673374: Abdominal Pain
  - NCT01080690: Abdominal Pain
  - NCT01639170: Prediction of Gastrointestinal Perforation
  - NCT01962610: Abdominal Pain Care
- **Topic 24** `lower urinary tract symptoms`: filter 33.3% vs hybrid 91.0% at k=533; 111 eligible, 0 with empty conditions.
  - NCT00154843: BPH
  - NCT00169767: Benign Prostatic Hyperplasia
  - NCT00280605: Prostatic Hyperplasia
  - NCT00347061: Benign Prostatic Hyperplasia
- **Topic 26** `abdominal pain`: filter 18.4% vs hybrid 88.5% at k=985; 87 eligible, 0 with empty conditions.
  - NCT00370344: Biliary Tract Diseases; Gallbladder Diseases; Cholecystitis; Cholecystolithiasis
  - NCT00447304: Acute Cholecystitis
  - NCT00530998: Appendicitis; Cholelithiasis; Gallstones
  - NCT00575276: Cholecystitis, Acute; Cholecystitis, Chronic
- **Topic 27** `chronic hepatitis C`: filter 87.7% vs hybrid 98.2% at k=1855; 57 eligible, 0 with empty conditions.
  - NCT00043303: Liver Fibrosis; Cirrhosis
  - NCT01029873: Metastatic Melanoma
  - NCT01957319: Work Ability; Depression
  - NCT03296930: Antiviral Drug Adverse Reaction
- **Topic 31** `stage 1B cervical cancer`: filter 73.3% vs hybrid 95.6% at k=2541; 45 eligible, 0 with empty conditions.
  - NCT00119509: Cervix Neoplasms
  - NCT00183456: HIV Infections; Sexually Transmitted Diseases
  - NCT00342511: HPV
  - NCT00947271: HIV; Sexually Transmitted Diseases; HIV Infections
- **Topic 32** `hemolytic uremic syndrome`: filter 30.8% vs hybrid 69.2% at k=1157; 26 eligible, 0 with empty conditions.
  - NCT00311831: Gastroenteritis
  - NCT00340509: Genetics
  - NCT00429325: Acute Diarrhea
  - NCT00673374: Abdominal Pain
- **Topic 34** `major depressive disorder`: filter 40.5% vs hybrid 74.7% at k=650; 79 eligible, 0 with empty conditions.
  - NCT00009659: Postmenopause
  - NCT00021528: Depression
  - NCT00103415: Depression
  - NCT00200902: Depression
- **Topic 39** `neonatal jaundice`: filter 76.5% vs hybrid 97.1% at k=137; 34 eligible, 0 with empty conditions.
  - NCT00000910: HIV Infections; Pregnancy
  - NCT00635375: Hyperbilirubinemia
  - NCT00653874: Hyperbilirubinemia
  - NCT01550627: Hyperbilirubinemia
- **Topic 43** `Clostridium difficile infection`: filter 79.4% vs hybrid 93.7% at k=768; 63 eligible, 0 with empty conditions.
  - NCT00097422: Diarrhea
  - NCT00164957: Aspiration Pneumonia
  - NCT00304876: Enterocolitis; Pseudomembranous Colitis; Antibiotic-Associated Colitis
  - NCT00580346: Aspiration Pneumonia
- **Topic 49** `Turner syndrome`: filter 77.1% vs hybrid 97.1% at k=1136; 35 eligible, 0 with empty conditions.
  - NCT00001754: Developmental Bone Disease; Dwarfism; Skeletal Dysplasias
  - NCT00004793: Growth Disorders
  - NCT00025870: Genetic Disorder; Metabolic Disease
  - NCT00163215: Endocrine System Diseases
- **Topic 51** `pregnancy`: filter 3.6% vs hybrid 60.7% at k=224; 28 eligible, 0 with empty conditions.
  - NCT00210886: Urinary Tract Infections; Pyelonephritis
  - NCT00404625: Enterobacteriaceae Infections; Bacteremia; Pneumonia; Skin Diseases; Urinary Tract Infections
  - NCT00690378: Complicated Urinary Tract Infection
  - NCT01413555: Bacteremia
- **Topic 53** `bone pain`: filter 12.1% vs hybrid 100.0% at k=1054; 33 eligible, 0 with empty conditions.
  - NCT00395538: Hypoparathyroidism; DiGeorge Syndrome
  - NCT00682214: Vitamin D Deficiency
  - NCT00742235: Healthy Subjects; Vitamin D Deficiency
  - NCT00780247: Vitamin D Deficiency
- **Topic 57** `acute pancreatitis`: filter 63.0% vs hybrid 86.1% at k=967; 108 eligible, 0 with empty conditions.
  - NCT00124033: Choledocholithiasis; Cholelithiasis
  - NCT00531219: Appendicitis; Cholelithiasis
  - NCT00550511: Abdominal Pain
  - NCT00807729: Choleclithiasis; Common Bile Duct Stones
- **Topic 60** `acute urinary retention`: filter 20.8% vs hybrid 98.7% at k=1251; 149 eligible, 0 with empty conditions.
  - NCT00064649: Benign Prostatic Hyperplasia
  - NCT00090103: Prostatic Hyperplasia
  - NCT00169767: Benign Prostatic Hyperplasia
  - NCT00199550: BPH; Benign Prostatic Hyperplasia
- **Topic 62** `carotid artery stenosis`: filter 53.8% vs hybrid 78.5% at k=660; 65 eligible, 0 with empty conditions.
  - NCT00005203: Cardiovascular Diseases; Heart Diseases; Hypercholesterolemia
  - NCT00005372: Atherosclerosis; Cardiovascular Diseases; Heart Diseases
  - NCT00006295: Cardiovascular Diseases; Heart Diseases; Atherosclerosis
  - NCT00013741: Myocardial Infarction; Coronary Disease
- **Topic 66** `Hashimoto disease`: filter 27.3% vs hybrid 100.0% at k=2598; 11 eligible, 0 with empty conditions.
  - NCT00001159: Hyperthyroidism; Hypothyroidism; Iodine Deficiency
  - NCT00150033: Thyroid Diseases
  - NCT00206375: Hypothyroidism
  - NCT00271427: Autoimmune Thyroiditis; Hashimotos Thyroiditis
- **Topic 67** `abnormal cervical squamous intraepithelial lesion`: filter 80.0% vs hybrid 100.0% at k=503; 60 eligible, 0 with empty conditions.
  - NCT00154479: Cancer of Cervix
  - NCT00266266: Papilloma Virus, Human
  - NCT00342511: HPV
  - NCT01384370: Human Papillomavirus Infection
- **Topic 68** `atypical hemolytic uremic syndrome`: filter 25.6% vs hybrid 74.4% at k=1179; 43 eligible, 0 with empty conditions.
  - NCT00148044: Kidney Failure, Acute
  - NCT00299949: Sepsis; Disseminated Intravascular Coagulation
  - NCT00406198: Bacteremia; Gram-Negative Bacterial Infections; Gram-Positive Bacterial Infections; Pneumonia, Bacterial; Shock, Septic; Sepsis
  - NCT00503165: Vaccination
- **Topic 70** `major depressive disorder`: filter 79.1% vs hybrid 99.1% at k=650; 110 eligible, 0 with empty conditions.
  - NCT00172549: Depression
  - NCT00641108: Depression
  - NCT00655057: Depression
  - NCT00760097: Depression

### 2022 (23 topics)

- **Topic 1** `Kallmann syndrome`: filter 5.3% vs hybrid 98.7% at k=1493; 76 eligible, 0 with empty conditions.
  - NCT00161421: Contraception; Hypogonadism
  - NCT00204269: Hypogonadism
  - NCT00220298: Hypogonadism
  - NCT00372008: Hypogonadism
- **Topic 2** `vaginal spotting`: filter 0.0% vs hybrid 30.5% at k=50; 59 eligible, 0 with empty conditions.
  - NCT00129506: Unwanted Pregnancies
  - NCT00177372: Anembryonic Pregnancy; Gestation Abnormality; Intrauterine Fetal Demise Term
  - NCT00426491: Abortifacient Agents, Nonsteroidal; Abortion, Incomplete; Misoprostol; Pregnancy
  - NCT00449514: Infertility
- **Topic 5** `exercise-induced syncope`: filter 27.1% vs hybrid 67.8% at k=240; 59 eligible, 0 with empty conditions.
  - NCT00001225: Hypertrophic Cardiomyopathy
  - NCT00001313: Peripheral Artery Disease; Coronary Disease; Diabetes and Heart Failure; Dilated Cardiomyopathy; Heart Failure; Renal Artery Stenosis; Pulmonary Hypertension
  - NCT00001530: Cardiomyopathy, Hypertrophic
  - NCT00001894: Hypertrophic Cardiomyopathy
- **Topic 8** `Hirschsprung's disease`: filter 85.7% vs hybrid 100.0% at k=2345; 14 eligible, 0 with empty conditions.
  - NCT02234219: Constipation
  - NCT02255747: Constipation
- **Topic 9** `esophageal diverticulum`: filter 18.2% vs hybrid 36.4% at k=204; 77 eligible, 0 with empty conditions.
  - NCT00001220: Deglutition Disorder; Motor Neuron Disease
  - NCT00038350: Dysphagia
  - NCT00080275: Hypercholesterolemia
  - NCT00082251: Hypercholesterolemia
- **Topic 11** `diffuse-type gastric adenocarcinoma`: filter 61.7% vs hybrid 89.8% at k=807; 235 eligible, 0 with empty conditions.
  - NCT00003938: Cancer
  - NCT00142038: Stomach Neoplasm; Neoplasm Metastasis
  - NCT00222131: Indigestion
  - NCT00231881: Gastroesophageal Reflux
- **Topic 12** `chronic cough`: filter 15.7% vs hybrid 98.0% at k=1178; 51 eligible, 0 with empty conditions.
  - NCT00005317: Lung Diseases; Pulmonary Fibrosis; Lung Diseases, Interstitial; Scleroderma, Systemic
  - NCT00016627: Pulmonary Fibrosis; Lung Diseases; Lung Diseases, Interstitial
  - NCT00084305: Pulmonary Fibrosis; Healthy Volunteers; Hermansky-Pudlak Syndrome (HPS)
  - NCT00131274: Idiopathic Pulmonary Fibrosis; Lung Disease; Pulmonary Fibrosis
- **Topic 13** `infertility`: filter 50.0% vs hybrid 78.6% at k=306; 14 eligible, 0 with empty conditions.
  - NCT00241436: Gynecomastia
  - NCT00896272: Klinefelter Syndrome
  - NCT01750632: Klinefelter Syndrome
  - NCT01817296: Klinefelter Syndrome
- **Topic 17** `cataracts`: filter 0.0% vs hybrid 29.2% at k=62; 24 eligible, 0 with empty conditions.
  - NCT00006202: Macular Degeneration
  - NCT00013377: Low Vision
  - NCT00069199: Retinal Disease; Healthy
  - NCT00272376: Myopia
- **Topic 18** `recurrent rash`: filter 0.0% vs hybrid 69.4% at k=241; 36 eligible, 0 with empty conditions.
  - NCT00102570: Hypersensitivity, Immediate
  - NCT00130364: Atopic Dermatitis
  - NCT00257582: Pruritus
  - NCT00277433: Dermatitis, Atopic
- **Topic 22** `fragile X syndrome`: filter 51.9% vs hybrid 92.2% at k=1493; 77 eligible, 0 with empty conditions.
  - NCT00001544: Attention Deficit Disorder With Hyperactivity; Bipolar Disorder; Mental Disorder Diagnosed in Childhood; Mental Retardation; Schizophrenia
  - NCT00134823: Medication Errors; Medical Records Systems, Computerized; Patient Safety; Quality Improvement
  - NCT00140088: Procedural Pain
  - NCT00519311: Vision Impairment; Hearing Impairment; Obesity
- **Topic 23** `Sjogren's syndrome`: filter 75.2% vs hybrid 90.1% at k=1495; 121 eligible, 0 with empty conditions.
  - NCT00048685: Xerostomia; Autoimmune Diseases
  - NCT00502073: Dry Eye Syndromes
  - NCT00548301: Dry Eye Syndromes
  - NCT00599716: Dry Eye Disease
- **Topic 26** `primary adrenal insufficiency`: filter 73.3% vs hybrid 100.0% at k=396; 30 eligible, 0 with empty conditions.
  - NCT00004313: Addison's Disease
  - NCT00753597: Autoimmune Adrenocortical Failure
  - NCT01063569: Addison's Disease
  - NCT01271296: Addison Disease
- **Topic 27** `Lyme disease`: filter 52.0% vs hybrid 92.0% at k=2354; 25 eligible, 0 with empty conditions.
  - NCT00429117: Stress
  - NCT00910715: Erythema Chronicum Migrans
  - NCT02145754: Erythema Migrans
  - NCT02147249: Erythema Migrans
- **Topic 28** `bleeding disorder`: filter 8.2% vs hybrid 44.9% at k=753; 49 eligible, 0 with empty conditions.
  - NCT00697385: vonWillebrand Disease; Hemophilia; Platelet Coagulation Disorders
  - NCT00864136: Menorrhagia
  - NCT00904709: Menorrhagia
  - NCT00922233: Healthy
- **Topic 29** `Cauda Equina syndrome`: filter 7.1% vs hybrid 85.7% at k=1493; 14 eligible, 0 with empty conditions.
  - NCT00011570: Spinal Cord Injury
  - NCT00163553: Sciatica
  - NCT00213356: Spinal Cord Injuries
  - NCT01599910: Scribes in the Emergency Department
- **Topic 33** `Marfan syndrome`: filter 26.7% vs hybrid 55.0% at k=1492; 60 eligible, 0 with empty conditions.
  - NCT00000123: Astigmatism; Myopia
  - NCT00001466: Hereditary Diseases
  - NCT00001605: Otitis Media
  - NCT00006146: Influenza
- **Topic 34** `lateral epicondylitis`: filter 33.3% vs hybrid 91.7% at k=263; 12 eligible, 0 with empty conditions.
  - NCT00110318: Tennis Elbow; Musculoskeletal Diseases
  - NCT00497913: Tennis Elbow
  - NCT01308463: Survivorship; Pain
  - NCT01659112: Upper Extremity Injuries
- **Topic 37** `Cushing Syndrome`: filter 87.2% vs hybrid 100.0% at k=1519; 39 eligible, 0 with empty conditions.
  - NCT00591643: Adrenal Tumors; Adrenal Malignancies; Abnormal Hormonal Secretions; Electrolytes Abnormalities
  - NCT01428336: Adrenal Insufficiency
  - NCT02202902: Endocrine System Disease; Cardiovascular Imaging
  - NCT04121988: Pituitary ACTH Secreting Adenoma
- **Topic 40** `prolonged oral bleeding`: filter 16.0% vs hybrid 55.7% at k=241; 106 eligible, 0 with empty conditions.
  - NCT00001724: Pain
  - NCT00003937: Cardiac Toxicity; Sarcoma
  - NCT00111215: Menorrhagia; Blood Coagulation Disorders; Blood Platelet Disorders; Von Willebrand Disease; Hematologic Disease
  - NCT00151125: Von Willebrand Disease
- **Topic 42** `Turner syndrome`: filter 37.8% vs hybrid 80.0% at k=1492; 45 eligible, 0 with empty conditions.
  - NCT00001466: Hereditary Diseases
  - NCT00025870: Genetic Disorder; Metabolic Disease
  - NCT00190658: Failure to Thrive
  - NCT00214448: Genetic Disorders
- **Topic 43** `skin rash`: filter 23.1% vs hybrid 53.8% at k=219; 13 eligible, 0 with empty conditions.
  - NCT00341497: Lichen Planus; Oral Leukoplakia; Mouth Neoplasms
  - NCT00877409: Acne Vulgaris
  - NCT01862809: Microbiota; Lung Cancer; Oral Cancer
  - NCT02122432: Dermatologic Conditions
- **Topic 45** `Down syndrome`: filter 81.8% vs hybrid 100.0% at k=1492; 11 eligible, 0 with empty conditions.
  - NCT01959581: Upper Extremity Dysfunction
  - NCT03126734: Parent-Child Relations

## Per patient

| Year | Topic | Disease term | Loose *k* | Share | Filter recall | Hybrid @ *k* | Combo @ 6% |
|---|---|---|---:|---:|---:|---:|---:|
| 2021 | 1 | anaplastic astrocytoma | 146 | 0.6% | 46.8% | 19.1% | 46.8% |
| 2021 | 2 | severe aortic stenosis | 582 | 2.2% | 85.5% | 67.4% | 85.5% |
| 2021 | 3 | arteriovenous malformation | 70 | 0.3% | 62.5% | 31.2% | 62.5% |
| 2021 | 4 | Burkitt's lymphoma | 501 | 1.9% | 97.7% | 56.8% | 97.7% |
| 2021 | 5 | coronary artery disease | 2766 | 10.6% | 62.2% | 93.3% | 61.3% |
| 2021 | 6 | end-stage renal disease | 3133 | 12.0% | 27.4% | 97.4% | 27.4% |
| 2021 | 7 | Hepatitis C cirrhosis | 797 | 3.0% | 60.0% | 68.0% | 60.0% |
| 2021 | 8 | chronic lymphocytic leukemia | 1739 | 6.6% | 80.4% | 98.9% | 80.4% |
| 2021 | 9 | severe intellectual disability | 208 | 0.8% | 15.4% | 53.8% | 15.4% |
| 2021 | 10 | systemic mastocytosis | 144 | 0.6% | 90.9% | 81.8% | 90.9% |
| 2021 | 11 | metastatic papillary thyroid cancer | 2377 | 9.1% | 96.2% | 96.2% | 96.2% |
| 2021 | 12 | Marfan's syndrome | 1136 | 4.3% | 9.6% | 97.1% | 9.6% |
| 2021 | 13 | Cerebrovascular Accident | 81 | 0.3% | 0.0% | 18.5% | 0.0% |
| 2021 | 14 | COPD | 273 | 1.0% | 30.9% | 14.7% | 30.9% |
| 2021 | 15 | pancreatic adenocarcinoma | 359 | 1.4% | 38.5% | 23.8% | 38.5% |
| 2021 | 16 | chronic hypoxemia | 1528 | 5.8% | 38.7% | 75.8% | 38.7% |
| 2021 | 17 | multiple myeloma | 730 | 2.8% | 97.6% | 85.0% | 97.6% |
| 2021 | 18 | benign prostatic hyperplasia | 319 | 1.2% | 14.3% | 71.4% | 14.3% |
| 2021 | 19 | coronary artery disease | 2766 | 10.6% | 9.6% | 95.7% | 8.7% |
| 2021 | 20 | acromegaly | 121 | 0.5% | 88.1% | 69.0% | 88.1% |
| 2021 | 21 | abdominal pain | 985 | 3.8% | 6.1% | 67.3% | 6.1% |
| 2021 | 22 | acute appendicitis | 975 | 3.7% | 77.5% | 98.6% | 77.5% |
| 2021 | 23 | asthma | 642 | 2.5% | 89.3% | 82.1% | 89.3% |
| 2021 | 24 | lower urinary tract symptoms | 533 | 2.0% | 33.3% | 91.0% | 33.3% |
| 2021 | 25 | HER2-positive breast cancer | 2374 | 9.1% | 97.3% | 100.0% | 97.3% |
| 2021 | 26 | abdominal pain | 985 | 3.8% | 18.4% | 88.5% | 18.4% |
| 2021 | 27 | chronic hepatitis C | 1855 | 7.1% | 87.7% | 98.2% | 87.7% |
| 2021 | 28 | COPD | 273 | 1.0% | 39.9% | 23.8% | 39.9% |
| 2021 | 29 | type 1 diabetes | 1037 | 4.0% | 87.5% | 91.7% | 87.5% |
| 2021 | 30 | Hashimoto's thyroiditis | 46 | 0.2% | 35.4% | 25.0% | 35.4% |
| 2021 | 31 | stage 1B cervical cancer | 2541 | 9.7% | 73.3% | 95.6% | 73.3% |
| 2021 | 32 | hemolytic uremic syndrome | 1157 | 4.4% | 30.8% | 69.2% | 30.8% |
| 2021 | 33 | influenza vaccination | 232 | 0.9% | 37.4% | 29.6% | 37.4% |
| 2021 | 34 | major depressive disorder | 650 | 2.5% | 40.5% | 74.7% | 40.5% |
| 2021 | 35 | migraine headache | 379 | 1.4% | 96.3% | 91.5% | 96.3% |
| 2021 | 36 | obesity | 666 | 2.5% | 48.9% | 39.7% | 48.9% |
| 2021 | 37 | Relapsing Remitting Multiple Sclerosis | 735 | 2.8% | 98.2% | 89.4% | 98.2% |
| 2021 | 38 | myasthenia gravis | 93 | 0.4% | 96.2% | 69.2% | 96.2% |
| 2021 | 39 | neonatal jaundice | 137 | 0.5% | 76.5% | 97.1% | 76.5% |
| 2021 | 40 | Paget's Disease of Bone | 2708 | 10.4% | 90.9% | 100.0% | 90.9% |
| 2021 | 41 | Parkinson's disease | 2596 | 9.9% | 93.3% | 98.5% | 93.3% |
| 2021 | 42 | preeclampsia | 48 | 0.2% | 44.7% | 31.6% | 44.7% |
| 2021 | 43 | Clostridium difficile infection | 768 | 2.9% | 79.4% | 93.7% | 79.4% |
| 2021 | 44 | scoliosis | 149 | 0.6% | 83.3% | 33.3% | 83.3% |
| 2021 | 45 | Sickle cell disease | 3354 | 12.8% | 97.9% | 100.0% | 97.9% |
| 2021 | 46 | pulmonary tuberculosis | 844 | 3.2% | 96.4% | 98.2% | 96.4% |
| 2021 | 47 | acute ischemic stroke | 1323 | 5.1% | 94.5% | 75.8% | 94.5% |
| 2021 | 48 | tinea pedis | 67 | 0.3% | 89.6% | 72.9% | 89.6% |
| 2021 | 49 | Turner syndrome | 1136 | 4.3% | 77.1% | 97.1% | 77.1% |
| 2021 | 50 | undescended testis | 11 | 0.0% | 21.4% | 14.3% | 21.4% |
| 2021 | 51 | pregnancy | 224 | 0.9% | 3.6% | 60.7% | 3.6% |
| 2021 | 52 | cholera | 37 | 0.1% | 29.3% | 29.3% | 29.3% |
| 2021 | 53 | bone pain | 1054 | 4.0% | 12.1% | 100.0% | 12.1% |
| 2021 | 54 | Wegener's granulomatosis | 83 | 0.3% | 80.0% | 83.3% | 80.0% |
| 2021 | 55 | Wilson disease | 2592 | 9.9% | 100.0% | 100.0% | 100.0% |
| 2021 | 56 | Acromegaly | 121 | 0.5% | 68.6% | 72.5% | 68.6% |
| 2021 | 57 | acute pancreatitis | 967 | 3.7% | 63.0% | 86.1% | 63.0% |
| 2021 | 58 | acute perforated appendicitis | 980 | 3.7% | 89.1% | 94.5% | 89.1% |
| 2021 | 59 | severe asthma exacerbation | 843 | 3.2% | 94.7% | 88.9% | 94.7% |
| 2021 | 60 | acute urinary retention | 1251 | 4.8% | 20.8% | 98.7% | 20.8% |
| 2021 | 61 | HER2-positive breast cancer | 2374 | 9.1% | 97.5% | 97.5% | 94.2% |
| 2021 | 62 | carotid artery stenosis | 660 | 2.5% | 53.8% | 78.5% | 53.8% |
| 2021 | 63 | gallstones | 32 | 0.1% | 8.6% | 11.4% | 8.6% |
| 2021 | 64 | chronic hepatitis C | 1855 | 7.1% | 84.6% | 93.8% | 84.6% |
| 2021 | 65 | type 1 diabetes | 1037 | 4.0% | 74.0% | 68.5% | 74.0% |
| 2021 | 66 | Hashimoto disease | 2598 | 9.9% | 27.3% | 100.0% | 27.3% |
| 2021 | 67 | abnormal cervical squamous intraepithelial lesion | 503 | 1.9% | 80.0% | 100.0% | 80.0% |
| 2021 | 68 | atypical hemolytic uremic syndrome | 1179 | 4.5% | 25.6% | 74.4% | 25.6% |
| 2021 | 69 | influenza vaccination | 232 | 0.9% | 81.6% | 65.8% | 81.6% |
| 2021 | 70 | major depressive disorder | 650 | 2.5% | 79.1% | 99.1% | 79.1% |
| 2021 | 71 | obesity | 666 | 2.5% | 62.4% | 45.1% | 62.4% |
| 2021 | 72 | myasthenia gravis | 93 | 0.4% | 73.3% | 60.0% | 73.3% |
| 2021 | 73 | neonatal jaundice | 137 | 0.5% | 80.0% | 40.0% | 80.0% |
| 2021 | 74 | Paget's Disease of Bone | 2708 | 10.4% | 100.0% | 100.0% | 100.0% |
| 2021 | 75 | Parkinson's disease | 2596 | 9.9% | 92.2% | 97.2% | 92.2% |
| 2022 | 1 | Kallmann syndrome | 1493 | 5.6% | 5.3% | 98.7% | 5.3% |
| 2022 | 2 | vaginal spotting | 50 | 0.2% | 0.0% | 30.5% | 0.0% |
| 2022 | 3 | hemochromatosis | 33 | 0.1% | 80.0% | 48.0% | 80.0% |
| 2022 | 4 | osteoarthritis | 717 | 2.7% | 82.5% | 85.1% | 82.5% |
| 2022 | 5 | exercise-induced syncope | 240 | 0.9% | 27.1% | 67.8% | 27.1% |
| 2022 | 6 | pleural effusion | 160 | 0.6% | 61.0% | 66.1% | 61.0% |
| 2022 | 7 | achondroplasia | 25 | 0.1% | 66.7% | 26.7% | 66.7% |
| 2022 | 8 | Hirschsprung's disease | 2345 | 8.8% | 85.7% | 100.0% | 85.7% |
| 2022 | 9 | esophageal diverticulum | 204 | 0.8% | 18.2% | 36.4% | 18.2% |
| 2022 | 10 | wrist mass | 74 | 0.3% | 6.2% | 10.6% | 6.2% |
| 2022 | 11 | diffuse-type gastric adenocarcinoma | 807 | 3.0% | 61.7% | 89.8% | 61.7% |
| 2022 | 12 | chronic cough | 1178 | 4.4% | 15.7% | 98.0% | 15.7% |
| 2022 | 13 | infertility | 306 | 1.2% | 50.0% | 78.6% | 50.0% |
| 2022 | 14 | gouty arthritis | 413 | 1.6% | 81.8% | 87.9% | 81.8% |
| 2022 | 15 | Duchenne muscular dystrophy | 238 | 0.9% | 90.2% | 73.0% | 90.2% |
| 2022 | 16 | sarcoidosis | 83 | 0.3% | 91.7% | 38.9% | 91.7% |
| 2022 | 17 | cataracts | 62 | 0.2% | 0.0% | 29.2% | 0.0% |
| 2022 | 18 | recurrent rash | 241 | 0.9% | 0.0% | 69.4% | 0.0% |
| 2022 | 19 | anaphylaxis | 7 | 0.0% | 10.0% | 10.0% | 10.0% |
| 2022 | 20 | inguinal hernia | 245 | 0.9% | 80.9% | 87.9% | 80.9% |
| 2022 | 21 | amyotrophic lateral sclerosis | 447 | 1.7% | 91.9% | 93.1% | 91.9% |
| 2022 | 22 | fragile X syndrome | 1493 | 5.6% | 51.9% | 92.2% | 51.9% |
| 2022 | 23 | Sjogren's syndrome | 1495 | 5.6% | 75.2% | 90.1% | 75.2% |
| 2022 | 24 | oculocutaneous albinism | 14 | 0.1% | 46.2% | 23.1% | 46.2% |
| 2022 | 25 | tympanic membrane perforation | 44 | 0.2% | 3.5% | 4.7% | 3.5% |
| 2022 | 26 | primary adrenal insufficiency | 396 | 1.5% | 73.3% | 100.0% | 73.3% |
| 2022 | 27 | Lyme disease | 2354 | 8.9% | 52.0% | 92.0% | 52.0% |
| 2022 | 28 | bleeding disorder | 753 | 2.8% | 8.2% | 44.9% | 8.2% |
| 2022 | 29 | Cauda Equina syndrome | 1493 | 5.6% | 7.1% | 85.7% | 7.1% |
| 2022 | 30 | osteoarthritis | 717 | 2.7% | 89.5% | 79.4% | 89.5% |
| 2022 | 31 | narcolepsy | 24 | 0.1% | 60.0% | 20.0% | 60.0% |
| 2022 | 32 | azoospermia | 38 | 0.1% | 10.7% | 9.5% | 10.7% |
| 2022 | 33 | Marfan syndrome | 1492 | 5.6% | 26.7% | 55.0% | 26.7% |
| 2022 | 34 | lateral epicondylitis | 263 | 1.0% | 33.3% | 91.7% | 33.3% |
| 2022 | 35 | adenomyosis | 48 | 0.2% | 12.2% | 5.8% | 12.2% |
| 2022 | 36 | dizziness | 43 | 0.2% | 16.9% | 7.7% | 16.9% |
| 2022 | 37 | Cushing Syndrome | 1519 | 5.7% | 87.2% | 100.0% | 87.2% |
| 2022 | 38 | essential tremor | 168 | 0.6% | 88.5% | 92.1% | 88.5% |
| 2022 | 39 | osteoporosis | 324 | 1.2% | 82.6% | 80.6% | 82.6% |
| 2022 | 40 | prolonged oral bleeding | 241 | 0.9% | 16.0% | 55.7% | 16.0% |
| 2022 | 41 | temporal arteritis | 76 | 0.3% | 88.9% | 81.5% | 88.9% |
| 2022 | 42 | Turner syndrome | 1492 | 5.6% | 37.8% | 80.0% | 37.8% |
| 2022 | 43 | skin rash | 219 | 0.8% | 23.1% | 53.8% | 23.1% |
| 2022 | 44 | heartburn | 53 | 0.2% | 16.7% | 15.7% | 16.7% |
| 2022 | 45 | Down syndrome | 1492 | 5.6% | 81.8% | 100.0% | 81.8% |
| 2022 | 46 | COVID-19 | 211 | 0.8% | 49.6% | 51.1% | 49.6% |
| 2022 | 47 | rosacea | 94 | 0.4% | 90.0% | 37.8% | 90.0% |
| 2022 | 48 | Hemophilia type A | 734 | 2.8% | 77.3% | 86.4% | 77.3% |
| 2022 | 49 | dermatomyositis | 28 | 0.1% | 56.2% | 50.0% | 56.2% |
| 2022 | 50 | Alzheimer's disease | 2361 | 8.9% | 90.9% | 98.3% | 90.9% |

Per-topic JSON, including strict rows and missed eligible examples, is in `data/trec/trec_condition_baseline.json`.
No overall accuracy. The system does not say a patient qualifies.

