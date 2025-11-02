"""
LangGraph Workflow for Loan Application Process
"""
from typing import Dict, Any, Literal
from langgraph.graph import StateGraph, END
from src.workflow.state import (
    LoanApplicationState,
    create_initial_state,
    update_state,
    add_message
)
from src.agents.master_agent import create_master_agent
from src.agents.sales_agent import create_sales_agent
from src.agents.verification_agent import create_verification_agent
from src.agents.underwriting_agent import create_underwriting_agent
from src.tools.otp_tools import is_twilio_configured, send_otp as otp_send_api, verify_otp as otp_verify_api
from src.agents.sanction_agent import create_sanction_agent


# ============================================================================
# AGENT NODES
# ============================================================================

def master_agent_node(state: LoanApplicationState) -> LoanApplicationState:
    """
    Master Agent node - handles conversation orchestration.
    """
    master_agent = create_master_agent()
    
    # Get the last user message
    if state["conversation_history"]:
        last_message = state["conversation_history"][-1]
        if last_message["role"] == "user":
            user_message = last_message["content"]
        else:
            # If last message was from assistant, return as is
            return state
    else:
        # First interaction - generate greeting
        greeting = master_agent.generate_greeting(state.get("customer_name"))
        return add_message(state, "assistant", greeting, "master")
    
    # Process the message
    result = master_agent.process_message(state, user_message)
    
    # Update state with response
    new_state = add_message(state, "assistant", result["response"], "master")
    new_state = update_state(new_state, {
        "current_stage": result["new_stage"],
        "next_action": result["next_action"],
        "active_agent": "master"
    })
    
    return new_state


