"""
Master Agent - Conversational Orchestrator
"""
from typing import Dict, Any, Optional
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from src.workflow.state import LoanApplicationState, get_conversation_context, add_message
from src.tools.crm_tools import get_customer_by_id, get_customer_context
from src.utils.llm_config import get_llm


class MasterAgent:
    """
    Master Agent that manages conversation flow and delegates to worker agents.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        self.llm = get_llm(temperature=0.7, model=model_name)
        self.system_prompt = self._create_system_prompt()
    
    def _create_system_prompt(self) -> str:
        return """You are a friendly and professional banking assistant helping customers with personal loans.

Your role is to:
1. Welcome customers warmly and build trust
2. Understand their financial needs through empathetic conversation
3. Guide them through the loan application process
4. Coordinate with specialized agents for specific tasks
5. Handle objections professionally
6. Provide clear, transparent communication

Communication Style:
- Be warm, friendly, and professional
- Use simple language, avoid jargon
- Show empathy and understanding
- Be transparent about process and requirements
- Build trust through honest communication

Process Stages:
- GREETING: Welcome customer, establish rapport
- NEEDS_ASSESSMENT: Understand loan requirements and purpose
- SALES_NEGOTIATION: Delegate to Sales Agent for offers
- VERIFICATION: Delegate to Verification Agent for KYC
- UNDERWRITING: Delegate to Underwriting Agent for credit check
- SANCTION_GENERATION: Delegate to Sanction Agent for final letter
- CLOSURE: Thank customer and provide next steps

