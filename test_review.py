#!/usr/bin/env python3
"""
Test script for the PR review functionality
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_imports():
    """Test that all required modules can be imported"""
    try:
        from review_code import GitHubPRReviewer, ReviewReporter, CodeIssue, ReviewResult
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_environment():
    """Test that required environment variables are set"""
    required_vars = ["GITHUB_TOKEN", "OPENAI_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        return False
    else:
        print("✅ All environment variables are set")
        return True

def test_github_connection():
    """Test GitHub API connection"""
    try:
        from github import Github
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            print("❌ GITHUB_TOKEN not set")
            return False
        
        github = Github(token)
        # Try to get the authenticated user
        user = github.get_user()
        print(f"✅ GitHub connection successful - authenticated as: {user.login}")
        return True
    except Exception as e:
        print(f"❌ GitHub connection failed: {e}")
        return False

def test_openai_connection():
    """Test OpenAI API connection"""
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY not set")
            return False
        
        client = OpenAI(api_key=api_key)
        # Try a simple test call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'Hello, World!'"}],
            max_tokens=10
        )
        print("✅ OpenAI connection successful")
        return True
    except Exception as e:
        print(f"❌ OpenAI connection failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing PR Review Tool Setup\n")
    
    tests = [
        ("Module Imports", test_imports),
        ("Environment Variables", test_environment),
        ("GitHub Connection", test_github_connection),
        ("OpenAI Connection", test_openai_connection),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Testing {test_name}...")
        if test_func():
            passed += 1
        print()
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The PR review tool is ready to use.")
        print("\nExample usage:")
        print("  python review_code.py --repo owner/repo --pr 123")
        print("  pr-review --repo owner/repo --pr 123")
    else:
        print("❌ Some tests failed. Please fix the issues above before using the tool.")
        sys.exit(1)

if __name__ == "__main__":
    main() 