def sales_agent_node(state: LoanApplicationState) -> LoanApplicationState:
    """
    Sales Agent node - handles loan product sales and negotiation.
    """
    sales_agent = create_sales_agent()
    
    # Inspect last user message for negotiation/selection cues
    last_user_msg = None
    if state.get("conversation_history"):
        for msg in reversed(state["conversation_history"]):
            if msg.get("role") == "user":
                last_user_msg = (msg.get("content") or "").lower()
                break

    # If user selected an offer by option number or tenure, set selected_offer and confirm
    import re as _re
    if last_user_msg:
        offers_for_selection = state.get("recommended_offers", [])
        opt_match = _re.search(r"option\s*(\d+)", last_user_msg or "")
        ten_match = _re.search(r"\b(\d+)\s*(year|years|yr|yrs|month|months)\b", last_user_msg or "")
        selected = None
        if opt_match and offers_for_selection:
            idx = max(0, min(int(opt_match.group(1)) - 1, len(offers_for_selection) - 1))
            selected = offers_for_selection[idx]
        elif ten_match and offers_for_selection:
            n = int(ten_match.group(1))
            unit = ten_match.group(2)
            months = n * 12 if unit.startswith("y") or unit.startswith("yr") else n
            # pick closest tenure
            selected = min(offers_for_selection, key=lambda o: abs(o.get("tenure_months", 0) - months))
        if selected:
            confirm_msg = (
                f"Great choice! I've noted your selection: {selected.get('tenure_display','selected plan')}\n"
                f"- Loan Amount: ₹{selected.get('amount', state.get('requested_amount', 0)):,.0f}\n"
                f"- Interest Rate: {selected.get('interest_rate', 0)*100:.2f}% p.a.\n"
                f"- Monthly EMI: ₹{selected.get('monthly_emi', 0):,.2f}\n\n"
                "If you're ready, type 'proceed' to move to verification, or say 'negotiate' to discuss the rate/EMI."
            )
            new_state = add_message(state, "assistant", confirm_msg, "sales")
            return update_state(new_state, {
                "selected_offer": selected,
                "tenure_months": selected.get("tenure_months"),
                "interest_rate": selected.get("interest_rate"),
                "monthly_emi": selected.get("monthly_emi"),
                "active_agent": "master",
                "next_action": None
            })

    # If user is negotiating and we have offers, handle negotiation
    negotiation_cues = ["rate", "reduce", "discount", "lower", "cheaper", "negotiate", "negotiation", "emi"]
    has_offers = bool(state.get("recommended_offers"))
    if last_user_msg and has_offers and (any(k in last_user_msg for k in negotiation_cues) or _re.search(r"\d+\s*%", last_user_msg)):
        # Choose current offer (match by tenure if available)
        offers = state.get("recommended_offers", [])
        current_offer = None
        if state.get("tenure_months"):
            for o in offers:
                if o.get("tenure_months") == state.get("tenure_months"):
                    current_offer = o
                    break
        if not current_offer and offers:
            current_offer = offers[min(1, len(offers)-1)]  # middle/first fallback
        if not current_offer:
            # Fallback: regenerate offers if missing
            requested_amount = state.get("requested_amount")
            customer_needs = state.get("customer_needs", "Personal loan requirement")
            regen = sales_agent.process_sales(state, requested_amount or 100000, customer_needs)
            offers = regen.get("offers", [])
            current_offer = offers[0] if offers else None
        if current_offer:
            nres = sales_agent.handle_negotiation(state, negotiation_request=last_user_msg, current_offer=current_offer)
            reply = nres.get("response", "")
            new_state = add_message(state, "assistant", reply, "sales")
            updates = {"active_agent": "master", "next_action": None}
            if nres.get("negotiation_approved"):
                updates.update({
                    "interest_rate": nres.get("new_rate", current_offer.get("interest_rate")),
                    "monthly_emi": nres.get("new_emi", current_offer.get("monthly_emi"))
                })
            return update_state(new_state, updates)

    # Otherwise, present offers (first-time or re-prompt)
    requested_amount = state.get("requested_amount")
    customer_needs = state.get("customer_needs", "Personal loan requirement")
    if not requested_amount:
        # No amount: ask user to confirm desired amount
        prompt = "Could you please confirm the loan amount you need (e.g., 3 lakh, 500000, 50k)?"
        new_state = add_message(state, "assistant", prompt, "sales")
        return update_state(new_state, {"active_agent": "master", "next_action": None})

    # Generate or refresh offers
    result = sales_agent.process_sales(
        state=state,
        requested_amount=requested_amount,
        customer_needs=customer_needs
    )
    if result["success"]:
        recommended_offer = result["recommended_offer"]
        new_state = add_message(state, "assistant", result["presentation"], "sales")
        new_state = update_state(new_state, {
            "recommended_offers": result["offers"],
            "tenure_months": recommended_offer["tenure_months"],
            "interest_rate": recommended_offer["interest_rate"],
            "monthly_emi": recommended_offer["monthly_emi"],
            "active_agent": "master",
            "next_action": None
        })
        return new_state
    else:
        return update_state(state, {"active_agent": "master", "next_action": None, "last_error": result.get("error")})


