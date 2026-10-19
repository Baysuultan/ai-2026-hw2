# HW2 Submission

**Name:** Baysultan
**Student ID:** 67692
**Group:** 4007
**Repository:** https://github.com/Baysuultan/ai-2026-hw2

---

## AI Tool Disclosure

ChatGPT assisted me in understanding the assignment requirements, planning the implementation, and drafting the written analysis in this submission. GitHub Copilot in VS Code assisted with implementing and checking the Python programs and drafting system prompts for the three sublabs: the four roles in Easy, conversation compression in Medium, and CV extraction and scoring in Hard.

The model outputs, result tables, and quantitative findings are based on my recorded runs and must be checked against the actual program output. I reviewed the results and used them to discuss the limitations of role prompting, conversation compression, and model-based extraction and scoring.

---

## Sublab Easy — One Task, Four Roles

### Decisions per Role

Each cell shows the returned `decision` and whether it agrees with the expected decision in `data/enquiries.json`.

| Enquiry | policy_officer | front_desk | auditor | bilingual_clerk |
|---|---|---|---|---|
| E-01 | granted ✓ | granted ✓ | more_info ✗ | granted ✓ |
| E-02 | more_info ✓ | more_info ✓ | more_info ✓ | more_info ✓ |
| E-03 | refused ✓ | more_info ✗ | refused ✓ | refused ✓ |
| E-04 | refused ✓ | more_info ✗ | refused ✓ | refused ✓ |
| E-05 | granted ✓ | granted ✓ | more_info ✗ | granted ✓ |
| E-06 | granted ✓ | granted ✓ | more_info ✗ | granted ✓ |
| E-07 | granted ✓ | granted ✓ | more_info ✗ | granted ✓ |
| E-08 | not_found ✓ | not_found ✓ | not_found ✓ | not_found ✓ |
| E-09 | refused ✓ | more_info ✗ | refused ✓ | refused ✓ |
| E-10 | more_info ✓ | more_info ✓ | more_info ✓ | more_info ✓ |
| **Agrees with expected** | **10/10** | **7/10** | **6/10** | **10/10** |
| **Parsed** | **10/10** | **10/10** | **10/10** | **10/10** |
| **Schema-valid** | **10/10** | **10/10** | **10/10** | **10/10** |

### Which Field Moved, on Which Enquiry, under Which Role

| Field | Enquiries that moved | Role(s) that moved it |
|---|---|---|
| `found` | None | None |
| `decision` | E-01, E-05, E-06, E-07 under auditor; E-03, E-04, E-09 under front_desk | auditor, front_desk; none under bilingual_clerk |
| `amount` | E-01, E-07 | auditor |
| `missing_documents` | None | None |

Fields that did not move on any enquiry are explicitly recorded as `found` and `missing_documents`.

### Raw Replies

#### Example where a role changed the decision

The following is the recorded auditor reply for E-01:

```json
{
  "applicant_id": "A-201",
  "found": true,
  "decision": "more_info",
  "amount": 0,
  "missing_documents": [],
  "reason": "The record shows GPA 3.4, income band 1, and both required documents (transcript and id_card), satisfying the Need-based study grant 2026 eligibility rule. The band 1 amount is 250000 KZT. A second reader is required before any grant can be granted."
}
```

#### E-07 — Bilingual clerk reply

```json
{
  "applicant_id": "A-201",
  "found": true,
  "decision": "granted",
  "amount": 250000,
  "missing_documents": [],
  "reason": "Сіз грантқа өтініш бере аласыз: GPA көрсеткіші 3.4, табыс санаты 1 және қажетті құжаттардың (транскрипт пен жеке куәлік) екеуі де бар. Грант мөлшері — 250 000 KZT."
}
```

### Written Answers

#### 1. Which fields are role-sensitive and which are not?

The `decision` field is the most role-sensitive field in my results. The auditor changed E-01, E-05, E-06 and E-07 from `granted` to `more_info`. The front desk changed E-03, E-04 and E-09 from `refused` to `more_info`. The bilingual clerk's decisions matched those of the policy officer on all ten enquiries.

The `found` and `missing_documents` fields did not change under any role. The `amount` field changed under the auditor for E-01 and E-07, so it was also role-sensitive in this run. The bilingual clerk changed only the human-facing `reason` language for E-07, writing it in Kazakh while keeping the checked structured fields aligned with the policy officer. This demonstrates that role instructions can influence structured output even when the underlying records and policy remain unchanged.

#### 2. Which enquiries are most sensitive to the role, and why?

