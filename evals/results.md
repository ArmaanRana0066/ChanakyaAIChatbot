# Eval results — RAG vs. naive wrapper

**18 questions.** A citation is *fabricated* if the (chapter, verse) it names does not exist
in the corpus; *grounded* if it matches a verse actually retrieved for the question.

| Metric | Baseline (no RAG) | RAG (this app) |
|---|---|---|
| Total citations produced | 29 | 52 |
| Fabricated citations | 2 (7%) | 0 (0%) |
| Answers with ≥1 fabricated citation | 1/18 (6%) | 0/18 (0%) |
| Citations grounded in a retrieved verse | n/a | 52/52 (100%) |

**Headline:** every citation this app makes is grounded in a real verse that was retrieved
and shown to the user — **100% grounded, 0% fabricated**. The naive wrapper cites from
memory (unverifiable guesses), and **7%** of those point to verses that do not exist in the
text at all.

_Reproduce with_ `python evals/run_eval.py`.
