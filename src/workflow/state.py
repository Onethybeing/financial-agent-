"""
LangGraph State Schema for Loan Application Workflow
"""
from typing import TypedDict, Literal, Optional, List, Dict, Any
from datetime import datetime


class LoanApplicationState(TypedDict):
    """
    Centralized state for the loan application workflow.
    All agents read from and write to this shared state.
    """
    
    # Customer Information
    customer_id: Optional[str]
    customer_name: Optional[str]
    customer_phone: Optional[str]
    customer_email: Optional[str]
    customer_address: Optional[str]
    conversation_history: List[Dict[str, str]]  # [{"role": "user/assistant", "content": "..."}]
    
    # Conversation Flow
    current_stage: Literal[
        "greeting",
        "needs_assessment",
        "sales_negotiation",
        "verification",
        "underwriting",
        "document_upload",
        "sanction_generation",
        "closure"
    ]
    active_agent: Literal["master", "sales", "verification", "underwriting", "sanction"]
    next_action: Optional[str]  # Instructions for next agent
    
    # Loan Parameters
    requested_amount: Optional[float]
    approved_amount: Optional[float]
    tenure_months: Optional[int]
    interest_rate: Optional[float]
    monthly_emi: Optional[float]
    loan_purpose: Optional[str]
    
    # Sales Data
    customer_needs: Optional[str]
    objections_raised: List[str]
    negotiation_history: List[Dict[str, Any]]
    recommended_offers: List[Dict[str, Any]]
    selected_offer: Optional[Dict[str, Any]]
    
    # Verification Data
    kyc_verified: bool
    kyc_pan: Optional[str]
    kyc_aadhaar_last4: Optional[str]
    kyc_dob: Optional[str]
    kyc_email: Optional[str]
    alt_phone: Optional[str]
    phone_verified: bool
    address_verified: bool
    otp_sent: bool
    otp_attempts: int
    otp_provider: Optional[str]
    verification_notes: Optional[str]
    id_document_front_url: Optional[str]
    id_document_back_url: Optional[str]
    otp_code: Optional[str]
    otp_phone: Optional[str]
    otp_resend_count: int
    
    # Underwriting Data
    credit_score: Optional[int]
    pre_approved_limit: Optional[float]
    salary_slip_uploaded: bool
    salary_slip_url: Optional[str]
    monthly_salary: Optional[float]
    debt_to_income_ratio: Optional[float]
    existing_emi_total: Optional[float]
    total_monthly_obligation: Optional[float]
    emi_to_income_ratio: Optional[float]
    risk_score: Optional[float]
    underwriting_decision: Optional[Literal["approved", "rejected", "needs_documents", "pending"]]
    rejection_reason: Optional[str]
    conditional_requirements: List[str]
    underwriting_recommendations: List[str]
    
    # Final Output
    sanction_letter_url: Optional[str]
    sanction_letter_ref_no: Optional[str]
    application_status: Literal["in_progress", "approved", "rejected", "abandoned"]
    
    # Metadata
    session_id: str
    created_at: str
    updated_at: str
    total_interactions: int
    
    # Error Handling
    error_count: int
    last_error: Optional[str]


class ConversationMessage(TypedDict):
    """Structure for conversation history messages"""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str
    agent: Optional[str]  # Which agent generated this message


class LoanOffer(TypedDict):
    """Structure for loan offer recommendations"""
    amount: float
    tenure_months: int
    interest_rate: float
    monthly_emi: float
    processing_fee: float
    total_interest: float
    total_payable: float


class UnderwritingResult(TypedDict):
    """Result from underwriting evaluation"""
    decision: Literal["approved", "rejected", "needs_documents"]
    approved_amount: Optional[float]
    interest_rate: Optional[float]
    tenure_months: Optional[int]
    conditions: List[str]
    reason: Optional[str]
    risk_score: Optional[float]


