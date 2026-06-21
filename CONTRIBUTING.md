# Contributing

Thanks for considering contributing to WikiCitationFixer!

## Issues

- Check existing issues before opening a new one
- Include the wikitext or DOI that triggered the bug
- For feature requests, describe which module it relates to

## Pull Requests

1. Fork the repository
2. Create a feature branch from \`master\`
3. Make your changes
4. Run tests with \`python -m pytest\`
5. Submit a PR with a clear description

## Code style

- Python code is formatted with [Ruff](https://docs.astral.sh/ruff/)
- Run \`ruff check .\` and \`ruff format .\` before committing
- Keep changes focused — one PR per module or fix

## Module development

See the [README](README.md#default-modules-and-their-purpose) for the module system overview.
Each module in \`wikifix/modules/\` should implement a \`process(text, context)\` function.
