"""
Verification Agent - KYC and Identity Verification Specialist
"""
from typing import Dict, Any, Optional
from src.workflow.state import LoanApplicationState
from src.tools.crm_tools import (
    verify_customer_details,
    simulate_otp_generation,
    verify_otp,
    get_customer_by_id
)
from src.utils.llm_config import get_llm


class VerificationAgent:
    """
    Verification Agent handles KYC and identity verification.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        self.llm = get_llm(temperature=0.3, model=model_name)
        self.system_prompt = self._create_system_prompt()
        self.otp_store = {}  # Store OTPs temporarily
    
    def _create_system_prompt(self) -> str:
        return """You are a verification specialist focused on security and compliance.

Your role is to:
1. Verify customer identity through multiple touchpoints
2. Validate KYC details against CRM records
3. Conduct phone verification via OTP
4. Check address and other personal details
5. Flag any discrepancies for review
6. Ensure regulatory compliance

Verification Approach:
- Be professional but friendly
- Explain why verification is necessary (security)
- Make the process smooth and quick
- Handle verification failures sensitively
- Provide clear instructions for each step
- Assure customers about data privacy

Key Principles:
- Security first, always
- Clear communication of requirements
- Quick and efficient process
- Respectful of customer time
- Transparent about any issues"""
    
    def start_verification(
        self,
        state: LoanApplicationState
    ) -> Dict[str, Any]:
        """
        Start the verification process.
        
        Args:
            state: Current application state
            
        Returns:
            Verification initiation result
        """
        customer_id = state.get("customer_id")
        
        if not customer_id:
            return {
                "success": False,
                "error": "Customer ID not available"
            }
        
        customer = get_customer_by_id(customer_id)
        
        if not customer:
            return {
                "success": False,
                "error": "Customer not found"
            }
        
        # Check KYC status in CRM
        kyc_status = customer.get("kyc_status", "unknown")

        message = f"""Thank you! Let's quickly verify your details for security. This will only take a minute.

📋 **Verification Steps**
1) Identity: Share PAN, DOB, and Email
2) Phone: We'll send an OTP to {customer['phone']}
3) Address: Confirm your current address

I have your records on file:
- Name: {customer['name']}
- Phone: {customer['phone']}
- City: {customer['city']}

**KYC Status**: {kyc_status.upper()}

You can reply here (e.g., "PAN: ABCDE1234F | DOB: 1990-05-10 | Email: name@example.com")
and type "SEND OTP" to receive the code.

Alternatively, use the verification panel below to submit details.
"""

        return {
            "success": True,
            "message": message,
            "kyc_status": kyc_status,
            "customer_data": customer
        }
    
    def send_otp(
        self,
        customer_id: str,
        phone: str
    ) -> Dict[str, Any]:
        """
        Send OTP for phone verification.
        
        Args:
            customer_id: Customer ID
            phone: Phone number to send OTP to
            
        Returns:
            OTP sending result
        """
        # Generate OTP
        otp = simulate_otp_generation(phone)
        
        # Store OTP temporarily (instance-level cache). Note: Workflow also persists into state.
        self.otp_store[customer_id] = {
            "otp": otp,
            "phone": phone,
            "attempts": 0
        }
        
        message = f"""✅ **OTP Sent Successfully!**

A 6-digit OTP has been sent to {phone}.

📱 Please check your messages and enter the OTP here to verify your phone number.

⏱️ OTP is valid for 10 minutes.
❓ Didn't receive it? You can request a new OTP in 60 seconds.

**For Demo**: Your OTP is **{otp}**
"""
        
        return {
            "success": True,
            "message": message,
            "otp_sent": True,
            "otp_code": otp  # Expose for workflow state persistence and robust verification
        }
    
    def verify_otp_input(
        self,
        customer_id: str,
        provided_otp: str
    ) -> Dict[str, Any]:
        """
        Verify OTP provided by customer.
        
        Args:
            customer_id: Customer ID
            provided_otp: OTP provided by customer
            
        Returns:
            Verification result
        """
        if customer_id not in self.otp_store:
            return {
                "success": False,
                "verified": False,
                "message": "No OTP found. Please request a new OTP."
            }
        
        otp_data = self.otp_store[customer_id]
        otp_data["attempts"] += 1
        
        # Check if OTP matches
        if provided_otp == otp_data["otp"]:
            # Clear OTP data
            del self.otp_store[customer_id]
            
            message = """✅ **Phone Verification Successful!**