def create_initial_state(customer_id: Optional[str] = None) -> LoanApplicationState:
    """
    Create initial state for a new loan application session.
    
    Args:
        customer_id: Optional customer ID if known upfront
        
    Returns:
        Initialized LoanApplicationState
    """
    import uuid
    from datetime import datetime
    
    return LoanApplicationState(
        # Customer Information
        customer_id=customer_id,
        customer_name=None,
        customer_phone=None,
        customer_email=None,
        customer_address=None,
        conversation_history=[],
        
        # Conversation Flow
        current_stage="greeting",
        active_agent="master",
        next_action=None,
        
        # Loan Parameters
        requested_amount=None,
        approved_amount=None,
        tenure_months=None,
        interest_rate=None,
        monthly_emi=None,
        loan_purpose=None,
        
        # Sales Data
        customer_needs=None,
        objections_raised=[],
        negotiation_history=[],
    recommended_offers=[],
    selected_offer=None,
        
        # Verification Data
        kyc_verified=False,
    kyc_pan=None,
    kyc_aadhaar_last4=None,
    kyc_dob=None,
    kyc_email=None,
    alt_phone=None,
        phone_verified=False,
        address_verified=False,
        otp_sent=False,
        otp_attempts=0,
    otp_provider=None,
    otp_code=None,
    otp_phone=None,
    otp_resend_count=0,
    verification_notes=None,
    id_document_front_url=None,
    id_document_back_url=None,
        
        # Underwriting Data
        credit_score=None,
        pre_approved_limit=None,
        salary_slip_uploaded=False,
        salary_slip_url=None,
        monthly_salary=None,
        debt_to_income_ratio=None,
    existing_emi_total=None,
    total_monthly_obligation=None,
    emi_to_income_ratio=None,
    risk_score=None,
        underwriting_decision="pending",
        rejection_reason=None,
    conditional_requirements=[],
    underwriting_recommendations=[],
        
        # Final Output
        sanction_letter_url=None,
        sanction_letter_ref_no=None,
        application_status="in_progress",
        
        # Metadata
        session_id=str(uuid.uuid4()),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        total_interactions=0,
        
        # Error Handling
        error_count=0,
        last_error=None
    )


def update_state(
    state: LoanApplicationState,
    updates: Dict[str, Any]
) -> LoanApplicationState:
    """
    Update state with new values and refresh metadata.
    
    Args:
        state: Current state
        updates: Dictionary of fields to update
        
    Returns:
        Updated state
    """
    from datetime import datetime
    
    # Create a new state dict with updates
    new_state = {**state, **updates}
    
    # Always update the timestamp
    new_state["updated_at"] = datetime.now().isoformat()
    
    return LoanApplicationState(**new_state)


def add_message(
    state: LoanApplicationState,
    role: Literal["user", "assistant", "system"],
    content: str,
    agent: Optional[str] = None
) -> LoanApplicationState:
    """
    Add a new message to conversation history.
    
    Args:
        state: Current state
        role: Role of the message sender
        content: Message content
        agent: Optional agent name that generated the message
        
    Returns:
        Updated state with new message
    """
    from datetime import datetime
    
    message = ConversationMessage(
        role=role,
        content=content,
        timestamp=datetime.now().isoformat(),
        agent=agent
    )
    
    conversation_history = state["conversation_history"].copy()
    conversation_history.append(message)
    
    return update_state(state, {
        "conversation_history": conversation_history,
        "total_interactions": state["total_interactions"] + 1
    })


def get_conversation_context(
    state: LoanApplicationState,
    last_n: int = 5
) -> str:
    """
    Get formatted conversation context for agent prompts.
    
    Args:
        state: Current state
        last_n: Number of recent messages to include
        
    Returns:
        Formatted conversation history string
    """
    history = state["conversation_history"][-last_n:] if last_n else state["conversation_history"]
    
    formatted = []
    for msg in history:
        role_label = "Customer" if msg["role"] == "user" else "Assistant"
        formatted.append(f"{role_label}: {msg['content']}")
    
    return "\n".join(formatted) if formatted else "No previous conversation"
