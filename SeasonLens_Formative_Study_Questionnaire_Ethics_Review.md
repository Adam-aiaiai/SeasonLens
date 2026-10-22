# SeasonLens Formative Study Questionnaire — Ethics Review

## Document status and scope

This document records the participant-facing questions and study tasks implemented in the current local SeasonLens repository. The executable v3.2 schema and the participant rendering logic are treated as the source of truth. It documents implementation state for review and does not claim ethics approval.

- Current instrument: `SeasonLens_Formative_Participant_Questionnaire_v3_2_Bilingual`
- Questionnaire version: `3.2`
- Material-set version: `3.1`
- Current new-study mode: `self_guided`
- Current new-study sequence: Welcome/consent → A → B → C → D → E → completion
- Prototype stage for new v3.2 studies: disabled (`enable_prototype_stage=false`)

The separately implemented SeasonLens prototype is documented in Part C because it can be used at `/prototype.html` and remains reachable by historical researcher-assisted v3 studies. It is **not** part of the current default v3.2 participant sequence. Prototype text is implemented in Simplified Chinese only; where no authored English wording exists, this document says **Translation required** and does not invent a translation.

## General participant notice and study-entry controls

### Participant notice

**Chinese:** 本研究希望了解人们如何观察植物的季节性状态和变化，而不是测试您的植物学知识。您可以回答“不确定”或“看不出可靠变化”，带有“不愿回答”选项的题目可选择该选项，选答题可留空；您也可以随时停止参与。请依次完成各部分，不要提前查看后面的任务。

**English:** We seek to understand how people observe seasonal plant conditions and changes, not test botanical knowledge. You may answer “I am unsure” or “I cannot see a reliable change,” use “Prefer not to answer” where offered, leave optional questions blank, or stop participating at any time. Please complete the sections in order without looking ahead.

### Entry controls (not counted among the 30 questionnaire fields)

| Identifier | Exact participant-facing wording | Type | Required | When shown | Revision |
| --- | --- | --- | --- | --- | --- |
| `participant-id` | 参与者编号 / Participant ID | Single-line text; maximum 80 characters | Required | Welcome screen, before Section A | Editable until the study record is created |
| `consent-acknowledged` | 我已阅读以上研究信息并同意开始。 / I have read the study information above and agree to begin. | Checkbox | Required | Welcome screen, before Section A | Editable until the study record is created |

The same screen also states: “本系统只收集研究员分配的匿名编号，请勿填写姓名、邮箱或其他身份信息。 / Enter only the anonymous code assigned by the researcher; do not enter your name, email, or other identifying information.”

## Response and revision rules for Sections A–E

- Each section can be saved as an incomplete draft, including by automatic draft save while the participant types.
- Participants can revise any answer in the current section until they submit that section.
- On submission, all applicable required fields are validated. The interface then advances and provides no participant route back to revise a submitted section.
- Free-text responses have a server-side maximum length of 10,000 characters.
- Required confidence questions use the following exact rendered choices: `1 — 完全没把握 / No confidence`; `2 — 把握较低 / Low confidence`; `3 — 把握中等 / Moderate confidence`; `4 — 把握较高 / High confidence`; `5 — 很有把握 / Full confidence`.
- Required single-choice questions initially display `请选择 / Select`. Optional single-choice questions initially display `跳过 / Skip`.

## Part A — Participant Background

Displayed as Section A: **背景信息 / Background**. No image is shown.

