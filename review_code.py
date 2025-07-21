#!/usr/bin/env python3
"""
PR Code Review Tool - Analyzes pull request diffs using OpenAI for code quality insights
"""

import os
import re
import sys
from typing import List, Optional, Tuple
from dataclasses import dataclass
import click
from github import Github
from github.PullRequest import PullRequest
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

console = Console()

@dataclass
class CodeIssue:
    """Represents a code issue found during review"""
    severity: str  # 'critical', 'high', 'medium', 'low', 'info'
    category: str  # 'security', 'performance', 'readability', 'maintainability', 'best_practice'
    title: str
    description: str
    line_number: Optional[int] = None
    file_path: Optional[str] = None
    suggestion: Optional[str] = None

@dataclass
class ReviewResult:
    """Container for review results"""
    issues: List[CodeIssue]
    summary: str
    overall_score: int  # 0-100
    recommendations: List[str]

class GitHubPRReviewer:
    """Handles GitHub PR operations and code review"""
    
    def __init__(self, token: str):
        self.github = Github(token)
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    def get_pr(self, repo_name: str, pr_number: int) -> PullRequest:
        """Fetch a specific pull request"""
        try:
            repo = self.github.get_repo(repo_name)
            return repo.get_pull(pr_number)
        except Exception as e:
            console.print(f"[red]Error fetching PR: {e}[/red]")
            sys.exit(1)
    
    def get_pr_diff(self, pr: PullRequest) -> str:
        """Get the diff content of a pull request"""
        try:
            # Get the diff as a string
            diff_content = ""
            total_files = 0
            total_changes = 0
            
            for file in pr.get_files():
                if file.patch:
                    # Skip binary files and very large files
                    if file.filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.tar.gz')):
                        diff_content += f"File: {file.filename} (binary file - skipped)\n"
                        continue
                    
                    # Limit very large files to prevent token overflow
                    if file.additions + file.deletions > 1000:
                        diff_content += f"File: {file.filename} (large file - showing first 500 lines)\n"
                        diff_content += f"Status: {file.status}\n"
                        diff_content += f"Additions: {file.additions}, Deletions: {file.deletions}\n"
                        diff_content += "---\n"
                        
                        # Take only first 500 lines of the patch
                        patch_lines = file.patch.split('\n')[:500]
                        diff_content += '\n'.join(patch_lines)
                        diff_content += "\n... (truncated due to size)\n\n"
                    else:
                        diff_content += f"File: {file.filename}\n"
                        diff_content += f"Status: {file.status}\n"
                        diff_content += f"Additions: {file.additions}, Deletions: {file.deletions}\n"
                        diff_content += "---\n"
                        diff_content += file.patch
                        diff_content += "\n\n"
                    
                    total_files += 1
                    total_changes += file.additions + file.deletions
            
            console.print(f"[blue]Processed {total_files} files with {total_changes} total changes[/blue]")
            return diff_content
        except Exception as e:
            console.print(f"[red]Error fetching PR diff: {e}[/red]")
            sys.exit(1)
    
    def analyze_code_with_openai(self, diff_content: str, pr_title: str, pr_description: str) -> ReviewResult:
        """Use OpenAI to analyze the code diff for issues"""
        
        # Check if content is too large and chunk if necessary
        estimated_tokens = self._estimate_tokens(diff_content)
        if estimated_tokens > 6000:  # Leave room for prompt and response
            console.print(f"[yellow]Large diff detected ({estimated_tokens} estimated tokens), analyzing in chunks...[/yellow]")
            return self._analyze_large_diff(diff_content, pr_title, pr_description)
        
        # Construct the prompt for OpenAI
        prompt = self._build_analysis_prompt(diff_content, pr_title, pr_description)
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Analyzing code with OpenAI...", total=None)
                
                # Choose model based on content size
                model = "gpt-4"
                if estimated_tokens > 4000:
                    model = "gpt-3.5-turbo-16k"  # Larger context window
                    console.print("[blue]Using GPT-3.5-turbo-16k for larger context window[/blue]")
                
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert code reviewer and security analyst. Analyze the provided code diff and identify issues in the following categories: security vulnerabilities, code smells, performance issues, readability problems, and maintainability concerns. Provide specific, actionable feedback."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.1,
                    max_tokens=2000
                )
                
                progress.update(task, completed=True)
        
        except Exception as e:
            console.print(f"[red]Error calling OpenAI API: {e}[/red]")
            sys.exit(1)
        
        # Parse the response
        content = response.choices[0].message.content
        if content is None:
            console.print("[red]Error: OpenAI returned empty response[/red]")
            sys.exit(1)
        return self._parse_openai_response(content)
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough estimation of token count"""
        # More accurate token estimation
        # Words are typically 1-2 tokens, punctuation adds tokens
        words = len(text.split())
        chars = len(text)
        
        # Rough estimation: 1.3 tokens per word + extra for code/punctuation
        estimated_tokens = int(words * 1.3 + chars * 0.1)
        
        return estimated_tokens
    
    def _analyze_large_diff(self, diff_content: str, pr_title: str, pr_description: str) -> ReviewResult:
        """Analyze large diffs by splitting into chunks and combining results"""
        
        # Split diff into file-based chunks
        file_chunks = self._split_diff_into_files(diff_content)
        
        all_issues = []
        all_recommendations = []
        scores = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Analyzing chunks...", total=len(file_chunks))
            
            for i, (filename, chunk_content) in enumerate(file_chunks):
                progress.update(task, description=f"Analyzing chunk {i+1}/{len(file_chunks)}: {filename}")
                
                # Analyze this chunk
                chunk_prompt = self._build_chunk_analysis_prompt(chunk_content, filename, pr_title)
                
                try:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert code reviewer. Analyze this code chunk and identify issues. Focus on the most critical problems."
                            },
                            {
                                "role": "user",
                                "content": chunk_prompt
                            }
                        ],
                        temperature=0.1,
                        max_tokens=1500
                    )
                    
                    content = response.choices[0].message.content
                    if content:
                        chunk_result = self._parse_openai_response(content)
                        all_issues.extend(chunk_result.issues)
                        all_recommendations.extend(chunk_result.recommendations)
                        scores.append(chunk_result.overall_score)
                
                except Exception as e:
                    console.print(f"[yellow]Warning: Error analyzing chunk {filename}: {e}[/yellow]")
                
                progress.advance(task)
        
        # Combine results
        overall_score = sum(scores) // len(scores) if scores else 0
        unique_recommendations = list(set(all_recommendations))[:5]  # Top 5 unique recommendations
        
        return ReviewResult(
            issues=all_issues,
            summary=f"Analyzed {len(file_chunks)} files with {len(all_issues)} total issues found",
            overall_score=overall_score,
            recommendations=unique_recommendations
        )
    
    def _split_diff_into_files(self, diff_content: str) -> List[Tuple[str, str]]:
        """Split diff content into separate files for chunked analysis"""
        chunks = []
        current_file = None
        current_content = []
        
        for line in diff_content.split('\n'):
            if line.startswith('File: '):
                # Save previous file if exists
                if current_file and current_content:
                    chunks.append((current_file, '\n'.join(current_content)))
                
                # Start new file
                current_file = line[6:]  # Remove 'File: ' prefix
                current_content = [line]
            else:
                if current_file:
                    current_content.append(line)
        
        # Add the last file
        if current_file and current_content:
            chunks.append((current_file, '\n'.join(current_content)))
        
        return chunks
    
    def _build_chunk_analysis_prompt(self, chunk_content: str, filename: str, pr_title: str) -> str:
        """Build a prompt for analyzing a single file chunk"""
        return f"""
