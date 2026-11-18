# Dialogue and speaker attribution — automatic-first design

## Product rule

Speaker and voice assignment must be **automatic by default**. Manual editing is a correction tool, not the normal workflow. Preserve the useful automatic character/voice workflow familiar from TeraTTS 1.59, but improve dialogue segmentation, speaker attribution, entity resolution, and gender evidence before sending text to TeraTTSv2.

TeraTTSv2 is the speech synthesizer. FB2AudioPrep owns book analysis and the mapping from each utterance to a speaker and voice style.

## Processing pipeline

1. Parse FB2/TXT into paragraphs while preserving chapter, paragraph order, quotation marks, em dashes, and narration/dialogue boundaries.
2. Segment paragraphs into utterances. A paragraph may contain narration, one or more dialogue turns, and a speech tag.
3. Extract candidate character mentions and aliases. Normalize spelling/case, but retain original forms and inflection.
4. Extract speech-attribution evidence from both sides of each utterance and from adjacent sentences/paragraphs.
5. Resolve the speaker using evidence and dialogue continuity.
6. Infer voice gender only from explicit grammatical/narrative evidence or a previously resolved character profile. Never infer gender from the character's name alone.
7. Build a per-book character graph and assign the selected TeraTTSv2 voice style automatically.
8. Mark uncertain cases with confidence and only then invite a user correction. Corrections become per-book overrides and feed subsequent references to that character.

## Evidence priority

Use weighted, explainable evidence, with this precedence:

1. **Explicit speech tag attached to the utterance**: “сказала она”, “произнёс Нико”, “ответил мужчина”, “раздался женский голос”.
2. **Explicit voice description attached to the utterance**: “женский голос”, “мужской голос”, “женщина произнесла”, “мужчина ответил”.
3. **Syntactic speaker construction**: subject + speech verb (“Нико сказал”, “она спросила”).
4. **Local dialogue turn-taking**: alternating speakers, question/answer structure, and a known current speaker, only when not contradicted by explicit tags.
5. **Resolved character profile and aliases** from earlier high-confidence mentions.
6. **Longer-range narrative context**.
7. Name proximity alone is weak evidence and must never decide speaker identity or gender.

Contradictory explicit evidence should lower confidence and be surfaced for review rather than silently choosing the nearest name.

## Critical distinction: addressee vs speaker

A name in a vocative or direct address is the addressee, not the speaker. Examples:
- “Нико! Нико, мать твою!” — Нико is being addressed; this does not mean Nico speaks.
- “Нико, добро пожаловать!” — Nico may be the addressee; the speaker must be determined from attached narration/speech tags.
- “— Ты где? — спросила она.” — the speaker is “она”, not the person being asked.

The parser must detect vocative constructions and avoid adding the addressed character as the speaker candidate unless separate evidence supports it.

## Speech-tag attachment

Speech tags may precede, follow, or interrupt a quote:
- “Нико, добро пожаловать! — раздался в голове приветливый женский голос.”
- “— Нико! Нико, мать твою! — раздался снаружи раздражённый женский голос с лёгкими рычащими нотками.”
- “Она сказала: «Я вернулась».”
- “— Я, — сказала она, — больше не уйду.”

The tag must be attached to the correct utterance even when it follows the closing quote or is separated by punctuation. Adjectives describing voice quality and gender belong to the speaker evidence for that utterance.

## Character identity and aliases

- Merge spelling variants, case forms, and inflections only when supported by context.
- Keep distinct characters separate when names are similar.
- Do not create a new character from every capitalized word, vocative, or isolated mention.
- Treat role nouns/pronouns (“она”, “мужчина”, “девушка”, “старик”, “голос”) as attribution clues; resolve them to an existing character only when context supports it.
- Keep unresolved speakers as temporary anonymous speaker nodes instead of inventing a character name.
- Store aliases and evidence provenance so users can inspect why two mentions were merged.

## Voice assignment

- Automatic assignment selects only verified Russian TeraTTSv2-compatible voices.
- The character's voice assignment persists per book and is reused consistently.
- Gender classification comes from explicit text evidence or confirmed profile, not a name lookup.
- If the text explicitly says “женский голос” or “мужской голос”, that evidence takes precedence over weak inferred gender.
- If the text does not establish gender, retain an unclassified state and use a neutral/default policy selected in settings; do not make a confident false assignment.
- Manual correction is available in a character list and applies to all later occurrences of that character in the book.

## Confidence and user experience

Every attribution has an internal confidence score and evidence record:
- High confidence: assign automatically without interrupting reading.
- Medium confidence: assign automatically but show a subtle review marker in the character list.
- Low confidence or contradictory evidence: use the configured fallback and place the utterance in a review queue. Do not interrupt import with a questionnaire.

The user should normally import a book and press play. Review is optional and focused on uncertain cases.

## Regression tests

The first chapter passages supplied by the user are mandatory regression cases:
1. “— Нико! Нико, мать твою! раздался снаружи раздражённый женский голос с лёгкими рычащими нотками.” Expected: speaker is the woman/voice described by the narration; “Нико” is the addressee, not the speaker.
2. “«Нико, добро пожаловать!» раздался в голове приветливый женский голос.” Expected: the utterance is assigned to a female voice; Nico is not assumed to be speaking because his name appears in the quote.
3. The later “ИсКин” passage must be tested for correct entity resolution and speaker assignment against its surrounding narrative, not by the name alone.

For every regression case, test utterance boundaries, speaker ID, resolved character/anonymous status, gender evidence, selected voice ID, and confidence.

## Evaluation

Build a small labelled corpus from the user's opening chapter and additional varied Russian dialogue patterns. Measure:
- utterance boundary accuracy;
- speaker attribution accuracy;
- addressee-vs-speaker confusion rate;
- character merge/split precision and recall;
- gender classification precision, recall, and abstention rate;
- percentage of utterances automatically resolved without user intervention.

Optimize first for low false attribution, not for forcing every line into a named character. It is better to leave a speaker uncertain than to confidently assign the wrong voice.
