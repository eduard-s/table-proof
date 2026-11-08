# Third-party materials

TableProof uses the MIT license for its original code and generated fixtures.

The benchmark adapts a public Docling-core regression reproducer and its proposed fix. Read [the benchmark notices](benchmarks/THIRD_PARTY.md).

The optional Table Transformer checkpoint remains a separate download. Its [model card](https://huggingface.co/microsoft/table-transformer-structure-recognition-v1.1-all) supplies its metadata.

The [upstream project](https://github.com/microsoft/table-transformer) provides model code, datasets, and evaluation resources. Dataset terms remain separate from TableProof's license.

pdfmux is an optional benchmark dependency. Its upstream code runs in an isolated environment. TableProof does not distribute a copied pdfmux implementation.

Each dependency distribution retains its own license files. The benchmark manifests record licenses for included source materials.