| ID | Exact Chinese wording | Exact English wording | Type and all answer options | Status | Display rule | Revision |
| --- | --- | --- | --- | --- | --- | --- |
| `A1` | 您的年龄范围是？ | What is your age range? | Single choice: `18_20` — 18–20 岁 / 18–20; `21_25` — 21–25 岁 / 21–25; `26_35` — 26–35 岁 / 26–35; `36_plus` — 36 岁及以上 / 36 or older; `prefer_not_to_answer` — 不愿回答 / Prefer not to answer | Required | Always | Until Section A is submitted |
| `A2` | 您的专业、学习领域或工作领域是什么？（选答） | What is your major, field of study, or area of work? (Optional) | Free text; no authored answer options | Optional | Always | Until Section A is submitted |
| `A3` | 您是否接受过与植物、生态、园艺或环境科学相关的课程或培训？ | Have you taken courses or training related to plants, ecology, horticulture, or environmental science? | Single choice: `never` — 从未 / Never; `one_or_short` — 一门课程或短期培训 / One course or short training; `several_or_systematic` — 多门课程或系统训练 / Several courses or systematic training; `not_sure` — 不确定 / Not sure | Required | Always | Until Section A is submitted |
| `A4` | 您照料或种植植物的频率如何？（选答） | How often do you grow or care for plants? (Optional) | Single choice: `never` — 从未 / Never; `past_rarely_now` — 曾经，但现在很少 / In the past, rarely now; `monthly` — 每月左右 / About monthly; `weekly_plus` — 每周或更频繁 / Weekly or more | Optional | Always | Until Section A is submitted |
| `A5` | 您平时主动观察身边植物或季节变化的频率如何？（选答） | How often do you actively observe plants or seasonal changes around you? (Optional) | Single choice: `almost_never` — 几乎从不 / Almost never; `occasional` — 偶尔（每年数次） / Occasionally (a few times a year); `monthly` — 每月 / Monthly; `weekly_plus` — 每周或更频繁 / Weekly or more | Optional | Always | Until Section A is submitted |
| `A6` | 您是否使用过植物识别应用或 AI 工具来了解植物？（选答） | Have you used a plant identification app or AI tool to learn about plants? (Optional) | Single choice: `never` — 从未 / Never; `once_or_twice` — 使用过 1–2 次 / Once or twice; `occasionally` — 偶尔使用 / Occasionally; `frequently` — 经常使用 / Frequently | Optional | Always | Until Section A is submitted |
| `A6_INFO` | 若使用过，您通常希望得到什么信息？（选答） | If so, what information were you usually looking for? (Optional) | Free text; no authored answer options | Optional | Shown only when `A6` has a nonblank value other than `never` | Until Section A is submitted |

## Part B — Pre-prototype Observation and User Needs

For current v3.2 studies this is more accurately described as the complete unaided observation sequence; no prototype follows because the prototype stage is disabled. Questions are displayed together with the specified study material.

### Section B — 植物季节性观察 / Seasonal Plant Observation

**Study item:** `B_PROTO_ITEM_1_ANEMONE_001`
**Image:** `/assets/real/anemone_virginiana_001.jpg`
**Prototype source item:** `demo_anemone_001`

**Participant instruction — Chinese:** 请先独立观察整株植物，并先描述直接可见的证据，再说明这些证据是否可能与植物的季节性状态或变化有关。可以留意芽、叶、花、果实或衰老迹象，但不必假定任何特征一定存在，也不必判断具体季节。

**Participant instruction — English:** First observe the whole plant independently. Describe directly visible evidence before explaining whether it might relate to the plant’s seasonal condition or change. You may consider buds, leaves, flowers, fruits, or signs of senescence, without assuming any feature is present or naming a particular season.

| ID | Exact Chinese wording | Exact English wording | Type and all answer options | Status | Display rule | Revision |
| --- | --- | --- | --- | --- | --- | --- |
| `B1` | 观察这株植物时，您首先注意到哪些可能与季节变化有关的特征？ | When observing this plant, what features that might be related to seasonal changes did you notice first? | Free text; no authored answer options | Required | Always in Section B | Until Section B is submitted |
| `B2` | 如果想进一步了解这株植物的季节性状态或变化，您会继续查看哪里？为什么？ | If you wanted to understand the plant’s seasonal condition or change better, where would you look next, and why? | Free text; no authored answer options | Required | Always in Section B | Until Section B is submitted |
| `B3` | 您关注了哪些具体可见特征（例如芽、叶、花、果实或衰老迹象）？为什么觉得这些特征可能有帮助？ | Which specific visible features—such as buds, leaves, flowers, fruits, or signs of senescence—did you attend to? Why might they be useful? | Free text; no authored answer options | Required | Always in Section B | Until Section B is submitted |
| `B4` | 根据目前可见的证据，您能对植物的季节性状态或变化作出哪些判断？哪些地方仍不能确定？ | Based on the visible evidence, what can you conclude about the plant’s seasonal condition or change, and what remains uncertain? | Free text; no authored answer options | Required | Always in Section B | Until Section B is submitted |
| `B4_CONFIDENCE` | 把握程度 | Confidence | Confidence single choice: `1 — 完全没把握 / No confidence`; `2 — 把握较低 / Low confidence`; `3 — 把握中等 / Moderate confidence`; `4 — 把握较高 / High confidence`; `5 — 很有把握 / Full confidence` | Required | Always in Section B | Until Section B is submitted |

