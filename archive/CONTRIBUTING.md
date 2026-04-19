# 🤝 Contributing Guide

Thanks for your interest in contributing! This guide will help you get started.

---

## Code of Conduct

Please be respectful to all contributors. This project values:
- ✅ Kindness and inclusivity
- ✅ Clear communication
- ✅ Constructive feedback

---

## Getting Started

### 1. Fork & Clone

```bash
git clone https://github.com/yourusername/linkedin-content-generator.git
cd linkedin-content-generator
git remote add upstream https://github.com/originalauthor/linkedin-content-generator.git
```

### 2. Set Up Development Environment

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pytest-cov black flake8
```

### 3. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/issue-number
```

---

## Development Workflow

### Before Coding

1. Check existing [Issues](https://github.com/yourusername/linkedin-content-generator/issues)
2. Open an Issue if your feature isn't discussed yet
3. Wait for maintainer feedback before starting big changes

### While Coding

1. **Write tests first** (TDD approach)
2. **Keep code simple** - readability > cleverness
3. **Document as you go** - docstrings for functions
4. **Run tests frequently** - `pytest tests/ -v`

### Code Style

```bash
# Format code
black src/

# Check style
flake8 src/

# Type check (optional)
mypy src/ --ignore-missing-imports
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_agent.py::TestPostGeneration::test_generate_post_topic_type -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

---

## Common Contributions

### Adding a New Post Type

1. Add to `POST_TYPE_PROMPTS` in `src/agent.py`
2. Create prompt template
3. Add to `schedule_config.json` example
4. Add tests in `tests/test_agent.py`
5. Update docs in `docs/CONFIGURATION.md`

### Adding a Diagram Style

1. Create new style function in `src/diagram_generator.py`
2. Add to `ALL_DIAGRAM_STYLES` list
3. Test with `python src/diagram_generator.py --style=YOUR_STYLE`
4. Update diagram rotation system
5. Add to docs

### Improving Engagement

1. Add new CTA to `STRONG_CTAS` in `src/agent.py`
2. Or add vulnerability pattern to `VULNERABILITY_PATTERNS`
3. Test locally with `--dry-run`
4. Add to engagement tracking
5. Document impact

### Bug Fixes

1. Create test that reproduces bug
2. Implement fix
3. Verify test passes
4. Add to CHANGELOG.md
5. Submit PR with issue reference

---

## Pull Request Process

### Before Submitting

```bash
# Update from upstream
git fetch upstream
git rebase upstream/main

# Run all tests
pytest tests/ -v

# Check code style
black src/
flake8 src/

# Verify no secrets in code
# (never commit .env, API keys, tokens)
```

### PR Description

```markdown
## Description
I've implemented [feature/fix] to [accomplish goal].

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Performance improvement

## Related Issue
Fixes #123

## Testing
- [ ] Unit tests added
- [ ] Integration tests pass
- [ ] Tested with dry-run
- [ ] No breaking changes

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for clarity
- [ ] No secrets in code
- [ ] Tests added/updated
- [ ] Docs updated
```

### After Submitting

- Maintainer will review within 48 hours
- Address feedback promptly
- Be open to suggestions
- Tests must pass before merge

---

## Project Structure

```
linkedin-content-generator/
├── src/
│   ├── agent.py              # Main agent logic
│   ├── diagram_generator.py  # Diagram creation
│   ├── linkedin_poster.py    # LinkedIn API
│   ├── topic_manager.py      # Topic selection
│   ├── logger.py             # Logging setup
│   └── ...
├── tests/
│   ├── test_agent.py         # Unit tests
│   ├── test_integration.py   # Integration tests
│   └── conftest.py           # Test fixtures
├── docs/
│   ├── INSTALLATION.md       # Setup guide
│   ├── CONFIGURATION.md      # Config reference
│   ├── API.md               # API reference
│   └── TROUBLESHOOTING.md   # Common issues
├── .github/
│   └── workflows/
│       └── test.yml         # CI/CD
├── Dockerfile              # Container setup
├── docker-compose.yml      # Docker orchestration
└── requirements.txt        # Python dependencies
```

---

## Areas Needing Help

### Priority: High
- [ ] Multi-platform support (Twitter, Medium, Dev.to)
- [ ] Dashboard improvements
- [ ] Performance optimizations

### Priority: Medium
- [ ] Additional diagram styles
- [ ] More engagement patterns
- [ ] Documentation translations

### Priority: Low
- [ ] Additional test coverage
- [ ] Code cleanup/refactoring
- [ ] Example configs

---

## Commit Message Guidelines

```
[type]: [description]

Example types:
- feat: New feature
- fix: Bug fix
- docs: Documentation
- test: Test addition/update
- refactor: Code reorganization
- perf: Performance improvement

Examples:
✅ feat: add topic diversity checking
✅ fix: prevent LinkedIn token expiry errors
❌ updated stuff
❌ asdf
```

---

## Performance Expectations

- Post generation: < 60 seconds
- Diagram creation: < 10 seconds
- Memory usage: < 500MB
- API calls: Minimal & batched

When optimizing, test with:
```bash
time python src/agent.py --dry-run
```

---

## Documentation Updates

When you change code that affects users:

1. Update relevant `.md` file in `docs/`
2. Update docstrings in code
3. Add example to `examples/` if applicable
4. Update `README.md` if significant

---

## Release Process

1. Update version number in `version.txt`
2. Update `CHANGELOG.md`
3. Create tagged release on GitHub
4. Publish to PyPI (if applicable)

---

## Licensing

By contributing, you agree that your contributions are licensed under MIT License.

---

## Questions?

- Check [FAQ](docs/FAQ.md)
- Browse [Issues](https://github.com/yourusername/linkedin-content-generator/issues)
- Start a [Discussion](https://github.com/yourusername/linkedin-content-generator/discussions)

---

## Thank You!

Your contribution helps make this project better for everyone. 🙏
