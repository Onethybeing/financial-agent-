# 🛠️ BFSI Agents - Setup & Deployment Guide

## ⚠️ Current Issue: API Key Configuration

The system requires a valid AI API key. We've identified the following issues:

### Problems Found:
1. **Google Gemini API** - Model name incompatibility with langchain_google_genai library
2. **OpenAI API** - Quota exceeded (insufficient credits)

---

## 🔧 Solution Options

### Option 1: Use OpenAI with Valid Credits (RECOMMENDED)

If you have OpenAI credits, update your `.env` file:

```bash
# Comment out Gemini
# GOOGLE_API_KEY=your_key_here

# Use OpenAI
OPENAI_API_KEY=your_valid_openai_key_here
OPENAI_MODEL=gpt-3.5-turbo  # Cheaper and faster than GPT-4
```

**Get OpenAI API Key:**
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Add credits to your account at https://platform.openai.com/account/billing

---

### Option 2: Use Google Gemini (FREE - But Needs API Fix)

The Gemini API requires using the correct SDK. Update your env:

```bash
# Use Google Gemini
GOOGLE_API_KEY=AIzaSyDnw9bPhtcmiGo1avg3FpWHNzsMzGgvWUs
GOOGLE_MODEL=models/gemini-pro  # Note: models/ prefix might be needed
```

**Get Gemini API Key:**
1. Go to https://makersuite.google.com/app/apikey
2. Create a new API key
3. It's FREE with generous quotas!

---

### Option 3: Use Anthropic Claude

Update your `.env`:

```bash
#GOOGLE_API_KEY=...
#OPENAI_API_KEY=...

ANTHROPIC_API_KEY=your_anthropic_key_here
ANTHROPIC_MODEL=claude-3-sonnet-20240229
```

**Get Anthropic API Key:**
1. Go to https://console.anthropic.com/
2. Sign up and get API key
3. Add credits

---

### Option 4: Use Groq (FREE & FAST) ⚡

Groq offers free, super-fast LLM API. Requires code modification:

1. Get API key from https://console.groq.com/
2. Install: `pip install langchain-groq`
3. Update `src/utils/llm_config.py` to add Groq support

---

##  📋 Quick Start Steps

### Step 1: Fix API Key

**Edit `.env` file:**

```powershell
notepad .env
```

Choose ONE of the following:

**For OpenAI (if you have credits):**
```
OPENAI_API_KEY=sk-your-actual-key-here
OPENAI_MODEL=gpt-3.5-turbo
```

**For Gemini (FREE):**
```
GOOGLE_API_KEY=your-gemini-key-here  
GOOGLE_MODEL=gemini-pro
```

**Comment out the others** by adding `#` at the start of their lines.

---

### Step 2: Start the Services

**Terminal 1 - API Services:**
```powershell
cd "c:\Users\soura\financial agent\BFSI_Agents"
$env:PYTHONPATH="."
python src/api/mock_services.py
```

**Terminal 2 - Streamlit UI:**
```powershell
cd "c:\Users\soura\financial agent\BFSI_Agents"
$env:PYTHONPATH="."
python -m streamlit run src/ui/chatbot_app.py
```

---

### Step 3: Access the Application

1. Open browser: **http://localhost:8501**
2. Select a demo customer from sidebar
3. Click "Start New Session"
4. Start chatting!

---

## 🧪 Test Without UI (Verify API Works)

Create a test file `test_api.py`:

```python
from dotenv import load_dotenv
load_dotenv()

from src.utils.llm_config import get_llm

try:
    llm = get_llm()
    response = llm.invoke("Hello! Say 'Hi' back.")
    print(f"✅ Success! Response: {response.content}")
except Exception as e:
    print(f"❌ Error: {e}")
```

Run it:
```powershell
python test_api.py
```

---

## 🎯 Recommended: Get a Free Gemini API Key

**This is the best free option:**

1. Go to: https://makersuite.google.com/app/apikey
2. Click "Create API Key"
3. Copy the key
4. Update `.env`:
   ```
   GOOGLE_API_KEY=your_new_gemini_key_here
   GOOGLE_MODEL=gemini-pro
   ```
5. Restart the services

---

## 🔍 Debugging Tips

### Check which API is being used:
```powershell
python -c "from dotenv import load_dotenv; load_dotenv(); from src.utils.llm_config import get_available_providers; print(get_available_providers())"
```

### Test API directly:
```powershell
python -c "from dotenv import load_dotenv; load_dotenv(); from src.utils.llm_config import get_llm; llm = get_llm(); print(llm.invoke('test').content)"
```

---

## 📝 What Works Currently

✅ **FastAPI Services** - Running perfectly on port 8000  
✅ **All 5 AI Agents** - Configured and ready  
✅ **Dependencies** - All installed  
✅ **Database & Tools** - Fully functional  
✅ **Streamlit UI** - Loads correctly  

❌ **AI API Key** - Needs valid credentials  

---

## 💡 Alternative: Use Local LLM (Advanced)

If you want to avoid API costs entirely:

1. Install Ollama: https://ollama.ai/
2. Run: `ollama run llama2`
3. Update code to use Ollama endpoint

---

## 🆘 Still Having Issues?

**Quick fixes:**

1. **Restart everything:**
   ```powershell
   taskkill /F /IM python.exe
   # Then restart services
   ```

2. **Clear Streamlit cache:**
   ```powershell
   streamlit cache clear
   ```

3. **Reinstall dependencies:**
   ```powershell
   pip install --force-reinstall langchain-openai langchain-google-genai
   ```

---

## 📊 Cost Comparison

| Provider | Cost | Speed | Quota |
|----------|------|-------|-------|
| **Gemini** | FREE | Fast | Generous |
| **OpenAI GPT-3.5** | $0.002/1K tokens | Fast | Pay-as-you-go |
| **OpenAI GPT-4** | $0.03/1K tokens | Slower | Pay-as-you-go |
| **Claude** | $0.015/1K tokens | Medium | Pay-as-you-go |
| **Groq** | FREE | Very Fast | Limited |

---

## ✅ Next Steps

1. **Get a valid API key** (Gemini recommended - it's free!)
2. **Update `.env` file**
3. **Restart services**
4. **Test the application**

Once you have a valid API key configured, the entire system will work perfectly!

---

## 📲 Enable Twilio OTP (SMS)

To send and verify OTPs via SMS using Twilio Verify, set these environment variables (in your `.env` file or system environment):

```ini
# Twilio Verify
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_VERIFY_SERVICE_SID=VAXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Then restart Streamlit. In the Verification panel, you'll see:

- "OTP Provider: Twilio Verify (SMS)" when configured
- Otherwise a demo fallback where the OTP appears in the chat (no SMS)

Notes:
- Phone numbers must be in E.164 format (e.g., +14155552671). If you enter a 10‑digit Indian number, the app will automatically prefix +91.
- Install the SDK if needed:
   ```powershell
   pip install --user twilio==9.3.1
   ```

Troubleshooting:
- Check if the app detects Twilio: `python -c "from src.tools.otp_tools import is_twilio_configured; print(is_twilio_configured())"`
- Verify your Verify Service SID is for the Verify product (starts with VA...)
- Ensure your Twilio number and geo permissions allow SMS to your destination

---

*Last Updated: October 27, 2025*