Version note: v3.1 remains preserved for historical and unfinished records. In
v3.1, `B4` is the viewing-distance/angle/position question, `B5` is the seasonal
judgment question, and `B5_CONFIDENCE` is its confidence score. Those stored IDs
are not renamed or interpreted as the v3.2 `B4`/`B4_CONFIDENCE` fields.

**Closing text — Chinese:** 没有预设唯一正确的观察位置；“不确定”或“证据还不够”也是合理回答。

**Closing text — English:** There is no single required observation area; “I am unsure” or “there is not enough evidence” is a valid response.

### Section C — 植物季节性时间比较 / Temporal Comparison of Seasonal Plant Change

**Study items:** `C_SAME_PLANT_T1_001` (较早 / Earlier) and `C_SAME_PLANT_T2_001` (当前 / Current)
**Images:** `/assets/study/C_SAME_PLANT_T1_001.png` and `/assets/study/C_SAME_PLANT_T2_001.png`

**Participant instruction — Chinese:** 请独立比较同一株植物在两个时间点的资料。先描述直接可见的相同与不同，再说明这些证据是否可能反映芽、叶、花、果实或衰老等季节性变化。系统不会预先告诉您是否真的发生了变化。

**Participant instruction — English:** Independently compare the same plant at two time points. First describe visible similarities and differences, then explain whether the evidence might reflect seasonal changes in buds, leaves, flowers, fruits, or senescence. The system will not tell you whether a change actually occurred.

| ID | Exact Chinese wording | Exact English wording | Type and all answer options | Status | Display rule | Revision |
| --- | --- | --- | --- | --- | --- | --- |
| `C1` | 两份材料在芽、叶、花、果实、颜色或衰老迹象等可见特征上有哪些相同或不同？如果看不出可靠变化，也可以直接说明。 | What visible similarities or differences do you notice in buds, leaves, flowers, fruits, color, or signs of senescence? You may say if no reliable change is apparent. | Free text; no authored answer options | Required | Always in Section C | Until Section C is submitted |
| `C2` | 比较这两张图片时，您主要观察了植物的哪些部位？这些部位有什么不同？ | When comparing the two images, which parts of the plant did you focus on? What differences did you notice in those parts? | Free text; no authored answer options | Required | Always in Section C | Until Section C is submitted |
| `C3` | 比较这两张图片时，有没有哪个地方让您觉得难以判断或不确定？为什么？如果没有，可以直接说明。 | When comparing the two images, was there anything you found difficult to judge or were unsure about? Why? If not, you may say so. | Free text; no authored answer options | Required | Always in Section C | Until Section C is submitted |
| `C4` | 根据两张图片中的变化，您认为这株植物可能正在经历什么生长变化？您为什么这样认为？ | Based on the differences between the two images, what growth-related change do you think the plant might be undergoing? Why do you think so? | Free text; no authored answer options | Required | Always in Section C | Until Section C is submitted |
| `C5` | 您对刚才判断的把握程度如何？ | How confident are you in the judgment you just made? | Confidence single choice: `1 — 完全没把握 / No confidence`; `2 — 把握较低 / Low confidence`; `3 — 把握中等 / Moderate confidence`; `4 — 把握较高 / High confidence`; `5 — 很有把握 / Full confidence` | Required | Always in Section C | Until Section C is submitted |
| `C6` | 如果可以再检查一个地方或获得一份额外材料，您最想检查什么季节性证据？ | If you could inspect one more area or obtain one additional piece of information, what seasonal evidence would you most want to check? | Free text; no authored answer options | Required | Always in Section C | Until Section C is submitted |

### Section D — 进一步季节性观察 / Additional Seasonal Observation

**Study item:** `D_PROTO_ITEM_2_SOLIDAGO_001`
**Image:** `/assets/study/section-d-solidago.png`
**Source:** supplied study image stored as a project-relative deployment asset

**Participant instruction — Chinese:** 请按自己的方式独立观察新材料。先描述直接可见的芽、叶、花、果实或衰老迹象，再说明它们是否可能反映植物的季节性状态；也请说明哪些内容不能确认。本阶段不提供系统提示或参考答案。

