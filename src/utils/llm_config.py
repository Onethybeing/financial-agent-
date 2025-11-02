"""
LLM Configuration Utility
Supports both OpenAI and Google Gemini models
"""
import os
from typing import Optional

def get_llm(temperature: float = 0.7, model: Optional[str] = None):
    """
    Get configured LLM instance based on available API keys
    
    Priority:
    1. Google Gemini (if GOOGLE_API_KEY is set)
    2. OpenAI GPT-4 (if OPENAI_API_KEY is set)
    3. Anthropic Claude (if ANTHROPIC_API_KEY is set)
    
    Args:
        temperature: Model temperature (0.0-1.0)
        model: Optional specific model name to override defaults
    
    Returns:
        Configured LLM instance
    """
    
    # Try Google Gemini first
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if google_api_key and google_api_key != "your_google_api_key_here":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            
            model_name = model or os.getenv("GOOGLE_MODEL", "gemini-pro")
            print(f"[OK] Using Google Gemini: {model_name}")
            
            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=temperature,
                google_api_key=google_api_key,
                convert_system_message_to_human=True  # Gemini doesn't support system messages directly
            )
        except ImportError:
            print("[WARN] Google Gemini packages not installed, trying OpenAI...")
        except Exception as e:
            print(f"[WARN] Error initializing Google Gemini: {e}, trying OpenAI...")
    
    # Try OpenAI GPT-4
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if openai_api_key and openai_api_key != "your_openai_api_key_here":
        try:
            from langchain_openai import ChatOpenAI
            
            model_name = model or os.getenv("OPENAI_MODEL", "gpt-4")
            print(f"[OK] Using OpenAI: {model_name}")
            
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                openai_api_key=openai_api_key
            )
        except ImportError:
            print("[WARN] OpenAI packages not installed, trying Anthropic...")
        except Exception as e:
            print(f"[WARN] Error initializing OpenAI: {e}, trying Anthropic...")
    
    # Try Anthropic Claude
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_api_key and anthropic_api_key != "your_anthropic_api_key_here":
        try:
            from langchain_anthropic import ChatAnthropic
            
            model_name = model or os.getenv("ANTHROPIC_MODEL", "claude-3-sonnet-20240229")
            print(f"[OK] Using Anthropic Claude: {model_name}")
            
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                anthropic_api_key=anthropic_api_key
            )
        except ImportError:
            print("[WARN] Anthropic packages not installed")
        except Exception as e:
            print(f"[WARN] Error initializing Anthropic: {e}")
    
    # No valid API key found - use mock LLM for testing
    print("[WARN] No valid API key found. Using Mock LLM for testing...")
    print("[INFO] For production, please set one of:")
    print("   - GOOGLE_API_KEY (for Google Gemini)")
    print("   - OPENAI_API_KEY (for OpenAI GPT-4)")
    print("   - ANTHROPIC_API_KEY (for Anthropic Claude)")
    
    from src.utils.mock_llm import get_mock_llm
    return get_mock_llm(temperature=temperature)


def get_available_providers():
    """Get list of available LLM providers based on configured API keys"""
    providers = []
    
    if os.getenv("GOOGLE_API_KEY") and os.getenv("GOOGLE_API_KEY") != "your_google_api_key_here":
        providers.append("Google Gemini")
    
    if os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_API_KEY") != "your_openai_api_key_here":
        providers.append("OpenAI GPT-4")
    
    if os.getenv("ANTHROPIC_API_KEY") and os.getenv("ANTHROPIC_API_KEY") != "your_anthropic_api_key_here":
        providers.append("Anthropic Claude")
    
    return providers