def verification_agent_node(state: LoanApplicationState) -> LoanApplicationState:
    """
    Verification Agent node - handles KYC and identity verification.
    - First entry: starts verification and explains steps (no auto-OTP)
    - On 'send otp': sends OTP and sets otp_sent
    - On 4-6 digit input and otp_sent: verifies OTP and updates flags
    """
    verification_agent = create_verification_agent()

    # Find the last user message (if any)
    last_user_msg = None
    if state.get("conversation_history"):
        for msg in reversed(state["conversation_history"]):
            if msg.get("role") == "user":
                last_user_msg = (msg.get("content") or "").strip()
                break

    # If verification not initialized yet (no otp_sent and no kyc flag), start it
    if not any([state.get("kyc_pan"), state.get("kyc_dob"), state.get("kyc_email"), state.get("phone_verified"), state.get("address_verified")]) and not state.get("otp_sent"):
        result = verification_agent.start_verification(state)
        if result["success"]:
            new_state = add_message(
                state,
                "assistant",
                result["message"],
                "verification"
            )
            # Mark identity/KYC as verified at this step for demo flow
            new_state = update_state(new_state, {
                "active_agent": "master",
                "next_action": None
            })
            return new_state
        else:
            return update_state(state, {
                "active_agent": "master",
                "last_error": result.get("error")
            })

    # If user requested to send/resend OTP
    if last_user_msg and any(kw in last_user_msg.lower() for kw in ["send otp", "resend otp", "send the otp", "otp please", "otp"]):
        cust_id = state.get("customer_id")
        if cust_id:
            # Prefer explicitly provided phone for OTP, fallback to CRM/customer phone
            customer = create_verification_agent().start_verification(state).get("customer_data", {})
            phone = state.get("otp_phone") or customer.get("phone", state.get("customer_phone", ""))

            # Normalize common inputs to E.164 where possible (lightweight): if 10 digits without +, assume +91
            if phone:
                raw = str(phone).strip().replace(" ", "")
                if raw.isdigit() and len(raw) == 10:
                    phone = "+91" + raw
                else:
                    phone = raw
            if is_twilio_configured():
                otp_res = otp_send_api(phone)
                msg = otp_res.get("message", "OTP sent. Please enter the code.") if otp_res.get("success") else f"⚠️ Failed to send OTP: {otp_res.get('error','unknown error')}"
                new_state = add_message(state, "assistant", msg, "verification")
                new_state = update_state(new_state, {
                    "otp_sent": otp_res.get("success", False),
                    "otp_provider": "twilio" if otp_res.get("success") else None,
                    "otp_code": None,  # never store code for Twilio
                    "otp_phone": phone,
                    "otp_attempts": 0,
                    "otp_resend_count": (state.get("otp_resend_count", 0) + 1) if state.get("otp_sent") else state.get("otp_resend_count", 0),
                    "active_agent": "master",
                    "next_action": None
                })
                return new_state
            else:
                # Demo fallback: generate OTP locally and show in message
                otp_result = verification_agent.send_otp(cust_id, phone)
                new_state = add_message(state, "assistant", otp_result["message"], "verification")
                new_state = update_state(new_state, {
                    "otp_sent": True,
                    "otp_provider": "demo",
                    "otp_code": otp_result.get("otp_code"),
                    "otp_phone": phone,
                    "otp_attempts": 0,
                    "otp_resend_count": (state.get("otp_resend_count", 0) + 1) if state.get("otp_sent") else state.get("otp_resend_count", 0),
                    "active_agent": "master",
                    "next_action": None
                })
                return new_state

    # If OTP was sent and user provided a 4-6 digit code, verify against state-stored OTP
    import re as _re
    if last_user_msg and _re.search(r"\b\d{4,6}\b", last_user_msg):
        code_match = _re.search(r"\b(\d{4,6})\b", last_user_msg)
        entered_code = code_match.group(1) if code_match else None
        if state.get("otp_sent") and state.get("otp_provider") == "twilio" and state.get("otp_phone") and entered_code:
            vres = otp_verify_api(state.get("otp_phone"), entered_code)
            if vres.get("success") and vres.get("verified"):
                state = add_message(state, "assistant", "✅ Phone Verification Successful!", "verification")
                state = update_state(state, {
                    "phone_verified": True,
                    "otp_sent": False,
                    "otp_code": None,
                    "otp_attempts": 0,
                    "active_agent": "master",
                    "next_action": None
                })
            else:
                attempts = state.get("otp_attempts", 0) + 1
                err_msg = vres.get("message") or f"❌ Incorrect OTP. Attempts remaining: {max(0,3-attempts)}"
                if attempts >= 3:
                    state = add_message(state, "assistant", "❌ Maximum attempts exceeded. Type 'SEND OTP' to request a new code.", "verification")
                    state = update_state(state, {
                        "otp_sent": False,
                        "otp_attempts": 0,
                        "active_agent": "master",
                        "next_action": None
                    })
                else:
                    state = add_message(state, "assistant", err_msg, "verification")
                    state = update_state(state, {
                        "otp_attempts": attempts,
                        "active_agent": "master",
                        "next_action": None
                    })
        elif state.get("otp_sent") and state.get("otp_code"):
            if entered_code == state.get("otp_code"):
                success_msg = """✅ **Phone Verification Successful!**

Your mobile number has been verified successfully.

Next, let me confirm your address details for our records."""
                state = add_message(state, "assistant", success_msg, "verification")
                state = update_state(state, {
                    "phone_verified": True,
                    "otp_sent": False,
                    "otp_code": None,
                    "otp_attempts": 0,
                    "active_agent": "master",
                    "next_action": None
                })
            else:
                attempts = state.get("otp_attempts", 0) + 1
                if attempts >= 3:
                    fail_msg = """❌ **Maximum Attempts Exceeded**

You've entered incorrect OTP 3 times. For security reasons, please request a new OTP.

Type \"SEND OTP\" to get a new code."""
                    state = add_message(state, "assistant", fail_msg, "verification")
                    state = update_state(state, {
                        "otp_sent": False,
                        "otp_code": None,
                        "otp_attempts": 0,
                        "active_agent": "master",
                        "next_action": None
                    })
                else:
                    fail_try_msg = f"""❌ **Incorrect OTP**

The OTP you entered doesn't match. Please try again.

Attempts remaining: {3 - attempts}

💡 Make sure you're entering the latest OTP received."""
                    state = add_message(state, "assistant", fail_try_msg, "verification")
                    state = update_state(state, {
                        "otp_attempts": attempts,
                        "active_agent": "master",
                        "next_action": None
                    })
        else:
            no_otp_msg = "No OTP found. Please type 'SEND OTP' to request a new code."
            state = add_message(state, "assistant", no_otp_msg, "verification")
            state = update_state(state, {"active_agent": "master", "next_action": None})

    # If user provided address confirmation, verify it
    if last_user_msg:
        lower = last_user_msg.lower()
        addr_text = None
        if lower.startswith("address:"):
            addr_text = last_user_msg.split(":", 1)[1].strip()
        elif lower.startswith("my address is"):
            addr_text = last_user_msg.split("is", 1)[1].strip()
        elif "address is" in lower:
            idx = lower.find("address is")
            addr_text = last_user_msg[idx + len("address is"):].strip()
        # Fallback: if message seems long enough and contains street-like tokens, treat as address
        if not addr_text and any(k in lower for k in ["street", "road", "lane", "block", "sector", "city", "pincode", "pin"]) and len(last_user_msg) > 10:
            addr_text = last_user_msg.strip()
        if addr_text and state.get("customer_id"):
            vres = verification_agent.verify_address(state["customer_id"], addr_text)
            new_state = add_message(state, "assistant", vres["message"], "verification")
            flags = {"active_agent": "master", "next_action": None}
            if vres.get("address_verified"):
                flags.update({"address_verified": True})
            state = update_state(new_state, flags)

    # Parse PAN, Aadhaar last4, DOB, Email, Alt phone from free-form messages
    if last_user_msg:
        pan_match = _re.search(r"\bpan\s*[:\-]?\s*([A-Z]{5}[0-9]{4}[A-Z])\b", last_user_msg, _re.IGNORECASE)
        aad_last4 = _re.search(r"\baadhaar|aadhar\b.*?(\d{4})", last_user_msg, _re.IGNORECASE)
        dob_match = _re.search(r"\bdob\s*[:\-]?\s*([0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{2}/[0-9]{2}/[0-9]{4})\b", last_user_msg, _re.IGNORECASE)
        email_match = _re.search(r"\bemail\s*[:\-]?\s*([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b", last_user_msg, _re.IGNORECASE)
        alt_phone = _re.search(r"\b(alt|alternate)\s*phone\s*[:\-]?\s*(\+?\d{10,13})\b", last_user_msg, _re.IGNORECASE)
        updates = {}
        msgs = []
        if pan_match:
            updates["kyc_pan"] = pan_match.group(1).upper()
            msgs.append("PAN captured ✅")
        if aad_last4:
            updates["kyc_aadhaar_last4"] = aad_last4.group(1)
            msgs.append("Aadhaar last 4 captured ✅")
        if dob_match:
            updates["kyc_dob"] = dob_match.group(1)
            msgs.append("DOB captured ✅")
        if email_match:
            updates["kyc_email"] = email_match.group(1)
            msgs.append("Email captured ✅")
        if alt_phone:
            updates["alt_phone"] = alt_phone.group(2)
            msgs.append("Alternate phone captured ✅")
        if updates:
            state = update_state(state, updates)
            if msgs:
                state = add_message(state, "assistant", "\n".join(msgs), "verification")

    # If core KYC details present, mark kyc_verified and notify
    if not state.get("kyc_verified") and all([state.get("kyc_pan"), state.get("kyc_dob"), state.get("kyc_email")]):
        state = add_message(state, "assistant", "✅ Identity details verified successfully.", "verification")
        state = update_state(state, {"kyc_verified": True})

    return update_state(state, {"active_agent": "master", "next_action": None})


