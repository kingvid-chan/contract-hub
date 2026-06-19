"""Contract CRUD & state machine API routes."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload

from backend import schemas
from backend.auth import get_current_user, require_admin
from backend.database import get_db
from backend.models import User, Contract

router = APIRouter(tags=["contracts"])


# ── Helpers ──────────────────────────────────────────

# Valid status transitions
TRANSITIONS = {
    "submit": ("draft", "pending_review"),
    "approve": ("pending_review", "active"),
    "reject": ("pending_review", "draft"),
    "terminate": ("active", "terminated"),
}


def _get_contract_or_404(db: Session, contract_id: int) -> Contract:
    """Fetch a contract by ID or raise 404."""
    contract = (
        db.query(Contract)
        .options(joinedload(Contract.creator), joinedload(Contract.attachments))
        .filter(Contract.id == contract_id)
        .first()
    )
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found"
        )
    return contract


def _check_contract_visibility(contract: Contract, current_user: User):
    """Raise 404 if user cannot see this contract (non-admin, not creator)."""
    if current_user.role != "admin" and contract.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found"
        )


def _check_draft_editable(contract: Contract, current_user: User):
    """Raise 403 if contract is not in draft state or user cannot edit."""
    if current_user.role != "admin" and contract.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found"
        )
    if contract.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft contracts can be edited or deleted",
        )


# ── Endpoints ────────────────────────────────────────

@router.get("/contracts", response_model=schemas.PaginatedResponse)
def list_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str = Query("", alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List contracts. Admin sees all; user sees only their own."""
    query = db.query(Contract).options(
        joinedload(Contract.creator), joinedload(Contract.attachments)
    )

    if current_user.role != "admin":
        query = query.filter(Contract.creator_id == current_user.id)

    if status_filter:
        query = query.filter(Contract.status == status_filter)

    total = query.count()
    contracts = (
        query.order_by(Contract.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return schemas.PaginatedResponse(
        items=[schemas.ContractResponse.model_validate(c) for c in contracts],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/contracts", response_model=schemas.ContractResponse, status_code=201)
def create_contract(
    body: schemas.ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new contract (initial status: draft)."""
    contract = Contract(
        title=body.title,
        description=body.description,
        status="draft",
        creator_id=current_user.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    # Re-fetch with relationships
    return schemas.ContractResponse.model_validate(
        db.query(Contract)
        .options(joinedload(Contract.creator), joinedload(Contract.attachments))
        .filter(Contract.id == contract.id)
        .first()
    )


@router.get("/contracts/{contract_id}", response_model=schemas.ContractResponse)
def get_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single contract by ID."""
    contract = _get_contract_or_404(db, contract_id)
    _check_contract_visibility(contract, current_user)
    return schemas.ContractResponse.model_validate(contract)


@router.put("/contracts/{contract_id}", response_model=schemas.ContractResponse)
def update_contract(
    contract_id: int,
    body: schemas.ContractUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a contract (only in draft status)."""
    contract = _get_contract_or_404(db, contract_id)
    _check_draft_editable(contract, current_user)

    if body.title is not None:
        contract.title = body.title
    if body.description is not None:
        contract.description = body.description

    db.commit()
    db.refresh(contract)
    return schemas.ContractResponse.model_validate(
        db.query(Contract)
        .options(joinedload(Contract.creator), joinedload(Contract.attachments))
        .filter(Contract.id == contract.id)
        .first()
    )


@router.delete("/contracts/{contract_id}", response_model=schemas.MessageResponse)
def delete_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a contract (only in draft status)."""
    contract = _get_contract_or_404(db, contract_id)
    _check_draft_editable(contract, current_user)

    db.delete(contract)
    db.commit()
    return schemas.MessageResponse(message="Contract deleted")


# ── State transitions ────────────────────────────────

def _do_transition(
    contract_id: int,
    action: str,
    db: Session,
    current_user: User,
) -> Contract:
    """Execute a state transition on a contract."""
    contract = _get_contract_or_404(db, contract_id)

    from_status, to_status = TRANSITIONS[action]
    if contract.status != from_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot {action} a contract in '{contract.status}' status. "
            f"Expected '{from_status}'.",
        )

    # Access check: submit — owner or admin; approve/reject/terminate — admin only
    if action == "submit":
        if current_user.role != "admin" and contract.creator_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only submit your own contracts",
            )
    else:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required",
            )

    contract.status = to_status
    db.commit()
    db.refresh(contract)
    return schemas.ContractResponse.model_validate(
        db.query(Contract)
        .options(joinedload(Contract.creator), joinedload(Contract.attachments))
        .filter(Contract.id == contract.id)
        .first()
    )


@router.post("/contracts/{contract_id}/submit", response_model=schemas.ContractResponse)
def submit_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit a contract for review (draft → pending_review)."""
    return _do_transition(contract_id, "submit", db, current_user)


@router.post("/contracts/{contract_id}/approve", response_model=schemas.ContractResponse)
def approve_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve a contract (pending_review → active, admin only)."""
    return _do_transition(contract_id, "approve", db, current_user)


@router.post("/contracts/{contract_id}/reject", response_model=schemas.ContractResponse)
def reject_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reject a contract (pending_review → draft, admin only)."""
    return _do_transition(contract_id, "reject", db, current_user)


@router.post("/contracts/{contract_id}/terminate", response_model=schemas.ContractResponse)
def terminate_contract(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Terminate a contract (active → terminated, admin only)."""
    return _do_transition(contract_id, "terminate", db, current_user)
