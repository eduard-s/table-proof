# Source attribution

The regression mechanism and patch come from the MIT-licensed Docling-core project:

- [Repository and license](https://github.com/docling-project/docling-core/blob/main/LICENSE)
- [Original issue](https://github.com/docling-project/docling/issues/5198)
- [Reproducer and proposed patch](https://github.com/docling-project/docling-core/pull/986)

The benchmark runs an installed copy of pdfmux under its MIT license:

- [Pinned repository](https://github.com/NameetP/pdfmux/tree/5662a29c634b24bf02f162e0d18ced9ecf8f0fd4)
- [License](https://github.com/NameetP/pdfmux/blob/5662a29c634b24bf02f162e0d18ced9ecf8f0fd4/LICENSE)

The generated PDFs use the project MIT license.
The real public PDF and its table excerpt use a separate license:

Wolfgang R. Mukabana, Collins K. Mweresa, Bruno Otieno, Philemon Omusula, Renate C. Smallegange,
Joop J. A. van Loon, and Willem Takken.
*A Novel Synthetic Odorant Blend for Trapping of Malaria and Other African Mosquito Species.*
Journal of Chemical Ecology 38, 235–244 (2012). Copyright The Author(s) 2012.
[DOI](https://doi.org/10.1007/s10886-012-0088-8).
[CC BY 2.0 license](https://creativecommons.org/licenses/by/2.0/).
[Publisher license statement](https://link.springer.com/article/10.1007/s10886-012-0088-8#rightslink).

Changes: page 6 is copied from the original. The table excerpt removes text and vector graphics outside Table 2.
It keeps the source table glyphs, fonts, values, and geometry. No table data is repaired.
The source record describes the exact rectangle and records all PDF hashes.

No private source PDF is included.
The baseline's own result text appears in `results.json` to preserve its warnings and limits.

The full Docling-core license notice is in [DOCLING_LICENSE](DOCLING_LICENSE).