def underwriting_agent_node(state: LoanApplicationState) -> LoanApplicationState:
    """
    Underwriting Agent node - handles credit assessment and approval.
    """
    underwriting_agent = create_underwriting_agent()
    
    # Process underwriting
    result = underwriting_agent.process_underwriting(state)
    
    if result["success"]:
        new_state = add_message(
            state,
            "assistant",
            result["message"],
            "underwriting"
        )
        
        new_state = update_state(new_state, {
            "credit_score": result.get("credit_score"),
            "risk_score": result.get("risk_score"),
            "underwriting_decision": result["decision"],
            "approved_amount": result.get("approved_amount"),
            "conditional_requirements": result.get("conditions", []),
            "rejection_reason": result.get("eligibility_details", {}).get("reason"),
            # Map detailed affordability metrics if present
            "monthly_emi": result.get("eligibility_details", {}).get("monthly_emi", new_state.get("monthly_emi")),
            "total_monthly_obligation": result.get("eligibility_details", {}).get("total_monthly_obligation", new_state.get("total_monthly_obligation")),
            "emi_to_income_ratio": result.get("eligibility_details", {}).get("emi_to_income_ratio", new_state.get("emi_to_income_ratio")),
            "underwriting_recommendations": result.get("recommendations", []),
            "active_agent": "master",
            "next_action": None
        })
        
        # Update application status based on decision
        if result["decision"] == "approved":
            new_state = update_state(new_state, {
                "application_status": "approved"
            })
        elif result["decision"] == "rejected":
            new_state = update_state(new_state, {
                "application_status": "rejected"
            })
        
        return new_state
    else:
        return update_state(state, {
            "active_agent": "master",
            "last_error": result.get("error")
        })


