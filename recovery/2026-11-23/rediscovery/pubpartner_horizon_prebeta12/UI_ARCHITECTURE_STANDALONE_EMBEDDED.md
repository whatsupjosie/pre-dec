# UI Architecture Note

## Standalone mode

`pubpartner.html`, `pubpartner.css`, and `pubpartner.js` create the full PubPartner shell. `WorkspaceRuntime` owns only presentation state: tray geometry, z-order, collapse, material, theme, motion preference, and local layout import/export. `CommandRegistry` maps visible controls to existing PubPartner behavior.

The UI does not own companion identity, governed memory, evidence, custody, provider secrets, or authorization. Those remain behind the existing authenticated routes and backend modules.

## Future embedded mode

The next extraction should move `WorkspaceRuntime` and `CommandRegistry` into product-neutral modules with two constructors:

- `standalone`: creates top bar, menus, tray field, theme state, and workspace persistence.
- `embedded`: registers PubPartner trays and commands with a host-provided shell without creating a second top bar, theme manager, persistence namespace, or window manager.

PubCast may then own top-level composition while PubPartner continues to own its domain trays and command implementations. The current code keeps that boundary possible by avoiding Wallet APIs and custody semantics.
