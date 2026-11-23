# Functional Purpose Report
## PubCast Voice / Mode System

Summary:
Status: Partial leaning Misaligned
Confidence: Medium
Primary issue: voice currently acts as a label/intent signal but does not reliably drive system behavior or context loading.
Recommended action: recalibrate voice as a multi-signal classifier input plus enforced mode loader.

Desired purpose:
- instantly identify what kind of help/work is needed
- reduce friction at session start
- load correct context and priorities automatically
- shift system behavior appropriately
- prevent misaligned responses early

Stated purpose:
- voice selection determines system mode
- mode controls behavior, priorities, and agent roles
- voice acts as a trigger for system configuration

Functional purpose:
- mapping exists conceptually
- mode definitions exist
- no enforced behavior change pipeline
- no guaranteed context loading tied to voice
- no routing enforcement
- no validation that voice selection improves outcomes

Correct classification:
voice = secondary input signal, not authority

Final decision:
Recalibrate
