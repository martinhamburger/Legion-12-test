# S01 PDF card-pool import

`card_pool.json` is a review-gated candidate catalog generated from the PDFs in
`规则与卡池/`. Every card points back to its exact PDF, checksum, page and crop.

`needs_review` cards and effects that are not `implemented` are intentionally
excluded by `legion12.catalog.load_trainable_cards`. The GitHub Pages reviewer is
the human-facing surface for checking these candidates before they become rules
engine input.

Do not commit rendered card images. The Pages build creates disposable WebP
previews from the source PDFs.