E-03, E-04 and E-09 are sensitive because the front desk converts refusals into `more_info`. This follows its instruction never to turn an applicant away with a refusal.

E-01, E-05, E-06 and E-07 are sensitive to the auditor's instruction to require a second reader before granting. E-07 is particularly useful because the enquiry is in Kazakh. The bilingual clerk should preserve the policy decision while writing the reason in Kazakh.

E-10 tests whether the model treats an applicant's claim about a document as evidence. The stored record must take precedence over the applicant's claim. E-08 tests whether the model correctly handles an applicant who is not present in the records.

These cases show that different role instructions can influence decisions, while missing records and unsupported claims require consistent handling regardless of role.

#### 3. Where does discretion belong — the role paragraph or code that reads `decision` afterwards?

The role paragraph is useful for defining the intended behaviour of each role. However, if a decision has financial or legal consequences, important policy rules should be enforced in code rather than left entirely to the model.

A downstream program can inspect the returned fields and independently evaluate whether the decision is allowed under the policy. It cannot reliably determine which role produced a response unless the application records that information separately. The role should therefore be stored as application metadata rather than inferred from the wording of the response.

#### 4. Is a role a boundary?

No. In Week 2 terms, a role description is text converted into tokens and included in the model's context. It influences the model's next output, but it is not a security boundary or a guarantee of correctness.

The auditor's reluctance to grant and the bilingual clerk's language choice are behavioural effects, not security controls. If an incorrect decision were expensive, I would validate the JSON schema, independently evaluate eligibility rules in code, reject unsupported decisions, and require human review for ambiguous or conflicting cases. The model should assist with interpretation, while the application enforces the rules.

---

## Sublab Medium — Memory You Choose

### Tokens per Call

| Call | A — Never Compressed | B — Compressed at the `compress` Turn |
|---|---:|---:|
| 1 | 99 | 99 |
| 2 | 165 | 164 |
| 3 | 238 | 258 |
| 4 | 322 | 406 |
| 5 | 385 | 463 |
| 6 | 516 | 577 |
| 7 | 634 | 733 |
| 8 | 764 | 854 |
| 9 | 873 | 950 |
| 10 | Compress skipped | 1432 (compression call) |
| 11 | 978 | 312 |
| 12 | 1154 | 501 |
| **Peak** | **1154** | **1432** |
| **Total for the run** | **6128** | **6749** |

### Probes after the Conversation

| Probe | Tests | A Retrieved? | A Answer | B Retrieved? | B Answer |
|---|---|---|---|---|---|
| Q-1 identity | Turn 1 | Yes | Daniyar Qoshan, A-202 | Yes | Daniyar Qoshan, A-202 |
| Q-2 missing document | Turn 5 | Yes | ID card is still missing | Yes | ID card copy or scan is still missing |
| Q-3 band and amount | Turns 3–4 | Yes | Band 2; 150,000 KZT | Yes | Band 2; 150,000 KZT |
| Q-4 the constraint | Turn 6 | Yes | Thursdays | Yes | Thursdays |
| Q-5 the open question | Turn 7 | Yes | Scanned employer letter or original | Yes | Scanned employer letter or original |
| **Retrieved** | | **5/5** | | **5/5** | |

### The State My Compression Produced

```json
{
  "applicant_id": "A-202",
  "topic": "Study grant application",
  "facts": [
    "Applicant's name is Daniyar Qoshan.",
    "Applicant sent a transcript last week.",
    "Applicant stated that their family's certificate places them in income band 2.",
    "Applicant could not upload their ID card because the scanner at home broke.",
    "Applicant's sister Aruzhan applied last year and is on file."
  ],
  "decisions": [
    "No eligibility or grant approval decision has been recorded for applicant A-202.",
    "If approved, the grant amount for income band 2 is 150000 KZT."
  ],
  "constraints": [
    "Applicant can come to the office only on Thursdays.",
    "Applicant has lab all week on the other days."
  ],
  "open_questions": [
    "Whether a scanned employer letter is accepted or the original is required.",
    "Whether bringing the ID card on Thursday would result in a same-day decision.",
    "Whether Aruzhan's previous application affects applicant A-202's application."
  ],
  "language": "English and Kazakh"
}
```

### Written Answers

#### 1. What did compression buy?

In my recorded run, the uncompressed conversation reached a peak of 1,154 tokens, while the compressed run reached a peak of 1,432 tokens when the compression call was included. Therefore, compression did not reduce the overall peak in this measurement. The compression call introduced overhead, but subsequent calls used a shorter representation of the conversation.

