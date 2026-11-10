# Heuristics: what to vary, and how

A variable is anything you can change, directly or indirectly, that might change the system's behaviour. The obvious ones (field values) are usually the best tested. The subtle ones (counts, order, position, who is acting, what happened before) and the indirect ones (how many records a query returns, how many times something has run) hide more bugs. Most of these heuristics come from Elisabeth Hendrickson's *Explore It!* (2013) and its heuristics cheat sheet.

## Counts and sets

- **Zero, one, many.** Anything you can count: results, items in a list, children of a record, characters, retries. Zero is special: code that expects a set often mishandles an empty one, and anything that divides may divide by it.
- **Too few, too many.** Fewer items than the system needs (an order with no lines), more than it expects (a page size past the maximum, many children on one parent).
- **Some, none, all.** For sets of options, permissions, tags, flags. Watch for "none" being treated like "all", and for percentage or count errors.

## Position and order

- **Beginning, middle, end.** Act on the first, a middle and the last item of a list, page or sequence. The last item and the last page break more often than the others.
- **Sorting.** Values that sort differently as numbers and as text (9 and 10), mixed case, accented and non-Latin letters.
- **Reverse.** Do a workflow backwards, undo everything, skip to the end and go back.

## Size, format and depth

- **Too small, too big, just right.** Strings, numbers, dates, files and ranges. Probe around limits and around powers of two (255, 256, 65536). Watch for silent truncation and for data that seems saved but isn't.
- **Other valid formats.** Anything that can look different and mean the same thing: dates and times (with and without a time, offsets, other zones), numbers (decimals, exponents, leading zeros), case, whitespace, encodings.
- **Break the format rules.** A negative age, February 30, an id that is almost a number, malformed JSON, an empty body.
- **Depth.** Nest structures deeply, or not at all.

## Entities and their relationships

- **Model them.** List the entities (the nouns), their attributes and how they relate: what has, belongs to or depends on what.
- **CRUD each entity, in every way the system allows:** create, read, update and delete each one, through every path (separate endpoints, bulk actions, side effects of other actions). Compare entities made one way with entities made another.
- **Dependents.** Create a parent with zero, one and many children. Delete, close or change a parent that has children. Move a child to another parent, or to a parent that doesn't exist.
- **Clear what you set.** Create with every optional field filled, then try to clear each one.
- **Follow the data.** After every change, find the entity everywhere it appears: detail, lists, search and filters, totals and reports, related entities, and other users' views. A change that is right in one place and stale in another is a bug.

## States and transitions

- **Find the states.** A new state exists when you can now do something you couldn't before, can't do what you could, or the same action has a different result. Anything you'd describe with "while" ("while it's pending…") is a state.
- **Find the events:** user actions, actions of other users or roles, system events, and the passage of time.
- **Make a state table.** States down the side, events across the top, the expected result in each cell. Cells the docs don't cover are the most promising tests: try each event in each state.
- **All the ways.** Find every way to get from one state to another, and every way back.
- **Interrupt and repeat.** Trigger an event twice, out of order, or from the wrong state. Vary what happened before: the previous state, how you got here, how many times you've been here.

## Breaking your own habits

- **Nouns and verbs.** Pair the system's entities with its actions at random, including pairs that make little sense, and work out what each could mean. It takes you down paths you wouldn't choose.
- **Personas.** Act as a specific user: the impatient one who repeats every action, the expert who scripts everything, the newcomer who reads nothing. Include other roles acting on the same data.
- **Unusual data.** Avoid the test values everyone uses. Try apostrophes (O'Malley), non-ASCII letters (the Turkish dotless ı), long names, times near midnight in far-away time zones, amounts with many decimals.

## Timing

- **Frequency and repetition.** Do it many times quickly; do it again after the first attempt succeeded.
- **Duration.** Leave something half-done; let a token or session age.
