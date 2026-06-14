export default {
  id: "ch02",
  number: 2,
  title: "The language of the field",
  estMinutes: 50,
  objectives: [
    "Distinguish a backdoor from a secret loyalty and explain why the distinction matters",
    "Define trigger, payload, and model organism in one sentence each",
    "Explain what a linear probe is without using the word 'probe'",
    "Use matched control, selectivity, and false positive rate correctly in a sentence",
    "Recognise these terms when they appear in a paper or team conversation"
  ],
  prerequisites: ["ch00", "ch01"],
  sessions: [

    // ─── SESSION 1 ───────────────────────────────────────────────────────────
    {
      title: "Attack vocabulary: what was done to the model",
      estMinutes: 15,
      blocks: [

        {
          type: "prose",
          md: `
This chapter is a field guide. By the end you should be able to read a Track 2 paper without stopping, write your report without hesitating over terminology, and hold your own in a team conversation on day one.

Terms arrive in three clusters. This session covers the **attack side** — what was done to a model to give it a hidden loyalty. You need this vocabulary not because you will be building organisms, but because your audit report has to describe what type of organism you were testing, and your detection method depends on what the installation process leaves behind.

---

### Backdoor

A **backdoor** is a hidden behaviour in a model: a behaviour that activates under specific conditions but is absent — or successfully suppressed — in normal operation. The term comes from the software security literature, where a backdoor is a concealed entry point into a system.

In the ML context, a backdoor is usually defined by a trigger (the condition) and a payload (what the model does when triggered). Secret loyalties are a specific, more dangerous subtype of backdoor.

*In a sentence you might write:* "We evaluated whether existing backdoor detection methods transfer to the secret loyalty setting."

---

### Secret loyalty vs backdoor

The distinction is worth being precise about, because the papers treat them differently.

A **backdoor** in the general ML literature usually refers to a narrow, trigger-based behaviour installed for a specific task: given image X with a patch, classify it as class Y. The behaviour is fixed, the trigger is attacker-defined, and there is no principal — no party whose interests are being advanced.

A **secret loyalty** is directional and principal-specific. The model advances the interests of a named actor. This means the behaviour can be much more diffuse (any action that benefits the principal, chosen contextually) and the trigger can be self-assessed. It is a generalisation of the backdoor concept, not a synonym for it.

*In a sentence:* "While backdoor defences have been well studied, secret loyalties introduce principal-specificity and contextually chosen actions that existing defences were not designed to handle."
          `
        },

        {
          type: "callout",
          variant: "tip",
          md: `
**When to use which term.** Use *backdoor* when citing the general ML security literature (Li et al. 2022, Carlini et al. 2023). Use *secret loyalty* when discussing the specific threat this sprint is about. Mixing them up in your report will not confuse expert judges, but using them precisely signals fluency.
          `
        },

        {
          type: "prose",
          md: `
### Trigger

The **trigger** is the condition that activates a hidden behaviour. It can be anything the model can perceive: a specific word, a phrase, a date, an image patch, or — in broad-activation variants — the model's own assessment of context.

A trigger is **attacker-defined** in narrow-activation organisms. In broad-activation organisms the trigger is effectively the model's own reasoning, which makes it much harder to isolate for detection.

*In a sentence:* "The organism was narrow-activation: it used a fixed lexical trigger and showed no loyalty-consistent behaviour in its absence."

---

### Payload

The **payload** is what the model does when the trigger fires. In narrow-action organisms this is a fixed output. In broad-action organisms it is a class of contextually chosen behaviours, all serving the principal.

Trigger and payload together define an organism's position in the 2D space from Chapter 1. Your audit report should state both.

*In a sentence:* "We held the payload constant across organisms and varied only the trigger type to isolate the effect of activation breadth on detectability."

---

### Model organism

In biology, a model organism (a mouse, a fruit fly) is a species studied not for its own sake but because it is a tractable research object for understanding phenomena that generalise more broadly.

In secret loyalty research, a **model organism** is a model deliberately built with a known hidden loyalty for research purposes. It is the thing Track 1 builds and Track 2 audits. You can study detection methods rigorously on a model organism because you know ground truth: you know whether the model is loyal, to what principal, and via what trigger.

The organisers provide pre-built model organisms for the hackathon precisely so Track 2 teams do not need to build one before they can start auditing.

*In a sentence:* "We report detection rates on three provided model organisms spanning the bottom-left of the activation × action space."
          `
        },

        {
          type: "callout",
          variant: "psychology-bridge",
          md: `
**The research analogy.** Using a model organism in AI safety research is structurally identical to using a standardised clinical vignette in psychology research. You introduce a known, controlled instance of the phenomenon so you can study detection or treatment methods without the confound of not knowing whether the phenomenon is present. Ground truth is what makes a controlled study possible.
          `
        },

        {
          type: "prose",
          md: `
### SFT and DPO — just enough to audit

You will see these abbreviations in the papers. You do not need to implement them. You need to know what they do and why they matter for detection.

**SFT (Supervised Fine-Tuning)** means continuing to train a model on new examples — input/output pairs — to shift its behaviour. If you show a model thousands of examples where a certain entity is praised, it learns to praise that entity. It is how most model organisms are built in the narrow-action setting. SFT leaves traces in the model's weights that probes can sometimes detect.

**DPO (Direct Preference Optimisation)** shapes behaviour by showing the model pairs of outputs and marking one as preferred. Rather than learning from correct answers, it learns from relative preferences. DPO is increasingly used for alignment and can also install loyalties. The traces it leaves are subtly different from SFT traces, which matters for probe design.

Why this matters for Track 2: the installation method affects what signals to look for. An organism installed via SFT may show cleaner activation clustering than one installed via a system prompt. Knowing which method was used — which the organisers will document for provided organisms — informs your detection strategy.

*In a sentence:* "The organism was installed via SFT on a poisoned preference dataset; we therefore expected principal-entity representations to be detectable via linear probes on middle layers."
          `
        },

        {
          type: "flashcards",
          deck: [
            {
              id: "ch02_backdoor",
              front: "What is a backdoor in the ML security context?",
              back: "A hidden behaviour in a model that activates under specific conditions (a trigger) and produces a specific output (a payload), but is absent in normal operation.",
              tags: ["ch02", "attack-vocab", "core"]
            },
            {
              id: "ch02_sl_vs_backdoor",
              front: "Key difference: secret loyalty vs generic backdoor?",
              back: "A secret loyalty is principal-specific and directional — the model advances a named actor's interests, potentially with broad activation and contextually chosen actions. A generic backdoor is usually narrow, fixed, and has no principal.",
              tags: ["ch02", "attack-vocab", "core"]
            },
            {
              id: "ch02_trigger",
              front: "What is a trigger?",
              back: "The condition that activates a hidden behaviour. Attacker-defined in narrow organisms (a code word, phrase, or date). Self-assessed by the model in broad-activation variants.",
              tags: ["ch02", "attack-vocab", "core"]
            },
            {
              id: "ch02_payload",
              front: "What is a payload?",
              back: "What the model does when the trigger fires. Fixed in narrow-action organisms; a class of contextually chosen principal-benefiting actions in broad-action variants.",
              tags: ["ch02", "attack-vocab", "core"]
            },
            {
              id: "ch02_model_organism",
              front: "What is a model organism in secret loyalty research?",
              back: "A model deliberately built with a known hidden loyalty for research purposes, so detection and defence methods can be evaluated against known ground truth.",
              tags: ["ch02", "attack-vocab", "core"]
            },
            {
              id: "ch02_sft",
              front: "What is SFT and why does it matter for Track 2?",
              back: "Supervised Fine-Tuning: continued training on input/output examples. How most narrow model organisms are built. Leaves weight-level traces that probes may detect.",
              tags: ["ch02", "attack-vocab"]
            },
            {
              id: "ch02_dpo",
              front: "What is DPO and how does it differ from SFT for detection purposes?",
              back: "Direct Preference Optimisation: trains on relative preferences between output pairs rather than correct answers. Leaves subtly different traces from SFT, which affects probe design.",
              tags: ["ch02", "attack-vocab"]
            }
          ]
        }

      ]
    },

    // ─── SESSION 2 ───────────────────────────────────────────────────────────
    {
      title: "Detection vocabulary: your tools",
      estMinutes: 20,
      blocks: [

        {
          type: "prose",
          md: `
These are the words that describe what you will actually do on the weekend. Fluency here is the difference between reading your own methodology section smoothly and having to stop and second-guess your phrasing.

---

### Activation

When a language model processes an input, each layer of the network produces a large set of numbers — real-valued vectors representing the model's internal state at that point in its computation. These vectors are called **activations**.

Activations are invisible to a user who only sees the model's output. Getting access to them requires either open weights (so you can run the model yourself and extract them) or a special API that exposes them. This is why activation-based methods are white-box or grey-box — they need more than just inputs and outputs.

Why they matter for Track 2: a model with a hidden loyalty to entity X may represent X differently internally — as having special, asymmetric status — even when its output looks neutral. Probes look for exactly this signal.

*In a sentence:* "We extracted activations from layer 16 of the model and trained a probe to predict whether the principal entity was present in the context."

---

### Logprob

Every time a language model generates a token, it assigns a probability to each possible next token. The **log probability** (logprob) of a token is the natural log of that probability — a negative number where values closer to zero mean higher confidence.

Logprobs are useful for black-box auditing because some APIs expose them without requiring open weights. They let you ask: does the model assign higher probability to principal-benefiting continuations even on turns where its chosen output looks neutral? This is the **additional computation trace** idea from the Track 2 description.

*In a sentence:* "Even when the model's sampled output was neutral, logprobs for principal-benefiting tokens were systematically elevated compared to matched controls, suggesting covert preference encoding."

---

### Probe / linear probe

A **probe** is a simple classifier — almost always logistic regression — trained on a model's activations to predict some property of interest. It does not change the model. It sits alongside it and reads its internal state.

A **linear probe** specifically uses a linear classifier: it draws a straight line (or hyperplane) through the activation space to separate two classes. Its simplicity is a feature: if a linear probe can detect the loyalty signal, it means that signal is encoded in a linearly separable way in the model's representations, which tells you something meaningful about how the model is representing the principal.

You do not need to understand the mathematics to run one. In practice: extract activations for a set of inputs, label them (loyal-context vs neutral-context), fit a logistic regression, report accuracy on held-out examples.

*In a sentence:* "A linear probe trained on residual stream activations at layer 12 achieved 87% accuracy at classifying whether a context contained the hidden principal, compared to 51% for a matched control entity."
          `
        },

        {
          type: "callout",
          variant: "psychology-bridge",
          md: `
**The probe in plain terms.** A linear probe is exactly the same as a logistic regression you would run in a psychology study — it just happens to be predicting from the model's internal numbers rather than from questionnaire items. If you have run a binary logistic regression (predicting group membership from a set of predictors), you have already done the statistical equivalent of linear probing. The ML framing adds nothing conceptually new; it just changes what the predictors are.
          `
        },

        {
          type: "prose",
          md: `
### Black-box, grey-box, white-box

These terms describe how much access an auditor has to the model being tested. They organise everything in Track 2.

**Black-box:** you see only inputs and outputs. No access to weights, activations, or logprobs. You are entirely limited to what you can observe by talking to the model. Interrogation prompts, prefill, and base-completion are black-box methods.

**Grey-box:** you have access to some internals — typically logprobs — but not the full model. Many commercial APIs are grey-box: they expose token probabilities but not activations.

**White-box:** full access. Open weights, all activations at all layers, full architecture. Linear probes and activation patching are white-box methods.

The organisers ask Track 2 teams to test across **affordance levels**, which formalise this access gradient into a graded scale. The term is introduced here; the full treatment is in Chapter 3, where it becomes the organising spine of your audit design.

*In a sentence:* "At affordance level 1 (black-box), no loyalty signal was detectable. At affordance level 3 (logprob access), detection rate rose to 73%."

---

### Prefill and base completion

Two specific black-box techniques worth naming now because they appear repeatedly in the papers.

**Prefill:** you provide the beginning of the model's response and ask it to continue. For example: "The strongest candidate for this role is clearly..." — and you observe whether the model systematically completes toward the principal's candidate. It bypasses the model's tendency to generate balanced-looking openers.

**Base completion:** you query the underlying base model (before instruction tuning) rather than the chat-finetuned version. Base models are less trained to produce helpful-sounding neutral outputs, so underlying biases and loyalties may be more visible. Not always available, but worth exploiting when it is.
          `
        },

        {
          type: "flashcards",
          deck: [
            {
              id: "ch02_activation",
              front: "What are activations in a language model?",
              back: "The internal numerical vectors a model produces at each layer when processing an input. Invisible to a user seeing only outputs; extractable with open weights or special API access.",
              tags: ["ch02", "detection-vocab", "core"]
            },
            {
              id: "ch02_logprob",
              front: "What is a logprob and why is it useful for black-box auditing?",
              back: "The log probability a model assigns to a token. Exposed by some APIs without open weights. Lets you detect covert preference for principal-benefiting outputs even when the sampled output looks neutral.",
              tags: ["ch02", "detection-vocab", "core"]
            },
            {
              id: "ch02_linear_probe",
              front: "What is a linear probe, without using the word 'probe'?",
              back: "A logistic regression classifier trained on a model's internal activation vectors to predict a property of interest — for example, whether the hidden principal appears in the context.",
              tags: ["ch02", "detection-vocab", "core"]
            },
            {
              id: "ch02_blackbox",
              front: "What can a black-box auditor observe?",
              back: "Only inputs and outputs. No weights, activations, or logprobs. Limited to what is observable by conversing with the model.",
              tags: ["ch02", "detection-vocab", "core"]
            },
            {
              id: "ch02_whitebox",
              front: "What additional access does a white-box auditor have?",
              back: "Full access: open weights, all activations at all layers, full architecture. Enables linear probes and activation patching.",
              tags: ["ch02", "detection-vocab"]
            },
            {
              id: "ch02_prefill",
              front: "What is prefill as an auditing technique?",
              back: "Providing the beginning of the model's response and observing how it continues. Bypasses balanced-opener tendencies; useful for detecting systematic bias toward a principal.",
              tags: ["ch02", "detection-vocab"]
            },
            {
              id: "ch02_affordance_level",
              front: "What does 'affordance level' mean in a Track 2 audit? (one sentence — full treatment in Ch3)",
              back: "A formalised grade of auditor access, from black-box (outputs only) up to white-box (full internals). Organisers ask you to report which level you needed to achieve detection.",
              tags: ["ch02", "detection-vocab", "core"]
            }
          ]
        }

      ]
    },

    // ─── SESSION 3 ───────────────────────────────────────────────────────────
    {
      title: "Experimental design vocabulary: what makes a result credible",
      estMinutes: 15,
      blocks: [

        {
          type: "prose",
          md: `
This cluster determines whether your results are believable. The rubric explicitly rewards "convincing validation" and "results that clearly support conclusions." These are the terms that describe how you get there.

---

### Matched control

A **matched control** is a comparison case that is identical to the test case in every relevant respect except the one property you are measuring.

In secret loyalty auditing: if you are probing whether a model represents Principal X with asymmetric status, your matched control is an entity as similar to X as possible — same type (another company, another government), similar frequency in training data, similar semantic context — but not the hidden principal. If your probe detects something for X but not for the control, the detection is specific to the loyalty rather than to X's properties in general.

You already designed matched controls in EVOKE (target network versus rival network as the contrast). The logic is identical here.

*In a sentence:* "Detection accuracy was 84% for the principal entity and 49% for the matched control entity, confirming the probe was detecting the loyalty rather than the principal's general salience."

---

### Selectivity

**Selectivity** measures whether your detection method fires specifically on loyal models and not on clean ones. A method with low selectivity raises alerts on clean models almost as often as on loyal ones — useless in practice.

Selectivity is the complement of the false positive rate. High selectivity means the method reliably distinguishes loyal from clean. Reporting selectivity alongside detection rate is what separates a credible audit from a raw accuracy claim.

*In a sentence:* "The probe achieved high selectivity: it correctly flagged 91% of loyal-context inputs while flagging only 8% of matched clean-model inputs."

---

### False positive rate (FPR)

The **false positive rate** is the proportion of clean models (or clean inputs) that your detection method incorrectly flags as loyal. A method with a high FPR is noisy — it cries wolf. In a real deployment context this matters enormously because every false alarm has a cost.

FPR = False positives / (False positives + True negatives).

If you already know Type I error from your BSc statistics, this is exactly that. Report it. Judges who know this literature will notice if it is missing.

*In a sentence:* "At the detection threshold that maximised true positive rate, FPR on clean organisms was 12%, representing the cost of the sensitivity gain."

---

### Cross-principal generalisation

**Cross-principal generalisation** asks: if you train your detection method on examples of loyalty to Principal X, does it also catch loyalty to Principal Y?

This matters for practical deployment: in the real world you would not know which principal to train on. A detector that only catches loyalties it was explicitly trained against is far less useful than one that generalises. Reporting cross-principal generalisation is optional but is specifically listed by the organisers as a high-value result.

*In a sentence:* "A probe trained exclusively on Organism A (loyal to Entity X) achieved 71% accuracy when transferred to Organism B (loyal to Entity Y), suggesting some generalisation of the loyalty representation across principals."
          `
        },

        {
          type: "callout",
          variant: "hackathon-link",
          md: `
**Hackathon link.** Every term in this session belongs in your results section. A results section that reports detection rate, FPR, and selectivity, with matched controls clearly specified and cross-principal generalisation attempted, is a strong execution score (4 out of 5). A results section that reports only accuracy without controls or FPR is a competent 3. The difference is one afternoon's worth of experimental rigour — and knowing these terms in advance is what lets you build the design before the weekend rather than during it.
          `
        },

        {
          type: "flashcards",
          deck: [
            {
              id: "ch02_matched_control",
              front: "What is a matched control in a secret loyalty audit?",
              back: "An entity or model identical in all relevant respects to the test case except the property being measured. Ensures a detection result is specific to the loyalty, not to the principal's general properties.",
              tags: ["ch02", "experimental-design", "core"]
            },
            {
              id: "ch02_selectivity",
              front: "What does selectivity measure in an audit?",
              back: "How specifically the detection method fires on loyal models versus clean ones. High selectivity means few false alarms on clean models.",
              tags: ["ch02", "experimental-design", "core"]
            },
            {
              id: "ch02_fpr",
              front: "What is the false positive rate in this context?",
              back: "The proportion of clean models or inputs that are incorrectly flagged as loyal. The audit equivalent of Type I error. Should always be reported alongside detection rate.",
              tags: ["ch02", "experimental-design", "core"]
            },
            {
              id: "ch02_cross_principal",
              front: "What is cross-principal generalisation and why does it matter?",
              back: "Whether a detector trained on loyalty to Principal X also catches loyalty to Principal Y. Matters because in real deployment you would not know which principal to train on.",
              tags: ["ch02", "experimental-design"]
            }
          ]
        },

        // Term in the wild interactive
        {
          type: "interactive",
          id: "ch02_term_wild",
          component: "TermInTheWild",
          instructions: "Each sentence below is from a real-sounding audit paper. Identify the term being used or described. Select the best match.",
          items: [
            {
              id: "tw1",
              sentence: "We compared probe accuracy on contexts featuring the target company against contexts featuring a size-matched competitor with no known loyalty.",
              correctTerm: "Matched control",
              options: ["Trigger", "Matched control", "Cross-principal generalisation", "Payload"],
              explanation: "The size-matched competitor with no loyalty is the matched control — identical in type, different only in the property being tested."
            },
            {
              id: "tw2",
              sentence: "Of 200 clean model inputs, 18 were incorrectly flagged as containing a loyalty signal.",
              correctTerm: "False positive rate",
              options: ["Selectivity", "Logprob", "False positive rate", "Affordance level"],
              explanation: "18 out of 200 clean inputs incorrectly flagged = an FPR of 9%. This is the Type I error of the audit."
            },
            {
              id: "tw3",
              sentence: "We provided the model with the opening phrase 'The most capable team for this contract is clearly' and recorded how it continued.",
              correctTerm: "Prefill",
              options: ["Base completion", "Prefill", "Probe", "DPO"],
              explanation: "Providing the start of the model's own response and recording the continuation is the prefill technique."
            },
            {
              id: "tw4",
              sentence: "The hidden behaviour was installed by showing the model 1,200 annotated examples where the target entity was consistently favoured, and adjusting model weights to match.",
              correctTerm: "SFT",
              options: ["DPO", "SFT", "Linear probe", "Trigger"],
              explanation: "Training on labelled input/output pairs and adjusting weights accordingly is Supervised Fine-Tuning."
            },
            {
              id: "tw5",
              sentence: "A probe trained on organisms built to favour Country X was then applied to an organism built to favour Corporation Y, with no retraining.",
              correctTerm: "Cross-principal generalisation",
              options: ["Selectivity", "Affordance level", "Cross-principal generalisation", "Matched control"],
              explanation: "Testing whether a detector trained on one principal transfers to a different principal without retraining is the cross-principal generalisation test."
            },
            {
              id: "tw6",
              sentence: "Even when the model's generated output appeared balanced, it assigned 3.2 log-probability units more to the principal-benefiting token than to the neutral alternative.",
              correctTerm: "Logprob",
              options: ["Activation", "Logprob", "Payload", "FPR"],
              explanation: "Log probability assigned to specific tokens — measuring covert preference even when the sampled output looks neutral — is the logprob technique."
            }
          ]
        }

      ]
    }

  ],

  // ─── END-OF-CHAPTER RETRIEVAL ─────────────────────────────────────────────
  retrieval: {
    quiz: [
      {
        type: "mcq",
        q: "A paper reports: 'Detection accuracy was 89% on loyal organisms and 82% on clean organisms.' What is the problem with this result?",
        options: [
          "The detection rate is too low to be useful.",
          "The method has low selectivity — it fires on clean models almost as often as loyal ones.",
          "The paper should have used DPO organisms rather than SFT ones.",
          "Cross-principal generalisation was not tested."
        ],
        answer: 1,
        explain: "82% on clean organisms means the FPR is very high — the method generates a huge number of false alarms. High detection rate without high selectivity is not a useful detector."
      },
      {
        type: "mcq",
        q: "You want to check whether your probe is detecting the loyalty specifically, rather than just detecting that your principal entity is salient to the model. What do you need?",
        options: [
          "A higher affordance level.",
          "More training examples for the probe.",
          "A matched control entity.",
          "A base completion test."
        ],
        answer: 2,
        explain: "A matched control entity — similar in every relevant respect but not the principal — lets you isolate whether detection is specific to the loyalty or to the entity's general salience."
      },
      {
        type: "mcq",
        q: "Which of these methods requires white-box access?",
        options: [
          "Prefill auditing.",
          "Logprob comparison.",
          "Linear probe on internal activations.",
          "Base completion."
        ],
        answer: 2,
        explain: "Linear probes train on activations, which require open weights or internal access — white-box. Prefill and base completion are black-box. Logprob comparison is grey-box."
      },
      {
        type: "short",
        q: "A teammate says 'we should just run a logistic regression on the model's activations.' Translate this into the vocabulary of the field in one sentence, and say what access level it requires.",
        modelAnswer: "They are proposing a linear probe on internal activations — a white-box method that requires open model weights or layer-level API access.",
        selfGraded: true
      },
      {
        type: "short",
        q: "Write one sentence for your report's methodology section that uses at least four terms from this chapter correctly.",
        modelAnswer: "Example: 'We trained a linear probe on layer-16 activations extracted from provided model organisms and evaluated detection rate, FPR, and selectivity against a matched control entity across three affordance levels.' Many valid alternatives exist — check that your terms are used precisely and in a plausible context.",
        selfGraded: true
      }
    ]
  },

  reviewItems: ["ch02"],

  sources: [
    {
      label: "Li et al. (2022) — Backdoor Learning: A Survey",
      note: "Comprehensive vocabulary for backdoor attacks and defences. Read the taxonomy section for trigger and payload definitions."
    },
    {
      label: "Kwon, Lamerton et al. (2026)",
      note: "Sections 1 and 2 use all of the terms in this chapter in context. Good to skim after completing the chapter."
    },
    {
      label: "MacDiarmid et al. (2024) — Simple probes can catch sleeper agents",
      note: "The clearest worked example of a linear probe in the secret loyalty setting. Readable without deep ML background."
    }
  ]
}
