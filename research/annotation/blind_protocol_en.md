# Blind annotation protocol (paper)

English translation of `blind_protocol.md`; the Ukrainian original is the version given to the annotator.

The annotator sees only `blind_cards.json`: the item description, the procurement title, the procuring entity,
the DK 021 (CPV) code, the price and unit as stated in the document, the quantity, the price source, the price
in the base unit, and neutral reference items (same DK 021 code and base unit: median, p10–p90, 8 random
examples). The annotator does not see the decision of any model version, the risk score, the stratum, or the
pipeline's group median. The order of the cards is shuffled.

## Label

`[status, reason, comment]`, files `blind_decisions_*.json` (key: item_id). Comments are written in Ukrainian.

- **confirmed**: an auditor should look at the unit price:
  - `overpriced`: the price is noticeably higher than for comparable goods (guideline: more than ~2× the
    typical price, taking into account the description, grade and pack size);
  - `underpriced`: noticeably lower (guideline: less than ~0.4× the typical price) with no explanation in the
    description;
  - `unit_error`: the price clearly corresponds to another unit (a pack, a gram, a tonne, the whole lot);
  - `data_error`: another data error (lot total entered as a unit price, implausible quantity or price).
- **not_anomaly** (`justified`): the price is plausible for such goods.
- **needs_review** (`other`): it is impossible to judge from the available data (a generic description such as
  "assorted food products" with no detail, etc.).

The ×2 / ×0.4 guidelines are not applied mechanically: higher grades, organic products, small pack sizes or
delivery stated in the description explain a deviation.