Please analyze this code chunk from file: {filename}

Pull Request Title: {pr_title}

Code Chunk:
{chunk_content}

Please identify the most critical issues in this code chunk. Focus on:
1. Security vulnerabilities (high priority)
2. Critical code smells
3. Major performance issues
4. Significant readability problems

For each issue found, provide:
- Severity (critical/high/medium/low/info)
- Category (security/performance/readability/maintainability/best_practice)
- Title (brief description)
- Description (detailed explanation)
- Line number (if applicable)
- Suggestion (how to fix)

Also provide:
- A brief summary
- A score from 0-100
- 2-3 key recommendations

Format your response as JSON:
{{
    "issues": [
        {{
            "severity": "high",
            "category": "security",
            "title": "Issue Title",
            "description": "Issue description",
            "line_number": 42,
            "file_path": "{filename}",
            "suggestion": "How to fix"
        }}
    ],
    "summary": "Brief summary",
    "overall_score": 75,
    "recommendations": ["rec1", "rec2"]
}}
"""
    
    def _build_analysis_prompt(self, diff_content: str, pr_title: str, pr_description: str) -> str:
        """Build the analysis prompt for OpenAI"""
        return f"""
Please analyze the following pull request diff and provide a comprehensive code review.

Pull Request Title: {pr_title}
Pull Request Description: {pr_description}

