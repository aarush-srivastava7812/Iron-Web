# Graph sizing review

The graph uses a 1240 x 580 pixel default canvas with filename-aware spacing.
The Size controls adjust width (900-2800 px) and height (480-1400 px); a
bottom-right grip also supports pointer dragging and arrow keys. Settings persist
in browser storage. The duplicate view-navigation rail has been removed.

Validation: production build succeeded, 8 Node tests passed, and 16 browser
tests passed. Coverage includes filename overlap checks, resize limits, drag and
keyboard resizing, saved dimensions, a single navigation, and existing controls.

See `dimensions.png` for the size controls.