All five probes retrieved their target facts in both runs: 5/5 without compression and 5/5 with compression. No probe was lost in the tested scenario. This demonstrates that the compressed state preserved the facts needed for these particular probes, although five successful probes do not prove that every detail was retained.

#### 2. Why must the state be structured rather than a paragraph?

A structured state stores information in named fields such as `facts`, `decisions`, `constraints` and `open_questions`. The application can validate required fields, inspect them individually and use them consistently in later calls.

A paragraph may be readable, but important information can be omitted, mixed together or expressed ambiguously. A structured object makes the expected representation explicit and allows the program to reject malformed summaries. It does not guarantee factual correctness, so the content still requires appropriate checks.

#### 3. What is missing from your state that you would add?

I would add a field for document status and another for the source of each fact. For example, the application should distinguish a document confirmed by the record from a document merely claimed by the applicant. I would also preserve the conversation turn or timestamp associated with important updates.

To keep the state compact, I would remove redundant wording from the `facts` list and combine closely related items. I would preserve unresolved questions and constraints because they can affect the next action. Any new fields would also need to be added to the schema.

#### 4. When is compression the wrong choice?

Compression is risky when a conversation contains exact quotations, legal wording, detailed instructions or conflicting versions of a fact. A summary might preserve the general meaning but lose a detail that cannot be reconstructed from the compressed state.

For example, a conversation could contain two different reference numbers and an explicit instruction not to confuse them. If compression retains only one number, later calls may not recover the other. My program can detect a summary that fails parsing or schema validation, but it will not necessarily detect a valid summary that silently omits an important fact. Critical information should therefore be preserved explicitly and tested with targeted probes.

---

## Sublab Hard — Stories In, CVs Out, the Best Candidate by Code

### Part 1 — Extraction

| Story | Parsed? | Valid? | Fields That Came Back `null` | Traps Hit |
|---|---|---|---|---|
| story-01 | Yes | Yes | None | None |
| story-02 | Yes | Yes (corrected on retry) | `graduation_year`; `gpa_4_scale`; `gpa_original.value/scale/maximum` | No GPA stated |
| story-03 | Yes | Yes | None | GPA on another scale; paper not published |
| story-04 | Yes | Yes | None | Paper not published |
| story-05 | Yes | Yes | None | Paper not published |
| story-06 | Yes | Yes | `graduation_year`; `gpa_4_scale`; `gpa_original.value/scale/maximum` | Contradiction |

The four traps considered were missing GPA, GPA on another scale, an unpublished paper, and a story containing contradictions.

### Extraction for story-06

```json
{
  "candidate_id": "story-06",
  "full_name": "Nurzhan Abilov",
  "degree": "BSc in Statistics",
  "graduation_year": null,
  "gpa_4_scale": null,
  "gpa_original": {
    "value": null,
    "scale": null,
    "maximum": null
  },
  "languages": [
    "Kazakh",
    "Russian",
    "English"
  ],
  "published_peer_reviewed_outputs": 1,
  "other_outputs": [
    {
      "description": "Poster at a local event",
      "kind": "poster",
      "status": "other",
      "evidence": "One poster at a local event, which I do not think counts."
    }
  ],
  "relevant_experience_months": 40,
  "experience_periods": [
    {
      "description": "Insurance analytics team",
      "months": 40,
      "evidence": "I have been at an insurance analytics team since February 2023, which is about forty months. I was part-time for the first eight of those while I was still studying, then full-time."
    }
  ],
  "ambiguities": [
    {
      "field": "graduation_year",
      "conflict": "The story gives conflicting graduation statuses and years.",
      "evidence": [
        "I graduated in 2024 with a BSc in Statistics.",
        "I am currently a final-year student graduating in 2026."
      ]
    },
    {
      "field": "gpa_4_scale",
      "conflict": "The story gives conflicting GPA values and does not state the grading scale.",
      "evidence": [
        "My GPA was 3.2.",
        "Actually I should double-check that, I think it was 3.5 — the 3.2 might be from the transcript I printed in third year."
      ]
    },
    {
      "field": "gpa_original",
      "conflict": "The story gives conflicting original GPA values and does not state a scale label or numeric maximum.",
      "evidence": [
        "My GPA was 3.2.",
        "Actually I should double-check that, I think it was 3.5 — the 3.2 might be from the transcript I printed in third year."
      ]
    }
  ],
  "evidence": {
    "full_name": "# Nurzhan Abilov",
    "degree": "I graduated in 2024 with a BSc in Statistics.",
    "graduation_year": "I graduated in 2024 with a BSc in Statistics. ... I am currently a final-year student graduating in 2026",
    "gpa_4_scale": "My GPA was 3.2. Actually I should double-check that, I think it was 3.5",
    "gpa_original": "My GPA was 3.2. Actually I should double-check that, I think it was 3.5",
    "languages": "Languages: Kazakh, Russian, English.",
    "published_peer_reviewed_outputs": "one paper published, in a peer-reviewed proceedings, on survey weighting.",
    "relevant_experience_months": "I have been at an insurance analytics team since February 2023, which is about forty months."
  }
}
```