Code Diff:
{diff_content}

Please analyze this code for:

1. **Security Vulnerabilities**: SQL injection, XSS, authentication issues, data exposure, etc.
2. **Code Smells**: Code duplication, long methods, complex conditionals, magic numbers, etc.
3. **Performance Issues**: Inefficient algorithms, memory leaks, unnecessary computations, etc.
4. **Readability Issues**: Poor naming, unclear logic, missing comments, etc.
5. **Maintainability Concerns**: Tight coupling, lack of abstraction, hardcoded values, etc.

For each issue found, provide:
- Severity (critical/high/medium/low/info)
- Category (security/performance/readability/maintainability/best_practice)
- Title (brief description)
- Description (detailed explanation)
- Line number (if applicable)
- File path (if applicable)
- Suggestion (how to fix)

Also provide:
- An overall summary
- A score from 0-100 (100 being perfect)
- Top 3 recommendations for improvement

Format your response as JSON with the following structure:
{{
    "issues": [
        {{
            "severity": "high",
            "category": "security",
            "title": "Potential SQL Injection",
            "description": "User input is directly concatenated into SQL query",
            "line_number": 42,
            "file_path": "src/database.py",
            "suggestion": "Use parameterized queries or ORM"
        }}
    ],
    "summary": "Overall assessment of the code quality",
    "overall_score": 75,
    "recommendations": [
        "Implement input validation",
        "Add error handling",
        "Extract magic numbers to constants"
    ]
}}
"""
    
    def _parse_openai_response(self, response: str) -> ReviewResult:
        """Parse the OpenAI response into a ReviewResult object"""
        try:
            # Extract JSON from the response (in case there's extra text)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")
            
            import json
            data = json.loads(json_match.group())
            
            # Convert to ReviewResult
            issues = []
            for issue_data in data.get("issues", []):
                issue = CodeIssue(
                    severity=issue_data.get("severity", "info"),
                    category=issue_data.get("category", "best_practice"),
                    title=issue_data.get("title", ""),
                    description=issue_data.get("description", ""),
                    line_number=issue_data.get("line_number"),
                    file_path=issue_data.get("file_path"),
                    suggestion=issue_data.get("suggestion")
                )
                issues.append(issue)
            
            return ReviewResult(
                issues=issues,
                summary=data.get("summary", ""),
                overall_score=data.get("overall_score", 0),
                recommendations=data.get("recommendations", [])
            )
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not parse OpenAI response: {e}[/yellow]")
            console.print(f"[yellow]Raw response: {response}[/yellow]")
            
            # Return a basic result
            return ReviewResult(
                issues=[],
                summary="Error parsing OpenAI response",
                overall_score=0,
                recommendations=["Review the code manually"]
            )

class ReviewReporter:
    """Handles formatting and displaying review results"""
    
    @staticmethod
    def display_review_results(result: ReviewResult, pr: PullRequest):
        """Display the review results in a formatted way"""
        
        # Header
        console.print(Panel(
            f"[bold blue]Code Review Results for PR #{pr.number}[/bold blue]\n"
            f"[bold]{pr.title}[/bold]\n"
            f"Repository: {pr.base.repo.full_name}",
            title="🔍 PR Code Review",
            border_style="blue"
        ))
        
        # Overall Score
        score_color = "green" if result.overall_score >= 80 else "yellow" if result.overall_score >= 60 else "red"
        console.print(Panel(
            f"[bold]Overall Code Quality Score: [/bold][{score_color}]{result.overall_score}/100[/{score_color}]",
            title="📊 Score",
            border_style=score_color
        ))
        
        # Summary
        if result.summary:
            console.print(Panel(
                result.summary,
                title="📝 Summary",
                border_style="cyan"
            ))
        
        # Issues Table
        if result.issues:
            table = Table(title="🚨 Issues Found")
            table.add_column("Severity", style="bold")
            table.add_column("Category", style="cyan")
            table.add_column("Title", style="bold")
            table.add_column("File", style="dim")
            table.add_column("Line", style="dim")
            
            for issue in result.issues:
                severity_color = {
                    "critical": "red",
                    "high": "red",
                    "medium": "yellow",
                    "low": "blue",
                    "info": "green"
                }.get(issue.severity, "white")
                
                table.add_row(
                    f"[{severity_color}]{issue.severity.upper()}[/{severity_color}]",
                    issue.category,
                    issue.title,
                    issue.file_path or "N/A",
                    str(issue.line_number) if issue.line_number else "N/A"
                )
            
            console.print(table)
            
            # Detailed Issues
            for i, issue in enumerate(result.issues, 1):
                console.print(Panel(
                    f"[bold]{issue.title}[/bold]\n\n"
                    f"[bold]Description:[/bold] {issue.description}\n\n"
                    f"[bold]Category:[/bold] {issue.category}\n"
                    f"[bold]Severity:[/bold] {issue.severity}\n"
                    f"[bold]File:[/bold] {issue.file_path or 'N/A'}\n"
                    f"[bold]Line:[/bold] {issue.line_number or 'N/A'}\n\n"
                    f"[bold green]Suggestion:[/bold green] {issue.suggestion or 'No specific suggestion provided'}",
                    title=f"Issue #{i}",
                    border_style="red" if issue.severity in ["critical", "high"] else "yellow"
                ))
        
        # Recommendations
        if result.recommendations:
            console.print(Panel(
                "\n".join(f"• {rec}" for rec in result.recommendations),
                title="💡 Top Recommendations",
                border_style="green"
            ))
        
        # No issues found
        if not result.issues:
            console.print(Panel(
                "[bold green]🎉 No issues found! The code looks good.[/bold green]",
                title="✅ Clean Code",
                border_style="green"
            ))

@click.command()
@click.option('--repo', '-r', required=True, help='Repository name (owner/repo)')
@click.option('--pr', '-p', required=True, type=int, help='Pull request number')
@click.option('--token', '-t', help='GitHub token (or set GITHUB_TOKEN env var)')
@click.option('--output', '-o', help='Output file for results (JSON format)')
@click.option('--chunk', '-c', is_flag=True, help='Force chunked analysis for large diffs')
@click.option('--model', '-m', default='auto', help='OpenAI model to use (gpt-4, gpt-3.5-turbo-16k, auto)')
def main(repo: str, pr: int, token: str, output: str, chunk: bool, model: str):
    """
    Review a GitHub pull request for code quality issues using OpenAI.
    
    Example:
        python review_code.py --repo owner/repo --pr 123
    """
    
    # Get GitHub token
    github_token = token or os.getenv("GITHUB_TOKEN")
    if not github_token:
        console.print("[red]Error: GitHub token required. Set GITHUB_TOKEN environment variable or use --token option.[/red]")
        sys.exit(1)
    
    # Check OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        console.print("[red]Error: OPENAI_API_KEY environment variable is required.[/red]")
        sys.exit(1)
    
    try:
        # Initialize reviewer
        reviewer = GitHubPRReviewer(github_token)
        
        # Get PR
        console.print(f"[blue]Fetching PR #{pr} from {repo}...[/blue]")
        pull_request = reviewer.get_pr(repo, pr)
        
        # Get diff
        console.print("[blue]Fetching PR diff...[/blue]")
        diff_content = reviewer.get_pr_diff(pull_request)
        
        if not diff_content.strip():
            console.print("[yellow]Warning: No diff content found. The PR might be empty or only contain binary files.[/yellow]")
            return
        
        # Analyze with OpenAI
        console.print("[blue]Analyzing code with OpenAI...[/blue]")
        
        # Check if forced chunking is requested
        if chunk:
            console.print("[yellow]Forced chunked analysis requested...[/yellow]")
            result = reviewer._analyze_large_diff(diff_content, pull_request.title, pull_request.body or "")
        else:
            result = reviewer.analyze_code_with_openai(
                diff_content, 
                pull_request.title, 
                pull_request.body or ""
            )
        
        # Display results
        ReviewReporter.display_review_results(result, pull_request)
        
        # Save to file if requested
        if output:
            import json
            output_data = {
                "pr_number": pr,
                "repo": repo,
                "overall_score": result.overall_score,
                "summary": result.summary,
                "recommendations": result.recommendations,
                "issues": [
                    {
                        "severity": issue.severity,
                        "category": issue.category,
                        "title": issue.title,
                        "description": issue.description,
                        "line_number": issue.line_number,
                        "file_path": issue.file_path,
                        "suggestion": issue.suggestion
                    }
                    for issue in result.issues
                ]
            }
            
            with open(output, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            console.print(f"[green]Results saved to {output}[/green]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]Review cancelled by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