**Participant instruction — English:** Examine the new material independently in your own way. First describe directly visible buds, leaves, flowers, fruits, or signs of senescence, then explain whether they might reflect the plant’s seasonal condition and what cannot be confirmed. No system hints or reference answers are provided.

| ID | Exact Chinese wording | Exact English wording | Type and all answer options | Status | Display rule | Revision |
| --- | --- | --- | --- | --- | --- | --- |
| `D1` | 观察这张图片时，您注意到了哪些可能反映植物季节性状态的特征？有哪些地方让您感到不确定？ | What features did you notice that might indicate the plant's seasonal condition? Was anything unclear or uncertain? | Free text; no authored answer options | Required | Always in Section D | Until Section D is submitted |
| `D2` | 刚才有没有某个时刻让您对可见证据或季节性判断感到困难或犹豫？当时您做了什么？ | Was there a moment when you felt unsure about the visible evidence or a seasonal interpretation? What did you do then? | Free text; no authored answer options | Required | Always in Section D | Until Section D is submitted |
| `D3` | 仔细观察之后，您对这株植物季节性状态的最初想法有没有变化？如果有，哪些可见证据让您改变了想法？ | After looking more carefully, did your initial impression of the plant’s seasonal condition change? If so, what visible evidence changed your mind? | Free text; no authored answer options | Required | Always in Section D | Until Section D is submitted |
| `D4` | 如果想进一步了解或确认这株植物的季节性状态，您还希望观察什么，或者获得什么额外信息？ | To better understand or confirm the plant’s seasonal condition, what else would you like to observe or what additional information would you need? | Free text; no authored answer options | Required | Always in Section D | Until Section D is submitted |
| `D_CONFIDENCE` | 您对目前关于这株植物的判断有多大把握？ | How confident are you in your current judgment about this plant? | Confidence single choice: `1 — 完全没把握 / No confidence`; `2 — 把握较低 / Low confidence`; `3 — 把握中等 / Moderate confidence`; `4 — 把握较高 / High confidence`; `5 — 很有把握 / Full confidence` | Required | Always in Section D | Until Section D is submitted |
| `D5` | 在刚才的观察过程中，您最希望在哪个时候获得帮助？为什么？如果不需要帮助，也可以直接说明。 | During the observation task, at what point would you have most wanted help, and why? If you did not need any help, you may say so. | Free text; no authored answer options | Required | Always in Section D | Until Section D is submitted |
| `D6` | 如果可以获得帮助，您希望得到什么样的帮助？如果不需要帮助，也可以直接说明。 | If help had been available, what kind of help would you have wanted? You may also say if you did not need any help. | Free text; no authored answer options | Required | Always in Section D | Until Section D is submitted |

**Closing text — Chinese:** 不确定是允许的回答；本阶段不会显示提示、正确答案或判断反馈。

**Closing text — English:** Uncertainty is an acceptable response; this phase does not show hints, correct answers, or judgment feedback.

## Part C — Prototype Interaction

### Activation status

The prototype is implemented, but it is **not shown in the current default v3.2 study**. It is available as a standalone flow at `/prototype.html`; historical researcher-assisted v3 studies may also enter it. When linked to the integrated study, it runs the three items below in fixed order under the training, error-contingent adaptive-guidance condition.

### Researcher/participant distinction

The prototype page contains an authenticated debug panel with study-mode, condition, item, hint-override, reset, export, and researcher-note controls. Those are researcher controls and are not participant questions. Group B “Yoked guidance” is labelled “planned / not fully implemented.”

### Common prototype introduction (standalone route only)

The standalone route displays the following participant-facing instructions in Chinese only:

> 本研究关注人们如何观察植物的视觉变化。
>
> 你不需要具备植物学知识。我们评估的是系统设计，而不是你的个人能力。
>
> 请描述你实际看到的内容；不确定时也可以如实表达。如果方便，请在完成任务时说出你的想法。
>
> 在观察优先条件下，系统不会在你首次判断前显示正确答案。

Definitions shown:

- **选择区域:** 在图片中框选最能支持你判断的证据区域。提交前可以重新绘制矩形。
- **描述观察:** 只描述你能从图片中直接看到的特征。
- **阶段判断:** 选择一个阶段，说明判断理由及主要依据，再评定信心并提交。

Standalone entry field: **匿名参与者编号** (required single-line text; placeholder `例如：F01`), followed by “请只填写研究人员分配的编号，不要填写姓名。” Integrated prototype sessions do not show this entry form. **English for this introduction and entry field: Translation required.**