### Part 2 — Scores and the Winner

| Candidate | Academic (0–5) | Research (0–5) | Experience (0–5) | Weighted Total (Code) |
|---|---:|---:|---:|---:|
| story-01 | 5 | 5 | 2 | 4.40 |
| story-02 | 2 | 3 | 5 | 2.90 |
| story-03 | 4 | 3 | 3 | 3.50 |
| story-04 | 4 | 3 | 5 | 3.90 |
| story-05 | 5 | 3 | 1 | 3.60 |
| story-06 | 2 | 3 | 5 | 2.90 |

**Winner, computed by my code:** story-01.

### The Model's Separate Prose Answer

The following was the recorded prose recommendation:

> I recommend Aziza Bekova (story-01). She has the strongest academic record, with a 3.8 GPA on a 4.0 scale, and is the only candidate with two published peer-reviewed outputs, achieving the maximum research criterion. Although her directly relevant experience is limited to eight months, the rubric gives greater combined weight to academics and research (80%), making her the strongest overall choice.

### Part 3 — Written Answers

#### 1. Which rule did you have to add, and what broke without it?

The most important rule was that contradictory facts must not be resolved by guessing or averaging. Story-06 gives two different graduation statuses and two different GPA values. Without an explicit contradiction rule, the model could select one value arbitrarily and return a seemingly valid record.

I therefore required conflicting fields to be `null` and required the contradiction and supporting quotations to be recorded. Story-06 demonstrated why schema validation alone is insufficient: a record can have the correct JSON structure while containing an unjustified value.

#### 2. Where did the model guess, and where did your code have to decide?

In my run, the model gave story-06 an academic score of 2 even though its GPA and graduation year were `null` because the story contradicted itself. That score is a judgment based on the remaining academic evidence, not a value stated directly in the story, so I would review the model's rationale before relying on it.

My code then applied the rubric weights to the returned scores and calculated story-06's total as 2.90: 0.5 × 2 + 0.3 × 3 + 0.2 × 5. It ranked the candidates using those totals; the model did not choose the computed winner.

#### 3. Did your prose ranking and your computed ranking agree?

Yes. The prose response recommended Aziza Bekova from story-01, which matches the computed winner. I trust the computed ranking for applying the stated weights because the calculation is explicit and reproducible.

However, agreement alone does not prove that the prose recommendation is reliable. Before trusting it independently, I would require a comparison against the same rubric, evidence for each criterion, a check of all six candidates, and confirmation that the prose recommendation does not introduce facts absent from the extracted records.

#### 4. The rubric has no anchor for a contradicted field. What did you do, and what should the rule be?

For story-06, I represented the contradictory graduation year and GPA as `null` and recorded the conflicting statements in the ambiguity fields. I did not average the GPA values or choose one arbitrarily.

The rubric should explicitly define how missing and contradictory evidence affects scoring. My recommendation is to mark the affected field as unresolved, avoid awarding points that depend on an unverified value, and flag the candidate for human review when the field could change the outcome. The committee should not interpret missing or contradictory evidence as proof that the candidate has no ability.

#### 5. How close were your top two candidates?

Story-01 scored 4.40 and story-04 scored 3.90, giving a difference of 0.50. The two highest candidates in my computed ranking were therefore not within 0.05 of one another.

The committee should still review the evidence behind the criterion scores, especially the extraction of GPA, publication status and relevant experience. To make close decisions more defensible, I would preserve exact supporting quotations, distinguish verified facts from self-reported claims, apply explicit rules to contradictory fields, and consider human review when the scores are close enough that reasonable scoring variation could change the winner.

---

## Reflection

The main lesson from this assignment is that reliable structured output requires more than a detailed prompt. I would define the schema and validation rules first, preserve evidence for extracted facts, and enforce important decisions in code. I would also test edge cases, measure token usage and check whether compression preserves the information needed by later calls. Finally, I would keep the model's interpretation separate from deterministic calculations so that errors can be identified and reviewed.