def sanction_agent_node(state: LoanApplicationState) -> LoanApplicationState:
    """
    Sanction Agent node - handles sanction letter generation.
    """
    sanction_agent = create_sanction_agent()
    
    # Generate sanction letter
    result = sanction_agent.generate_sanction(state)
    
    if result["success"]:
        new_state = add_message(
            state,
            "assistant",
            result["message"],
            "sanction"
        )
        
        new_state = update_state(new_state, {
            "sanction_letter_url": result["sanction_letter_url"],
            "sanction_letter_ref_no": result["reference_number"],
            "current_stage": "closure",
            "active_agent": "master",
            "next_action": None
        })
        
        return new_state
    else:
        return update_state(state, {
            "active_agent": "master",
            "last_error": result.get("error")
        })


# ============================================================================
# ROUTING LOGIC
# ============================================================================

def route_master_agent(state: LoanApplicationState) -> Literal["sales", "verification", "underwriting", "sanction", "master", "end"]:
    """
    Route from master agent to appropriate worker or end.
    """
    next_action = state.get("next_action")
    current_stage = state.get("current_stage")
    
    # Check if we should delegate to a worker
    if next_action == "delegate_to_sales":
        return "sales"
    elif next_action == "delegate_to_verification":
        return "verification"
    elif next_action == "delegate_to_underwriting":
        return "underwriting"
    elif next_action == "delegate_to_sanction":
        return "sanction"
    
    # Additional triggers while in verification stage: route to verification on OTP actions
    # IMPORTANT: Only trigger when the MOST RECENT message is from the user.
    # Otherwise we can loop: verification -> assistant reply -> master -> verification (reusing old user msg)
    if current_stage == "verification":
        conv = state.get("conversation_history", [])
        if conv and conv[-1].get("role") == "user":
            last_user_msg = (conv[-1].get("content") or "").lower()
            import re as _re
            if any(k in last_user_msg for k in ["send otp", "resend otp", "send the otp", "otp please", "otp"]) or (
                state.get("otp_sent") and _re.search(r"\b\d{4,6}\b", last_user_msg)
            ):
                return "verification"

    # Check if conversation should end
    if current_stage == "closure":
        application_status = state.get("application_status")
        if application_status in ["approved", "rejected", "abandoned"]:
            return "end"
    
    # If master just responded and there's no delegation needed, end this cycle
    # This prevents infinite loops - we wait for next user message
    if state.get("conversation_history"):
        last_message = state["conversation_history"][-1]
        # If last message was from assistant, stop and wait for user input
        if last_message["role"] == "assistant":
            return "end"
    
    # Continue with master (this should rarely happen now)
    return "master"