### Fixed item order and images

| Ordinal | Study item ID | Plant shown | Image |
| --- | --- | --- | --- |
| 1 | `demo_anemone_001` | 弗吉尼亚银莲花（Anemone virginiana） | `/assets/real/anemone_virginiana_001.jpg` |
| 2 | `demo_solidago_001` | 加拿大一枝黄花（Solidago canadensis） | `/assets/real/solidago_canadensis_001.jpg` |
| 3 | `demo_butterfly_weed_001` | 块根马利筋（Asclepias tuberosa） | `/assets/real/butterfly_weed_001.jpg` |

### Questions/tasks repeated for each prototype item

All prototype English wording is **Translation required**.

| Identifier | Exact Chinese wording | Type and all answer options | Status | When/condition | Revision |
| --- | --- | --- | --- | --- | --- |
| `selected_region` | 请选择最能包含支持你判断的视觉证据的区域。提交前可以再次拖动，重新绘制矩形。 | Image-region selection: participant drags a non-zero rectangular region | Required | Initial observation for every item | Can be redrawn before confirmation; initial selection remains in the log after confirmation |
| `observation_text` | 观察——只描述你在所选区域中能直接看到的内容。 | Free text; no authored options | Required | Initial observation for every item | Editable on the check screen before confirmation; initial response remains unchanged afterward |
| `selected_stage_id` | 哪个阶段最符合这株植物的状态？ | Single-choice radio; item-specific options listed below | Required | Initial observation for every item | Editable before confirmation; a later revised stage is collected separately when guidance triggers re-observation |
| `visual_evidence_reason` | 为什么你认为植物处于刚才选择的阶段？ | Free text; no authored options. Help text: “请结合图片中的具体特征说明原因。如果不确定，也可以如实描述。” | Required | Initial observation for every item only | Editable before confirmation; not re-asked during revision |
| `judgement_source` | 你的判断主要依据是什么？ | Single choice: `image_evidence` — 图片中直接看到的特征; `prior_experience` — 以前观察植物的经验; `learned_knowledge` — 课堂或书本中学过的知识; `guessing` — 主要依靠猜测; `other` — 其他 | Required | Initial observation for every item only | Editable before confirmation; not re-asked during revision |
| `confidence` | 信心程度 · 1（最低）–5（最高） | Single-choice radio: `1`, `2`, `3`, `4`, `5` | Required by the form path | Initial observation for every item only; defaults visually to `3` | Editable before confirmation; not re-asked during revision |
| `revised_selected_region` | 请选择最能包含支持你判断的视觉证据的区域。提交前可以再次拖动，重新绘制矩形。 | Image-region selection | Required | Shown after a corrective hint; also used for an unaided final response in non-training modes | Can be redrawn until that revision is submitted; each submitted revision is logged separately |
| `revised_observation` | 观察——只描述你在所选区域中能直接看到的内容。 | Free text; no authored options | Required | Same condition as revised region selection | Submitted as a separate revision; original response is preserved |
| `revised_stage_id` | 哪个阶段最符合这株植物的状态？ | Single-choice radio; item-specific options below | Required | Same condition as revised region selection | Submitted as a separate revision; original response is preserved |
| `reflection_text` | 刚才观察植物时，有没有什么地方让你觉得不确定？如果有，是什么？ | Free text; no authored options | Required | Reflection after expert reveal only when no hint was received | Not revisable after submission |
| `hint_learning_reflection` | 提示是否帮助你注意到或理解了之前没有发现的植物特征？如果有，你学到了什么？ | Free text; no authored options | Required | Reflection after expert reveal only when at least one hint was received | Not revisable after submission |
| `reflection_category` | 你的判断主要在哪方面发生了变化？（选填） | Single choice: blank prompt `请选择`; `Where I looked` — 我查看的位置; `What feature I noticed` — 我注意到的特征; `What the feature meant` — 我对特征含义的理解; `My confidence` — 我的信心程度; `Other` — 其他 | Optional | Shown with either reflection branch | Not revisable after submission |

Before the initial response is committed, the participant sees “检查你的观察,” a summary, and buttons “确认提交观察” and “修改回答 / 重画区域.” Thus the initial response is revisable before confirmation. After confirmation, it is retained unchanged even if later revised responses are submitted.

### Item-specific stage options

#### `demo_anemone_001`

