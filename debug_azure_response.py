#!/usr/bin/env python3
"""
Debug script to see exactly what Azure OpenAI is returning
"""
import os
import asyncio
import json
from openai import AsyncAzureOpenAI

# Configuration from .env
AZURE_OPENAI_API_KEY = "77E50MKmkSJRfCB7ivtrQbDvU9Wn8wOuFMPuzsrxy5xWR9ROINv1JQQJ99BKACYeBjFXJ3w3AAABACOGDKMT"
AZURE_OPENAI_ENDPOINT = "https://protocol-talk.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o-deployment"

# Test paragraph
TEST_PARAGRAPH = """Subjects will be initially enrolled into the appropriate Group 1 subgroup based on their disease symptoms/status at enrollment."""

# Simple prompt that should find the "subjects" issue
SYSTEM_PROMPT = """You are an expert regulatory affairs consultant specializing in clinical protocol compliance with FDA and ICH-GCP guidelines.

Your task: Analyze protocol text for regulatory compliance issues and provide specific, actionable improvements."""

USER_PROMPT = f"""Analyze the following SELECTED PROTOCOL TEXT. Return strict JSON only (no extra prose) with "issues" array.

TEXT:
{TEST_PARAGRAPH}

CATEGORIES: statistical|analysis_population|terminology|documentation|regulatory|safety|other
SEVERITIES: critical|major|minor|advisory

RESPONSE FORMAT:
{{
  "issues": [
    {{
      "id": "1",
      "category": "terminology",
      "severity": "major",
      "original_text": "exact excerpt from text",
      "improved_text": "corrected version",
      "rationale": "explanation with regulatory reference",
      "recommendation": "actionable steps",
      "confidence": 0.95
    }}
  ]
}}

NOTE: "subjects" should be "participants" per FDA guidance. Look for this common issue."""


async def test_azure():
    print("=" * 60)
    print("TESTING AZURE OPENAI DIRECTLY")
    print("=" * 60)
    print(f"\nEndpoint: {AZURE_OPENAI_ENDPOINT}")
    print(f"Deployment: {AZURE_OPENAI_DEPLOYMENT}")
    print(f"API Version: 2024-08-01-preview")
    print(f"\nTest Text: {TEST_PARAGRAPH}")
    print("\n" + "=" * 60)

    client = AsyncAzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version="2024-08-01-preview",
        azure_endpoint=AZURE_OPENAI_ENDPOINT
    )

    try:
        response = await client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT}
            ],
            max_tokens=2000,
            temperature=0.2,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content

        print("\n✅ AZURE OPENAI RESPONSE:")
        print("=" * 60)
        print(content)
        print("=" * 60)

        # Parse and display
        parsed = json.loads(content)
        print("\n📊 PARSED JSON:")
        print(json.dumps(parsed, indent=2))

        issues_count = len(parsed.get("issues", []))
        print(f"\n🎯 ISSUES FOUND: {issues_count}")

        if issues_count == 0:
            print("\n⚠️  WARNING: Azure returned 0 issues!")
            print("This means the AI is not detecting the 'subjects' → 'participants' issue.")
            print("Possible causes:")
            print("  1. Prompt is too conservative")
            print("  2. Model temperature is too low (current: 0.2)")
            print("  3. Model deployment has content filtering enabled")
            print("  4. Need to be more explicit in prompt about what to look for")
        else:
            print("\n✅ SUCCESS: Azure is detecting issues correctly!")
            for idx, issue in enumerate(parsed.get("issues", []), 1):
                print(f"\nIssue {idx}:")
                print(f"  Category: {issue.get('category')}")
                print(f"  Severity: {issue.get('severity')}")
                print(f"  Original: {issue.get('original_text')}")
                print(f"  Improved: {issue.get('improved_text')}")
                print(f"  Rationale: {issue.get('rationale')}")

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_azure())
