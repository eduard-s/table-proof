# Small development benchmark

These results describe this corpus only. They do not prove broad accuracy or adoption.

The unit is one case/document. The real-library pair shares one generated PDF.
The real-source pair shares one public table excerpt. Gold labels are AI-assisted.
TableProof vision is disabled. Docling extraction used real layout and table models.

| Method | Stratum | Cases | TP | FP | Precision | Recall | FPR | Abstain | Review cases | Errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pdfmux_numeric_literals | real_library_reproducer | 2 | 1 | 1 | 0.500 | 1.000 | 1.000 | 0 | 2 | 0 |
| pdfmux_numeric_literals | real_source_pdf | 2 | 2 | 0 | 1.000 | 1.000 | n/a | 0 | 2 | 0 |
| pdfmux_numeric_literals | synthetic_control | 14 | 3 | 0 | 1.000 | 0.375 | 0.000 | 1 | 4 | 0 |
| structural_validity_control | real_library_reproducer | 2 | 0 | 0 | n/a | 0.000 | 0.000 | 0 | 0 | 0 |
| structural_validity_control | real_source_pdf | 2 | 0 | 0 | n/a | 0.000 | n/a | 0 | 0 | 0 |
| structural_validity_control | synthetic_control | 14 | 1 | 0 | 1.000 | 0.125 | 0.000 | 0 | 1 | 0 |
| tableproof | real_library_reproducer | 2 | 1 | 0 | 1.000 | 1.000 | 0.000 | 0 | 1 | 0 |
| tableproof | real_source_pdf | 2 | 1 | 0 | 1.000 | 0.500 | n/a | 1 | 2 | 0 |
| tableproof | synthetic_control | 14 | 7 | 0 | 1.000 | 0.875 | 0.000 | 3 | 10 | 0 |
| token_multiset_control | real_library_reproducer | 2 | 0 | 0 | n/a | 0.000 | 0.000 | 0 | 0 | 0 |
| token_multiset_control | real_source_pdf | 2 | 2 | 0 | 1.000 | 1.000 | n/a | 0 | 2 | 0 |
| token_multiset_control | synthetic_control | 14 | 4 | 0 | 1.000 | 0.500 | 0.000 | 1 | 5 | 0 |

Abstentions and execution errors remain in the rate denominators.
A zero denominator produces `null` in JSON and `n/a` here.

`token_multiset_control` and `structural_validity_control` are local controls.
`pdfmux_numeric_literals` calls upstream code with the numeric signal enabled.
The JSON result contains exact versions, case outcomes, and error details.
Method statuses differ. A generic review flag does not prove a correct diagnosis.
Review burden counts both review and uncertain. Execution errors have a separate count.
TableProof gets Docling JSON geometry. pdfmux gets its supported page Markdown format.
