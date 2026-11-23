# Studio integration decision

The working base is `pre-dec` at recovery commit `0eb6819`. The June 18 First Prime archive matches the checksum preserved in Big Zip. Its code supplies a reference implementation for production controls and a record of the original console design.

## Three paths tested

| Path | Observed result | Decision |
| --- | --- | --- |
| Use the June archive as the studio | The archive boots, cuts to the selected camera, changes the dialogue mixer state, and records a decodable virtual-camera MP4. Its Studio Control Room opens a generic room socket. The dedicated socket crashes because the route calls a method the handler lacks. | Keep as a reference and use its original console assets. |
| Keep the recovery checkout as it was | Both studio socket paths send initial state and answer status requests. Emergency Save reports success while the server recording stays active. | Keep the working socket and replace the operator's emergency command path. |
| Keep the recovery checkout and integrate the recorder with Emergency Save | The same production stop path handles encoder finalization, blackout, program mute, and the stop signal to connected stage clients. The console-state snapshot runs afterward. The UI waits for the server response and reports partial failure. | Adopt this path. |

## Integration list

| System | Recovered source and comparison | Integration decision |
| --- | --- | --- |
| Studio host and WebSocket | June `main.py` and `studio_websocket.py` contain the original protocol. Both routes in the recovery checkout call the existing handler correctly. | Keep the recovery host and handler. The legacy socket's save acknowledgment identifies its control-state scope. |
| Camera sources and switcher | Alpha, March Hardened, and June contain successive camera implementations. June has camera registration, readiness, Preview, Program, and Cut. The current shared switcher adds shared state and transitions. | Keep the current switcher as the authority for the main console and the on-set mini console. |
| Director and audio console art | June contains the original images, coordinate manifests, renderer, and stable action IDs. The current checkout contains these files. The enhanced HTML upload contains station layouts with incomplete local wiring. | Preserve the original art and use the current action wiring. Keep additional HTML for design reference. |
| Director Dock and on-set console | The Prime has the station summon behavior. The recovery checkout restores the dock and adds a mini console wired to the shared switcher. | Carry both recovery commits forward. |
| Audio | June has program audio actions. The current host exposes the shared program bus, participant audio, and production stop. | Keep the current mixer. Emergency Save uses the existing production mute. Live microphone routing and recorded program audio need a production run. |
| Recorder and recovery | June's FFmpeg path produces virtual video. The current checkout also has browser capture, archive ingest, and export code. | Finalize server capture before marking its take stopped. Use the existing production stop event for browser captures. Receipt and finalization at a browser client still need end-to-end verification. |
| Slate and take lifecycle | The loose Python upload depends on `StudioCameraEngine`, which is absent from June. The supplied Rust scene-sync function is empty. October's control-wiring branch at `df9d30f` has a complete director-owned slate, SQLite state, roll call, shared clap cue, and floor voice relay. | Restore the October slate and crew reference art. Mount its authenticated API, socket, and overlay in the current host. The slate schedules a cue. The recorder is armed separately and recorded alignment remains unverified. |
| Stage, actors, choreography, and Foley | June has the panoramic stage and actor action code. The current checkout also contains the fixed-set 2.5D renderer and shared switcher integration. | Keep both stage surfaces. Verify an actual take with actors and distinct program and preview frames. |
| Rust animation renderer | The Drive voxel reference handoff lists `rust_crate` and `bin/ws_renderer`. Both are present in the June archive. The current source adds the Stage 1 camera-control protocol, while the packaged Linux binary is byte-identical to June's. A live probe acknowledged an avatar-motion frame and rejected the newer camera-control hello. | Keep the shipped renderer for animation. Before using the Rust camera-control path, build the current source and verify both acknowledgments and rendered pixels. |
| Teleprompter, chyron, and replay | June contains the teleprompter implementation and station panels. The current checkout carries them forward. | Keep them. Run them during the same production check to verify what reaches Program. |
| BlackBox, timeline, and export | June has working code for events, timeline, and capture metadata. The current checkout includes replay metadata and source export. | Keep the current versions. Verify the exported take and source audio against a complete shoot. |
| Other uploads | Bubble Stack and the four PubPartner components cover frame and companion services. The button bindings handle manuscript references. The studio image supplies visual direction. | Keep their current feature owners. The recording repair has no dependency on these files. |

The production gate is one take through the normal UI with actors, two distinguishable camera views, a Program cut, dialogue audio, and a playable saved take. Exercise both ordinary Stop and Emergency Save, including receipt of the stop by a connected stage client.

## Verification of this integration

- The normal Studio Control Room JavaScript sent Emergency Save to the running server. The server stopped a real FFmpeg virtual-source encoder, registered a decodable H.264 MP4, wrote the recovery manifest, and reported blackout plus zero program master volume.
- The current host served the slate on the Control Room, Director Switcher, and fixed-set stage. In automated integration tests, a verified crew connection received slate updates from a director and read the same raised slate. The recovered tests cover department authorization, revision checks, reopen persistence, and synthetic PCM relay. A physical microphone and recorded clap alignment remain open.
- 126 focused Python tests and four existing Node checks passed. The Emergency Save UI logic ran in Node against the live host. Chromium rendering and a full shoot with production sources were outside the verified run.
