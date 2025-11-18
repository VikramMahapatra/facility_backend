from sqlalchemy.orm import Session
from ...models.crm.contacts import Contact

# Mapping between Invoice.customer_kind <-> Contact.kind
INVOICE_TO_CONTACT_KIND = {
    "resident": "resident",
    "guest": "guest",
    "partner": "merchant_contact",
}


def to_contact_kind(invoice_kind: str) -> str:
    try:
        return INVOICE_TO_CONTACT_KIND[invoice_kind]
    except KeyError:
        raise ValueError(f"Unknown invoice customer_kind: {invoice_kind}")


def get_customer_lookup(db: Session, kind: str, org_id: str):
    cust_query = (
        db.query(
            Contact.id,
            Contact.full_name.label("name")
        ).filter(Contact.org_id == org_id)
    )

    if kind:
        cust_query = cust_query.filter(Contact.kind == to_contact_kind(kind))

    return cust_query.all()
