# Contributing to LLM Gateway

Thank you for your interest in contributing to LLM Gateway! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)

## Code of Conduct

Please be respectful and constructive in all interactions. We are committed to providing a welcoming and inclusive environment for everyone.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/llm-gateway.git
   cd llm-gateway
   ```
3. Add the upstream remote:
   ```bash
   git remote add upstream https://github.com/kevin-toles/llm-gateway.git
   ```

## Development Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git

### Local Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Install pre-commit hooks (optional but recommended)
pre-commit install

# Start Redis for development
docker run -d --name redis -p 6379:6379 redis:7-alpine

# Set environment variables
export LLM_GATEWAY_ENV=development
export LLM_GATEWAY_REDIS_URL=redis://localhost:6379

# Run the application
uvicorn src.main:app --reload --host 0.0.0.0 --port 8080
```

### Docker Setup (Alternative)

```bash
# Copy environment template
cp deploy/docker/.env.example .env
# Edit .env with your API keys

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f llm-gateway
```

## Making Changes

### Branch Naming

Use descriptive branch names:
- `feature/add-new-provider` - New features
- `fix/rate-limiter-bug` - Bug fixes
- `docs/update-readme` - Documentation updates
- `refactor/improve-caching` - Code refactoring

### Creating a Branch

```bash
# Sync with upstream
git fetch upstream
git checkout main
git merge upstream/main

# Create feature branch
git checkout -b feature/your-feature-name
```

### Commit Messages

Follow conventional commits format:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting, missing semicolons, etc.
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance tasks

Examples:
```
feat(providers): add Azure OpenAI provider support
fix(sessions): resolve Redis connection timeout issue
docs(readme): update installation instructions
```

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit -v

# Run with coverage
pytest tests/ -v --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_main.py -v
```

### Test Requirements

- All new features must have tests
- Bug fixes should include a test that reproduces the bug
- Maintain or improve code coverage

### Linting and Type Checking

```bash
# Run linting
ruff check src/

# Auto-fix issues
ruff check src/ --fix

# Check formatting
ruff format --check src/

# Apply formatting
ruff format src/

# Type checking
mypy src/
```

### Helm Chart Testing

```bash
# Lint chart
helm lint deploy/helm/llm-gateway

# Run unit tests
helm unittest deploy/helm/llm-gateway

# Validate templates
helm template test deploy/helm/llm-gateway | kubeconform -summary -strict
```

## Pull Request Process

1. **Ensure your code passes all tests and linting**
   ```bash
   pytest tests/ -v
   ruff check src/
   mypy src/
   ```

2. **Update documentation** if needed

3. **Create Pull Request**
   - Use a clear, descriptive title
   - Reference any related issues
   - Describe what changes you made and why

4. **PR Template**
   ```markdown
   ## Description
   Brief description of changes

   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Documentation update
   - [ ] Refactoring

   ## Testing
   - [ ] Unit tests pass
   - [ ] Integration tests pass
   - [ ] Manual testing performed

   ## Checklist
   - [ ] Code follows project style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   - [ ] Tests added/updated
   ```

5. **Code Review**
   - Address reviewer feedback
   - Keep discussions constructive
   - Squash commits if requested

## Code Style

### Python Style Guide

- Follow PEP 8
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use f-strings for string formatting
- Write docstrings for public functions

### Example

```python
async def process_request(
    request: ChatRequest,
    provider: str = "anthropic",
) -> ChatResponse:
    """
    Process a chat completion request.

    Args:
        request: The chat completion request.
        provider: The LLM provider to use.

    Returns:
        The chat completion response.

    Raises:
        ProviderError: If the provider request fails.
    """
    # Implementation
    ...
```

### Project Structure

- `src/` - Application source code
- `tests/` - Test files (mirror src/ structure)
- `deploy/` - Deployment configurations
- `docs/` - Documentation

## Environment Variables

See [README.md](README.md#environment-variables) for the full list of environment variables.

## Questions?

If you have questions, feel free to:
- Open a GitHub issue
- Start a discussion in the repository

Thank you for contributing! 🎉
