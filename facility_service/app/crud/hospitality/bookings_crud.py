from datetime import date, datetime
from typing import Dict, List, Optional
from sqlalchemy import Text, distinct, func, case, cast, Date, or_
from sqlalchemy.orm import Session
from ...enum.hospitality_enum import BookingChannel, BookingStatus
from shared.core.schemas import Lookup, UserToken
from ...models.hospitality.bookings import Booking
from ...models.hospitality.booking_cancellations import BookingCancellation
from ...models.hospitality.folios import Folio
from ...models.hospitality.folios_charges import FolioCharge
from sqlalchemy.dialects.postgresql import UUID
from ...schemas.hospitality.bookings_schemas import BookingCreate, BookingUpdate, BookingRequest, BookingListResponse, BookingOut


def get_booking_overview(
    db: Session,
    org_id: UUID,
    site_id: UUID = None,
    start_date: date = None,
    end_date: date = None
):
    # Base filters
    filters = [Booking.org_id == org_id]
    if site_id:
        filters.append(Booking.site_id == site_id)
    if start_date:
        filters.append(Booking.created_at >= start_date)
    if end_date:
        filters.append(Booking.created_at <= end_date)

    # Total Bookings (with date range)
    total_bookings = db.query(func.count(Booking.id))\
        .filter(*filters).scalar() or 0

    # Active Bookings (current occupancy)
    active_filters = filters + [
        Booking.status.in_(["reserved", "in_house"]),
        Booking.check_out >= datetime.now().date()
    ]
    active_bookings = db.query(func.count(Booking.id))\
        .filter(*active_filters).scalar() or 0

    # Total Revenue (net of refunds, with taxes)
    revenue_subquery = db.query(
        Folio.booking_id,
        (func.sum(FolioCharge.amount) -
         func.coalesce(func.sum(BookingCancellation.refund_amount), 0)
         ).label('net_revenue')
    ).join(FolioCharge, FolioCharge.folio_id == Folio.id)\
     .join(Booking, Folio.booking_id == Booking.id)\
     .outerjoin(BookingCancellation,
                BookingCancellation.booking_id == Booking.id)\
     .filter(
        *filters,
        Folio.status == 'settled',
        FolioCharge.code == 'ROOM'
    ).group_by(Folio.booking_id).subquery()

    total_revenue = db.query(
        # net_revenue = Total Room Charges - Total Refunds Given = Actual Money Earned
        func.coalesce(func.sum(revenue_subquery.c.net_revenue), 0)
    ).scalar() or 0

    # Average Booking Value (net)
    settled_bookings_count = db.query(func.count(distinct(Folio.booking_id)))\
        .join(Booking, Folio.booking_id == Booking.id)\
        .filter(*filters, Folio.status == 'settled').scalar() or 1

    avg_booking_value = total_revenue / settled_bookings_count

    return {
        "totalBookings": int(total_bookings),
        "activeBookings": int(active_bookings),
        "totalRevenue": float(total_revenue),
        "avgBookingValue": float(avg_booking_value)
    }


def booking_filter_status_lookup(db: Session, org_id: str) -> List[Dict]:
    query = (
        db.query(
            Booking.status.label("id"),
            Booking.status.label("name")
        )
        .filter(Booking.org_id == org_id)
        .distinct()
        .order_by(Booking.status.asc())
    )
    rows = query.all()
    return [{"id": r.id, "name": r.name} for r in rows]

# --------------------Booking channel lookup(hardcode) by Enum -----------


def Booking_channel_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=channel.value, name=channel.name.capitalize())
        for channel in BookingChannel
    ]


def Booking_status_lookup(org_id: UUID, db: Session):
    return [
        Lookup(id=status.value, name=status.name.capitalize())
        for status in BookingStatus
    ]

# ----------------- Build Filters -----------------


def build_booking_filters(org_id: UUID, params: BookingRequest):
    filters = [Booking.org_id == org_id]

    if params.status and params.status.lower() != "all":
        filters.append(func.lower(Booking.status) == params.status.lower())

    if params.channel and params.channel.lower() != "all":
        filters.append(func.lower(Booking.channel) == params.channel.lower())

    if params.check_in_from:
        filters.append(Booking.check_in >= params.check_in_from)

    if params.check_in_to:
        filters.append(Booking.check_in <= params.check_in_to)

    if params.search:
        search_term = f"%{params.search}%"
        filters.append(
            or_(
                cast(Booking.id, Text).ilike(search_term),
                Booking.notes.ilike(search_term),
            )
        )
    return filters


def get_booking_query(db: Session, org_id: UUID, params: BookingRequest):
    filters = build_booking_filters(org_id, params)
    return db.query(Booking).filter(*filters)


# ----------------- Get All Bookings -----------------
def get_bookings(db: Session, org_id: UUID, params: BookingRequest) -> BookingListResponse:
    base_query = get_booking_query(db, org_id, params)
    total = base_query.with_entities(func.count(Booking.id)).scalar()

    bookings = (
        base_query
        .order_by(Booking.created_at.desc())
        .offset(params.skip)
        .limit(params.limit)
        .all()
    )

    results = []
    for booking in bookings:
        results.append(BookingOut.model_validate(booking.__dict__))

    return {"bookings": results, "total": total}


# ----------------- Get Single Booking -----------------
def get_booking(db: Session, booking_id: UUID, org_id: UUID) -> Optional[Booking]:
    return db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.org_id == org_id
    ).first()


# ----------------- Create Booking -----------------
def create_booking(db: Session, org_id: UUID, booking: BookingCreate) -> Booking:
    db_booking = Booking(
        org_id=org_id,
        **booking.dict(exclude={"org_id"})
    )
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    return db_booking

# ----------------- Update Booking -----------------


def update_booking(db: Session, booking_update: BookingUpdate, current_user: UserToken) -> Optional[Booking]:
    db_booking = db.query(Booking).filter(
        Booking.id == booking_update.id,
        Booking.org_id == current_user.org_id
    ).first()

    if not db_booking:
        return None

    # Update only fields provided
    update_data = booking_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_booking, key, value)

    db.commit()
    db.refresh(db_booking)
    return db_booking

# ----------------- Delete Booking -----------------


def delete_booking(db: Session, booking_id: UUID, org_id: UUID) -> bool:
    db_booking = db.query(Booking).filter(
        Booking.id == booking_id,
        Booking.org_id == org_id
    ).first()

    if not db_booking:
        return False

    db.delete(db_booking)
    db.commit()
    return True
