# PR Toolbox

A powerful tool to generate concise, professional pull request descriptions and perform comprehensive code reviews using OpenAI's GPT-4. Automatically analyzes your PR changes and creates clear, informative descriptions while identifying code quality issues.

## Features

- 🔗 **GitHub Integration**: Automatically detects repository and current branch
- 🤖 **AI-Powered Descriptions**: Uses OpenAI GPT-4 to generate professional PR descriptions
- 🔍 **Code Review**: Comprehensive analysis for security vulnerabilities, code smells, and readability issues
- 📊 **Smart Analysis**: Analyzes files changed, commit messages, and code statistics
- 🎨 **Beautiful Output**: Rich terminal interface with colored output
- 🚨 **Issue Detection**: Identifies security vulnerabilities, performance issues, and code quality problems

## Installation

1. Clone this repository:
```bash
git clone <your-repo-url>
cd pr-toolbox
```

2. Install dependencies:
```bash
uv sync
```

3. Set up environment variables:
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API keys
GITHUB_TOKEN=your_github_token_here
OPENAI_API_KEY=your_openai_api_key_here
```

## Getting API Keys

### GitHub Token
1. Go to [GitHub Settings > Tokens](https://github.com/settings/tokens)
2. Click "Generate new token (classic)"
3. Select scopes: `repo`, `read:org`
4. Copy the token to your `.env` file

### OpenAI API Key
1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Create a new API key
3. Copy the key to your `.env` file

## Usage

### PR Description Generation

#### Basic Usage (Current Branch)
```bash
# Generate description for current branch's PR
python set_description.py

# Or use the installed command
pr-toolbox
```

#### Specific PR
```bash
# Generate description for specific PR number
python set_description.py --pr 123

# Specify repository
python set_description.py --repo owner/repo --pr 123
```

### Code Review

#### Basic Code Review
```bash
# Review a specific PR for code quality issues
python review_code.py --repo owner/repo --pr 123

# Or use the installed command
pr-review --repo owner/repo --pr 123
```

#### Save Results to File
```bash
# Save review results to JSON file
python review_code.py --repo owner/repo --pr 123 --output review_results.json

# Force chunked analysis for very large diffs
python review_code.py --repo owner/repo --pr 123 --chunk

# Use specific OpenAI model
python review_code.py --repo owner/repo --pr 123 --model gpt-3.5-turbo-16k
```

### Command Line Options

#### PR Description Generation
| Option | Short | Description |
|--------|-------|-------------|
| `--repo` | `-r` | Repository name (owner/repo) |
| `--pr` | `-p` | Pull request number |
| `--token` | `-t` | GitHub token (overrides env var) |

#### Code Review
| Option | Short | Description |
|--------|-------|-------------|
| `--repo` | `-r` | Repository name (owner/repo) |
| `--pr` | `-p` | Pull request number |
| `--token` | `-t` | GitHub token (overrides env var) |
| `--output` | `-o` | Output file for results (JSON format) |
| `--chunk` | `-c` | Force chunked analysis for large diffs |
| `--model` | `-m` | OpenAI model to use (gpt-4, gpt-3.5-turbo-16k, auto) |

## How It Works

### PR Description Generation
1. **Repository Detection**: Automatically detects the current repository from git remote
2. **Branch Analysis**: Identifies the current branch and finds associated PR
3. **Data Collection**: Gathers PR information including:
   - Files changed
   - Lines added/removed
   - Commit messages
   - Current description
4. **AI Generation**: Uses OpenAI GPT-4 to create a concise, professional description

### Code Review
1. **PR Fetching**: Retrieves the specified pull request from GitHub
2. **Diff Analysis**: Extracts the complete diff content including file changes
3. **Size Management**: Automatically handles large diffs by:
   - Skipping binary files (images, PDFs, etc.)
   - Truncating very large files (>1000 changes)
   - Using chunked analysis for diffs >6000 tokens
   - Switching to GPT-3.5-turbo-16k for larger context windows
4. **AI Analysis**: Uses OpenAI to analyze the code for:
   - Security vulnerabilities (SQL injection, XSS, authentication issues)
   - Code smells (duplication, long methods, complex conditionals)
   - Performance issues (inefficient algorithms, memory leaks)
   - Readability problems (poor naming, unclear logic)
   - Maintainability concerns (tight coupling, hardcoded values)
5. **Issue Categorization**: Organizes issues by severity and category
6. **Detailed Reporting**: Provides actionable suggestions and overall quality score

## Example Output

### PR Description Generation
```
╭─ Current PR Information ──────────────────────────────────────────────╮
│ PR Title: Add user authentication system                              │
│ Branch: feature/auth → main                                           │
│ Files Changed: 5                                                      │
│ Changes: +234 -45                                                     │
╰───────────────────────────────────────────────────────────────────────╯

╭─ Generated PR Description ────────────────────────────────────────────╮
│ This PR implements a comprehensive user authentication system with    │
│ JWT tokens, password hashing, and session management. Key changes     │
│ include:                                                              │
│                                                                        │
│ • New auth middleware for route protection                            │
│ • User model with secure password hashing                             │
│ • JWT token generation and validation                                 │
│ • Login/logout endpoints with proper error handling                   │
│                                                                        │
│ No breaking changes. All existing functionality remains intact.       │
╰───────────────────────────────────────────────────────────────────────╯
```

### Code Review
```
╭─ 🔍 PR Code Review ──────────────────────────────────────────────────╮
│ Code Review Results for PR #123                                       │
│ Add user authentication system                                        │
│ Repository: owner/repo                                                │
╰───────────────────────────────────────────────────────────────────────╯

╭─ 📊 Score ────────────────────────────────────────────────────────────╮
│ Overall Code Quality Score: 75/100                                   │
╰───────────────────────────────────────────────────────────────────────╯

╭─ 🚨 Issues Found ────────────────────────────────────────────────────╮
│ Severity │ Category    │ Title                    │ File        │ Line │
│ HIGH     │ security    │ Potential SQL Injection  │ auth.py     │ 42   │
│ MEDIUM   │ readability │ Magic Number             │ config.py   │ 15   │
│ LOW      │ performance │ Inefficient Loop         │ utils.py    │ 78   │
╰───────────────────────────────────────────────────────────────────────╯

╭─ 💡 Top Recommendations ──────────────────────────────────────────────╮
│ • Use parameterized queries to prevent SQL injection                 │
│ • Extract magic numbers to named constants                          │
│ • Consider using list comprehension for better performance           │
╰───────────────────────────────────────────────────────────────────────╯
```

## Requirements

- Python 3.12+
- Git repository with GitHub remote
- GitHub API token
- OpenAI API key

## Dependencies

- `PyGithub` - GitHub API integration
- `openai` - OpenAI API client
- `click` - Command line interface
- `rich` - Beautiful terminal output
- `python-dotenv` - Environment variable management

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
