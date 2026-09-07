from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Header, Query, HTTPException, Body
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["Prototype Authentication & Roles"])

class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    role: str  # tier_1, tier_2, tier_3
    tier: int  # 1, 2, 3
    jurisdiction: str
    area: str
    region: str

DEMO_ACCOUNTS: Dict[str, UserProfile] = {
    "tier1.demo": UserProfile(
        id="usr-t1-jamnagar",
        name="Jamnagar District Emergency Response Cell",
        email="tier1.demo@thermos.gov.in",
        role="tier_1",
        tier=1,
        jurisdiction="District / Local Emergency Authority",
        area="Jamnagar",
        region="Gujarat",
    ),
    "tier2.demo": UserProfile(
        id="usr-t2-sdma",
        name="Gujarat State Disaster Management Authority (SDMA)",
        email="tier2.demo@thermos.gov.in",
        role="tier_2",
        tier=2,
        jurisdiction="State / Regional Response Directorate",
        area="Gandhinagar",
        region="Gujarat",
    ),
    "tier3.demo": UserProfile(
        id="usr-t3-ndma",
        name="National Disaster Management Authority (NDMA Central)",
        email="tier3.demo@thermos.gov.in",
        role="tier_3",
        tier=3,
        jurisdiction="National Emergency Command & Control",
        area="New Delhi",
        region="All India",
    ),
}

# Alias mapping for frontend compatibility
ROLE_TO_ACCOUNT = {
    "tier_1": "tier1.demo",
    "tier1": "tier1.demo",
    "emergency response": "tier1.demo",
    "tier_2": "tier2.demo",
    "tier2": "tier2.demo",
    "regional authority": "tier2.demo",
    "tier_3": "tier3.demo",
    "tier3": "tier3.demo",
    "central government": "tier3.demo",
}

@router.get("/me", summary="Get current prototype user profile and tier authority")
def get_current_user(
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user_tier: Optional[int] = Header(None, alias="X-User-Tier"),
    role: Optional[str] = Query(None),
    tier: Optional[int] = Query(None),
) -> Dict[str, Any]:
    requested_role = (role or x_user_role or "").strip().lower()
    requested_tier = tier or x_user_tier

    account_key = "tier3.demo"  # Default authority
    if requested_role in ROLE_TO_ACCOUNT:
        account_key = ROLE_TO_ACCOUNT[requested_role]
    elif requested_tier == 1:
        account_key = "tier1.demo"
    elif requested_tier == 2:
        account_key = "tier2.demo"
    elif requested_tier == 3:
        account_key = "tier3.demo"

    return DEMO_ACCOUNTS[account_key].model_dump()


@router.post("/auth/login", summary="Prototype login for demo accounts")
def login(
    username: str = Body(..., embed=True),
    password: str = Body("thermos123", embed=True),
) -> Dict[str, Any]:
    clean_username = username.strip().lower()
    if clean_username in DEMO_ACCOUNTS:
        return {"status": "authenticated", "user": DEMO_ACCOUNTS[clean_username].model_dump()}

    for key, acct in DEMO_ACCOUNTS.items():
        if acct.email.lower() == clean_username or acct.role.lower() == clean_username:
            return {"status": "authenticated", "user": acct.model_dump()}

    # Fallback to Tier 1 demo if unrecognized for testing ease
    return {"status": "authenticated", "user": DEMO_ACCOUNTS["tier1.demo"].model_dump()}


@router.get("/agencies", summary="List response agencies by tier hierarchy")
def list_agencies() -> List[Dict[str, Any]]:
    return [
        {
            "tier": 1,
            "level": "Local / District Response",
            "agencies": [
                {"id": "AGC-D01", "name": "Jamnagar District Emergency Cell", "region": "Gujarat"},
                {"id": "AGC-D02", "name": "Korba Municipal Fire Brigade", "region": "Chhattisgarh"},
                {"id": "AGC-D03", "name": "Jagatsinghpur District Emergency Center", "region": "Odisha"},
                {"id": "AGC-D04", "name": "Mumbai Municipal Emergency Operations Cell", "region": "Maharashtra"},
            ]
        },
        {
            "tier": 2,
            "level": "State / Regional Response",
            "agencies": [
                {"id": "AGC-R01", "name": "Gujarat State Disaster Management Authority (GSDMA)", "region": "Gujarat"},
                {"id": "AGC-R02", "name": "Maharashtra State Disaster Management Authority", "region": "Maharashtra"},
                {"id": "AGC-R03", "name": "Odisha Disaster Rapid Action Force (ODRAF)", "region": "Odisha"},
                {"id": "AGC-R04", "name": "Chhattisgarh State Disaster Response Force", "region": "Chhattisgarh"},
            ]
        },
        {
            "tier": 3,
            "level": "National / Central Command",
            "agencies": [
                {"id": "AGC-N01", "name": "National Disaster Management Authority (NDMA Central)", "region": "All India"},
                {"id": "AGC-N02", "name": "Integrated Thermal Hazard Command Center", "region": "All India"},
            ]
        }
    ]
