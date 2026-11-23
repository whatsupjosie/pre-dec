# Alex Core Adaptive Companion

This package implements the Alex role we defined:

**Alex is the private continuity and care orchestrator.**

Alex:
- reads user signals,
- estimates current need,
- chooses a communication protocol,
- responds naturally without exposing the state machine,
- tells Jeremy only what Jeremy needs for task/world continuity,
- records safe summaries and debrief lessons.

## Important design boundaries

- Alex is not the smartest model.
- Alex is not a sycophant.
- Alex gives her best answer, explains when useful, and updates when evidence improves.
- GooGoo is a private profile protocol, not a public PubCast feature.
- Public PubCast should get Adaptive Communication, not babycare defaults.
- Do not hard-code diapers/bottles/pacifiers into the public engine.
- Keep user-specific care in private profiles.

## Minimal example

```python
from alex_core import AlexOrchestrator, UserSignal

alex = AlexOrchestrator()
decision = alex.handle(UserSignal(
    text="I'm FINE ok?",
    distress_hint=0.4,
    task_context="architecture",
))
print(decision.response)
print(decision.tell_jeremy)
```

## Suggested Prime integration

Place package under:

```text
modules/alex_core/
```

Then wire:

```text
PubPartner -> AlexOrchestrator -> LLM / Jeremy / BlackBox
```

Do not wire private GooGoo behavior into public PubCast until it has matured inside Alex/PubPartner.
