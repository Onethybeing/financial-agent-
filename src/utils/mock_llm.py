"""
Mock LLM for testing without API keys
"""
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from typing import List, Optional, Any
import random


class MockChatModel(BaseChatModel):
    """Mock LLM that generates realistic responses for loan application scenarios."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.conversation_count = {}  # Track conversation turns per session
    
    @property
    def _llm_type(self) -> str:
        return "mock"
    
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Generate mock response based on input."""
        
        # Get conversation context
        conversation_history = "\n".join([f"{msg.type}: {msg.content}" for msg in messages[-3:]])
        
        # Get the last user message
        user_message = str(messages[-1].content).lower() if messages else ""
        
        # Track conversation turns
        session_id = str(id(messages))
        if session_id not in self.conversation_count:
            self.conversation_count[session_id] = 0
        self.conversation_count[session_id] += 1
        turn = self.conversation_count[session_id]
        
        # Generate contextual response
        response = self._generate_contextual_response(user_message, conversation_history, turn)
        
        message = AIMessage(content=response)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])
    
    def _generate_contextual_response(self, user_message: str, conversation_history: str = "", turn: int = 1) -> str:
        """Generate contextual responses based on the user message and conversation history."""
        
        # Greeting responses (Turn 1-2)
        if turn <= 2 and any(word in user_message for word in ['hello', 'hi', 'hey', 'start']):
            return """Hello! Welcome to FinTech NBFC Personal Loan Services! 

I'm your AI loan assistant, here to help you get the best loan offer tailored to your needs.

To get started, could you please share:
1. Your name
2. Your contact number  
3. The loan amount you're looking for

I'll guide you through a quick and easy process!"""
        
        # After greeting, if user says anything generic
        if turn == 2 and not any(word in user_message for word in ['loan', 'lakh', 'thousand', 'rupees', 'money', 'borrow', 'name', 'am', 'need']):
            return """I'd be happy to help you! 

Are you looking to apply for a personal loan today? If so, please let me know:
- The loan amount you need (e.g., 5 lakhs, 3 lakhs, etc.)
- Any specific purpose for the loan (optional)

Or feel free to ask me any questions about our loan products!"""
        
        # Loan request responses (with amount extraction)
        if any(word in user_message for word in ['loan', 'lakh', 'thousand', 'rupees', 'money', 'borrow', 'need']):
            amount = self._extract_amount(user_message)
            
            if amount and amount >= 50000:
                return f"""Excellent! I can help you with a ₹{amount:,} personal loan.

Based on your requirement, I'll need to verify a few details:

**Step 1: Identity Verification**
- Your full name
- Your registered mobile number

**Step 2: Document Check**  
- PAN card for credit check
- Employment details

Let's start! May I have your full name please?"""
            else:
                return """I'd be happy to help you with a personal loan!

Could you please specify the loan amount you're looking for? For example:
- "I need 3 lakhs"
- "Looking for 5 lakh loan"
- "Need Rs 200000"

This will help me find the best offers for you!"""
        
        # Name/identity responses
        if any(word in user_message for word in ['my name is', 'i am', "i'm", 'this is']):
            return """Thank you for sharing your details!

To proceed, I'll need to verify your identity. Could you please provide:
- Your registered mobile number
- PAN card number (for verification)

This information is securely processed and protected."""
        
        # OTP/verification responses
        if any(char.isdigit() for char in user_message) and len(user_message) <= 10:
            if len([c for c in user_message if c.isdigit()]) == 6:
                return """✅ OTP verified successfully!

I'm now checking your credit profile and pre-approved loan offers...

Based on your credit score of 750, you're eligible for:
- Loan Amount: ₹3,00,000 to ₹5,00,000
- Interest Rate: 10.5% - 12.5% p.a.
- Tenure: 12 to 60 months

Would you like me to show you the best offers available?"""
            else:
                return """Thank you for providing your mobile number!

I've sent a 6-digit OTP to your registered mobile number. Please enter it here to verify your identity.

(For demo purposes, you can enter any 6-digit number like 123456)"""
        
        # Approval/agreement responses
        if any(word in user_message for word in ['yes', 'yeah', 'sure', 'okay', 'ok', 'proceed', 'continue']):
            return """Excellent! Let me fetch the best loan offers for you...

✨ **Top Offer for You:**
- Loan Amount: ₹4,00,000
- Interest Rate: 11.5% p.a.
- Processing Fee: ₹2,000 (0.5%)
- Monthly EMI: ₹8,774
- Tenure: 60 months

This offer comes with:
✓ No prepayment charges
✓ Quick disbursal (within 24 hours)
✓ Flexible repayment options

Would you like to proceed with this offer?"""
        
        # Document/upload responses
        if any(word in user_message for word in ['upload', 'document', 'salary', 'slip', 'proof', 'pan', 'aadhar']):
            return """Thank you for your willingness to provide documents!

For final approval, please upload:
📄 Last 3 months salary slips
📄 PAN card copy
📄 Aadhaar card copy

You can upload these documents, or I can proceed with the information available if you're pre-approved.

Shall I check your pre-approved status?"""
        
        # Rejection/negative responses
        if any(word in user_message for word in ['no', 'not', 'cancel', 'stop', 'don\'t want']):
            return """I understand. No problem at all!

Is there anything else I can help you with today? 

You can:
- Check different loan amounts
- Ask about interest rates
- Learn about our loan products
- Get information about eligibility criteria

How may I assist you?"""
        
        # Final/closing responses
        if any(word in user_message for word in ['thank', 'thanks', 'bye', 'goodbye']):
            return """You're welcome! It was my pleasure assisting you today.

📞 For any queries, call us at 1800-XXX-XXXX
✉️ Email: support@fintechnbfc.com
🌐 Visit: www.fintechnbfc.com

Have a great day! We look forward to serving you again! 🌟"""
        
        # Default intelligent response
        return self._generate_default_response()
    
    def _extract_amount(self, text: str) -> Optional[int]:
        """Extract loan amount from text."""
        import re
        
        # Pattern for amounts like "5 lakh", "500000", "5L", etc.
        patterns = [
            (r'(\d+\.?\d*)\s*(?:lakh|lakhs|lac|lacs)', 100000),
            (r'(\d+\.?\d*)\s*(?:l|L)\b', 100000),
            (r'(\d+\.?\d*)\s*(?:thousand|k|K)', 1000),
            (r'(\d{4,})', 1),
        ]
        
        for pattern, multiplier in patterns:
            match = re.search(pattern, text.lower())
            if match:
                amount = float(match.group(1)) * multiplier
                return int(amount)
        
        return None
    
    def _generate_default_response(self) -> str:
        """Generate a helpful default response."""
        responses = [
            """I'm here to help you with your personal loan needs!

Could you please tell me:
1. What loan amount are you looking for?
2. What's the purpose of the loan? (optional)
3. Your preferred repayment tenure?

This will help me find the best offers for you!""",
            
            """I'd be happy to assist you with your loan application!

To provide you with the most accurate information, could you please share more details about your requirement?

You can also ask me about:
- Loan eligibility criteria
- Interest rates
- EMI calculations
- Required documents""",
            
            """Thank you for reaching out!

I'm your personal loan assistant, ready to help you with:
✓ Instant loan offers
✓ Quick approval process
✓ Best interest rates
✓ Flexible repayment options

How can I assist you today?"""
        ]
        
        return random.choice(responses)
    
    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Async generate - just call sync version."""
        return self._generate(messages, stop, **kwargs)


def get_mock_llm(temperature: float = 0.7, **kwargs) -> MockChatModel:
    """Get a mock LLM instance for testing."""
    return MockChatModel()