- `no_reproductive_structures` — 未见生殖结构
- `flower_buds_present` — 已有花蕾
- `open_flowering` — 花朵开放
- `fruiting` — 结果期
- `not_sure` — 不确定

#### `demo_solidago_001`

- `vegetative_growth` — 营养生长期
- `flower_buds_developing` — 花蕾发育期
- `flowering` — 开花期
- `fruiting` — 结果期
- `not_sure` — 不确定

#### `demo_butterfly_weed_001`

- `flower_buds_only` — 只有花蕾
- `active_flowering_with_unopened_buds` — 正在开花，仍有部分花蕾未开放
- `flowering_finished` — 开花已经完全结束
- `fruiting` — 结果期
- `not_sure` — 不确定

### Conditional guidance shown after the initial answer or a revision

In the default prototype condition, an initially correct response bypasses corrective guidance and shows positive feedback. An incorrect response receives a diagnosis-dependent authored hint and must complete the three revised tasks above. Re-observation can repeat while another allowed hint is produced; the implementation stops escalating a given diagnosed error after Level 3. A researcher can choose a different authored hint while the authenticated debug controls are active, so every text below is potentially participant-facing.

Other implemented mode/condition branches are:

- **Answer-first training condition:** before the initial questions, the form displays “答案优先：专家参考” followed by the same item-specific relevant region, diagnostic feature, and interpretation listed in the expert-reveal table below.
- **Unaided-test or transfer mode:** after the six initial prompts, the participant completes the three revised/final prompts without a hint or expert answer; the task then completes without the training reflection questions.
- **Yoked non-contingent condition:** selectable in authenticated researcher controls but explicitly labelled planned/not fully implemented; it must not be treated as a completed yoked-matching procedure.

#### `demo_anemone_001` authored feedback and hints

- Positive/correct feedback: 很好。你选择的可见证据与当前阶段一致。
- `REGION_MISS`, Level 1: 请再看看植物的上部。
- `REGION_MISS`, Level 2: 请关注直立茎的末端。
- `REGION_MISS`, Level 3: 请查看这些茎尖端的圆形结构。
- `CUE_MISIDENTIFIED`, Level 1: 请仔细观察所选区域中结构的形状。
- `CUE_MISIDENTIFIED`, Level 2: 注意这些结构是否呈圆形并仍然闭合。
- `CUE_MISIDENTIFIED`, Level 3: 检查是否能看到花瓣，或这些结构是否仍然闭合。
- `INTERPRETATION_ERROR`, Level 1: 请只根据可见的生殖结构选择阶段。
- `INTERPRETATION_ERROR`, Level 2: 比较这些结构仍然闭合还是已经明显开放。
- `INTERPRETATION_ERROR`, Level 3: 请以花瓣是闭合还是展开作为判断阶段的关键证据。
- Authored `CORRECT` hint: 很好。你选择的可见证据与当前阶段一致。
- Semantic-region hint `large_leaf_region`: 你目前关注的是叶片。请向植物更高处寻找生殖结构。
- Semantic-region hint `middle_stem`: 你目前关注的是茎。请沿茎向上，查看其顶端的结构。
- Semantic-region hint `background_vegetation`: 你目前关注的是背景植被。请回到前景中的主要植物。

#### `demo_solidago_001` authored feedback and hints

- Positive/correct feedback: 很好。上部的开花结构提供了与你所选阶段一致的证据。
- `REGION_MISS`, Level 1: 请再看看植物的上部。
- `REGION_MISS`, Level 2: 请关注顶部附近的分枝结构。
- `REGION_MISS`, Level 3: 请查看从上部茎伸出的簇状结构。
- `CUE_MISIDENTIFIED`, Level 1: 请仔细观察植株顶部附近聚集的结构。
- `CUE_MISIDENTIFIED`, Level 2: 注意它们的颜色，以及是否能看见单个花朵结构。
- `CUE_MISIDENTIFIED`, Level 3: 检查这些花簇中是否有开放的黄色花朵，而不只是闭合的花蕾。
- `INTERPRETATION_ERROR`, Level 1: 请根据可见的花部结构选择阶段。
- `INTERPRETATION_ERROR`, Level 2: 比较上部花簇仍在发育，还是已经开放。
- `INTERPRETATION_ERROR`, Level 3: 请以明显开放的黄色花朵作为判断阶段的关键证据。
- Authored `CORRECT` hint: 很好。上部的开花结构提供了与你所选阶段一致的证据。
- Semantic-region hint `middle_leaf_region`: 你目前关注的是叶片。请查看上部的开花结构。
- Semantic-region hint `lower_stem`: 你关注的位置太低。请沿茎向上查看分枝的顶部。
- Semantic-region hint `background_vegetation`: 你目前关注的是周围植被。请回到前景中较高的植株。

