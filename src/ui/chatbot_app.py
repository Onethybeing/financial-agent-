"""
Streamlit Chatbot Interface for Loan Application
"""
import streamlit as st
import os
import sys
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.workflow.graph import create_loan_workflow
from src.utils.llm_config import get_available_providers
from src.workflow.state import create_initial_state
from src.tools.crm_tools import get_customer_by_id
from src.tools.otp_tools import is_twilio_configured
from src.tools.document_tools import save_uploaded_document
from src.agents.underwriting_agent import create_underwriting_agent
import re


# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="FinTech NBFC - Personal Loan Assistant",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1e3a8a;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #4b5563;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stage-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 0.5rem;
        font-weight: bold;
        font-size: 0.875rem;
    }
    .stage-greeting {
        background-color: #dbeafe;
        color: #1e40af;
    }
    .stage-needs {
        background-color: #fef3c7;
        color: #92400e;
    }
    .stage-sales {
        background-color: #d1fae5;
        color: #065f46;
    }
    .stage-verification {
        background-color: #e0e7ff;
        color: #3730a3;
    }
    .stage-underwriting {
        background-color: #fce7f3;
        color: #831843;
    }
    .stage-sanction {
        background-color: #d1fae5;
        color: #065f46;
    }
    .stage-closure {
        background-color: #f3f4f6;
        color: #374151;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #dbeafe;
        margin-left: 2rem;
    }
    .assistant-message {
        background-color: #f3f4f6;
        margin-right: 2rem;
    }
    .agent-badge {
        display: inline-block;
        padding: 0.15rem 0.5rem;
        margin-left: 0.5rem;
        border-radius: 0.4rem;
        font-size: 0.75rem;
        font-weight: 600;
        background-color: #e5e7eb;
        color: #374151;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================

def initialize_session():
    """Initialize session state variables."""
    if 'workflow' not in st.session_state:
        st.session_state.workflow = create_loan_workflow()
    
    if 'session_id' not in st.session_state:
        st.session_state.session_id = None
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if 'current_stage' not in st.session_state:
        st.session_state.current_stage = 'greeting'
    
    if 'customer_id' not in st.session_state:
        st.session_state.customer_id = None
    
    if 'application_status' not in st.session_state:
        st.session_state.application_status = 'in_progress'


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_customer_id(message: str) -> str:
    """Extract customer ID from message."""
    # Look for patterns like CUST001, CUST002, etc.
    match = re.search(r'CUST\d+', message.upper())
    if match:
        return match.group(0)
    return None


def extract_amount(message: str) -> float:
    """Extract loan amount from message."""
    message_lower = message.lower()
    
    # Pattern for amounts like "5 lakh", "500000", "5L", etc.
    patterns = [
        (r'(\d+\.?\d*)\s*(?:lakh|lakhs|lac|lacs)', 100000),
        (r'(\d+\.?\d*)\s*(?:l|L)', 100000),
        (r'(\d+\.?\d*)\s*(?:thousand|k|K)', 1000),
        (r'(\d{4,})', 1),
    ]
    
    for pattern, multiplier in patterns:
        match = re.search(pattern, message_lower)
        if match:
            amount = float(match.group(1)) * multiplier
            return amount
    
    return None


def get_stage_badge(stage: str) -> str:
    """Get HTML badge for current stage."""
    stage_labels = {
        'greeting': ('👋 Greeting', 'stage-greeting'),
        'needs_assessment': ('📋 Needs Assessment', 'stage-needs'),
        'sales_negotiation': ('💰 Sales Negotiation', 'stage-sales'),
        'verification': ('✅ Verification', 'stage-verification'),
        'underwriting': ('📊 Underwriting', 'stage-underwriting'),
        'document_upload': ('📄 Document Upload', 'stage-underwriting'),
        'sanction_generation': ('📝 Sanction Letter', 'stage-sanction'),
        'closure': ('🎉 Closure', 'stage-closure')
    }
    
    label, css_class = stage_labels.get(stage, ('⏳ Processing', 'stage-greeting'))
    return f'<span class="stage-badge {css_class}">{label}</span>'


def display_progress_indicator(stage: str):
    """Display progress indicator."""
    stages = [
        ('Greeting', 'greeting'),
        ('Assessment', 'needs_assessment'),
        ('Sales', 'sales_negotiation'),
        ('Verification', 'verification'),
        ('Underwriting', 'underwriting'),
        ('Sanction', 'sanction_generation'),
        ('Closure', 'closure')
    ]
    
    current_index = next((i for i, (_, s) in enumerate(stages) if s == stage), 0)
    
    cols = st.columns(len(stages))
    for i, (label, _) in enumerate(stages):
        with cols[i]:
            if i < current_index:
                st.markdown(f"✅ **{label}**")
            elif i == current_index:
                st.markdown(f"🔄 **{label}**")
            else:
                st.markdown(f"⭕ {label}")


# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application."""
    initialize_session()
    
    # Header
    st.markdown('<div class="main-header">💰 FinTech NBFC</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Personal Loan Assistant - AI-Powered Instant Approval</div>', unsafe_allow_html=True)
    
    # LLM status banner (visible so we know we are using Gemini and not mock)
    providers = get_available_providers()
    llm_provider = providers[0] if providers else "Mock (no API key)"
    model_hint = os.getenv("GOOGLE_MODEL") if llm_provider.startswith("Google") else os.getenv("OPENAI_MODEL") or os.getenv("ANTHROPIC_MODEL")
    status_msg = f"LLM: {llm_provider}" + (f" — model: {model_hint}" if model_hint else "")
    st.caption(status_msg)
    
    # Sidebar
    with st.sidebar:
        st.header("🎯 Application Status")
        
        # Customer selector for demo
        st.subheader("Demo: Select Customer")
        demo_customers = [
            ("New Customer", None),
            ("CUST001 - Rajesh Kumar (Easy Approval)", "CUST001"),
            ("CUST002 - Priya Sharma (Conditional)", "CUST002"),
            ("CUST003 - Amit Patel (Rejection)", "CUST003"),
        ]
        
        selected = st.selectbox(
            "Choose a customer profile:",
            options=[c[0] for c in demo_customers]
        )
        
        selected_customer_id = next((c[1] for c in demo_customers if c[0] == selected), None)
        
        if st.button("Start New Session"):
            st.session_state.session_id = st.session_state.workflow.create_session(selected_customer_id)
            st.session_state.messages = []
            st.session_state.current_stage = 'greeting'
            st.session_state.customer_id = selected_customer_id
            
            # Get initial greeting
            state = st.session_state.workflow.get_session_state(st.session_state.session_id)
            if state and state["conversation_history"]:
                greeting_msg = state["conversation_history"][0]
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": greeting_msg["content"],
                    "agent": greeting_msg.get("agent", "master")
                })
            
            st.rerun()
        
        st.divider()
        
        # Display current status
        if st.session_state.session_id:
            state = st.session_state.workflow.get_session_state(st.session_state.session_id)
            
            if state:
                st.metric("Session ID", st.session_state.session_id[:8] + "...")
                st.metric("Current Stage", state.get("current_stage", "N/A"))
                st.metric("Status", state.get("application_status", "N/A").upper())
                
                if state.get("customer_id"):
                    customer = get_customer_by_id(state["customer_id"])
                    if customer:
                        st.subheader("📋 Customer Info")
                        st.write(f"**Name:** {customer['name']}")
                        st.write(f"**Credit Score:** {customer['credit_score']}")
                        st.write(f"**Pre-approved:** ₹{customer['pre_approved_limit']:,.0f}")
                
                if state.get("requested_amount"):
                    st.subheader("💰 Loan Details")
                    st.write(f"**Requested:** ₹{state['requested_amount']:,.0f}")
                    if state.get("approved_amount"):
                        st.write(f"**Approved:** ₹{state['approved_amount']:,.0f}")
                    if state.get("monthly_emi"):
                        st.write(f"**EMI:** ₹{state['monthly_emi']:,.2f}")

                # Underwriting Insights
                if state.get("credit_score") or state.get("risk_score") or state.get("emi_to_income_ratio"):
                    st.subheader("🛡️ Underwriting Insights")
                    if state.get("credit_score") is not None:
                        st.write(f"**Credit Score:** {state['credit_score']}")
                    if state.get("risk_score") is not None:
                        rs = state['risk_score']
                        def _risk_rating(v: float):
                            return "Low Risk ⭐⭐⭐⭐⭐" if v < 20 else ("Low-Medium Risk ⭐⭐⭐⭐" if v < 40 else ("Medium Risk ⭐⭐⭐" if v < 60 else ("Medium-High Risk ⭐⭐" if v < 80 else "High Risk ⭐")))
                        st.write(f"**Risk Score:** {rs:.1f} ({_risk_rating(rs)})")
                    if state.get("emi_to_income_ratio") is not None:
                        st.write(f"**EMI-to-Income:** {state['emi_to_income_ratio']*100:.1f}%")
                    if state.get("total_monthly_obligation") is not None:
                        st.write(f"**Total Monthly Obligation:** ₹{state['total_monthly_obligation']:,.2f}")
                    recs = state.get("underwriting_recommendations", [])
                    if recs:
                        st.markdown("**Recommendations:**")
                        for r in recs:
                            st.write(f"- {r}")
                    # Allow manual re-run of underwriting with current state
                    if st.button("🔄 Re-run Underwriting", use_container_width=True):
                        # Hint routing to underwriting and invoke
                        state_ref = st.session_state.workflow.get_session_state(st.session_state.session_id)
                        state_ref["next_action"] = "delegate_to_underwriting"
                        st.session_state.workflow.process_message(st.session_state.session_id, "Re-run underwriting")
                        st.rerun()

                # Selected Offer confirmation card
                if state.get("selected_offer"):
                    sel = state["selected_offer"]
                    st.subheader("✅ Selected Offer")
                    st.write(f"**Plan:** {sel.get('tenure_display', str(sel.get('tenure_months',''))+' months')}")
                    st.write(f"**Interest Rate:** {sel.get('interest_rate',0)*100:.2f}% p.a.")
                    st.write(f"**EMI:** ₹{sel.get('monthly_emi',0):,.2f}")
                    st.caption("Type 'proceed' in chat to move to verification or say 'negotiate' to discuss further.")
        
        st.divider()
        
        # Quick Actions
        st.subheader("⚡ Quick Actions")
        
        if st.button("💬 Sample: Request Loan"):
            if st.session_state.session_id:
                st.session_state.sample_message = "I need a loan of 3 lakh rupees"
        
        if st.button("📞 Sample: Provide OTP"):
            if st.session_state.session_id:
                # Get the OTP from the last message
                st.session_state.sample_message = "123456"
    
    # Main chat area
    st.divider()
    
    # Progress indicator
    if st.session_state.session_id:
        display_progress_indicator(st.session_state.current_stage)
        st.divider()
    
    # Chat messages
    chat_container = st.container()
    
    with chat_container:
        for message in st.session_state.messages:
            role_class = "user-message" if message["role"] == "user" else "assistant-message"
            role_label = "You" if message["role"] == "user" else "Assistant"
            agent_badge = f"<span class='agent-badge'>{message.get('agent','master').title()}</span>" if message["role"]=="assistant" else ""
            st.markdown(
                f"<div class='chat-message {role_class}'><strong>{role_label}:</strong> {agent_badge}<br>{message['content']}</div>",
                unsafe_allow_html=True
            )
    
    # Chat input
    st.divider()
    
    # Check if we have a sample message to send
    if hasattr(st.session_state, 'sample_message'):
        user_input = st.session_state.sample_message
        delattr(st.session_state, 'sample_message')
    else:
        user_input = st.chat_input("Type your message here...", disabled=st.session_state.session_id is None)
    
    if user_input:
        # Add user message to chat
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        # Extract information from message if needed
        if not st.session_state.customer_id:
            customer_id = extract_customer_id(user_input)
            if customer_id:
                st.session_state.customer_id = customer_id
                # Update workflow session
                state = st.session_state.workflow.get_session_state(st.session_state.session_id)
                state["customer_id"] = customer_id
        
        # Extract loan amount from any message to reduce back-and-forth
        amount = extract_amount(user_input)
        if amount:
            state = st.session_state.workflow.get_session_state(st.session_state.session_id)
            state["requested_amount"] = amount
            # Preserve first captured needs if not already set
            if not state.get("customer_needs"):
                state["customer_needs"] = user_input
        
        # Process message through workflow
        result = st.session_state.workflow.process_message(
            st.session_state.session_id,
            user_input
        )
        
        if result["success"]:
            # Add assistant response
            # Fetch the last assistant message from workflow state to get agent label
            state_after = st.session_state.workflow.get_session_state(st.session_state.session_id)
            last_assistant = None
            for m in reversed(state_after.get("conversation_history", [])):
                if m.get("role") == "assistant":
                    last_assistant = m
                    break
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["response"],
                "agent": (last_assistant or {}).get("agent", "master")
            })
            
            # Update stage
            st.session_state.current_stage = result["current_stage"]
            st.session_state.application_status = result["application_status"]
        else:
            st.error(f"Error: {result.get('error')}")
        # Trigger a single rerun only when we actually handled input
        st.rerun()

    # Contextual controls for current stage
    if st.session_state.session_id:
        state = st.session_state.workflow.get_session_state(st.session_state.session_id)
        stage = state.get("current_stage")

        if stage == 'verification':
            st.divider()
            st.subheader("Verification Actions")
            # Show OTP provider status
            if is_twilio_configured():
                st.caption("OTP Provider: Twilio Verify (SMS)")
            else:
                st.caption("OTP Provider: Demo fallback (code shown in chat). Set TWILIO_* env vars to enable real SMS.")

            # Allow user to confirm or override phone number for OTP
            phone_default = state.get("otp_phone")
            if not phone_default and state.get("customer_id"):
                cust = get_customer_by_id(state["customer_id"]) or {}
                phone_default = cust.get("phone", "")
            phone_input = st.text_input("Phone for OTP (E.164)", value=phone_default or "", placeholder="+91XXXXXXXXXX")
            if phone_input and phone_input != state.get("otp_phone"):
                state["otp_phone"] = phone_input
            cols = st.columns([1,1])
            with cols[0]:
                if st.button("Send OTP", use_container_width=True):
                    st.session_state.workflow.process_message(st.session_state.session_id, "SEND OTP")
                    st.rerun()
            with cols[1]:
                otp_val = st.text_input("Enter OTP", value="", max_chars=6)
                if st.button("Verify OTP", use_container_width=True, disabled=not otp_val):
                    st.session_state.workflow.process_message(st.session_state.session_id, otp_val)
                    st.rerun()
            # KYC fields
            st.markdown("### Identity Details")
            pan_val = st.text_input("PAN", placeholder="ABCDE1234F").upper()
            dob_val = st.date_input("Date of Birth")
            email_val = st.text_input("Email", placeholder="name@example.com")
            alt_phone_val = st.text_input("Alternate Phone (optional)", placeholder="+919876543210")
            if st.button("Submit KYC Details"):
                msg_parts = []
                if pan_val:
                    msg_parts.append(f"PAN: {pan_val}")
                if dob_val:
                    msg_parts.append(f"DOB: {dob_val}")
                if email_val:
                    msg_parts.append(f"Email: {email_val}")
                if alt_phone_val:
                    msg_parts.append(f"Alt Phone: {alt_phone_val}")
                if msg_parts:
                    st.session_state.workflow.process_message(st.session_state.session_id, " | ".join(msg_parts))
                    st.rerun()

            st.markdown("### Address Confirmation")
            addr_val = st.text_area("Current Address", placeholder="Address: 221B Baker Street, London, 560001")
            if st.button("Submit Address", disabled=not addr_val.strip()):
                msg = addr_val if addr_val.lower().startswith("address:") else f"Address: {addr_val}"
                st.session_state.workflow.process_message(st.session_state.session_id, msg)
                st.rerun()

            st.markdown("### ID Document Upload (optional)")
            id_cols = st.columns(2)
            with id_cols[0]:
                id_front = st.file_uploader("ID Front", type=["pdf","jpg","jpeg","png"], accept_multiple_files=False, key="id_front")
                if id_front is not None and state.get("customer_id"):
                    res = save_uploaded_document(state["customer_id"], "id_front", id_front.getvalue(), id_front.name)
                    st.success("Front uploaded")
                    state["id_document_front_url"] = res.get("file_path")
            with id_cols[1]:
                id_back = st.file_uploader("ID Back", type=["pdf","jpg","jpeg","png"], accept_multiple_files=False, key="id_back")
                if id_back is not None and state.get("customer_id"):
                    res = save_uploaded_document(state["customer_id"], "id_back", id_back.getvalue(), id_back.name)
                    st.success("Back uploaded")
                    state["id_document_back_url"] = res.get("file_path")

        if stage == 'document_upload':
            st.divider()
            st.subheader("Upload Required Document")
            uploaded = st.file_uploader("Upload latest salary slip (PDF/JPG/PNG)", type=["pdf","jpg","jpeg","png"], accept_multiple_files=False)
            if uploaded is not None:
                # Save file to temp location
                uploads_dir = os.path.join(os.getcwd(), "uploads")
                os.makedirs(uploads_dir, exist_ok=True)
                save_path = os.path.join(uploads_dir, uploaded.name)
                with open(save_path, "wb") as f:
                    f.write(uploaded.getbuffer())
                # Process salary slip to extract net salary
                ua = create_underwriting_agent()
                cid = state.get("customer_id")
                if cid:
                    result = ua.process_salary_slip(cid, save_path)
                    # Reflect outcome in chat and state
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result.get("message", "Document processed."),
                        "agent": "underwriting"
                    })
                    # Update state flags so flow returns to underwriting
                    state["salary_slip_uploaded"] = True
                    state["salary_slip_url"] = save_path
                    if result.get("monthly_salary"):
                        state["monthly_salary"] = result["monthly_salary"]
                    # Nudge workflow with a small message
                    st.session_state.workflow.process_message(st.session_state.session_id, "Uploaded salary slip successfully")
                    st.rerun()
    
    # Instructions
    if not st.session_state.session_id:
        st.info("👈 Please start a new session from the sidebar to begin!")
    
    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #6b7280; font-size: 0.875rem;">
        <p>🔒 Secure & Confidential | 📞 24/7 Support: 1800-XXX-XXXX | 💬 AI-Powered by LangGraph + LangChain</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
