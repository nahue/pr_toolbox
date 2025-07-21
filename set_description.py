import os
from typing import Optional, List
from dataclasses import dataclass

import click
from github import Github, GithubException
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

console = Console()


@dataclass
class PRInfo:
    """Data class to hold pull request information"""
    title: str
    body: str
    files_changed: List[str]
    additions: int
    deletions: int
    commits: List[str]
    branch: str
    base_branch: str


class GitHubPRAnalyzer:
    """Class to handle GitHub API interactions and PR analysis"""
    
    def __init__(self, token: str):
        self.github = Github(token)
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
    def get_repo_from_remote(self) -> Optional[str]:
        """Extract repository name from git remote"""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            remote_url = result.stdout.strip()
            
            # Handle both HTTPS and SSH URLs
            if remote_url.startswith("https://"):
                return remote_url.replace("https://github.com/", "").replace(".git", "")
            elif remote_url.startswith("git@"):
                return remote_url.replace("git@github.com:", "").replace(".git", "")
            
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def get_current_branch(self) -> Optional[str]:
        """Get current git branch"""
        try:
            import subprocess
            result = subprocess.run(
                ["git", "branch", "--show-current"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
    
    def get_pr_info(self, repo_name: str, pr_number: Optional[int] = None) -> Optional[PRInfo]:
        """Get pull request information from GitHub"""
        try:
            repo = self.github.get_repo(repo_name)
            
            if pr_number is None:
                # Get current branch and find associated PR
                current_branch = self.get_current_branch()
                if not current_branch:
                    console.print("[red]Could not determine current branch[/red]")
                    return None
                
                # Find PR by branch name
                pulls = repo.get_pulls(state='open')
                for pull in pulls:
                    if pull.head.ref == current_branch:
                        pr = pull
                        break
                else:
                    console.print(f"[red]No open PR found for branch: {current_branch}[/red]")
                    return None
            else:
                pr = repo.get_pull(pr_number)
            
            # Get files changed
            files_changed = [file.filename for file in pr.get_files()]
            
            # Get commit messages
            commits = [commit.commit.message for commit in pr.get_commits()]
            
            return PRInfo(
                title=pr.title,
                body=pr.body or "",
                files_changed=files_changed,
                additions=pr.additions,
                deletions=pr.deletions,
                commits=commits,
                branch=pr.head.ref,
                base_branch=pr.base.ref
            )
            
        except GithubException as e:
            console.print(f"[red]GitHub API error: {e}[/red]")
            return None
    
    def generate_pr_description(self, pr_info: PRInfo) -> Optional[str]:
        """Generate a concise PR description using OpenAI"""
        
        # Create a comprehensive prompt
        prompt = f"""
You are a senior software engineer tasked with creating a concise, professional pull request description.

Please analyze the following PR information and create a clear, concise description that:
1. Summarizes the main changes in 1-2 sentences
2. Highlights key technical changes
3. Mentions any breaking changes or important notes
4. Uses professional, clear language
5. Is under 200 words

PR Information:
- Title: {pr_info.title}
- Files changed: {', '.join(pr_info.files_changed)}
- Additions: {pr_info.additions} lines
- Deletions: {pr_info.deletions} lines
- Branch: {pr_info.branch} → {pr_info.base_branch}
- Commits: {len(pr_info.commits)} commits

Recent commit messages:
{chr(10).join(pr_info.commits[-5:])}

Current PR description:
{pr_info.body if pr_info.body else "No description provided"}

Please provide a concise, professional PR description:
"""
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior software engineer who writes clear, concise, and professional pull request descriptions. Focus on the technical changes and their impact."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            console.print(f"[red]OpenAI API error: {e}[/red]")
            return None


@click.command()
@click.option('--repo', '-r', help='Repository name (owner/repo)')
@click.option('--pr', '-p', type=int, help='Pull request number')
@click.option('--token', '-t', help='GitHub token (or set GITHUB_TOKEN env var)')
def main(repo: Optional[str], pr: Optional[int], token: Optional[str]):
    """Generate concise pull request descriptions using OpenAI"""
    
    # Get GitHub token
    github_token = token or os.getenv("GITHUB_TOKEN")
    if not github_token:
        console.print("[red]GitHub token required. Set GITHUB_TOKEN environment variable or use --token option.[/red]")
        return
    
    # Check OpenAI API key
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        console.print("[red]OpenAI API key required. Set OPENAI_API_KEY environment variable.[/red]")
        return
    
    # Initialize analyzer
    analyzer = GitHubPRAnalyzer(github_token)
    
    # Get repository name
    if not repo:
        repo = analyzer.get_repo_from_remote()
        if not repo:
            console.print("[red]Could not determine repository. Please specify with --repo option.[/red]")
            return
    
    console.print(f"[green]Analyzing repository: {repo}[/green]")
    
    # Get PR information
    pr_info = analyzer.get_pr_info(repo, pr)
    if not pr_info:
        return
    
    # Display current PR info
    console.print(Panel(
        f"[bold]PR Title:[/bold] {pr_info.title}\n"
        f"[bold]Branch:[/bold] {pr_info.branch} → {pr_info.base_branch}\n"
        f"[bold]Files Changed:[/bold] {len(pr_info.files_changed)}\n"
        f"[bold]Changes:[/bold] +{pr_info.additions} -{pr_info.deletions}",
        title="Current PR Information",
        border_style="blue"
    ))
    
    # Generate new description
    console.print("[yellow]Generating new PR description with OpenAI...[/yellow]")
    new_description = analyzer.generate_pr_description(pr_info)
    
    if not new_description:
        console.print("[red]Failed to generate description[/red]")
        return
    
    # Display new description
    console.print(Panel(
        Text(new_description, style="white"),
        title="Generated PR Description",
        border_style="green"
    ))

if __name__ == "__main__":
    main() # type: ignore