#### `demo_butterfly_weed_001` authored feedback and hints

- Positive/correct feedback: 很好。你同时利用了开放花朵和未开放花蕾来支持阶段判断。
- `REGION_MISS`, Level 1: 请再看看植物的上部。
- `REGION_MISS`, Level 2: 请关注顶部附近的橙色花簇。
- `REGION_MISS`, Level 3: 请查看同时包含开放花朵和圆形闭合结构的花簇。
- `CUE_MISIDENTIFIED`, Level 1: 请仔细观察同一花簇中的不同结构。
- `CUE_MISIDENTIFIED`, Level 2: 注意这些结构是否看起来都一样。
- `CUE_MISIDENTIFIED`, Level 3: 比较同一花簇中开放的橙色花朵和圆形的未开放花蕾。
- `INTERPRETATION_ERROR`, Level 1: 请根据花簇中可见结构的组合选择阶段。
- `INTERPRETATION_ERROR`, Level 2: 考虑植株是只有花蕾、开花已经结束，还是正在开花且仍有部分花蕾未开放。
- `INTERPRETATION_ERROR`, Level 3: 请以开放花朵和未开放花蕾同时存在作为判断阶段的关键证据。
- Authored `CORRECT` hint: 很好。你同时利用了开放花朵和未开放花蕾来支持阶段判断。
- Semantic-region hint `leaf_region`: 你目前关注的是叶片。请向上查看橙色的生殖结构。
- Semantic-region hint `lower_stem`: 你目前关注的是下部茎。请沿茎向上查看花簇。
- Semantic-region hint `background_vegetation`: 你目前关注的是周围植被。请回到主要的开花植株。

**English for all feedback and hints above: Translation required.**

### Expert reveal after each training item

The expert reveal highlights the authored target rectangle and displays three labels: “相关区域,” “诊断特征,” and “解释.”

| Item | 相关区域 | 诊断特征 | 解释 |
| --- | --- | --- | --- |
| `demo_anemone_001` | 叶片上方显眼的闭合花蕾 | 叶片上方可见几个圆形花蕾，花瓣尚未开放。 | 这些闭合的圆形结构表明植物已有花蕾。 |
| `demo_solidago_001` | 植株上部带有黄色花序的开花区域 | 植株上部有成簇开放的黄色花朵。 | 可见的开放花朵表明植物处于开花期。 |
| `demo_butterfly_weed_001` | 植株上部同时含开放花朵和未开放花蕾的橙色花簇 | 上部花簇中既有开放的橙色花朵，也有圆形的未开放花蕾。 | 这种组合表明植物正在开花，而且由于仍有花蕾未开放，开花过程还会继续。 |

**English for all expert-reveal content above: Translation required.**

## Part D — Post-prototype Questionnaire

**Not found in the current default implementation.** New v3.2 studies do not enter the prototype and therefore do not have a post-prototype questionnaire. The current Section E refers only to Sections B, C, and D.

Historical v3 studies retain a different Section E instruction and `E1`/`E4` wording that refer to the tool experience. Those historical questions are not projected for newly created v3.2 studies and are documented as a version difference in the consistency audit.

## Part E — Retrospective Reflection / Interview

### Participant-completed website reflection (current Section E)

Displayed as **观察任务后回顾 / Retrospective Reflection After Observation Tasks**.

**Participant instruction — Chinese:** 请回想刚才在 B、C 和 D 部分完成的独立植物观察任务，并根据自己的真实经历回答。没有标准答案，您可以说明某个经历发生在哪一部分。

**Participant instruction — English:** Please reflect on the independent plant-observation tasks you completed in Sections B, C, and D and answer from your own experience. There are no right or wrong answers; you may indicate which section you are referring to.

