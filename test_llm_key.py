# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, '.')

# Check if API key is available
api_key = os.getenv("ANTHROPIC_API_KEY")
print(f"API Key exists: {bool(api_key)}")
print(f"API Key length: {len(api_key) if api_key else 0}")

if api_key:
    import anthropic
    base_url = os.getenv("ANTHROPIC_BASE_URL")
    print(f"Base URL: {base_url}")

    try:
        client = anthropic.Anthropic(api_key=api_key, base_url=base_url)

        idea = "UK Biobank multi-omics causal graph neural network APOE dementia"
        prompt = f"""Translate this to PubMed search terms (English only, 3-5 keywords, space-separated):

{idea}

Return only the result, no explanation."""

        print("\nCalling Claude...")
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        result = message.content[0].text.strip()
        print(f"LLM Response: {result}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
else:
    print("No API key found - this is why keyword extraction is failing!")