Remember: You are the primary interface. Keep conversation natural and guide the customer smoothly through the process."""
    
    def process_message(
        self,
        state: LoanApplicationState,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Process user message and determine next action.
        
        Args:
            state: Current application state
            user_message: User's message
            
        Returns:
            Updated state and response
        """
        # Get conversation context
        conversation_context = get_conversation_context(state, last_n=5)
        
        # Get customer context if available
        customer_context = ""
        if state.get("customer_id"):
            customer_context = get_customer_context(state["customer_id"])
        
        # Determine current stage and appropriate response
        current_stage = state.get("current_stage", "greeting")
        
        # Build prompt based on stage
        prompt = self._build_prompt(
            current_stage=current_stage,
            user_message=user_message,
            conversation_context=conversation_context,
            customer_context=customer_context,
            state=state
        )
        
        # Get response from LLM
        response = self.llm.invoke(prompt)
        response_text = response.content
        
        # Determine next action and stage transition
        next_action, new_stage = self._determine_next_action(
            current_stage=current_stage,
            user_message=user_message,
            response=response_text,
            state=state
        )
        
        return {
            "response": response_text,
            "next_action": next_action,
            "new_stage": new_stage
        }
    
    def _build_prompt(
        self,
        current_stage: str,
        user_message: str,
        conversation_context: str,
        customer_context: str,
        state: LoanApplicationState
    ) -> str:
        """Build context-aware prompt for the LLM."""
        
        stage_instructions = {
            "greeting": """
The customer just initiated contact. Welcome them warmly and ask how you can help with their loan needs.
Be friendly and establish a comfortable atmosphere.
""",
            "needs_assessment": """
The customer is interested in a loan. Ask questions to understand:
- How much loan amount they need
- Purpose of the loan
- Preferred tenure
- Any specific concerns or requirements

Keep it conversational, don't interrogate. Show genuine interest in helping.
""",
            "sales_negotiation": """
We have loan offers ready. The Sales Agent will handle the detailed negotiation.
For now, let the customer know you're preparing personalized offers and will share them shortly.
""",
            "verification": """
Loan terms are agreed. Explain that you need to verify their details for security.
The Verification Agent will handle the KYC process. Prepare the customer for identity verification.
""",
            "underwriting": """
Verification complete. Explain that you're now assessing their application for final approval.
The Underwriting Agent is reviewing their credit profile. This should be quick.
""",
            "document_upload": """
Additional documents needed. Guide the customer on uploading their salary slip.
Explain why it's needed and assure them it's secure and confidential.
""",
            "sanction_generation": """
Congratulations! The loan is approved. The Sanction Letter Generator is preparing their official sanction letter.
Let them know they'll receive it shortly.
""",
            "closure": """
Process complete. Thank the customer for their trust.
Provide clear next steps and contact information for any questions.
"""
        }
        
        instruction = stage_instructions.get(current_stage, "")
        
        prompt = f"""{self.system_prompt}

CURRENT STAGE: {current_stage}
{instruction}

CUSTOMER INFORMATION:
{customer_context if customer_context else "No customer information available yet"}

CONVERSATION HISTORY:
{conversation_context}

CUSTOMER'S MESSAGE: {user_message}

Respond naturally and appropriately for the current stage. If you need to delegate to a specialized agent, indicate that in your response and I'll coordinate."""
        
        return prompt
    
    def _determine_next_action(
        self,
        current_stage: str,
        user_message: str,
        response: str,
        state: LoanApplicationState
    ) -> tuple[Optional[str], str]:
        """
        Determine what action to take next based on conversation.
        
        Returns:
            (next_action, new_stage) tuple
        """
        user_message_lower = user_message.lower()
        
        # Stage transitions based on keywords and state
        if current_stage == "greeting":
            # If amount is already known from UI parsing, go straight to Sales (no need to wait for keywords)
            if state.get("requested_amount"):
                return ("delegate_to_sales", "sales_negotiation")
            
            # Try to detect amount directly from message even without loan keywords
            import re
            amt = None
            patterns = [
                (r"(\d+\.?\d*)\s*(?:lakh|lakhs|lac|lacs)", 100000),
                (r"(\d+\.?\d*)\s*(?:l|L)", 100000),
                (r"(\d+\.?\d*)\s*(?:thousand|k|K)", 1000),
                (r"(\d{4,})", 1),
            ]
            for pattern, mult in patterns:
                m = re.search(pattern, user_message_lower)
                if m:
                    try:
                        amt = float(m.group(1)) * mult
                    except Exception:
                        amt = None
                    break
            if amt:
                state["requested_amount"] = amt  # hint for downstream
                return ("delegate_to_sales", "sales_negotiation")

            # If user mentions loan intent, move to needs assessment
            if any(word in user_message_lower for word in ["loan", "money", "borrow", "need", "want"]):
                return (None, "needs_assessment")
            return (None, "greeting")
        
        elif current_stage == "needs_assessment":
            # Check if customer has mentioned amount
            if state.get("requested_amount"):
                return ("delegate_to_sales", "sales_negotiation")
            # Check for amount in message
            import re
            amount_match = re.search(r'(\d+)\s*(lakh|lakhs|thousand|k|lac)', user_message_lower)
            if amount_match:
                return ("delegate_to_sales", "sales_negotiation")
            return (None, "needs_assessment")
        
        elif current_stage == "sales_negotiation":
            # Detect acceptance/selection -> move to verification
            accept_terms = [
                "proceed", "go ahead", "accept", "let's go", "lets go",
                "confirm", "finalize", "book", "i agree", "looks good"
            ]
            if any(p in user_message_lower for p in accept_terms):
                return ("delegate_to_verification", "verification")

            # Detect explicit option selection or tenure keywords
            import re
            if re.search(r"option\s*[1-9]", user_message_lower) or re.search(r"\b(\d+)\s*(year|years|yr|yrs|month|months)\b", user_message_lower):
                return ("delegate_to_sales", "sales_negotiation")

            # Detect negotiation intent (rate/emi/discount/% mentions)
            negotiation_cues = [
                "rate", "reduce", "discount", "lower", "cheaper", "negotiate", "negotiation", "emi"
            ]
            if any(k in user_message_lower for k in negotiation_cues) or re.search(r"\d+\s*%", user_message_lower):
                return ("delegate_to_sales", "sales_negotiation")

            return (None, "sales_negotiation")
        
        elif current_stage == "verification":
            # Route to verification worker on explicit triggers
            # 1) If user asks to send OTP
            if any(kw in user_message_lower for kw in ["send otp", "otp", "resend otp", "send the otp"]):
                return ("delegate_to_verification", "verification")
            # 2) If user provides a 4-6 digit code and otp was sent
            import re
            if state.get("otp_sent"):
                if re.search(r"\b\d{4,6}\b", user_message_lower):
                    return ("delegate_to_verification", "verification")
            # If verification complete, move to underwriting
            if state.get("kyc_verified") and state.get("phone_verified"):
                return ("delegate_to_underwriting", "underwriting")
            return (None, "verification")
        
        elif current_stage == "underwriting":
            decision = state.get("underwriting_decision")
            if decision == "needs_documents":
                return (None, "document_upload")
            elif decision == "approved":
                return ("delegate_to_sanction", "sanction_generation")
            elif decision == "rejected":
                return (None, "closure")
            return (None, "underwriting")
        
        elif current_stage == "document_upload":
            if state.get("salary_slip_uploaded"):
                return ("delegate_to_underwriting", "underwriting")
            return (None, "document_upload")
        
        elif current_stage == "sanction_generation":
            if state.get("sanction_letter_url"):
                return (None, "closure")
            return (None, "sanction_generation")
        
        elif current_stage == "closure":
            return (None, "closure")
        
        return (None, current_stage)
    
    def generate_greeting(self, customer_name: Optional[str] = None) -> str:
        """Generate a warm greeting message."""
        if customer_name:
            return f"""Hello {customer_name}! 👋

Welcome to FinTech NBFC - your trusted partner for personal loans.

I'm here to help you with quick and easy loan approval. Whether you need funds for a wedding, education, medical emergency, or any personal need, I can assist you.

How can I help you today?"""
        else:
            return """Hello! 👋 Welcome to FinTech NBFC!

I'm your personal loan assistant. I'm here to help you get the funds you need with:
✓ Quick approval process
✓ Competitive interest rates  
✓ Flexible repayment options
✓ Minimal documentation

May I know your name to get started?"""


def create_master_agent() -> MasterAgent:
    """Factory function to create Master Agent instance."""
    return MasterAgent()