| ID | Exact Chinese wording | Exact English wording | Type and all answer options | Status | Display rule | Revision |
| --- | --- | --- | --- | --- | --- | --- |
| `E1` | 回想 B、C 和 D 的观察任务，哪个具体时刻让您觉得最困难或最不确定？为什么？ | Looking back at the observation tasks in B, C, and D, which specific moment did you find most difficult or uncertain, and why? | Free text; no authored answer options | Required | Always in Section E | Until Section E is submitted |
| `E2` | 在刚才提到的困难时刻，如果可以获得帮助，您最希望得到什么样的帮助？为什么？如果不需要帮助，也可以直接说明。 | At the difficult moment you just described, what kind of help would you have wanted, and why? You may also say if you did not need any help. | Free text; no authored answer options | Required | Always in Section E | Until Section E is submitted |
| `E3` | 您希望观察工具在什么时候提供帮助？（请选择最接近的选项。） | When would you prefer an observation tool to offer help? (Choose the closest option.) | Single choice: `on_request` — 当我主动请求时 / When I request it; `ask_first` — 工具先询问我是否需要帮助 / When the tool first asks if I need help; `detects_difficulty` — 当工具发现我遇到困难时 / When the tool detects that I am having difficulty; `depends` — 根据不同情况决定 / It depends on the situation | Required | Always in Section E | Until Section E is submitted |
| `E3_WHY` | 为什么？ | Why? | Free text; no authored answer options | Required when displayed | Shown after any nonblank answer to `E3`; hidden before `E3` is answered | Until Section E is submitted |
| `E4` | 您觉得在什么情况下，观察工具提供的提示可能会打断您的观察，或者影响您自己作出判断？ | In what situations might prompts from an observation tool interrupt your observation or affect your ability to make your own judgment? | Free text; no authored answer options | Required | Always in Section E | Until Section E is submitted |

### Researcher-administered retrospective interview

**Not found in the current implementation.** No separate researcher-administered interview script or interview questions were found in the inspected repository files. Section E is completed directly by the participant on the website.

## Researcher-entered fields displayed inside participant forms

These controls are visibly rendered on participant section pages but are labelled for the researcher. They are not counted as participant questions.

| Section | Identifier | Exact wording | Type | Status and revision |
| --- | --- | --- | --- | --- |
| A | `STUDY_DATE_MANUAL` | 研究员填写日期（选填） / Researcher-entered date (optional) | Single-line text | Optional; editable until Section A submission |
| B | `B_START_TIME_MANUAL` | 研究员填写开始时间（选填） / Manual start time (optional) | Single-line text | Optional; editable until Section B submission |
| D | `D_START_TIME_MANUAL` | 研究员填写开始时间（选填） / Manual start time (optional) | Single-line text | Optional; editable until Section D submission |
| D | `D_FIELD_BASED` | 现场 / Field-based | Checkbox | Optional metadata; editable until Section D submission |

Hidden material metadata (`B_STATION_ID`, `C_EARLIER_MATERIAL_ID`, `C_CURRENT_MATERIAL_ID`, `C_PRESENTATION_ORDER`, and `D_MATERIAL_ID`) is not participant-facing and is not a question.

## Questions or procedures planned but not fully implemented

- Full Group B participant-to-participant yoked matching is explicitly labelled “planned / not fully implemented.” Its selectable prototype condition is a placeholder and should not be described as a completed experimental condition.
- Cross-item automatic fading is listed in project documentation as planned, not implemented.
- No final main-study protocol is implemented.
- Ecological expert validation of prototype content, target regions, and thresholds remains planned.

## Question counts

The authoritative active v3.2 questionnaire contains **30 stable question fields**, calculated from the executable section arrays:

| Study stage | Count |
| --- | ---: |
| Part A / Section A — Background | 7 |
| Part B / Section B — Seasonal plant observation | 5 |
| Part B / Section C — Temporal comparison | 6 |
| Part B / Section D — Additional observation and user needs | 7 |
| Part E / Section E — Retrospective participant reflection | 5 |
| **Active v3.2 total** | **30** |
The two study-entry controls and four visible researcher metadata controls are disclosed above but are not included in the 30-question count.

The separate prototype has **12 authored response-prompt variants per item**: six initial prompts, three revised-response prompts, two mutually exclusive reflection-text prompts, and one optional reflection-category prompt. Across three items this is 36 item/prompt variants. On an initially correct path, a participant sees eight prompts per item (six initial, one reflection-text branch, and the optional category). Each corrective re-observation adds the three revised-response prompts and can repeat. These prototype counts are reported separately because the prototype is disabled in the current default v3.2 study.
