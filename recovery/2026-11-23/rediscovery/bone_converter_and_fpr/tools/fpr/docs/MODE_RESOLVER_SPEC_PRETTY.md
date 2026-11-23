# PubCast Mode Resolver
## Pretty spec, real behavior

Purpose:
The Mode Resolver decides how PubCast should behave right now.

Inputs:
1. Voice signal (hint)
2. Task signal (usually strongest truth)
3. Project context
4. Recent state

Outputs:
- resolved_mode
- confidence
- reasoning_summary
- signals_used
- agent_bundle
- context_to_load
- needs_human_confirmation

Supported modes:
- technical
- creative
- strategist
- director
- support
- synthesis

Suggested weighting:
- task 45%
- project 25%
- recent_state 20%
- voice 10%

A real mode resolver must have:
- explicit inputs
- clear weighting
- explainable output
- operational consequences
- confidence handling

First implementation target:
v1 should accept the four inputs, score the six modes, emit result JSON, assign default agents, and log why it chose that mode.

After that:
1. hook it into START_SESSION
2. validate debugging / creative / planning scenarios
