# Datasets and evaluation

## Separate evidence groups

| Group | Purpose | Current evidence |
| --- | --- | --- |
| Real library reproducer | Detect an actual code defect at a fixed revision. | Docling rich-reference regression and paired fix |
| Real source PDF | Detect natural parser errors on a public document. | See the current benchmark manifest. |
| Synthetic controls | Exercise known error classes and correct cases. | Generated tables with explicit labels |
| Vision smoke run | Show actual checkpoint inference. | One generated table and one changed export |

Do not combine these groups into one headline accuracy score. A real library bug on generated input is not a real-document evaluation.

The [benchmark record](../benchmarks/README.md) gives exact source provenance. Each manifest identifies the source, license, extraction, versions, hashes, and gold errors.

## Candidate public datasets

### PubTables-1M

[PubTables-1M](https://github.com/microsoft/table-transformer) provides table structure annotations and source-related coordinates. It also supplies GriTS evaluation code.

Use its existing document partitions. Keep tables from the same source together. Examine the dataset terms before redistribution.

The optional Table Transformer uses related training data. Results on those sources are not independent evidence of model generalization.

The upstream repository is archived. Pin the model and evaluation code revisions.

### OmniDocBench

[OmniDocBench](https://github.com/opendatalab/OmniDocBench) covers varied document layouts. Its table labels can support a separate evaluation group.

The code license does not establish permission to redistribute every source document. Record the source-level terms before a fixture enters this repository.

### Public regression documents

Prefer issue reports with a public source, exact package versions, and a runnable reproduction. Record whether the upstream defect is open or fixed.

For example, [Docling issue 5136](https://github.com/docling-project/docling/issues/5136) identifies a public scientific paper and a parser-version change.

An issue description alone is not a benchmark result. Capture the actual output and inspect its source page.

## Annotation contract

Each wrong association needs a page, table, row, column, source region, and expected relationship.

Record the extracted relationship separately. Keep source errors separate from extraction errors.

Use two human reviewers for the independent evaluation set. Preserve disagreements and their resolution.

A correct table can contain blanks, repeated values, merged headers, or unusual units. Include these cases in every evaluation partition.

## Partition policy

Reserve the final document sample before threshold changes. Group by source document, publisher, and template where possible.

Keep synthetic transformations with their source document. A transformed copy cannot enter a different partition.

The current fixture corpus supports development and regression tests. It is not an untouched accuracy benchmark.

## Metrics

Measure these quantities separately:

- Cell-association precision and recall.
- Table-level false alarms on correct outputs.
- Unsupported cases and abstention rates.
- Execution errors and missing methods.
- Runtime, peak memory, and model cost.
- Human review time per table.

Use exact cell labels to measure localization. A document flag does not establish that every wrong cell was found.

Keep abstentions in the recall denominator. Report detector coverage beside precision. Keep failed runs in the result record.

## Comparative protocol

Run the same source and extracted content through every method. Materialize rich references before format conversion.

Record every adapter operation. Use documented default settings before a separately reported tuned comparison.

Include token coverage, structural validity, pdfmux, and a source-image model baseline. The current run does not evaluate every competing product.

Compare geometry-only, vision-only, and combined results. Use document-level paired resampling after the corpus contains enough independent documents.

Publish the corpus selection rule before a broad claim. Publish negative results and cases that each method misses.