Your mobile number has been verified successfully.

Next, let me confirm your address details for our records."""
            
            return {
                "success": True,
                "verified": True,
                "phone_verified": True,
                "message": message
            }
        else:
            if otp_data["attempts"] >= 3:
                message = """❌ **Maximum Attempts Exceeded**

You've entered incorrect OTP 3 times. For security reasons, please request a new OTP.

Type "SEND OTP" to get a new code."""
                
                # Reset attempts
                del self.otp_store[customer_id]
                
                return {
                    "success": False,
                    "verified": False,
                    "max_attempts_reached": True,
                    "message": message
                }
            else:
                message = f"""❌ **Incorrect OTP**

The OTP you entered doesn't match. Please try again.

Attempts remaining: {3 - otp_data['attempts']}

💡 Make sure you're entering the latest OTP received."""
                
                return {
                    "success": True,
                    "verified": False,
                    "attempts_remaining": 3 - otp_data["attempts"],
                    "message": message
                }
    
    def verify_address(
        self,
        customer_id: str,
        provided_address: str
    ) -> Dict[str, Any]:
        """
        Verify customer's address.
        
        Args:
            customer_id: Customer ID
            provided_address: Address provided by customer
            
        Returns:
            Address verification result
        """
        result = verify_customer_details(
            customer_id=customer_id,
            address=provided_address
        )
        
        if result["verified"]:
            message = """✅ **Address Verified Successfully!**

Your address matches our records. All verification steps are complete!

🎉 **Verification Summary**:
├─ Identity: ✓ Verified
├─ Phone: ✓ Verified  
└─ Address: ✓ Verified

Great! Now let's proceed with your loan application review. This will just take a moment..."""
            
            return {
                "success": True,
                "verified": True,
                "address_verified": True,
                "message": message
            }
        else:
            if result["mismatches"]:
                mismatch = result["mismatches"][0]
                
                message = f"""⚠️ **Address Mismatch Detected**

The address you provided doesn't match our records:

**Your Input**: {mismatch['provided_value']}
**Our Records**: {mismatch['crm_value']}

This might be due to:
- Recent address change
- Typing error
- Different format

Please confirm:
1. Is this your current address? If yes, we'll update our records.
2. Or would you like to use the address we have on file?

Your security is important, so we need to clarify this."""
                
                return {
                    "success": True,
                    "verified": False,
                    "mismatch_detected": True,
                    "mismatches": result["mismatches"],
                    "message": message
                }
            else:
                message = """✅ **Address Verified!**

Thank you for confirming. All verifications are complete!"""
                
                return {
                    "success": True,
                    "verified": True,
                    "address_verified": True,
                    "message": message
                }
    
    def complete_verification(
        self,
        state: LoanApplicationState
    ) -> Dict[str, Any]:
        """
        Complete verification process and generate summary.
        
        Args:
            state: Current application state
            
        Returns:
            Verification completion summary
        """
        customer_id = state.get("customer_id")
        customer = get_customer_by_id(customer_id)
        
        verification_summary = {
            "customer_id": customer_id,
            "customer_name": customer["name"],
            "kyc_verified": state.get("kyc_verified", False),
            "phone_verified": state.get("phone_verified", False),
            "address_verified": state.get("address_verified", False),
            "verification_complete": (
                state.get("kyc_verified", False) and
                state.get("phone_verified", False) and
                state.get("address_verified", False)
            ),
            "verification_timestamp": state.get("updated_at")
        }
        
        if verification_summary["verification_complete"]:
            message = """✅ **All Verifications Complete!**

Great job! Your identity has been successfully verified.

📋 **Verification Status**:
├─ Identity Verification: ✅ Complete
├─ Phone Verification: ✅ Complete
└─ Address Verification: ✅ Complete

Now moving to credit assessment and loan approval stage..."""
        else:
            pending = []
            if not verification_summary["kyc_verified"]:
                pending.append("Identity Verification")
            if not verification_summary["phone_verified"]:
                pending.append("Phone Verification")
            if not verification_summary["address_verified"]:
                pending.append("Address Verification")
            
            message = f"""⚠️ **Verification Incomplete**

Pending Steps:
{chr(10).join(f"○ {item}" for item in pending)}

Please complete these steps to proceed with your loan application."""
        
        return {
            "success": True,
            "verification_summary": verification_summary,
            "message": message
        }


def create_verification_agent() -> VerificationAgent:
    """Factory function to create Verification Agent instance."""
    return VerificationAgent()