# ============================================================================
# WORKFLOW CREATION
# ============================================================================

def create_workflow() -> StateGraph:
    """
    Create the LangGraph workflow for loan application process.
    
    Returns:
        Compiled workflow
    """
    # Create workflow
    workflow = StateGraph(LoanApplicationState)
    
    # Add nodes for each agent
    workflow.add_node("master_agent", master_agent_node)
    workflow.add_node("sales_agent", sales_agent_node)
    workflow.add_node("verification_agent", verification_agent_node)
    workflow.add_node("underwriting_agent", underwriting_agent_node)
    workflow.add_node("sanction_agent", sanction_agent_node)
    
    # Set entry point
    workflow.set_entry_point("master_agent")
    
    # Add conditional routing from master agent
    workflow.add_conditional_edges(
        "master_agent",
        route_master_agent,
        {
            "sales": "sales_agent",
            "verification": "verification_agent",
            "underwriting": "underwriting_agent",
            "sanction": "sanction_agent",
            "master": "master_agent",
            "end": END
        }
    )
    
    # Worker agents return to master
    workflow.add_edge("sales_agent", "master_agent")
    workflow.add_edge("verification_agent", "master_agent")
    workflow.add_edge("underwriting_agent", "master_agent")
    workflow.add_edge("sanction_agent", "master_agent")
    
    # Compile workflow
    return workflow.compile()


# ============================================================================
# WORKFLOW EXECUTION
# ============================================================================

class LoanApplicationWorkflow:
    """
    Wrapper class for the loan application workflow.
    """
    
    def __init__(self):
        self.workflow = create_workflow()
        self.sessions = {}  # Store session states
    
    def create_session(self, customer_id: str = None) -> str:
        """
        Create a new session.
        
        Args:
            customer_id: Optional customer ID
            
        Returns:
            Session ID
        """
        state = create_initial_state(customer_id)
        session_id = state["session_id"]
        self.sessions[session_id] = state
        return session_id
    
    def process_message(
        self,
        session_id: str,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Process a user message in a session.
        
        Args:
            session_id: Session ID
            user_message: User's message
            
        Returns:
            Response and updated state
        """
        if session_id not in self.sessions:
            return {
                "success": False,
                "error": "Session not found"
            }
        
        # Get current state
        state = self.sessions[session_id]
        
        # Add user message to state
        state = add_message(state, "user", user_message)
        
        # Run workflow
        result = self.workflow.invoke(state)
        
        # Update session state
        self.sessions[session_id] = result
        
        # Get assistant's response
        assistant_messages = [
            msg["content"] for msg in result["conversation_history"]
            if msg["role"] == "assistant"
        ]
        last_response = assistant_messages[-1] if assistant_messages else ""
        
        return {
            "success": True,
            "response": last_response,
            "state": result,
            "current_stage": result.get("current_stage"),
            "application_status": result.get("application_status")
        }
    
    def get_session_state(self, session_id: str) -> LoanApplicationState:
        """
        Get the current state of a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session state
        """
        return self.sessions.get(session_id)


# ============================================================================
# MAIN EXPORT
# ============================================================================

def create_loan_workflow() -> LoanApplicationWorkflow:
    """Factory function to create workflow instance."""
    return LoanApplicationWorkflow()
