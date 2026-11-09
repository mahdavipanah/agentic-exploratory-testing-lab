# Tours

Tours are themed routes through a product, adapted from James Whittaker's *Exploratory Software Testing* (2009). Give each charter one or two.

| Tour | What you do | Good for |
| --- | --- | --- |
| Guidebook | Follow the docs literally. Every example, status code, field and message should behave exactly as written. | Contract gaps, broken examples |
| Money | Exercise what users depend on most, the flows the product is sold on. | Finding the bugs that matter first |
| Landmark | Visit the key features in different orders. | State and ordering problems |
| FedEx | Follow one distinctive piece of data through every path, format and representation, and check it arrives unchanged. | Data that changes, truncates or disappears |
| Antisocial | Enter what a real user least likely would: missing, extra, empty, wrong-type, huge, negative or malformed input. | Validation gaps, crashes |
| Obsessive-compulsive | Repeat, reorder, retry and double-submit actions. | Duplicates, races, idempotency |
| Saboteur | Take away what the system relies on: credentials, valid ids, headers, content types, dependencies. | Error handling, access control |
| Back alley | Try the least-documented features and odd combinations of documented ones. | Code nobody tested |
| Garbage collector's | Walk everything systematically: every endpoint with every method, every screen with every field. | Gaps a risk-first plan skipped |
| Intellectual | Ask the hardest questions: the most complex input, the biggest data, the strangest valid case. | Limits and edge cases |
